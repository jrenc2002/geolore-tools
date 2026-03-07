#!/usr/bin/env python3
"""测试 AI 配置是否正确"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.common.config import load_llm_config, PROVIDER_GEMINI, PROVIDER_CLAUDE
from src.common.llm_client import call_llm


def test_provider(provider_name: str):
    """测试指定的 AI 供应商"""
    print(f"\n{'='*60}")
    print(f"测试 {provider_name.upper()} 配置")
    print(f"{'='*60}")

    try:
        # 加载配置
        config = load_llm_config(provider=provider_name)

        print(f"✓ 配置加载成功:")
        print(f"  Provider: {config.provider}")
        print(f"  Model: {config.model}")
        print(f"  Base URL: {config.base_url}")
        print(f"  API Key: {config.api_key[:20]}...{config.api_key[-10:]}")

        # 构建端点
        from src.common.llm_client import PROVIDER_CLAUDE
        if config.provider == PROVIDER_CLAUDE:
            endpoint = config.base_url.rstrip("/") + "/messages"
        else:
            endpoint = config.base_url.rstrip("/") + "/chat/completions"

        print(f"  Endpoint: {endpoint}")

        # 测试简单调用
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
    print("AI 配置测试工具")
    print("="*60)

    # 测试 Gemini
    gemini_ok = test_provider(PROVIDER_GEMINI)

    # 测试 Claude
    claude_ok = test_provider(PROVIDER_CLAUDE)

    # 总结
    print(f"\n{'='*60}")
    print("测试总结")
    print(f"{'='*60}")
    print(f"Gemini: {'✅ 通过' if gemini_ok else '❌ 失败'}")
    print(f"Claude: {'✅ 通过' if claude_ok else '❌ 失败'}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
