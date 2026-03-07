#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
故实巡礼 · 自动下载脚本
持续下载书籍直到 API 配额耗尽

用法：
    python scripts/auto_download_until_quota_exhausted.py
    python scripts/auto_download_until_quota_exhausted.py --min-quota 5  # 保留 5 次配额
    python scripts/auto_download_until_quota_exhausted.py --batch-size 10  # 每批下载 10 本
"""

import sys
import os
import json
import time
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.textsource.fetcher import fetch_full_text
from src.tracking.tracker import BookTracker


def get_pending_books(tracker: BookTracker, limit: int = 50):
    """获取待下载的书籍列表"""
    books = tracker.get_books_by_status("pending")
    # 按 geo_score 排序
    books.sort(key=lambda x: x.get("geo_score", 0), reverse=True)
    return books[:limit]


def download_book(title: str, author: str, language: str, output_dir: str):
    """
    下载单本书籍

    Returns:
        (success: bool, quota_left: int, error: str)
    """
    try:
        result = fetch_full_text(title, author, language)

        if not result:
            return False, None, "下载失败"

        # 保存到指定目录
        book_dir = Path(output_dir) / title.replace("/", "_")
        book_dir.mkdir(parents=True, exist_ok=True)

        # 保存文本
        text_file = book_dir / f"{title}.txt"
        with open(text_file, "w", encoding="utf-8") as f:
            f.write(result.full_text)

        # 保存元数据
        meta_file = book_dir / "fetch_meta.json"
        meta = {
            "title": result.title,
            "author": result.author,
            "language": result.language,
            "word_count": result.word_count,
            "source": result.source,
            "url": result.url,
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "metadata": result.metadata,
        }
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        # 尝试从元数据中提取配额信息
        quota_left = None
        if result.metadata and "api_quota" in result.metadata:
            quota_left = result.metadata["api_quota"].get("downloads_left")

        return True, quota_left, None

    except Exception as e:
        return False, None, str(e)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="自动下载书籍直到 API 配额耗尽")
    parser.add_argument(
        "--min-quota",
        type=int,
        default=0,
        help="保留的最小配额数（默认 0，即用完所有配额）"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=25,
        help="每批下载的书籍数量（默认 25）"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output/books",
        help="书籍保存目录（默认 output/books）"
    )
    parser.add_argument(
        "--registry",
        type=str,
        default="output/book_registry.json",
        help="书籍注册表路径"
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=2,
        help="每本书下载后的延迟秒数（默认 2 秒）"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("📚 故实巡礼 · 自动下载脚本")
    print("=" * 60)
    print(f"  最小保留配额: {args.min_quota} 次")
    print(f"  批次大小: {args.batch_size} 本")
    print(f"  下载延迟: {args.delay} 秒")
    print(f"  输出目录: {args.output_dir}")
    print("=" * 60)
    print()

    # 初始化 tracker
    tracker = BookTracker(args.registry)

    total_downloaded = 0
    total_failed = 0
    last_quota = None

    while True:
        # 获取待下载书籍
        pending = get_pending_books(tracker, args.batch_size)

        if not pending:
            print("\n✅ 所有书籍已下载完成！")
            break

        print(f"\n📋 本批待下载: {len(pending)} 本书")
        print("-" * 60)

        batch_success = 0
        batch_failed = 0

        for i, book in enumerate(pending, 1):
            title = book.get("title", "")
            author = book.get("author", "")
            language = book.get("language", "zh")

            print(f"\n[{i}/{len(pending)}] 《{title}》 - {author}")

            # 下载书籍
            success, quota_left, error = download_book(
                title, author, language, args.output_dir
            )

            if success:
                print(f"  ✅ 下载成功")
                batch_success += 1
                total_downloaded += 1

                # 更新注册表状态
                tracker.update_book_status(title, "downloaded")

                # 显示配额信息
                if quota_left is not None:
                    last_quota = quota_left
                    print(f"  📊 剩余配额: {quota_left} 次")

                    # 检查是否达到最小配额限制
                    if quota_left <= args.min_quota:
                        print(f"\n⚠️  配额已达到最小保留值 ({args.min_quota})，停止下载")
                        print(f"  本次共下载: {total_downloaded} 本")
                        print(f"  下载失败: {total_failed} 本")
                        return
            else:
                print(f"  ❌ 下载失败: {error}")
                batch_failed += 1
                total_failed += 1

                # 更新注册表状态
                tracker.update_book_status(title, "failed")

            # 延迟
            if i < len(pending):
                time.sleep(args.delay)

        print("\n" + "=" * 60)
        print(f"📊 本批统计:")
        print(f"  ✅ 成功: {batch_success} 本")
        print(f"  ❌ 失败: {batch_failed} 本")
        if last_quota is not None:
            print(f"  📊 剩余配额: {last_quota} 次")
        print("=" * 60)

        # 如果本批全部失败，可能是网络问题，停止
        if batch_success == 0 and batch_failed > 0:
            print("\n⚠️  本批全部失败，可能是网络问题，停止下载")
            break

    print("\n" + "=" * 60)
    print("🎉 下载任务完成！")
    print("=" * 60)
    print(f"  总计下载: {total_downloaded} 本")
    print(f"  下载失败: {total_failed} 本")
    if last_quota is not None:
        print(f"  剩余配额: {last_quota} 次")
    print("=" * 60)


if __name__ == "__main__":
    main()
