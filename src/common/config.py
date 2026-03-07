#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
故实巡礼 · 统一配置管理

集中管理所有环境变量、API 端点、模型名称等配置项。
所有脚本和模块统一从此处读取配置，杜绝散落各处的硬编码。

环境变量（优先级：命令行参数 > 环境变量 > 此处默认值）：
  GEOLORE_API_KEY    — LLM API 密钥（必填）
  GEOLORE_BASE_URL   — LLM API 端点
  GEOLORE_USE_PROXY  — "1" 启用系统代理，默认直连
  AMAP_KEY           — 高德地图 API Key（地理编码用）
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlparse


# ─────────────────────────── 默认值 ───────────────────────────

PROVIDER_GEMINI = "gemini"
PROVIDER_CLAUDE = "claude"

DEFAULT_BASE_URL = "https://api-k.devdove.site/v1"
DEFAULT_CLAUDE_BASE_URL = "https://tokenmax.vip"
DEFAULT_REGISTRY_PATH = "output/data/registry.json"
DEFAULT_TRACKING_DIR = "output/tracking"
DEFAULT_CACHE_DIR = "output/.text_cache"
DEFAULT_OUTPUT_DIR = "output/books"

# LLM 模型分工
MODEL_PRO = "gemini-3.1-pro-preview-search"       # 选题 + 搜索（需联网）
MODEL_FLASH = "gemini-3-flash-preview-search"      # 地点提取（需联网）
MODEL_FLASH_STRUCT = "gemini-3-flash-preview"      # 结构化 + 审查（纯 JSON，不联网）
MODEL_CLAUDE = "claude-sonnet-4-6"


# ─────────────────────────── 配置数据类 ───────────────────────


@dataclass
class LLMConfig:
    """LLM API 统一配置

    所有需要调用 LLM 的地方都使用此数据类。
    """
    api_key: str = ""
    provider: str = PROVIDER_GEMINI
    base_url: str = DEFAULT_BASE_URL
    model: str = MODEL_FLASH_STRUCT
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: int = 300
    retry_count: int = 3
    retry_delay: float = 5.0
    expect_json: bool = False


@dataclass
class GeocodingConfig:
    """地理编码配置"""
    amap_key: str = ""
    nominatim_sleep: float = 1.0
    cache_path: str = "geocode_cache.json"
    enable_validation: bool = True


# ─────────────────────────── 工厂函数 ───────────────────────


def _load_dotenv() -> None:
    """自动加载项目根目录的 .env 文件到环境变量（不覆盖已有值）"""
    env_file = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    env_file = os.path.normpath(env_file)
    if not os.path.isfile(env_file):
        return
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            if key and key not in os.environ:
                os.environ[key] = val


_load_dotenv()


def _load_ai_config() -> Dict[str, Any]:
    """加载项目根目录的 .ai_config.json。"""
    config_file = os.path.join(os.path.dirname(__file__), "..", "..", ".ai_config.json")
    config_file = os.path.normpath(config_file)
    if not os.path.isfile(config_file):
        return {}
    try:
        with open(config_file, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _normalize_base_url(base_url: str, provider: str) -> str:
    """规范化供应商 base URL。"""
    normalized = (base_url or "").rstrip("/")
    if not normalized:
        return normalized
    if provider == PROVIDER_CLAUDE:
        if normalized.endswith("/messages"):
            normalized = normalized[: -len("/messages")]
        if normalized.endswith("/chat/completions"):
            normalized = normalized[: -len("/chat/completions")]
        parsed = urlparse(normalized)
        if parsed.scheme and parsed.netloc and parsed.path in ("", "/"):
            return normalized + "/v1"
        return normalized
    if normalized.endswith("/chat/completions"):
        return normalized[: -len("/chat/completions")]
    return normalized


def _provider_defaults(provider: str, ai_config: Dict[str, Any]) -> Dict[str, Any]:
    """从 .ai_config.json 读取供应商默认配置。"""
    provider_config = ai_config.get(provider, {})
    if not isinstance(provider_config, dict):
        provider_config = {}

    if provider == PROVIDER_CLAUDE:
        return {
            "api_key": provider_config.get("api_key", ""),
            "base_url": _normalize_base_url(
                provider_config.get("base_url", DEFAULT_CLAUDE_BASE_URL),
                provider,
            ),
            "model": provider_config.get("model", MODEL_CLAUDE),
        }

    model_from_config = provider_config.get("model")
    models = provider_config.get("models", {})
    if not model_from_config and isinstance(models, dict):
        model_from_config = models.get("pro") or models.get("flash")

    return {
        "api_key": provider_config.get("api_key", ""),
        "base_url": _normalize_base_url(
            provider_config.get("base_url", DEFAULT_BASE_URL),
            provider,
        ),
        "model": model_from_config or MODEL_FLASH_STRUCT,
    }


def load_llm_config(
    provider: str = PROVIDER_GEMINI,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    **overrides,
) -> LLMConfig:
    """从环境变量 + 参数构造 LLMConfig

    优先级：显式参数 > 环境变量 > 默认值
    """
    provider = provider or PROVIDER_GEMINI
    ai_config = _load_ai_config()
    defaults = _provider_defaults(provider, ai_config)

    if provider == PROVIDER_CLAUDE:
        env_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        env_base_url = os.environ.get("ANTHROPIC_BASE_URL", "")
        env_model = os.environ.get("CLAUDE_MODEL", "")
    else:
        env_api_key = os.environ.get("GEOLORE_API_KEY", "")
        env_base_url = os.environ.get("GEOLORE_BASE_URL", "")
        env_model = os.environ.get("GEOLORE_MODEL", "")

    return LLMConfig(
        provider=provider,
        api_key=api_key or env_api_key or defaults["api_key"],
        base_url=_normalize_base_url(
            base_url or env_base_url or defaults["base_url"],
            provider,
        ),
        model=model or env_model or defaults["model"],
        **overrides,
    )


def use_proxy() -> bool:
    """是否使用系统代理"""
    return os.environ.get("GEOLORE_USE_PROXY", "0") == "1"
