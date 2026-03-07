#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
故实巡礼 · 原文获取脚本

从 Anna's Archive 获取文学作品原文（唯一数据源）。
可独立使用，也可被 auto_pipeline.py 自动调用。

用法：
  # 指定作品获取
  python scripts/fetch_text.py --title "Great Expectations" --author "Charles Dickens"

  # 指定语言
  python scripts/fetch_text.py --title "红楼梦" --author "曹雪芹" --language zh

  # 批量获取（从选题文件）
  python scripts/fetch_text.py --topics-file output/data/topics.json --output output/texts/

  # 列出缓存内容
  python scripts/fetch_text.py --list-cache

  # 清除缓存
  python scripts/fetch_text.py --clear-cache
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import glob

# 添加项目根目录到 path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.textsource.fetcher import (
    fetch_full_text,
    fetch_full_text_batch,
    TextResult,
    DEFAULT_CACHE_DIR,
)


def cmd_fetch_single(args: argparse.Namespace) -> None:
    """获取单部作品"""
    sources = args.sources.split(",") if args.sources else None

    result = fetch_full_text(
        title=args.title,
        author=args.author or "",
        language=args.language or "",
        cache_dir=args.cache_dir,
        use_cache=not args.no_cache,
        sources=sources,
        min_length=args.min_length,
    )

    if not result:
        print(f"\n❌ 未找到《{args.title}》的原文")
        sys.exit(1)

    # 保存到输出目录
    if args.output:
        _save_result(result, args.output)

    # 打印摘要
    _print_result_summary(result)


def cmd_fetch_batch(args: argparse.Namespace) -> None:
    """从选题文件批量获取"""
    if not os.path.exists(args.topics_file):
        print(f"❌ 选题文件不存在: {args.topics_file}")
        sys.exit(1)

    with open(args.topics_file, "r", encoding="utf-8") as f:
        topics = json.load(f)

    if not isinstance(topics, list):
        print(f"❌ 选题文件格式错误（需要 JSON 数组）")
        sys.exit(1)

    works = []
    for t in topics:
        works.append({
            "title": t.get("title", ""),
            "author": t.get("author", ""),
            "language": t.get("language", ""),
        })

    print(f"\n📚 准备批量获取 {len(works)} 部作品...")

    results = fetch_full_text_batch(
        works=works,
        cache_dir=args.cache_dir,
        delay=args.delay,
    )

    # 保存结果
    if args.output:
        os.makedirs(args.output, exist_ok=True)
        for i, (work, result) in enumerate(zip(works, results)):
            if result:
                _save_result(result, args.output)

    # 汇总报告
    print(f"\n{'='*60}")
    print(f"📊 批量获取完成")
    print(f"{'='*60}")
    for work, result in zip(works, results):
        title = work.get("title", "?")
        if result:
            print(f"  ✅ 《{title}》 → {result.summary()}")
        else:
            print(f"  ❌ 《{title}》 → 未找到")


def cmd_list_cache(args: argparse.Namespace) -> None:
    """列出缓存内容"""
    cache_dir = args.cache_dir
    if not os.path.exists(cache_dir):
        print(f"📂 缓存目录不存在: {cache_dir}")
        return

    meta_files = glob.glob(os.path.join(cache_dir, "*.meta.json"))
    if not meta_files:
        print(f"📂 缓存为空")
        return

    print(f"\n📂 缓存内容（{cache_dir}）:")
    print(f"{'─'*70}")

    total_size = 0
    for mf in sorted(meta_files):
        try:
            with open(mf, "r", encoding="utf-8") as f:
                meta = json.load(f)
            txt_file = mf.replace(".meta.json", ".txt")
            size = os.path.getsize(txt_file) if os.path.exists(txt_file) else 0
            total_size += size

            title = meta.get("title", "?")
            author = meta.get("author", "?")
            source = meta.get("source", "?")
            lang = meta.get("language", "?")
            wc = meta.get("word_count", 0)
            cached_at = meta.get("cached_at", "?")

            size_str = f"{size / 1024:.1f}KB" if size < 1024 * 1024 else f"{size / 1024 / 1024:.1f}MB"
            print(f"  📖 《{title}》— {author}")
            print(f"     {source} | {lang} | {wc:,} 字 | {size_str} | {cached_at}")
        except Exception:
            continue

    print(f"{'─'*70}")
    total_str = f"{total_size / 1024:.1f}KB" if total_size < 1024 * 1024 else f"{total_size / 1024 / 1024:.1f}MB"
    print(f"  合计: {len(meta_files)} 本 | {total_str}")


