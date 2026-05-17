"""
Структуры данных StepWise Alchemy.
"""

from dataclasses import dataclass, field
from typing import Optional, List

from utils.logging_setup import get_logger
logger = get_logger("schemas")

@dataclass
class StageResult:
    """Результат выполнения одного этапа для одного источника."""
    ok: bool = False
    num_records: int = 0
    duration_sec: float = 0.0
    finished_at: str = ""
    languages: Optional[List[str]] = None


@dataclass
class SourceMetadata:
    """Метаданные источника по всем этапам."""
    source_name: str
    raw_extraction: Optional[StageResult] = None
    cleaning: Optional[StageResult] = None


# --- Для этапа 3 (Assembly) ---

@dataclass
class MixingRule:
    """Правило смешивания для одного источника."""
    source_name: str
    use_all: bool = False
    proportion: Optional[float] = None  # 0.0 – 1.0 от объёма base_tier


@dataclass
class AssemblyConfig:
    """Конфигурация этапа 3."""
    # Общие
    output_dir: str = "output"
    tokenizer_name: str = "microsoft/Phi-3.5-mini-instruct"
    shuffle: bool = True
    seed: int = 42
    max_total_tokens: Optional[int] = None

    # Chat
    chat_min_messages: int = 2
    chat_max_tokens: int = 4096
    chat_apply_chat_template: bool = False

    # Text
    text_chunk_sizes: List[int] = field(default_factory=lambda: [64, 128, 256, 512])
    text_stride: int = 448
    text_min_tokens: int = 64
    text_chunking: str = "fixed"

    # Mixing
    base_tier: int = 1
    mixing_rules: List[MixingRule] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> 'AssemblyConfig':
        """Создаёт AssemblyConfig из словаря (из config.yaml)."""
        
        # Известные ключи
        known_keys = {"output_dir", "tokenizer", "shuffle", "seed",
                      "max_total_tokens", "chat", "text", "mixing"}
        unknown = set(data.keys()) - known_keys
        if unknown:
            logger.warning("Неизвестные ключи в assembly: %s", unknown)
        
        chat = data.get("chat", {})
        text = data.get("text", {})
        mixing = data.get("mixing", {})
        
        # Валидация chat
        chat_known = {"min_messages", "max_tokens", "apply_chat_template"}
        chat_unknown = set(chat.keys()) - chat_known
        if chat_unknown:
            logger.warning("Неизвестные ключи в assembly.chat: %s", chat_unknown)
        
        # Валидация text
        text_known = {"chunk_sizes", "stride", "min_tokens", "chunking"}
        text_unknown = set(text.keys()) - text_known
        if text_unknown:
            logger.warning("Неизвестные ключи в assembly.text: %s", text_unknown)
        
        # Валидация mixing
        mixing_known = {"base_tier", "sources"}
        mixing_unknown = set(mixing.keys()) - mixing_known
        if mixing_unknown:
            logger.warning("Неизвестные ключи в assembly.mixing: %s", mixing_unknown)
        
        # Парсим правила смешивания
        rules = []
        mixing_sources = mixing.get("sources", {})
        for source_name, rule_data in mixing_sources.items():
            if isinstance(rule_data, dict):
                rule_known = {"use_all", "proportion"}
                rule_unknown = set(rule_data.keys()) - rule_known
                if rule_unknown:
                    logger.warning(
                        "Неизвестные ключи в mixing.sources.%s: %s",
                        source_name, rule_unknown,
                    )
                rules.append(MixingRule(
                    source_name=source_name,
                    use_all=rule_data.get("use_all", False),
                    proportion=rule_data.get("proportion"),
                ))
            else:
                logger.warning(
                    "mixing.sources.%s: ожидался словарь, получен %s. Пропущено.",
                    source_name, type(rule_data).__name__,
                )

        return cls(
            output_dir=data.get("output_dir", "output"),
            tokenizer_name=data.get("tokenizer", "microsoft/Phi-3.5-mini-instruct"),
            shuffle=data.get("shuffle", True),
            seed=data.get("seed", 42),
            max_total_tokens=data.get("max_total_tokens"),
            chat_min_messages=chat.get("min_messages", 2),
            chat_max_tokens=chat.get("max_tokens", 4096),
            chat_apply_chat_template=chat.get("apply_chat_template", False),
            text_chunk_sizes=text.get("chunk_sizes", [64, 128, 256, 512]),
            text_stride=text.get("stride", 448),
            text_min_tokens=text.get("min_tokens", 64),
            text_chunking=text.get("chunking", "fixed"),
            base_tier=mixing.get("base_tier", 1),
            mixing_rules=rules,
        )