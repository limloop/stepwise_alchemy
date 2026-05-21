# Streaming-first dataset assembler for large-scale LLM corpora.

import math
import random
import time
import tempfile
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Iterable, Iterator, List
from collections import defaultdict

from tqdm import tqdm

from core.registry import SourceRegistry
from core.schemas import AssemblyConfig
from data_io.parquet import count_rows, read_parquet, read_parquet_full, write_parquet_streaming
from utils.logging_setup import get_logger

logger = get_logger("pipeline.assembly")


def estimate_chars_per_token(lang: str, cfg) -> float:
    """Estimate characters per token for a given language, with optional overrides."""
    overrides = cfg.chunking.approximate_token_estimation.chars_per_token_by_lang
    if lang in overrides:
        return overrides[lang]
    return cfg.chunking.approximate_token_estimation.default_chars_per_token


def estimate_chunk_chars(target_tokens: int, chars_per_token: float, safety_margin: float) -> int:
    """Calculate target character count for a chunk given token target and safety margin."""
    return int(target_tokens * chars_per_token * safety_margin)


def chunk_text_by_chars(text: str, target_chars: int, stride_chars: int, min_chars: int, max_chunks: int):
    """Yield character-based chunks from text with sliding window."""
    emitted = 0
    for i in range(0, len(text), stride_chars):
        if emitted >= max_chunks:
            break
        chunk = text[i:i + target_chars]
        if len(chunk) < min_chars:
            continue
        yield chunk
        emitted += 1


def process_chunk_batch(batch):
    """Process a batch of items for parallel chunking."""
    output = []
    for item in batch:
        global_base_id, source_name, lang, text, target_chars, stride_chars, min_chars, max_chunks = item
        local_id = 0
        for chunk in chunk_text_by_chars(text=text, target_chars=target_chars, stride_chars=stride_chars,
                                         min_chars=min_chars, max_chunks=max_chunks):
            output.append({
                "id": global_base_id + local_id,
                "source": source_name,
                "lang": lang,
                "text": chunk,
                "char_count": len(chunk),
            })
            local_id += 1
    return output


def buffered_shuffle(iterator: Iterable, buffer_size: int, seed: int):
    """Shuffle items from an iterator using an in-memory buffer."""
    rng = random.Random(seed)
    buffer = []
    for item in iterator:
        buffer.append(item)
        if len(buffer) >= buffer_size:
            rng.shuffle(buffer)
            while buffer:
                yield buffer.pop()
    rng.shuffle(buffer)
    while buffer:
        yield buffer.pop()


def resolve_mixing_plan(cfg, registry: SourceRegistry, cache_root: str) -> Dict[str, int]:
    """Determine how many records to use from each source based on mixing config."""
    available = {}
    for name, source in registry.list_all().items():
        path = Path(cache_root) / name / "cleaned.parquet"
        if path.exists():
            available[name] = source

    if not available:
        logger.error("No cleaned datasets found.")
        return {}

    tiers = {}
    for name, source in available.items():
        tiers.setdefault(source.quality_tier, []).append(name)

    base_tier = cfg.mixing.base_tier
    if base_tier not in tiers:
        base_tier = min(tiers.keys())

    base_total = 0
    for name in tiers[base_tier]:
        path = Path(cache_root) / name / "cleaned.parquet"
        base_total += count_rows(str(path))

    logger.info("Base tier=%d size=%d", base_tier, base_total)

    rules = cfg.mixing.sources or {}
    plan = {}

    for name in available:
        rule = rules.get(name)
        if not rule:
            plan[name] = None
            continue
        if rule.get("use_all"):
            plan[name] = None
        elif "proportion" in rule:
            plan[name] = int(base_total * rule["proportion"])
        else:
            plan[name] = None

    return plan


def iter_source_records(source_name: str, cache_root: str):
    """Iterate over cleaned records for a single source."""
    path = Path(cache_root) / source_name / "cleaned.parquet"
    yield from read_parquet(str(path))


