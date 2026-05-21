"""
Структуры данных StepWise Alchemy.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from utils.logging_setup import get_logger

logger = get_logger("schemas")


# ============================================================
# Pipeline metadata
# ============================================================

@dataclass
class StageResult:
    """Результат выполнения одного этапа."""

    ok: bool = False

    num_records: int = 0

    duration_sec: float = 0.0

    finished_at: str = ""

    languages: Optional[List[str]] = None


@dataclass
class SourceMetadata:
    """Метаданные источника."""

    source_name: str

    raw_extraction: Optional[StageResult] = None

    cleaning: Optional[StageResult] = None

    assembly: Optional[StageResult] = None


# ============================================================
# Assembly config structures
# ============================================================

@dataclass
class MixingRule:
    """Правило смешивания для одного источника."""

    use_all: bool = False

    proportion: Optional[float] = None


@dataclass
class ApproximateTokenEstimationConfig:
    """Приблизительная оценка токенов."""

    enabled: bool = True

    default_chars_per_token: float = 4.0

    chars_per_token_by_lang: Dict[str, float] = field(
        default_factory=lambda: {
            "ru": 4.0,
            "en": 6.0,
        }
    )

    safety_margin: float = 1.15

    max_document_chars: int = 250000


@dataclass
class TokenizerRefinementConfig:
    """Опциональная корректировка через tokenizer."""

    enabled: bool = False

    tokenizer: str = "microsoft/Phi-3.5-mini-instruct"

    max_refinement_tokens: int = 2048


@dataclass
class ChunkingConfig:
    """Настройки chunking."""

    target_tokens: int = 512

    stride_tokens: int = 448

    min_tokens: int = 128

    max_chunks_per_document: int = 32

    approximate_token_estimation: ApproximateTokenEstimationConfig = field(
        default_factory=ApproximateTokenEstimationConfig
    )

    tokenizer_refinement: TokenizerRefinementConfig = field(
        default_factory=TokenizerRefinementConfig
    )


@dataclass
class ShuffleConfig:
    """Настройки shuffle."""

    enabled: bool = True

    global_shuffle: bool = True

    shuffle_shards: bool = True

    shuffle_within_shard: bool = True

    export_batch_size: int = 100_000
    buffer_size: int = 10000

    index_file: str = "shuffle.idx"


@dataclass
class CacheBuildConfig:
    """Настройки промежуточного cache."""

    enabled: bool = True

    cache_dir: str = "output/text/cache"

    target_shard_size_mb: int = 1024

    write_buffer_size: int = 10000

    cleanup_after_finalize: bool = True


@dataclass
class StorageConfig:
    """Настройки хранения датасета."""

    format: str = "text"

    store_text: bool = True

    store_token_ids: bool = False

    tokenizer: str = "microsoft/Phi-3.5-mini-instruct"

    compression: str = "zstd"


@dataclass
class OutputConfig:
    """Настройки финального output."""

    target_shard_size_mb: int = 1024

    row_group_size: int = 10000

    compression: str = "zstd"


@dataclass
class MixingConfig:
    """Настройки mixing."""

    base_tier: Optional[int] = None

    sources: Dict[str, MixingRule] = field(
        default_factory=dict
    )

# ============================================================
# Main assembly config
# ============================================================

@dataclass
class AssemblyConfig:
    """Конфигурация Assembly."""

    output_dir: str = "output"

    seed: int = 42

    cleanup_intermediate: bool = True

    max_total_chunks: Optional[int] = None

    shuffle: ShuffleConfig = field(
        default_factory=ShuffleConfig
    )

    chunking: ChunkingConfig = field(
        default_factory=ChunkingConfig
    )

    cache_build: CacheBuildConfig = field(
        default_factory=CacheBuildConfig
    )

    storage: StorageConfig = field(
        default_factory=StorageConfig
    )

    output: OutputConfig = field(
        default_factory=OutputConfig
    )

    mixing: Optional[MixingConfig] = field(
        default_factory=MixingConfig
    )

    # ========================================================
    # Parsing
    # ========================================================

    @classmethod
    def from_dict(
        cls,
        data: dict,
    ) -> "AssemblyConfig":

        # ----------------------------------------------------
        # Sections
        # ----------------------------------------------------

        shuffle_data = data.get("shuffle", {})

        chunking_data = data.get("chunking", {})

        cache_data = data.get("cache_build", {})

        storage_data = data.get("storage", {})

        output_data = data.get("output", {})

        mixing_data = data.get("mixing", {})

        # ----------------------------------------------------
        # Approximate estimation
        # ----------------------------------------------------

        estimation_data = chunking_data.get(
            "approximate_token_estimation",
            {},
        )

        estimation_cfg = (
            ApproximateTokenEstimationConfig(
                enabled=estimation_data.get(
                    "enabled",
                    True,
                ),

                default_chars_per_token=(
                    estimation_data.get(
                        "default_chars_per_token",
                        4.0,
                    )
                ),

                chars_per_token_by_lang=(
                    estimation_data.get(
                        "chars_per_token_by_lang",
                        {
                            "ru": 4.0,
                            "en": 6.0,
                        },
                    )
                ),

                safety_margin=(
                    estimation_data.get(
                        "safety_margin",
                        1.15,
                    )
                ),

                max_document_chars=(
                    estimation_data.get(
                        "max_document_chars",
                        250000,
                    )
                ),
            )
        )

        # ----------------------------------------------------
        # Tokenizer refinement
        # ----------------------------------------------------

        refinement_data = chunking_data.get(
            "tokenizer_refinement",
            {},
        )

        refinement_cfg = (
            TokenizerRefinementConfig(
                enabled=refinement_data.get(
                    "enabled",
                    False,
                ),

                tokenizer=refinement_data.get(
                    "tokenizer",
                    "microsoft/Phi-3.5-mini-instruct",
                ),

                max_refinement_tokens=(
                    refinement_data.get(
                        "max_refinement_tokens",
                        2048,
                    )
                ),
            )
        )

        # ----------------------------------------------------
        # Chunking
        # ----------------------------------------------------

        chunking_cfg = ChunkingConfig(
            target_tokens=chunking_data.get(
                "target_tokens",
                512,
            ),

            stride_tokens=chunking_data.get(
                "stride_tokens",
                448,
            ),

            min_tokens=chunking_data.get(
                "min_tokens",
                128,
            ),

            max_chunks_per_document=(
                chunking_data.get(
                    "max_chunks_per_document",
                    32,
                )
            ),

            approximate_token_estimation=(
                estimation_cfg
            ),

            tokenizer_refinement=(
                refinement_cfg
            ),
        )

        # ----------------------------------------------------
        # Mixing rules
        # ----------------------------------------------------

        mixing_sources = mixing_data.get(
            "sources",
            {},
        )

        parsed_rules = {}

        for source_name, rule_data in mixing_sources.items():

            if not isinstance(rule_data, dict):

                logger.warning(
                    "mixing.sources.%s должен быть dict",
                    source_name,
                )

                continue

            parsed_rules[source_name] = (
                MixingRule(
                    use_all=rule_data.get(
                        "use_all",
                        False,
                    ),

                    proportion=rule_data.get(
                        "proportion",
                    ),
                )
            )

        # ----------------------------------------------------
        # Final config
        # ----------------------------------------------------

        return cls(

            output_dir=data.get(
                "output_dir",
                "output",
            ),

            seed=data.get(
                "seed",
                42,
            ),

            cleanup_intermediate=data.get(
                "cleanup_intermediate",
                True,
            ),

            max_total_chunks=data.get(
                "max_total_chunks",
            ),

            shuffle=ShuffleConfig(
                enabled=shuffle_data.get(
                    "enabled",
                    True,
                ),

                global_shuffle=shuffle_data.get(
                    "global_shuffle",
                    True,
                ),

                shuffle_shards=shuffle_data.get(
                    "shuffle_shards",
                    True,
                ),

                shuffle_within_shard=(
                    shuffle_data.get(
                        "shuffle_within_shard",
                        True,
                    )
                ),

                index_file=shuffle_data.get(
                    "index_file",
                    "shuffle.idx",
                ),
            ),

            chunking=chunking_cfg,

            cache_build=CacheBuildConfig(
                enabled=cache_data.get(
                    "enabled",
                    True,
                ),

                cache_dir=cache_data.get(
                    "cache_dir",
                    "output/text/cache",
                ),

                target_shard_size_mb=(
                    cache_data.get(
                        "target_shard_size_mb",
                        1024,
                    )
                ),

                write_buffer_size=(
                    cache_data.get(
                        "write_buffer_size",
                        10000,
                    )
                ),

                cleanup_after_finalize=(
                    cache_data.get(
                        "cleanup_after_finalize",
                        True,
                    )
                ),
            ),

            storage=StorageConfig(
                format=storage_data.get(
                    "format",
                    "text",
                ),

                store_text=storage_data.get(
                    "store_text",
                    True,
                ),

                store_token_ids=(
                    storage_data.get(
                        "store_token_ids",
                        False,
                    )
                ),

                tokenizer=storage_data.get(
                    "tokenizer",
                    "microsoft/Phi-3.5-mini-instruct",
                ),

                compression=storage_data.get(
                    "compression",
                    "zstd",
                ),
            ),

            output=OutputConfig(
                target_shard_size_mb=(
                    output_data.get(
                        "target_shard_size_mb",
                        1024,
                    )
                ),

                row_group_size=output_data.get(
                    "row_group_size",
                    10000,
                ),

                compression=output_data.get(
                    "compression",
                    "zstd",
                ),
            ),

            mixing=MixingConfig(
                base_tier=mixing_data.get(
                    "base_tier",
                ),

                sources=parsed_rules,
            ),
        )