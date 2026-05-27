#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
批量处理所有待处理书籍的流水线脚本

对 output/books/ 下所有有 .txt 原文但还没有 *_places_structured.json 的书目，
并发执行完整流水线（Step 2 提取 → Step 3 富化 → Step 3b 元数据 → Step 4 审查 → Step 5 输出）。

用法：
  python scripts/batch_process_all_books.py
  python scripts/batch_process_all_books.py --force   # 强制重新处理已有结果的书
  python scripts/batch_process_all_books.py --book-concurrency 3  # 同时处理3本书
  python scripts/batch_process_all_books.py --dry-run  # 只列出待处理书目不执行

环境变量：
  GEOLORE_API_KEY: API 密钥
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# 添加项目根目录到 path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.common.config import LLMConfig, DEFAULT_BASE_URL
from scripts.auto_pipeline import run_pipeline_for_work

# ─────────────────────────── 书目元数据 ───────────────────────────

# 手动维护的书目元数据（补充 fetch_meta.json 中没有的字段）
BOOK_META_OVERRIDES: Dict[str, Dict] = {
    "a-moveable-feast": {
        "work_type": "travelogue",
        "era_setting": "1920年代",
        "geo_scope": "法国巴黎",
    },
    "angels-demons": {
        "work_type": "novel",
        "era_setting": "现代",
        "geo_scope": "瑞士日内瓦、梵蒂冈、罗马",
    },
    "country-driving-a-journey-through-china-from-farm-to-factory": {
        "work_type": "travelogue",
        "era_setting": "2000年代",
        "geo_scope": "中国（长城沿线、农村、工厂）",
    },
    "dubliners": {
        "work_type": "novel",
        "era_setting": "20世纪初",
        "geo_scope": "爱尔兰都柏林",
    },
    "in-patagonia": {
        "work_type": "travelogue",
        "era_setting": "1970年代",
        "geo_scope": "阿根廷巴塔哥尼亚",
    },
    "inferno": {
        "work_type": "novel",
        "era_setting": "现代",
        "geo_scope": "意大利佛罗伦萨、威尼斯、土耳其伊斯坦布尔",
    },
    "midnight-in-the-garden-of-good-and-evil": {
        "work_type": "biography",
        "era_setting": "1980年代",
        "geo_scope": "美国乔治亚州萨凡纳",
    },
    "the-beach": {
        "work_type": "novel",
        "era_setting": "1990年代",
        "geo_scope": "泰国（曼谷、秘密海滩）",
    },
    "the-da-vinci-code": {
        "work_type": "novel",
        "era_setting": "现代",
        "geo_scope": "法国巴黎、英国伦敦、苏格兰",
    },
    "the-motorcycle-diaries": {
        "work_type": "travelogue",
        "era_setting": "1950年代",
        "geo_scope": "南美洲（阿根廷、智利、秘鲁等）",
    },
    "the-old-capital": {
        "work_type": "novel",
        "era_setting": "战后昭和时代",
        "geo_scope": "日本京都",
    },
    "the-shadow-of-the-wind": {
        "work_type": "novel",
        "era_setting": "1940-1960年代",
        "geo_scope": "西班牙巴塞罗那",
    },
    "东京梦华录": {
        "work_type": "history",
        "era_setting": "北宋（约1100年）",
        "geo_scope": "中国河南开封（北宋东京）",
    },
    "大唐西域记": {
        "work_type": "travelogue",
        "era_setting": "唐朝（629-645年）",
        "geo_scope": "中亚、南亚（丝绸之路沿线）",
    },
    "湘行散记": {
        "work_type": "travelogue",
        "era_setting": "1934年",
        "geo_scope": "中国湖南湘西",
    },
    "繁花": {
        "work_type": "novel",
        "era_setting": "1960-1990年代",
        "geo_scope": "中国上海",
    },
    "老残游记": {
        "work_type": "novel",
        "era_setting": "清末（约1900年）",
        "geo_scope": "中国山东（济南、黄河流域）",
    },
    "长安十二时辰": {
        "work_type": "novel",
        "era_setting": "唐朝天宝三年（744年）",
        "geo_scope": "中国陕西长安（唐都）",
    },
}

# ─────────────────────────── 辅助函数 ───────────────────────────

