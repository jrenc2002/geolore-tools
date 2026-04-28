#!/usr/bin/env python3
"""
统一 MiMo API 消耗脚本

使用方法:
    python consume_api.py
"""

import sys
import time
import argparse
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.common.config import load_llm_config, PROVIDER_MIMO
from src.common.llm_client import call_llm

# 配置
TARGET_REQUESTS = 100  # 每天目标请求次数
DELAY_BETWEEN_REQUESTS = 2  # 请求间隔（秒）


def generate_prompt(index):
    """生成多样化的提示词"""
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
    return prompts[index % len(prompts)]


def consume_api():
    """消耗 MiMo API 配额"""
    print(f"开始消耗 MiMo API - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    config = load_llm_config(provider=PROVIDER_MIMO)
    print(f"模型: {config.model}")
    print(f"端点: {config.base_url}")
    print(f"目标: {TARGET_REQUESTS} 次请求\n")

    success_count = 0
    error_count = 0

    for i in range(TARGET_REQUESTS):
        try:
            prompt = generate_prompt(i)
            print(f"[{i+1}/{TARGET_REQUESTS}] 发送请求: {prompt[:50]}...")

            messages = [{"role": "user", "content": prompt}]
            response_text = call_llm(messages, config)

            if response_text:
                success_count += 1
                print(f"✓ 成功 (响应长度: {len(response_text)} 字符)")
            else:
                error_count += 1
                print(f"✗ 响应为空")

            time.sleep(DELAY_BETWEEN_REQUESTS)

        except Exception as e:
            error_count += 1
            print(f"✗ 错误: {str(e)}")
            time.sleep(DELAY_BETWEEN_REQUESTS * 2)

    print(f"\n完成! 成功: {success_count}, 失败: {error_count}")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    try:
        consume_api()
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断执行")

