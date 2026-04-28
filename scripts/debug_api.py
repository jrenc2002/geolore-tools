#!/usr/bin/env python3
"""调试 MiMo API 请求，复用项目唯一调用链路。"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.common.config import load_llm_config, PROVIDER_MIMO
from src.common.llm_client import call_llm


def debug_mimo() -> None:
    config = load_llm_config(provider=PROVIDER_MIMO)
    endpoint = config.base_url.rstrip("/") + "/chat/completions"
    print("=" * 60)
    print("测试 MiMo API")
    print("=" * 60)
    print(f"URL: {endpoint}")
    print(f"Model: {config.model}")

    try:
        response = call_llm(
            [{"role": "user", "content": "只回复 pong"}],
            config,
            max_tokens=32,
        )
        print("✅ 调用成功")
        print(f"响应: {response}")
    except Exception as exc:
        print(f"❌ 调用失败: {exc}")


if __name__ == "__main__":
    debug_mimo()