def iter_materialized_chunks(cfg, registry, cache_root, plan):
    """Materialize chunked records from all sources according to the mixing plan."""
    chunk_cfg = cfg.chunking
    estimation = chunk_cfg.approximate_token_estimation
    global_id = 0

    for source_name, limit in plan.items():
        source = registry.get(source_name)
        if source is None or source.content_type != "text":
            continue

        logger.info("[%s] materializing...", source_name)
        path = Path(cache_root) / source_name / "cleaned.parquet"
        total_rows = count_rows(str(path))
        if limit:
            total_rows = min(total_rows, limit)

        records = iter_source_records(source_name, cache_root)
        if cfg.shuffle.enabled:
            records = buffered_shuffle(records, buffer_size=cfg.shuffle.buffer_size, seed=cfg.seed)

        processed = 0
        with tqdm(total=total_rows, desc=source_name, unit="docs") as pbar:
            for record in records:
                if limit and processed >= limit:
                    break

                text = record.get("text", "")
                if not text:
                    continue

                lang = record.get("lang", "unknown")
                chars_per_token = estimate_chars_per_token(lang, cfg)
                target_chars = estimate_chunk_chars(chunk_cfg.target_tokens, chars_per_token, estimation.safety_margin)
                stride_chars = max(int(chunk_cfg.stride_tokens * chars_per_token), 1)
                min_chars = max(int(chunk_cfg.min_tokens * chars_per_token), 1)

                if len(text) > estimation.max_document_chars:
                    text = text[:estimation.max_document_chars]

                for chunk in chunk_text_by_chars(text=text, target_chars=target_chars, stride_chars=stride_chars,
                                                 min_chars=min_chars, max_chunks=chunk_cfg.max_chunks_per_document):
                    yield {
                        "id": global_id,
                        "source": source_name,
                        "lang": lang,
                        "text": chunk,
                        "char_count": len(chunk),
                    }
                    global_id += 1

                processed += 1
                pbar.update(1)


def estimate_compression_ratio(sample_rows):
    """Estimate parquet compression ratio based on a sample of rows."""
    if not sample_rows:
        return 1.0

    raw_size = sum(len(row["text"].encode("utf-8")) for row in sample_rows)
    if raw_size == 0:
        return 1.0

    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=True) as tmp:
        write_parquet_streaming(iter(sample_rows), tmp.name)
        parquet_size = Path(tmp.name).stat().st_size

    if parquet_size == 0:
        return 1.0

    return raw_size / parquet_size


