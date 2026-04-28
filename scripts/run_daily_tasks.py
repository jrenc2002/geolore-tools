#!/usr/bin/env python3
"""
故实巡礼 · 每日任务统一管理脚本

管理两个每日刷新的任务：
1. MiMo API 额度消耗
2. Anna's Archive 书籍下载

使用方法:
  python run_daily_tasks.py              # 交互式选择
  python run_daily_tasks.py --all        # 运行所有任务
  python run_daily_tasks.py --mimo       # 只运行 MiMo 消耗
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
    print("=" * 70)
    print("  故实巡礼 · 每日任务管理")
    print("  Daily Tasks Manager - Geolore Tools")
    print("=" * 70)
    print(f"  开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()


def run_mimo_task():
    print("\n" + "▶" * 35)
    print("  任务 1: 消耗 MiMo API 额度")
    print("▶" * 35 + "\n")
    try:
        from scripts.consume_api import consume_api
        consume_api()
        return True
    except Exception as e:
        print(f"❌ MiMo 任务失败: {e}")
        return False


def run_books_task():
    print("\n" + "▶" * 35)
    print("  任务 2: 下载 Anna's Archive 书籍")
    print("▶" * 35 + "\n")
    try:
        from scripts.consume_book_downloads import consume_downloads
        consume_downloads()
        return True
    except Exception as e:
        print(f"❌ 书籍下载任务失败: {e}")
        return False


def interactive_menu():
    print("请选择要执行的任务：")
    print("  1) 消耗 MiMo API 额度")
    print("  2) 下载 Anna's Archive 书籍")
    print("  3) 运行所有任务")
    print("  0) 退出")
    print()
    return input("请输入选项 [0-3]: ").strip()


def main():
    parser = argparse.ArgumentParser(description="故实巡礼 · 每日任务管理")
    parser.add_argument("--all", action="store_true", help="运行所有任务")
    parser.add_argument("--mimo", action="store_true", help="只运行 MiMo API 消耗")
    parser.add_argument("--books", action="store_true", help="只运行书籍下载任务")
    args = parser.parse_args()

    print_banner()

    results = {"mimo": None, "books": None}

    if args.all or args.mimo or args.books:
        if args.all or args.mimo:
            results["mimo"] = run_mimo_task()
        if args.all or args.books:
            results["books"] = run_books_task()
    else:
        choice = interactive_menu()
        if choice == "1":
            results["mimo"] = run_mimo_task()
        elif choice == "2":
            results["books"] = run_books_task()
        elif choice == "3":
            results["mimo"] = run_mimo_task()
            results["books"] = run_books_task()
        elif choice == "0":
            print("退出")
            return
        else:
            print("❌ 无效选项")
            return

    print("\n" + "=" * 70)
    print("  任务执行总结")
    print("=" * 70)
    task_display = {"mimo": "MiMo API", "books": "书籍下载"}
    executed = [k for k, v in results.items() if v is not None]
    if executed:
        for name, result in results.items():
            if result is not None:
                status = "✅ 成功" if result else "❌ 失败"
                print(f"  {task_display[name]}: {status}")
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
