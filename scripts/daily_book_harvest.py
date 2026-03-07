#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
故实巡礼 · 每日书目收割机 (Daily Book Harvest)

一键完成：
  1. AI 选书：调用 recommend_books.py scout 模式，让 AI 推荐 25 本高地图价值书目
  2. 按分数排序，取前 N 本（默认 25，受每日配额限制）
  3. 逐一从 Anna's Archive 下载原文，保存到 output/books/{slug}/
  4. 已下载的书目自动跳过（幂等操作）
  5. 可选：下载完成后自动触发 batch_process_all_books.py 跑 pipeline

用法：
  # 标准用法：AI 选 25 本，下载前 25 本
  python scripts/daily_book_harvest.py

  # 只选书，不下载（看看 AI 推荐什么）
  python scripts/daily_book_harvest.py --scout-only

  # 只下载，不选书（用注册表里已有推荐）
  python scripts/daily_book_harvest.py --download-only

  # 下载完后自动跑 pipeline
  python scripts/daily_book_harvest.py --auto-pipeline

  # 指定偏好地区和类型
  python scripts/daily_book_harvest.py --prefer-region "日本,东南亚" --prefer-type "travelogue"

  # 调整配额上限
  python scripts/daily_book_harvest.py --quota 25

  # 干跑：只打印，不实际下载
  python scripts/daily_book_harvest.py --dry-run

环境变量：
  GEOLORE_API_KEY: Gemini API 密钥
  ANNAS_ARCHIVE_KEY: Anna's Archive Fast Download API 密钥
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# 添加项目根目录到 path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.common.config import LLMConfig, load_llm_config, DEFAULT_BASE_URL
from src.textsource.fetcher import fetch_full_text, TextResult
from src.memory.book_registry import load_registry, save_registry

# ─────────────────────────── 配置 ───────────────────────────

DEFAULT_REGISTRY = os.path.join(_PROJECT_ROOT, "output/data/registry.json")
DEFAULT_BOOKS_DIR = os.path.join(_PROJECT_ROOT, "output/books")
DEFAULT_QUOTA = 25          # Anna's Archive 每日配额
SCOUT_TOTAL = 25            # 每次 AI 选书总数（scout 模式）
SCOUT_BATCH = 5             # 每轮 API 请求本数（5 轮 × 5 = 25）
INTER_DOWNLOAD_DELAY = 3    # 两次下载之间的间隔（秒），避免触发限速

# ─────────────────────────── 工具函数 ───────────────────────────

