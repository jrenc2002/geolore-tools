#!/usr/bin/env python3
"""
故实巡礼 · 每日任务统一管理脚本

管理三个每日刷新的任务：
1. Gemini API 额度消耗
2. Claude API 额度消耗
3. Anna's Archive 书籍下载

使用方法:
  python run_daily_tasks.py              # 交互式选择
  python run_daily_tasks.py --all        # 运行所有任务
  python run_daily_tasks.py --gemini     # 只运行 Gemini
  python run_daily_tasks.py --claude     # 只运行 Claude
  python run_daily_tasks.py --books      # 只运行书籍下载
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def print_banner():
    """打印横幅"""
    print("=" * 70)
    print("  故实巡礼 · 每日任务管理")
    print("  Daily Tasks Manager - Geolore Tools")
    print("=" * 70)
    print(f"  开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()


def run_gemini_task():
    """运行 Gemini API 消耗任务"""
    print("\n" + "▶" * 35)
    print("  任务 1: 消耗 Gemini API 额度")
    print("▶" * 35 + "\n")

    try:
        from scripts.consume_api import consume_api
        from src.common.config import PROVIDER_GEMINI
        consume_api(PROVIDER_GEMINI)
        return True
    except Exception as e:
        print(f"❌ Gemini 任务失败: {e}")
        return False


def run_claude_task():
    """运行 Claude API 消耗任务"""
    print("\n" + "▶" * 35)
    print("  任务 2: 消耗 Claude API 额度")
    print("▶" * 35 + "\n")

    try:
        from scripts.consume_api import consume_api
        from src.common.config import PROVIDER_CLAUDE
        consume_api(PROVIDER_CLAUDE)
        return True
    except Exception as e:
        print(f"❌ Claude 任务失败: {e}")
        return False


def run_books_task():
    """运行书籍下载任务"""
    print("\n" + "▶" * 35)
    print("  任务 3: 下载 Anna's Archive 书籍")
    print("▶" * 35 + "\n")

    try:
        from scripts.consume_book_downloads import consume_downloads
        consume_downloads()
        return True
    except Exception as e:
        print(f"❌ 书籍下载任务失败: {e}")
        return False


def interactive_menu():
    """交互式菜单"""
    print("请选择要执行的任务：")
    print("  1) 消耗 Gemini API 额度")
    print("  2) 消耗 Claude API 额度")
    print("  3) 下载 Anna's Archive 书籍")
    print("  4) 运行所有任务")
    print("  0) 退出")
    print()

    choice = input("请输入选项 [0-4]: ").strip()
    return choice


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="故实巡礼 · 每日任务管理")
    parser.add_argument("--all", action="store_true", help="运行所有任务")
    parser.add_argument("--gemini", action="store_true", help="只运行 Gemini 任务")
    parser.add_argument("--claude", action="store_true", help="只运行 Claude 任务")
    parser.add_argument("--books", action="store_true", help="只运行书籍下载任务")

    args = parser.parse_args()

    print_banner()

    results = {
        "gemini": None,
        "claude": None,
        "books": None,
    }

    # 命令行参数模式
    if args.all or args.gemini or args.claude or args.books:
        if args.all or args.gemini:
            results["gemini"] = run_gemini_task()

        if args.all or args.claude:
            results["claude"] = run_claude_task()

        if args.all or args.books:
            results["books"] = run_books_task()

    # 交互式模式
    else:
        choice = interactive_menu()

        if choice == "1":
            results["gemini"] = run_gemini_task()
        elif choice == "2":
            results["claude"] = run_claude_task()
        elif choice == "3":
            results["books"] = run_books_task()
        elif choice == "4":
            results["gemini"] = run_gemini_task()
            results["claude"] = run_claude_task()
            results["books"] = run_books_task()
        elif choice == "0":
            print("退出")
            return
        else:
            print("❌ 无效选项")
            return

    # 打印总结
    print("\n" + "=" * 70)
    print("  任务执行总结")
    print("=" * 70)

    executed_tasks = [k for k, v in results.items() if v is not None]
    if executed_tasks:
        for task_name, result in results.items():
            if result is not None:
                status = "✅ 成功" if result else "❌ 失败"
                task_display = {
                    "gemini": "Gemini API",
                    "claude": "Claude API",
                    "books": "书籍下载",
                }
                print(f"  {task_display[task_name]}: {status}")
    else:
        print("  未执行任何任务")

    print("=" * 70)
    print(f"  结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断执行")
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
