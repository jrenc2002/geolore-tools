#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
故实巡礼 · 原文获取 + 追踪系统 集成测试

本脚本用一组真实的中英文书目测试：
  1. 从 Gutenberg / Wikisource / Open Library 获取原文
  2. 将每次获取尝试写入 SQLite 追踪数据库
  3. 导出 CSV 报告
  4. 打印仪表盘

运行:
  python scripts/test_fetch_and_track.py

输出:
  output/tracking/pipeline_runs.csv   — 运行记录 CSV
  output/tracking/books.csv           — 书目追踪 CSV
  output/tracking/text_fetches.csv    — 原文获取日志 CSV
  output/tracking/pipeline_steps.csv  — 步骤执行记录 CSV
"""

from __future__ import annotations

import os
import sys
import time

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.textsource.fetcher import (
    fetch_full_text,
    search_gutenberg,
    search_wikisource,
    search_openlibrary,
    TextResult,
)
from src.tracking.tracker import PipelineTracker

# ─────────────────────────── 测试书单 ───────────────────────────

TEST_BOOKS = [
    # ── 英文经典（Gutenberg 高命中率）──
    {
        "title": "Pride and Prejudice",
        "author": "Jane Austen",
        "language": "en",
        "type": "novel",
        "grade": "S",
        "geo_region": "England",
        "reason": "英国乡村庄园，地理化场景丰富",
    },
    {
        "title": "The Great Gatsby",
        "author": "F. Scott Fitzgerald",
        "language": "en",
        "type": "novel",
        "grade": "A",
        "geo_region": "New York",
        "reason": "纽约长岛，地理标志性极强",
    },
    # ── 中文古典（Wikisource 高命中率）──
    {
        "title": "三国演义",
        "author": "罗贯中",
        "language": "zh",
        "type": "novel",
        "grade": "S",
        "geo_region": "华中",
        "reason": "古战场遍布全国，地理化价值极高",
    },
    # ── 中文近现代（可能只有元数据）──
    {
        "title": "围城",
        "author": "钱钟书",
        "language": "zh",
        "type": "novel",
        "grade": "A",
        "geo_region": "华东",
        "reason": "上海-内地旅途，线性路线",
    },
    # ── 法语经典（多源测试）──
    {
        "title": "Les Misérables",
        "author": "Victor Hugo",
        "language": "fr",
        "type": "novel",
        "grade": "S",
        "geo_region": "法国",
        "reason": "巴黎街巷极其丰富",
    },
]


def test_individual_sources(tracker: PipelineTracker):
    """逐源测试每本书，记录每次尝试"""
    print(f"\n{'━'*60}")
    print(f"  🧪 阶段 1: 逐源测试各数据源")
    print(f"{'━'*60}")

    sources_to_test = [
        ("gutenberg", search_gutenberg),
        ("wikisource", search_wikisource),
        ("openlibrary", search_openlibrary),
    ]

    for book in TEST_BOOKS:
        title = book["title"]
        author = book["author"]
        lang = book["language"]

        print(f"\n  📖 《{title}》— {author} [{lang}]")
        print(f"  {'─'*50}")

        for source_name, search_fn in sources_to_test:
            t0 = time.time()
            try:
                if source_name == "gutenberg":
                    result = search_fn(title, author, lang)
                elif source_name == "wikisource":
                    result = search_fn(title, author, lang)
                else:
                    result = search_fn(title, author, lang)

                elapsed_ms = int((time.time() - t0) * 1000)

                if result:
                    tracker.log_text_fetch(
                        book_title=title,
                        source=source_name,
                        found=True,
                        is_full_text=result.is_full_text,
                        word_count=result.word_count,
                        url=result.url,
                        response_ms=elapsed_ms,
                    )
                    status = "全文" if result.is_full_text else "元数据"
                    print(f"    ✅ {source_name:12s} → {status} | {result.word_count:>8,} 字 | {elapsed_ms}ms")
                else:
                    tracker.log_text_fetch(
                        book_title=title,
                        source=source_name,
                        found=False,
                        response_ms=elapsed_ms,
                    )
                    print(f"    ❌ {source_name:12s} → 未找到 | {elapsed_ms}ms")

            except Exception as e:
                elapsed_ms = int((time.time() - t0) * 1000)
                tracker.log_text_fetch(
                    book_title=title,
                    source=source_name,
                    found=False,
                    error=str(e)[:200],
                    response_ms=elapsed_ms,
                )
                print(f"    ⚠️  {source_name:12s} → 异常: {str(e)[:80]} | {elapsed_ms}ms")

            # API 限速
            time.sleep(1.5)


def test_unified_fetch(tracker: PipelineTracker):
    """测试统一入口 fetch_full_text（自动选源）"""
    print(f"\n{'━'*60}")
    print(f"  🧪 阶段 2: 统一获取测试 (fetch_full_text)")
    print(f"{'━'*60}")

    for book in TEST_BOOKS:
        title = book["title"]
        author = book["author"]
        lang = book["language"]

        # 更新书籍状态
        tracker.update_book(title, status="fetching", started_at=tracker._now())

        t0 = time.time()
        result = fetch_full_text(
            title=title,
            author=author,
            language=lang,
            cache_dir="output/.text_cache",
        )
        elapsed = time.time() - t0

        if result:
            tracker.update_book(
                title,
                text_source=result.source,
                text_fetched=1,
                text_is_full=1 if result.is_full_text else 0,
                text_word_count=result.word_count,
                text_url=result.url,
                status="completed",
                elapsed_sec=round(elapsed, 1),
                finished_at=tracker._now(),
            )
        else:
            tracker.update_book(
                title,
                text_source="none",
                text_fetched=0,
                status="failed",
                error_message="未在任何数据源中找到",
                elapsed_sec=round(elapsed, 1),
                finished_at=tracker._now(),
            )

        time.sleep(2)


def main():
    tracking_dir = os.path.join(_PROJECT_ROOT, "output", "tracking")
    output_dir = os.path.join(_PROJECT_ROOT, "output")

    print(f"{'═'*60}")
    print(f"  🧪 Geolore 原文获取 + 追踪系统 集成测试")
    print(f"{'═'*60}")
    print(f"  数据库: {db_path}")
    print(f"  书目数: {len(TEST_BOOKS)}")
    print(f"  数据源: Gutenberg / Wikisource / Open Library")
    print(f"{'═'*60}")

    tracker = PipelineTracker(tracking_dir)
    run_id = tracker.start_run(mode="test", config={
        "test": True,
        "book_count": len(TEST_BOOKS),
        "sources": ["gutenberg", "wikisource", "openlibrary"],
    })
    print(f"  运行 ID: {run_id}\n")

    # 注册所有测试书目
    for book in TEST_BOOKS:
        tracker.add_book(
            title=book["title"],
            author=book["author"],
            language=book.get("language", ""),
            book_type=book.get("type", "novel"),
            grade=book.get("grade", ""),
            geo_region=book.get("geo_region", ""),
            reason=book.get("reason", ""),
        )

    # 阶段 1: 逐源测试
    step_id = tracker.start_step("_all_", "test_individual_sources")
    try:
        test_individual_sources(tracker)
        tracker.finish_step(step_id, status="completed", item_count=len(TEST_BOOKS) * 3)
    except Exception as e:
        tracker.finish_step(step_id, status="failed", error=str(e))
        raise

    # 阶段 2: 统一获取测试
    step_id = tracker.start_step("_all_", "test_unified_fetch")
    try:
        test_unified_fetch(tracker)
        tracker.finish_step(step_id, status="completed", item_count=len(TEST_BOOKS))
    except Exception as e:
        tracker.finish_step(step_id, status="failed", error=str(e))
        raise

    # 结束运行
    tracker.finish_run("completed")

    # 导出 CSV
    print(f"\n{'━'*60}")
    print(f"  📊 导出报告")
    print(f"{'━'*60}")
    tracker.export_all_csv(output_dir)

    # 打印仪表盘
    tracker.print_dashboard()

    # 打印 CSV 查阅提示
    print(f"\n{'═'*60}")
    print(f"  💡 CSV 文件位置")
    print(f"{'═'*60}")
    print(f"  output/tracking/pipeline_runs.csv     — 运行记录")
    print(f"  output/tracking/books.csv             — 书目状态")
    print(f"  output/tracking/text_fetches.csv      — 原文获取日志")
    print(f"  output/tracking/pipeline_steps.csv    — 步骤执行记录")
    print(f"{'═'*60}")

    tracker.close()
    print(f"\n✅ 测试完成！")


if __name__ == "__main__":
    main()