def slugify(text: str) -> str:
    """将书名转换为目录名 slug"""
    text = text.lower().strip()
    text = re.sub(r"[《》「」『』【】（）()\"'\s]+", "-", text)
    text = re.sub(r"[^\w\-\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]", "", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "unknown"


def get_already_downloaded(books_dir: str) -> set:
    """返回已经有 .txt 文件的书目 slug 集合"""
    downloaded = set()
    if not os.path.isdir(books_dir):
        return downloaded
    for book_id in os.listdir(books_dir):
        d = os.path.join(books_dir, book_id)
        if not os.path.isdir(d):
            continue
        txts = [f for f in os.listdir(d) if f.endswith(".txt") and not f.startswith(".")]
        if txts:
            downloaded.add(book_id)
    return downloaded


def get_already_processed(books_dir: str) -> set:
    """返回已经有 *_places_structured.json 的书目 slug 集合"""
    processed = set()
    if not os.path.isdir(books_dir):
        return processed
    for book_id in os.listdir(books_dir):
        d = os.path.join(books_dir, book_id)
        if not os.path.isdir(d):
            continue
        jsons = [f for f in os.listdir(d) if f.endswith("_places_structured.json")]
        if jsons:
            processed.add(book_id)
    return processed


# 可下载的状态集合（不含 completed/downloaded）
_DOWNLOADABLE_STATUSES = {"recommended", "pending"}


def sync_registry_with_disk(
    registry_path: str,
    books_dir: str,
    save: bool = True,
) -> Tuple[int, int]:
    """
    自动同步注册表状态与磁盘实际文件：
    - 有 *_places_structured.json → status = completed
    - 有 .txt 但没有 structured.json → status = downloaded
    返回 (completed更新数, downloaded更新数)
    """
    if not os.path.isfile(registry_path):
        return 0, 0

    # 扫描磁盘
    actual_downloaded: set = set()
    actual_completed: set = set()
    if os.path.isdir(books_dir):
        for entry in os.scandir(books_dir):
            if not entry.is_dir():
                continue
            files = os.listdir(entry.path)
            has_txt = any(f.endswith(".txt") for f in files)
            has_structured = any(f.endswith("_places_structured.json") for f in files)
            if has_structured:
                actual_completed.add(entry.name)
            elif has_txt:
                actual_downloaded.add(entry.name)

    registry = load_registry(registry_path)
    books = registry.get("books", [])
    n_completed = 0
    n_downloaded = 0

    for book in books:
        title = book.get("title", "")
        slug = slugify(title)
        title_en = book.get("title_en", "")
        slug_en = slugify(title_en) if title_en else ""
        current_status = book.get("status", "")

        in_completed = (
            slug in actual_completed
            or slug_en in actual_completed
            or title in actual_completed
        )
        in_downloaded = (
            slug in actual_downloaded
            or slug_en in actual_downloaded
            or title in actual_downloaded
        )

        if in_completed and current_status != "completed":
            book["status"] = "completed"
            n_completed += 1
        elif in_downloaded and current_status not in ("completed", "downloaded"):
            book["status"] = "downloaded"
            n_downloaded += 1

    if save and (n_completed + n_downloaded) > 0:
        save_registry(registry, registry_path)

    return n_completed, n_downloaded


def get_top_candidates(registry_path: str, limit: int, exclude_slugs: set) -> List[Dict]:
    """
    从注册表中取出 **真正未下载** 的推荐书目，
    按 geo_score 降序排列，跳过已下载的，返回前 limit 本。
    """
    if not os.path.isfile(registry_path):
        return []
    registry = load_registry(registry_path)
    books = registry.get("books", [])

    candidates = []
    for book in books:
        if book.get("status", "") not in _DOWNLOADABLE_STATUSES:
            continue
        title = book.get("title", "")
        slug = slugify(title)
        if slug in exclude_slugs:
            continue
        # 也检查原始 book_id 或英文标题
        title_en = book.get("title_en", "")
        if title_en:
            slug_en = slugify(title_en)
            if slug_en in exclude_slugs:
                continue
        candidates.append(book)

    # 按 geo_score 降序
    candidates.sort(
        key=lambda b: b.get("extra", {}).get("geo_score", b.get("geo_score", 0)),
        reverse=True,
    )
    return candidates[:limit]


def save_txt_to_book_dir(
    result: TextResult,
    books_dir: str,
    book_slug: str,
) -> str:
    """将 TextResult 的全文保存为 {books_dir}/{slug}/{title}.txt，返回保存路径"""
    book_dir = os.path.join(books_dir, book_slug)
    os.makedirs(book_dir, exist_ok=True)

    # 文件名用原始标题（中英均可）
    safe_title = re.sub(r'[\\/:*?"<>|]', "_", result.title)
    txt_path = os.path.join(book_dir, f"{safe_title}.txt")

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(result.full_text)

    # 同时保存 fetch_meta.json
    meta_path = os.path.join(book_dir, "fetch_meta.json")
    meta = {
        "title": result.title,
        "author": result.author,
        "language": result.language,
        "word_count": result.word_count,
        "source": result.source,
        "url": result.url,
        "fetched_at": datetime.now().isoformat(),
        "metadata": result.metadata,
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return txt_path


# ─────────────────────────── 主流程 ───────────────────────────

def run_scout(
    config: LLMConfig,
    registry_path: str,
    total: int = SCOUT_TOTAL,
    batch_size: int = SCOUT_BATCH,
    prefer_region: str = "",
    prefer_type: str = "",
    prefer_language: str = "",
    dry_run: bool = False,
) -> List[Dict]:
    """调用 recommend_books.cmd_scout 让 AI 推荐书目"""
    # 直接 import 而不是 subprocess，保持同进程执行
    from scripts.recommend_books import cmd_scout
    new_books = cmd_scout(
        total=total,
        config=config,
        registry_path=registry_path,
        prefer_region=prefer_region,
        prefer_type=prefer_type,
        prefer_language=prefer_language,
        batch_size=batch_size,
        dry_run=dry_run,
    )
    return new_books


def run_downloads(
    candidates: List[Dict],
    books_dir: str,
    quota: int,
    dry_run: bool = False,
) -> Tuple[List[str], List[str]]:
    """
    下载 candidates 中的书目（最多 quota 本），
    返回 (成功列表, 失败列表) 各为 book_slug
    """
    success: List[str] = []
    failed: List[str] = []

    already_downloaded = get_already_downloaded(books_dir)

    to_download = []
    for book in candidates:
        if len(to_download) >= quota:
            break
        title = book.get("title", "")
        slug = slugify(title)
        # 也试英文标题
        title_en = book.get("title_en", "")
        if slug in already_downloaded or (title_en and slugify(title_en) in already_downloaded):
            print(f"  ⏩ 已存在，跳过: 《{title}》")
            continue
        to_download.append(book)

    print(f"\n{'═'*60}")
    print(f"⬇️  开始下载 {len(to_download)} 本书（配额: {quota}/天）")
    print(f"{'═'*60}")

    for i, book in enumerate(to_download, 1):
        title = book.get("title", "")
        author = book.get("author", "未知")
        language = book.get("language", "")
        slug = slugify(title)

        print(f"\n  [{i}/{len(to_download)}] 《{title}》— {author}")

        if dry_run:
            print(f"  [dry-run] 跳过实际下载，slug={slug}")
            success.append(slug)
            continue

        try:
            result = fetch_full_text(
                title=title,
                author=author,
                language=language,
                use_cache=True,
            )

            if result and result.full_text:
                txt_path = save_txt_to_book_dir(result, books_dir, slug)
                print(f"  ✅ 已保存: {txt_path} ({result.word_count:,} 字)")
                success.append(slug)
            else:
                print(f"  ❌ 下载失败: 《{title}》（未找到原文）")
                failed.append(slug)

        except Exception as e:
            print(f"  ❌ 下载异常: 《{title}》— {e}")
            import traceback
            traceback.print_exc()
            failed.append(slug)

        # 两次下载之间等待，避免限速
        if i < len(to_download):
            time.sleep(INTER_DOWNLOAD_DELAY)

    return success, failed


def run_pipeline(books_dir: str, book_concurrency: int = 3) -> None:
    """下载完成后启动 batch_process_all_books.py 跑 pipeline"""
    api_key = os.environ.get("GEOLORE_API_KEY", "")
    python = sys.executable
    script = os.path.join(_PROJECT_ROOT, "scripts/batch_process_all_books.py")
    cmd = [
        python, "-u", script,
        "--book-concurrency", str(book_concurrency),
    ]
    print(f"\n{'═'*60}")
    print(f"🚀 启动 pipeline 处理新下载书目...")
    print(f"{'═'*60}")
    env = os.environ.copy()
    env["GEOLORE_API_KEY"] = api_key
    subprocess.run(cmd, env=env)


# ─────────────────────────── CLI ───────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="每日书目收割机：AI 选书 → 下载原文 → 可选 pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--quota", type=int, default=DEFAULT_QUOTA,
        help=f"Anna's Archive 每日下载配额（默认: {DEFAULT_QUOTA}）",
    )
    parser.add_argument(
        "--scout-count", type=int, default=SCOUT_TOTAL,
        help=f"AI 每次选书总数（默认: {SCOUT_TOTAL}，分 {SCOUT_TOTAL//SCOUT_BATCH} 轮请求）",
    )
    parser.add_argument(
        "--scout-batch", type=int, default=SCOUT_BATCH,
        help=f"每轮 AI 请求本数（默认: {SCOUT_BATCH}）",
    )
    parser.add_argument(
        "--prefer-region", default="",
        help="偏好地区，逗号分隔，如 '日本,东南亚,南美'",
    )
    parser.add_argument(
        "--prefer-type", default="",
        help="偏好类型，逗号分隔，如 'travelogue,biography'",
    )
    parser.add_argument(
        "--prefer-language", default="",
        help="偏好语言，逗号分隔，如 'zh,en,ja'",
    )
    parser.add_argument(
        "--scout-only", action="store_true",
        help="只进行 AI 选书，不下载",
    )
    parser.add_argument(
        "--download-only", action="store_true",
        help="只下载（使用注册表已有推荐），不跑 AI 选书",
    )
    parser.add_argument(
        "--auto-pipeline", action="store_true",
        help="下载完成后自动启动 pipeline 处理新书",
    )
    parser.add_argument(
        "--pipeline-concurrency", type=int, default=3,
        help="pipeline 书目并发数（默认: 3）",
    )
    parser.add_argument(
        "--registry", default=DEFAULT_REGISTRY,
        help=f"注册表路径（默认: {DEFAULT_REGISTRY}）",
    )
    parser.add_argument(
        "--books-dir", default=DEFAULT_BOOKS_DIR,
        help=f"书目输出目录（默认: {DEFAULT_BOOKS_DIR}）",
    )
    parser.add_argument(
        "--api-key", default=os.environ.get("GEOLORE_API_KEY", ""),
        help="Gemini API Key（或设置 GEOLORE_API_KEY 环境变量）",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="干跑：打印计划但不实际执行",
    )
    parser.add_argument(
        "--sync-registry", action="store_true",
        help="扫描磁盘同步注册表状态后退出（不选书不下载）",
    )
    parser.add_argument(
        "--show-queue", action="store_true",
        help="显示下载队列（按 geo_score 排名的待下载书目）后退出",
    )
    args = parser.parse_args()

    # ── 读取 API Key ──
    if not args.api_key:
        env_file = os.path.join(_PROJECT_ROOT, ".env")
        if os.path.isfile(env_file):
            for line in open(env_file):
                line = line.strip()
                if line.startswith("GEOLORE_API_KEY="):
                    args.api_key = line.split("=", 1)[1].strip()
                    break
    if not args.api_key and not args.download_only:
        print("❌ 需要 GEOLORE_API_KEY（AI 选书需要）")
        sys.exit(1)

    config = LLMConfig(api_key=args.api_key, base_url=DEFAULT_BASE_URL)

    print(f"\n{'═'*60}")
    print(f"📚 故实巡礼 · 每日书目收割机")
    print(f"{'═'*60}")
    print(f"  日期: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  AI 选书: {args.scout_count} 本（每轮 {args.scout_batch} 本）")
    print(f"  下载配额: {args.quota} 本/天")
    print(f"  下载目录: {args.books_dir}")
    if args.prefer_region:
        print(f"  偏好地区: {args.prefer_region}")
    if args.prefer_type:
        print(f"  偏好类型: {args.prefer_type}")
    print()

    # ── 自动同步注册表状态（始终执行）──
    print(f"🔄 自动同步注册表状态...")
    n_comp, n_dl = sync_registry_with_disk(
        registry_path=args.registry,
        books_dir=args.books_dir,
        save=not args.dry_run,
    )
    if n_comp + n_dl > 0:
        print(f"   ↳ 更新 {n_comp} 本→completed，{n_dl} 本→downloaded")
    else:
        print(f"   ↳ 注册表状态已是最新")
    print()

    # ── --sync-registry 模式：同步后退出 ──
    if args.sync_registry:
        print("✅ 同步完成（--sync-registry 模式）")
        return

    # ── --show-queue 模式：显示下载队列后退出 ──
    if args.show_queue:
        already = get_already_downloaded(args.books_dir)
        candidates = get_top_candidates(args.registry, limit=100, exclude_slugs=already)
        print(f"{'─'*60}")
        print(f"📋 待下载队列（按 geo_score 排名，共 {len(candidates)} 本）")
        print(f"{'─'*60}")
        if not candidates:
            print("  ⚠️  队列为空！注册表中没有 status=recommended 的书目")
            print("  💡 先运行：python scripts/daily_book_harvest.py --scout-only")
        else:
            for i, book in enumerate(candidates, 1):
                title = book.get("title", "?")
                author = book.get("author", "?")
                score = book.get("geo_score", 0)
                grade = book.get("grade", "?")
                region = book.get("geo_region", "?")
                lang = book.get("language", "?")
                print(f"  {i:3d}. [{grade}|{score:5.1f}] 《{title}》— {author} [{lang}] {region}")
        print()
        return

    # ── Step 1: AI 选书 ──
    if not args.download_only:
        print(f"{'─'*60}")
        print(f"🤖 Step 1: AI 选书（scout 模式，{args.scout_count} 本）")
        print(f"{'─'*60}")
        run_scout(
            config=config,
            registry_path=args.registry,
            total=args.scout_count,
            batch_size=args.scout_batch,
            prefer_region=args.prefer_region,
            prefer_type=args.prefer_type,
            prefer_language=args.prefer_language,
            dry_run=args.dry_run,
        )
    else:
        print("⏩ 跳过 AI 选书（--download-only 模式）")

    if args.scout_only:
        print("\n✅ 选书完成（--scout-only 模式，不下载）")
        return

    # ── Step 2: 取候选书目 ──
    already = get_already_downloaded(args.books_dir)
    candidates = get_top_candidates(args.registry, limit=args.quota * 3, exclude_slugs=already)

    if not candidates:
        print("\n⚠️  注册表中没有可下载的推荐书目（status=recommended 且未下载）")
        print("   请先运行：python scripts/recommend_books.py --mode scout --count 25")
        return

    print(f"\n{'─'*60}")
    print(f"📋 Step 2: 候选书目（按地图价值排序，取前 {args.quota} 本）")
    print(f"{'─'*60}")
    for i, book in enumerate(candidates[:args.quota], 1):
        title = book.get("title", "?")
        author = book.get("author", "?")
        score = book.get("extra", {}).get("geo_score", book.get("geo_score", 0))
        grade = book.get("grade", "?")
        region = book.get("geo_region", "?")
        lang = book.get("language", "?")
        print(f"  {i:2d}. [{grade}|{score:.0f}分] 《{title}》— {author} [{lang}] {region}")

    # ── Step 3: 下载 ──
    print(f"\n{'─'*60}")
    print(f"⬇️  Step 3: 下载原文（最多 {args.quota} 本）")
    print(f"{'─'*60}")

    success, failed = run_downloads(
        candidates=candidates[:args.quota * 2],   # 多给一些候选，失败时可顺延
        books_dir=args.books_dir,
        quota=args.quota,
        dry_run=args.dry_run,
    )

    # ── 汇总 ──
    print(f"\n{'═'*60}")
    print(f"🎉 每日收割完成！")
    print(f"{'═'*60}")
    print(f"  ✅ 成功下载: {len(success)} 本")
    print(f"  ❌ 下载失败: {len(failed)} 本")
    if failed:
        print(f"  失败书目: {', '.join(failed)}")

    # 更新注册表状态
    if success and not args.dry_run:
        registry = load_registry(args.registry)
        for book in registry.get("books", []):
            slug = slugify(book.get("title", ""))
            if slug in success:
                book["status"] = "downloaded"
        save_registry(registry, args.registry)
        print(f"  💾 注册表已更新（{len(success)} 本标记为 downloaded）")

    # ── Step 4: 可选 pipeline ──
    if args.auto_pipeline and success and not args.dry_run:
        print(f"\n{'─'*60}")
        print(f"🚀 Step 4: 自动启动 pipeline 处理 {len(success)} 本新书")
        print(f"{'─'*60}")
        run_pipeline(args.books_dir, book_concurrency=args.pipeline_concurrency)
    elif success:
        print(f"\n  💡 下一步：运行 pipeline 处理新书：")
        print(f"     python scripts/batch_process_all_books.py --book-concurrency 3")

    print(f"\n{'═'*60}")


if __name__ == "__main__":
    main()