def cmd_clear_cache(args: argparse.Namespace) -> None:
    """清除缓存"""
    cache_dir = args.cache_dir
    if not os.path.exists(cache_dir):
        print(f"📂 缓存目录不存在: {cache_dir}")
        return

    files = glob.glob(os.path.join(cache_dir, "*"))
    if not files:
        print(f"📂 缓存已为空")
        return

    count = len(files)
    for f in files:
        os.remove(f)

    print(f"🗑️  已清除 {count} 个缓存文件")


def _save_result(result: TextResult, output_dir: str) -> None:
    """保存获取结果到输出目录"""
    os.makedirs(output_dir, exist_ok=True)

    # 生成安全文件名
    import re
    safe_name = re.sub(r'[^\w\u4e00-\u9fff]+', '_', result.title)[:50]
    safe_name = safe_name.strip("_")
    if not safe_name:
        safe_name = "unknown"

    # 保存全文
    txt_path = os.path.join(output_dir, f"{safe_name}.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(result.full_text)

    # 保存元数据
    meta_path = os.path.join(output_dir, f"{safe_name}.meta.json")
    meta = {
        "title": result.title,
        "author": result.author,
        "source": result.source,
        "language": result.language,
        "url": result.url,
        "word_count": result.word_count,
        "is_full_text": result.is_full_text,
        **result.metadata,
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"  💾 已保存: {txt_path} ({result.word_count:,} 字)")


def _print_result_summary(result: TextResult) -> None:
    """打印获取结果摘要"""
    print(f"\n{'='*60}")
    print(f"📖 《{result.title}》— {result.author}")
    print(f"{'='*60}")
    print(f"  数据源: {result.summary()}")
    print(f"  URL: {result.url}")
    if result.metadata.get("subjects"):
        subjects = result.metadata["subjects"][:10]
        print(f"  主题: {', '.join(str(s) for s in subjects)}")
    print(f"\n  前 500 字预览:")
    print(f"  {'─'*50}")
    preview = result.full_text[:500].replace("\n", "\n  ")
    print(f"  {preview}...")
    print(f"  {'─'*50}")


def main():
    parser = argparse.ArgumentParser(
        description="故实巡礼 · 原文获取工具 — 从全球开放文学数据库获取小说全文",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
数据源说明:
  gutenberg   — Project Gutenberg（75K+ 公版书，英文为主）
  wikisource  — Wikisource 维基文库（多语种，含大量中文古典文学）
  openlibrary — Open Library（2000万+ 元数据，部分全文）

示例:
  # 获取英文小说
  python scripts/fetch_text.py --title "Great Expectations" --author "Dickens"

  # 获取中文古典文学
  python scripts/fetch_text.py --title "三国演义" --author "罗贯中" --language zh

  # 从选题文件批量获取
  python scripts/fetch_text.py --topics-file output/data/topics.json --output output/books/

  # 只从 Gutenberg 获取
  python scripts/fetch_text.py --title "Moby Dick" --sources gutenberg
        """,
    )

    # 模式选择
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--title", help="作品名称（单部获取模式）")
    mode.add_argument("--topics-file", help="选题文件路径（批量获取模式）")
    mode.add_argument("--list-cache", action="store_true", help="列出缓存内容")
    mode.add_argument("--clear-cache", action="store_true", help="清除缓存")

    # 作品信息
    parser.add_argument("--author", default="", help="作者名")
    parser.add_argument("--language", default="", help="语言代码（zh/en/ja/fr...）")

    # （保留 --sources 参数兼容性，但实际只用 Anna's Archive）
    parser.add_argument(
        "--sources",
        default="",
        help=argparse.SUPPRESS,
    )

    # 输出
    parser.add_argument("--output", default="", help="输出目录（保存获取的文本）")

    # 缓存
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR, help="缓存目录")
    parser.add_argument("--no-cache", action="store_true", help="不使用缓存")

    # 其他
    parser.add_argument("--min-length", type=int, default=1000, help="有效结果最小字符数")
    parser.add_argument("--delay", type=float, default=2.0, help="批量获取时作品间延迟（秒）")

    args = parser.parse_args()

    # 路由到对应命令
    if args.list_cache:
        cmd_list_cache(args)
    elif args.clear_cache:
        cmd_clear_cache(args)
    elif args.topics_file:
        cmd_fetch_batch(args)
    elif args.title:
        cmd_fetch_single(args)


if __name__ == "__main__":
    main()