def write_cache_shards(cfg, chunk_iterator):
    """Write chunked records to parquet shards, using adaptive compression estimation."""
    cache_cfg = cfg.cache_build
    cache_dir = Path(cache_cfg.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    target_size_mb = cache_cfg.target_shard_size_mb
    target_size_bytes = target_size_mb * 1024 * 1024

    shard_paths = []
    shard_index = 0
    current_rows = []
    current_size_bytes = 0

    # Adaptive compression estimation
    SAMPLE_TARGET_MB = 16
    sample_rows = []
    sample_raw_bytes = 0
    compression_ratio = None
    effective_target_bytes = target_size_bytes

    # Language statistics
    lang_stats = defaultdict(lambda: {"records": 0, "chars": 0})

    logger.info("Writing cache shards...")

    for row in chunk_iterator:
        size_bytes = len(row["text"].encode("utf-8"))

        # Collect compression sample
        if compression_ratio is None:
            sample_rows.append(row)
            sample_raw_bytes += size_bytes
            if sample_raw_bytes >= SAMPLE_TARGET_MB * 1024 * 1024:
                compression_ratio = estimate_compression_ratio(sample_rows)
                effective_target_bytes = int(target_size_bytes * compression_ratio)
                logger.info("Estimated parquet compression ratio: %.2f (effective raw target: %.2f MB)",
                           compression_ratio, effective_target_bytes / 1024 / 1024)
                sample_rows = []

        current_rows.append(row)
        current_size_bytes += size_bytes

        # Update language stats
        lang = row.get("lang", "unknown")
        lang_stats[lang]["records"] += 1
        lang_stats[lang]["chars"] += row.get("char_count", 0)

        # Flush shard if target size reached
        if current_size_bytes >= effective_target_bytes:
            shard_path = cache_dir / f"shard_{shard_index:06d}.parquet"
            write_parquet_streaming(iter(current_rows), str(shard_path))
            shard_paths.append(shard_path)
            logger.info("Shard saved: %s rows=%d raw_size=%.2f MB",
                       shard_path.name, len(current_rows), current_size_bytes / 1024 / 1024)
            shard_index += 1
            current_rows = []
            current_size_bytes = 0

    # Final shard
    if current_rows:
        shard_path = cache_dir / f"shard_{shard_index:06d}.parquet"
        write_parquet_streaming(iter(current_rows), str(shard_path))
        shard_paths.append(shard_path)
        logger.info("Final shard saved: %s rows=%d", shard_path.name, len(current_rows))

    # Save language statistics
    stats_dir = Path(cfg.output_dir) / "text"
    stats_dir.mkdir(parents=True, exist_ok=True)
    stats_path = stats_dir / "language_stats.json"

    sorted_stats = dict(sorted(lang_stats.items(), key=lambda x: x[1]["chars"], reverse=True))
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(sorted_stats, f, ensure_ascii=False, indent=2)

    logger.info("Language stats saved: %s", stats_path)
    return shard_paths


def build_shuffle_index(shard_paths, seed):
    """Build a global shuffle index mapping output order to (shard_id, row_id) pairs."""
    logger.info("Building shuffle index...")
    index = []
    for shard_id, path in enumerate(shard_paths):
        rows = count_rows(str(path))
        for row_id in range(rows):
            index.append((shard_id, row_id))

    rng = random.Random(seed)
    rng.shuffle(index)
    logger.info("Shuffle index size=%d", len(index))
    return index


def export_final_dataset(cfg, shard_paths, shuffle_index):
    """Export final dataset using batched sparse shard reads."""
    output_dir = Path(cfg.output_dir) / "text"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "dataset.parquet"

    logger.info("Exporting final dataset...")

    # Tune this depending on RAM / IO tradeoff
    batch_size = getattr(cfg.shuffle, "export_batch_size", 100_000)

    def load_required_rows(shard_path, wanted_rows):
        """
        Sequentially scan a shard and return only requested rows.
        """
        loaded = {}

        if not wanted_rows:
            return loaded

        wanted = set(wanted_rows)

        for idx, row in enumerate(read_parquet_full(str(shard_path))):
            if idx in wanted:
                loaded[idx] = row

                # Early stop once all rows gathered
                if len(loaded) >= len(wanted):
                    break

        return loaded

    def final_rows():
        total = len(shuffle_index)

        for start in tqdm(range(0, total, batch_size), desc="final_export_batches"):
            batch = shuffle_index[start:start + batch_size]

            # Preserve original shuffled order
            ordered_positions = []

            # Group required rows by shard
            shard_requests = defaultdict(list)

            for position, (shard_id, row_id) in enumerate(batch):
                shard_requests[shard_id].append(row_id)
                ordered_positions.append((position, shard_id, row_id))

            # Load only required rows from each shard
            loaded_rows = {}

            for shard_id, row_ids in tqdm(shard_requests.items()):
                shard_loaded = load_required_rows(
                    shard_paths[shard_id],
                    row_ids
                )

                for row_id, row in shard_loaded.items():
                    loaded_rows[(shard_id, row_id)] = row

            # Emit rows in exact shuffled order
            for _, shard_id, row_id in ordered_positions:
                row = loaded_rows.get((shard_id, row_id))
                if row is not None:
                    yield row

            # Explicit cleanup
            loaded_rows.clear()
            shard_requests.clear()

    write_parquet_streaming(final_rows(), str(output_file))

    logger.info("Final dataset saved: %s", output_file)


def cleanup_cache(shard_paths):
    """Remove intermediate cache shard files."""
    logger.info("Cleaning cache...")
    for path in shard_paths:
        try:
            path.unlink()
        except Exception as e:
            logger.warning("Failed to remove %s: %s", path, e)


def run_assembly_stage(sources, registry, config, modes):
    """Main entrypoint for the assembly stage."""
    assembly_cfg = config.get("assembly", {})
    if not assembly_cfg:
        logger.error("Assembly config missing.")
        return

    cfg = AssemblyConfig.from_dict(assembly_cfg)
    cache_root = config.get("cache", {}).get("root", "cache")

    logger.info("=" * 60)
    logger.info("Assembly started")
    start_time = time.time()

    cache_dir = Path(cfg.cache_build.cache_dir)
    stats_path = Path(cfg.output_dir) / "text" / "language_stats.json"

    # Reuse existing cache shards if already built
    if stats_path.exists():
        logger.info("Existing language stats found, skipping chunk materialization.")

        shard_paths = sorted(cache_dir.glob("shard_*.parquet"))

        if not shard_paths:
            logger.error("language_stats.json exists but no cache shards found.")
            return

    else:
        plan = resolve_mixing_plan(cfg, registry, cache_root)
        chunk_iterator = iter_materialized_chunks(cfg, registry, cache_root, plan)
        shard_paths = write_cache_shards(cfg, chunk_iterator)

    shuffle_index = build_shuffle_index(shard_paths, seed=cfg.seed)
    export_final_dataset(cfg, shard_paths, shuffle_index)

    if cfg.cache_build.cleanup_after_finalize:
        cleanup_cache(shard_paths)

    elapsed = time.time() - start_time
    logger.info("Assembly completed in %.1f sec", elapsed)