import os
from dataclasses import dataclass, field
from typing import Optional

import yaml


@dataclass
class EmbeddingConfig:
    provider: str = "ollama"
    model: str = "nomic-embed-text"
    base_url: Optional[str] = "http://localhost:11434"
    api_key: Optional[str] = None


@dataclass
class ContextConfig:
    semantic: str = "auto"
    topup_recent: bool = True


@dataclass
class MemoryConfig:
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    context: ContextConfig = field(default_factory=ContextConfig)


def get_memory_home() -> str:
    return os.environ.get("MEMORY_HOME", os.path.join(os.path.expanduser("~"), ".memory"))


def load_config(path: str) -> MemoryConfig:
    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        return MemoryConfig()

    config = MemoryConfig()
    if "embedding" in data:
        e = data["embedding"]
        config.embedding = EmbeddingConfig(
            provider=e.get("provider", "ollama"),
            model=e.get("model", "nomic-embed-text"),
            base_url=e.get("base_url", "http://localhost:11434"),
            api_key=e.get("api_key"),
        )
    if "context" in data:
        cx = data["context"]
        config.context = ContextConfig(
            semantic=cx.get("semantic", "auto"),
            topup_recent=cx.get("topup_recent", True),
        )
    return config
