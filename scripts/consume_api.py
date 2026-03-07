#!/usr/bin/env python3
"""
统一 AI API 消耗脚本
支持 Claude 和 Gemini 两种供应商

使用方法:
    python consume_api.py --provider gemini    # 使用 Gemini
    python consume_api.py --provider claude    # 使用 Claude
    python consume_api.py                      # 交互式选择
"""

import sys
import time
import argparse
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.common.config import load_llm_config, PROVIDER_GEMINI, PROVIDER_CLAUDE
from src.common.llm_client import call_llm

# 配置
TARGET_REQUESTS = 100  # 每天目标请求次数
DELAY_BETWEEN_REQUESTS = 2  # 请求间隔（秒）


def generate_prompt(index, provider):
    """生成多样化的提示词"""
    if provider == PROVIDER_GEMINI:
        prompts = [
            f"请用中文写一首关于第{index}天的诗",
            f"请解释什么是{index}号元素",
            f"请讲一个关于数字{index}的有趣故事",
            f"请列出{index}个编程最佳实践",
            f"请描述{index}种不同的云服务架构模式",
            f"请分析{index}个著名的算法及其时间复杂度",
            f"请介绍{index}个世界著名的旅游景点",
            f"请推荐{index}本值得阅读的技术书籍",
        ]
    else:  # PROVIDER_CLAUDE
        prompts = [
            f"请用中文详细分析第{index}个斐波那契数的数学特性",
            f"请写一篇关于{index}世纪科技发展的文章",
            f"请设计一个处理{index}个并发请求的系统架构",
            f"请解释{index}种不同的机器学习算法及其应用场景",
            f"请创作一个包含{index}个角色的短篇故事",
            f"请分析{index}个著名开源项目的架构设计",
            f"请列举{index}个提高代码质量的方法并详细说明",
            f"请描述{index}种不同的数据库优化策略",
        ]
    return prompts[index % len(prompts)]


def consume_api(provider):
    """消耗 API 配额

    Args:
        provider: PROVIDER_GEMINI 或 PROVIDER_CLAUDE
    """
    provider_name = "Gemini" if provider == PROVIDER_GEMINI else "Claude"
    print(f"开始消耗 {provider_name} API - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 加载配置
    config = load_llm_config(provider=provider)
    print(f"模型: {config.model}")
    print(f"端点: {config.base_url}")
    print(f"目标: {TARGET_REQUESTS} 次请求\n")

    success_count = 0
    error_count = 0

    for i in range(TARGET_REQUESTS):
        try:
            prompt = generate_prompt(i, provider)
            print(f"[{i+1}/{TARGET_REQUESTS}] 发送请求: {prompt[:50]}...")

            messages = [{"role": "user", "content": prompt}]
            response_text = call_llm(messages, config)

            if response_text:
                success_count += 1
                print(f"✓ 成功 (响应长度: {len(response_text)} 字符)")
            else:
                error_count += 1
                print(f"✗ 响应为空")

            # 避免触发速率限制
            time.sleep(DELAY_BETWEEN_REQUESTS)

        except Exception as e:
            error_count += 1
            print(f"✗ 错误: {str(e)}")
            time.sleep(DELAY_BETWEEN_REQUESTS * 2)  # 出错后等待更长时间

    print(f"\n完成! 成功: {success_count}, 失败: {error_count}")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def interactive_select_provider():
    """交互式选择供应商"""
    print("\n请选择 AI 供应商:")
    print("  1. Gemini")
    print("  2. Claude")
    print("  0. 退出")

    while True:
        choice = input("\n请输入选项 (0-2): ").strip()
        if choice == "1":
            return PROVIDER_GEMINI
        elif choice == "2":
            return PROVIDER_CLAUDE
        elif choice == "0":
            print("退出")
            sys.exit(0)
        else:
            print("无效选项，请重新输入")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="统一 AI API 消耗脚本")
    parser.add_argument(
        "--provider",
        choices=["gemini", "claude"],
        help="指定 AI 供应商 (gemini 或 claude)"
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=TARGET_REQUESTS,
        help=f"目标请求次数 (默认: {TARGET_REQUESTS})"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DELAY_BETWEEN_REQUESTS,
        help=f"请求间隔秒数 (默认: {DELAY_BETWEEN_REQUESTS})"
    )

    args = parser.parse_args()

    # 更新全局配置
    global TARGET_REQUESTS, DELAY_BETWEEN_REQUESTS
    TARGET_REQUESTS = args.requests
    DELAY_BETWEEN_REQUESTS = args.delay

    # 确定供应商
    if args.provider:
        provider = PROVIDER_GEMINI if args.provider == "gemini" else PROVIDER_CLAUDE
    else:
        provider = interactive_select_provider()

    # 执行消耗
    try:
        consume_api(provider)
    except KeyboardInterrupt:
        print("\n\n用户中断执行")
    except Exception as e:
        print(f"\n执行失败: {str(e)}")


if __name__ == "__main__":
    main()
