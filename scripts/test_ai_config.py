#!/usr/bin/env python3
"""测试 MiMo AI 配置是否正确"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.common.config import load_llm_config, PROVIDER_MIMO
from src.common.llm_client import call_llm


def test_mimo():
    """测试 MiMo 供应商"""
    print(f"\n{'='*60}")
    print("测试 MiMo 配置")
    print(f"{'='*60}")

    try:
        config = load_llm_config(provider=PROVIDER_MIMO)

        print(f"✓ 配置加载成功:")
        print(f"  Provider: {config.provider}")
        print(f"  Model: {config.model}")
        print(f"  Base URL: {config.base_url}")
        key = config.api_key
        print(f"  API Key: {key[:20]}...{key[-10:] if len(key) > 30 else key}")

        endpoint = config.base_url.rstrip("/") + "/chat/completions"
        print(f"  Endpoint: {endpoint}")

        print(f"\n🤖 发送测试请求...")
        messages = [{"role": "user", "content": "请用中文回复：你好"}]
        response = call_llm(messages, config)

        print(f"✅ 调用成功!")
        print(f"响应内容: {response[:100]}...")
        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "="*60)
    print("MiMo AI 配置测试工具")
    print("="*60)

    ok = test_mimo()

    print(f"\n{'='*60}")
    print("测试总结")
    print(f"{'='*60}")
    print(f"MiMo: {'✅ 通过' if ok else '❌ 失败'}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
