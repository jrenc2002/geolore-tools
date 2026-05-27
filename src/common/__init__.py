"""
公共工具模块 - 故实巡礼 · 公共基础设施

提供统一的 LLM 配置、调用、JSON 解析能力，
消除各脚本/模块间的重复实现。

子模块:
  config      — LLMConfig / GeocodingConfig / 环境变量加载
  llm_client  — 统一 LLM HTTP 调用（WAF 规避、重试）
  json_utils  — 从脏文本中提取 JSON
"""

# 兼容两种导入路径：
#   - 从项目根目录: from src.common.config import ...
#   - 从 src/ 目录: from common.config import ...
try:
    from src.common.config import (
        LLMConfig,
        GeocodingConfig,
        PROVIDER_MIMO,
        load_llm_config,
        use_proxy,
    )
    from src.common.llm_client import call_llm, call_llm_for_extraction, call_tts
    from src.common.json_utils import extract_json_from_text, extract_json_array, strip_code_fences
except ImportError:
    from common.config import (
        LLMConfig,
        GeocodingConfig,
        PROVIDER_MIMO,
        load_llm_config,
        use_proxy,
    )
    from common.llm_client import call_llm, call_llm_for_extraction, call_tts
    from common.json_utils import extract_json_from_text, extract_json_array, strip_code_fences

__all__ = [
    "LLMConfig",
    "GeocodingConfig",
    "PROVIDER_MIMO",
    "load_llm_config",
    "use_proxy",
    "call_llm",
    "call_llm_for_extraction",
    "call_tts",
    "extract_json_from_text",
    "extract_json_array",
    "strip_code_fences",
]