def discover_pending_books(books_dir: str, force: bool = False) -> List[Dict]:
    """扫描 output/books/，找出有 .txt 原文但没有 *_places_structured.json 的书目"""
    pending = []
    skip_prefixes = ("work-",)  # 跳过临时 work-* 目录

    for book_id in sorted(os.listdir(books_dir)):
        book_dir = os.path.join(books_dir, book_id)
        if not os.path.isdir(book_dir):
            continue

        # 跳过 work-* 临时目录
        if any(book_id.startswith(p) for p in skip_prefixes):
            continue

        # 查找 .txt 原文
        txt_files = [f for f in os.listdir(book_dir) if f.endswith(".txt")]
        if not txt_files:
            continue  # 无原文，跳过

        txt_path = os.path.join(book_dir, txt_files[0])

        # 检查是否已有 places_structured.json
        existing_json = [f for f in os.listdir(book_dir) if f.endswith("_places_structured.json")]
        if existing_json and not force:
            continue  # 已处理，跳过

        # 读取 fetch_meta.json
        meta_path = os.path.join(book_dir, "fetch_meta.json")
        if os.path.isfile(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        else:
            meta = {}

        title = meta.get("title", book_id)
        author = meta.get("author", "未知")
        language = meta.get("language", "zh")

        # 获取额外元数据
        overrides = BOOK_META_OVERRIDES.get(book_id, {})
        work_type = overrides.get("work_type", "novel")
        era_setting = overrides.get("era_setting", "")
        geo_scope = overrides.get("geo_scope", "")

        pending.append({
            "book_id": book_id,
            "title": title,
            "author": author,
            "language": language,
            "work_type": work_type,
            "era_setting": era_setting,
            "geo_scope": geo_scope,
            "txt_path": txt_path,
            "book_dir": book_dir,
            "already_done": bool(existing_json),
        })

    return pending


_print_lock = threading.Lock()


def process_one_book(
    book_info: Dict,
    config: LLMConfig,
    output_dir: str,
    resume_from: Optional[str] = None,
) -> Tuple[str, bool, Optional[str]]:
    """处理单本书，返回 (book_id, success, output_file)"""
    book_id = book_info["book_id"]
    title = book_info["title"]
    author = book_info["author"]

    with _print_lock:
        print(f"\n{'🔷 '*3} 开始处理《{title}》（{author}）{'🔷 '*3}")
        if resume_from:
            print(f"   断点续跑：从 {resume_from} 开始")

    try:
        result_file = run_pipeline_for_work(
            config=config,
            title=title,
            author=author,
            work_type=book_info["work_type"],
            era_setting=book_info["era_setting"],
            geo_scope=book_info["geo_scope"],
            output_dir=output_dir,
            min_places=15,
            tracker=None,
            text_file=book_info["txt_path"],
            resume_from=resume_from,
        )
        if result_file:
            with _print_lock:
                print(f"\n  ✅ 《{title}》完成 → {result_file}")
            return (book_id, True, result_file)
        else:
            with _print_lock:
                print(f"\n  ❌ 《{title}》失败（run_pipeline_for_work 返回 None）")
            return (book_id, False, None)
    except Exception as e:
        with _print_lock:
            print(f"\n  ❌ 《{title}》异常: {e}")
        import traceback
        traceback.print_exc()
        return (book_id, False, None)


def main():
    parser = argparse.ArgumentParser(
        description="批量处理所有待处理书籍",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--books-dir",
        default="output/books",
        help="书目目录（默认: output/books）",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新处理已有结果的书",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只列出待处理书目，不执行流水线",
    )
    parser.add_argument(
        "--book-concurrency",
        type=int,
        default=2,
        help="同时处理多少本书（默认: 2，建议不超过3避免API过热）",
    )
    parser.add_argument(
        "--only",
        nargs="+",
        help="只处理指定的 book_id（如 --only 繁花 湘行散记）",
    )
    parser.add_argument(
        "--resume-from",
        choices=["step2", "step3", "step3b", "step4"],
        default=None,
        help="断点续跑：从指定步骤开始重跑（step2/step3/step3b/step4）。\n"
             "不指定时自动检测 checkpoint 文件决定跳过哪些步骤。",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("GEOLORE_API_KEY", ""),
        help="API Key (或设置 GEOLORE_API_KEY 环境变量)",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("GEOLORE_BASE_URL", DEFAULT_BASE_URL),
        help="API Base URL",
    )
    args = parser.parse_args()

    if not args.api_key:
        # 尝试从 .env 文件读取
        env_file = os.path.join(_PROJECT_ROOT, ".env")
        if os.path.isfile(env_file):
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GEOLORE_API_KEY="):
                        args.api_key = line.split("=", 1)[1].strip()
                        break

    if not args.api_key:
        # 尝试从 .ai_config.json 加载
        from src.common.config import load_llm_config as _load_cfg
        fallback_config = _load_cfg()
        args.api_key = fallback_config.api_key
        if not args.base_url or args.base_url == DEFAULT_BASE_URL:
            args.base_url = fallback_config.base_url

    if not args.api_key:
        print("❌ 需要 API Key: --api-key 或环境变量 GEOLORE_API_KEY 或 .env 或 .ai_config.json")
        sys.exit(1)

    config = LLMConfig(api_key=args.api_key, base_url=args.base_url)

    # 扫描待处理书目
    # 支持绝对路径和相对路径（相对于脚本所在项目根目录）
    if os.path.isabs(args.books_dir):
        books_dir = args.books_dir
    else:
        books_dir = os.path.join(_PROJECT_ROOT, args.books_dir)
    pending = discover_pending_books(books_dir, force=args.force)

    # 过滤 --only
    if args.only:
        pending = [b for b in pending if b["book_id"] in args.only or b["title"] in args.only]

    if not pending:
        print("✅ 没有待处理的书目（所有书都已有 places_structured.json）")
        print("   如需强制重新处理，使用 --force 参数")
        return

    print(f"\n{'='*70}")
    print(f"📚 批量处理任务概览")
    print(f"{'='*70}")
    print(f"  待处理书目: {len(pending)} 本")
    print(f"  并发数: {args.book_concurrency} 本/轮")
    print(f"  输出目录: {books_dir}")
    print(f"{'='*70}")

    for i, b in enumerate(pending, 1):
        status = "⚡ 将覆盖" if b["already_done"] else "📖 待处理"
        print(f"  {i:2d}. [{status}] 《{b['title']}》— {b['author']}")
        print(f"       类型: {b['work_type']} | 时代: {b['era_setting'] or '未知'} | 地域: {b['geo_scope'] or '未知'}")
        print(f"       原文: {os.path.basename(b['txt_path'])}")

    if args.dry_run:
        print(f"\n{'='*70}")
        print(f"  [dry-run] 以上书目将被处理，但本次不实际执行。")
        print(f"{'='*70}")
        return

    print(f"\n{'='*70}")
    print(f"🚀 开始批量处理（并发: {args.book_concurrency}）...")
    print(f"  开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}")

    # 执行流水线
    total_start = time.time()
    results: List[Tuple[str, bool, Optional[str]]] = []

    if args.book_concurrency > 1:
        # 多并发：同时处理多本书（每本书内部自己的 step2 已有 6 并发）
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.book_concurrency) as pool:
            futures = {
                pool.submit(
                    process_one_book, book_info, config, books_dir,
                    getattr(args, 'resume_from', None)
                ): book_info["book_id"]
                for book_info in pending
            }
            for future in concurrent.futures.as_completed(futures):
                book_id = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as exc:
                    with _print_lock:
                        print(f"  ❌ {book_id} 出现未捕获异常: {exc}")
                    results.append((book_id, False, None))
    else:
        # 单线程逐本处理
        for book_info in pending:
            result = process_one_book(
                book_info, config, books_dir,
                resume_from=getattr(args, 'resume_from', None)
            )
            results.append(result)

    # 汇总报告
    total_elapsed = time.time() - total_start
    success = [(b, r) for b, ok, r in results if ok]
    failed = [b for b, ok, _ in results if not ok]

    print(f"\n{'='*70}")
    print(f"🎉 批量处理完成！")
    print(f"{'='*70}")
    print(f"  ✅ 成功: {len(success)} 本")
    print(f"  ❌ 失败: {len(failed)} 本")
    print(f"  ⏱️  总耗时: {total_elapsed/60:.1f} 分钟")
    print(f"  完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if success:
        print(f"\n  成功的书目：")
        for book_id, out_file in success:
            print(f"    ✅ {book_id} → {out_file}")

    if failed:
        print(f"\n  失败的书目（可单独重试）：")
        for book_id in failed:
            print(f"    ❌ {book_id}")
            print(f"       python scripts/batch_process_all_books.py --only {book_id}")

    print(f"\n  下一步：对生成的 *_places_structured.json 执行地理编码")
    print(f"    python scripts/geocode_places.py --input <file> --amap-key $AMAP_KEY")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
