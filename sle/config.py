"""Resolve the active LLM config.

Resolution order:
1. ``--llm-config <path>`` (CLI) or ``FS_LLM_CONFIG`` env var.
2. ``conf/llm/local.yaml`` (git-ignored; our keyless GPT-5.5 lives here).
3. ``conf/llm/openai_compatible.example.yaml`` (public placeholder).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml

from .llm import LLMClient, LLMConfig

CONF_DIR = Path(__file__).parent / "conf" / "llm"


def resolve_llm_config_path(explicit: Optional[str] = None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("FS_LLM_CONFIG")
    if env:
        return Path(env).expanduser().resolve()
    local = CONF_DIR / "local.yaml"
    if local.is_file():
        return local
    return CONF_DIR / "openai_compatible.example.yaml"


def load_llm_client(explicit: Optional[str] = None) -> LLMClient:
    path = resolve_llm_config_path(explicit)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return LLMClient(LLMConfig.from_dict(data))
