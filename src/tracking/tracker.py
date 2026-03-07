#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
故实巡礼 · 流水线追踪（CSV 存储）

使用 CSV 文件记录整个流水线的全生命周期：
  - AI 选题推荐 → 原文获取 → LLM 搜索 → 地点提取 → 结构化 → 审查 → 输出

文件结构（存储在同一目录下）：
  pipeline_runs.csv   — 每次流水线运行记录
  books.csv           — 每本书的选题/处理状态
  text_fetches.csv    — 原文获取尝试日志（每个源一行）
  pipeline_steps.csv  — 每个 step 的执行记录
"""

from __future__ import annotations

import csv
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


DEFAULT_TRACKING_DIR = "output/tracking"

# ─────────────────────────── CSV 列定义 ───────────────────────────

_RUNS_HEADERS = [
    "run_id", "mode", "started_at", "finished_at", "status",
    "total_books", "books_succeeded", "books_failed", "config_json",
]

_BOOKS_HEADERS = [
    "run_id", "title", "title_en", "author", "language", "book_type",
    "grade", "geo_region", "geo_scope", "era_setting",
    "place_count_est", "density_index", "reachability", "reason", "status",
    "text_source", "text_fetched", "text_is_full", "text_word_count", "text_url",
    "places_extracted", "places_final", "output_file", "error_message",
    "started_at", "finished_at", "elapsed_sec", "created_at",
]

_FETCHES_HEADERS = [
    "id", "run_id", "book_title", "source", "searched_at",
    "found", "is_full_text", "word_count", "url", "error", "response_ms",
]

_STEPS_HEADERS = [
    "id", "run_id", "book_title", "step_name", "started_at", "finished_at",
    "status", "model_used", "input_size", "output_size", "item_count", "notes", "error",
]


# ─────────────────────────── CSV 读写工具 ───────────────────────────

def _csv_path(base_dir: str, name: str) -> str:
    return os.path.join(base_dir, f"{name}.csv")


def _read_csv(path: str, headers: List[str]) -> List[Dict]:
    """读取 CSV，文件不存在返回空列表"""
    if not os.path.exists(path):
        return []
    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _write_csv(path: str, headers: List[str], rows: List[Dict]) -> None:
    """全量覆盖写入 CSV"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _append_csv(path: str, headers: List[str], row: Dict) -> None:
    """追加一行到 CSV（文件不存在则创建并写表头）"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    write_header = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(row)


# ─────────────────────────── Tracker Class ───────────────────────────


class PipelineTracker:
    """流水线追踪器 — 记录每一步到 CSV 文件"""

    def __init__(self, tracking_dir: str = DEFAULT_TRACKING_DIR):
        self._dir = os.path.abspath(tracking_dir)
        os.makedirs(self._dir, exist_ok=True)
        self._run_id: Optional[str] = None
        self._step_counter: int = 0   # 模拟自增 ID
        self._fetch_counter: int = 0

        # 从已有 CSV 中恢复计数器
        steps = _read_csv(_csv_path(self._dir, "pipeline_steps"), _STEPS_HEADERS)
        if steps:
            self._step_counter = max(int(r.get("id", 0) or 0) for r in steps)
        fetches = _read_csv(_csv_path(self._dir, "text_fetches"), _FETCHES_HEADERS)
        if fetches:
            self._fetch_counter = max(int(r.get("id", 0) or 0) for r in fetches)

    @property
    def run_id(self) -> str:
        if not self._run_id:
            raise RuntimeError("No active run. Call start_run() first.")
        return self._run_id

    def _now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    def _books_path(self) -> str:
        return _csv_path(self._dir, "books")

    def _runs_path(self) -> str:
        return _csv_path(self._dir, "pipeline_runs")

    def _fetches_path(self) -> str:
        return _csv_path(self._dir, "text_fetches")

    def _steps_path(self) -> str:
        return _csv_path(self._dir, "pipeline_steps")

    # ─── Run lifecycle ───

    def start_run(self, mode: str, config: Optional[Dict] = None) -> str:
        """开始一次流水线运行"""
        self._run_id = f"run_{int(time.time())}_{os.getpid()}"
        _append_csv(self._runs_path(), _RUNS_HEADERS, {
            "run_id": self._run_id,
            "mode": mode,
            "started_at": self._now(),
            "finished_at": "",
            "status": "running",
            "total_books": 0,
            "books_succeeded": 0,
            "books_failed": 0,
            "config_json": json.dumps(config or {}, ensure_ascii=False),
        })
        return self._run_id

    def finish_run(self, status: str = "completed") -> None:
        """结束流水线运行，更新统计"""
        books = [r for r in _read_csv(self._books_path(), _BOOKS_HEADERS)
                 if r.get("run_id") == self.run_id]
        total = len(books)
        succ = sum(1 for b in books if b.get("status") == "completed")
        fail = sum(1 for b in books if b.get("status") == "failed")

        runs = _read_csv(self._runs_path(), _RUNS_HEADERS)
        for r in runs:
            if r.get("run_id") == self.run_id:
                r["finished_at"] = self._now()
                r["status"] = status
                r["total_books"] = total
                r["books_succeeded"] = succ
                r["books_failed"] = fail
        _write_csv(self._runs_path(), _RUNS_HEADERS, runs)

    # ─── Book tracking ───

    def add_book(self, title: str, author: str = "", **kwargs) -> None:
        """记录一本推荐/指定的书"""
        _append_csv(self._books_path(), _BOOKS_HEADERS, {
            "run_id": self.run_id,
            "title": title,
            "title_en": kwargs.get("title_en", ""),
            "author": author,
            "language": kwargs.get("language", ""),
            "book_type": kwargs.get("book_type", "novel"),
            "grade": kwargs.get("grade", ""),
            "geo_region": kwargs.get("geo_region", ""),
            "geo_scope": kwargs.get("geo_scope", ""),
            "era_setting": kwargs.get("era_setting", ""),
            "place_count_est": kwargs.get("place_count_est", 0),
            "density_index": kwargs.get("density_index", 0.0),
            "reachability": kwargs.get("reachability", 0),
            "reason": kwargs.get("reason", ""),
            "status": kwargs.get("status", "recommended"),
            "text_source": "", "text_fetched": 0, "text_is_full": 0,
            "text_word_count": 0, "text_url": "",
            "places_extracted": 0, "places_final": 0,
            "output_file": "", "error_message": "",
            "started_at": "", "finished_at": "", "elapsed_sec": 0.0,
            "created_at": self._now(),
        })

    def update_book(self, title: str, **kwargs) -> None:
        """更新书籍状态（原地修改对应行）"""
        rows = _read_csv(self._books_path(), _BOOKS_HEADERS)
        for row in rows:
            if row.get("run_id") == self.run_id and row.get("title") == title:
                row.update({k: v for k, v in kwargs.items()})
                break
        _write_csv(self._books_path(), _BOOKS_HEADERS, rows)

    # ─── Text fetch tracking ───

    def log_text_fetch(
        self,
        book_title: str,
        source: str,
        found: bool,
        is_full_text: bool = False,
        word_count: int = 0,
        url: str = "",
        error: str = "",
        response_ms: int = 0,
    ) -> None:
        """记录一次原文获取尝试"""
        self._fetch_counter += 1
        _append_csv(self._fetches_path(), _FETCHES_HEADERS, {
            "id": self._fetch_counter,
            "run_id": self.run_id,
            "book_title": book_title,
            "source": source,
            "searched_at": self._now(),
            "found": 1 if found else 0,
            "is_full_text": 1 if is_full_text else 0,
            "word_count": word_count,
            "url": url,
            "error": error,
            "response_ms": response_ms,
        })

    # ─── Step tracking ───

    def start_step(self, book_title: str, step_name: str, model: str = "", input_size: int = 0) -> int:
        """记录步骤开始，返回步骤 ID"""
        self._step_counter += 1
        step_id = self._step_counter
        _append_csv(self._steps_path(), _STEPS_HEADERS, {
            "id": step_id,
            "run_id": self.run_id,
            "book_title": book_title,
            "step_name": step_name,
            "started_at": self._now(),
            "finished_at": "",
            "status": "running",
            "model_used": model,
            "input_size": input_size,
            "output_size": 0,
            "item_count": 0,
            "notes": "",
            "error": "",
        })
        return step_id

    def finish_step(
        self, step_id: int, status: str = "completed",
        output_size: int = 0, item_count: int = 0, notes: str = "", error: str = ""
    ) -> None:
        """记录步骤完成"""
        rows = _read_csv(self._steps_path(), _STEPS_HEADERS)
        for row in rows:
            if str(row.get("id")) == str(step_id):
                row["finished_at"] = self._now()
                row["status"] = status
                row["output_size"] = output_size
                row["item_count"] = item_count
                row["notes"] = notes
                row["error"] = error
                break
        _write_csv(self._steps_path(), _STEPS_HEADERS, rows)

    # ─── CSV Export（保持接口兼容，实际就是复制到指定路径）───

    def export_books_csv(self, path: str = "output/books_report.csv") -> str:
        """导出书籍追踪数据为 CSV"""
        import shutil
        src = self._books_path()
        if os.path.exists(src) and os.path.abspath(src) != os.path.abspath(path):
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            shutil.copy2(src, path)
        rows = _read_csv(src, _BOOKS_HEADERS)
        print(f"  📊 books CSV: {src} ({len(rows)} 行)")
        return src

    def export_fetches_csv(self, path: str = "output/text_fetches_report.csv") -> str:
        """导出原文获取日志为 CSV"""
        import shutil
        src = self._fetches_path()
        if os.path.exists(src) and os.path.abspath(src) != os.path.abspath(path):
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            shutil.copy2(src, path)
        rows = _read_csv(src, _FETCHES_HEADERS)
        print(f"  📊 text_fetches CSV: {src} ({len(rows)} 行)")
        return src

    def export_all_csv(self, output_dir: str = "output") -> List[str]:
        """导出所有 CSV（接口兼容，实际文件已在 output 目录下）"""
        return [
            self.export_books_csv(os.path.join(output_dir, "books_report.csv")),
            self.export_fetches_csv(os.path.join(output_dir, "text_fetches_report.csv")),
        ]

    # ─── Query helpers ───

    def get_run_summary(self, run_id: Optional[str] = None) -> Dict[str, Any]:
        """获取运行摘要"""
        rid = run_id or self.run_id
        runs = _read_csv(self._runs_path(), _RUNS_HEADERS)
        run_row = next((r for r in runs if r.get("run_id") == rid), None)
        if not run_row:
            return {}

        books = [
            {
                "title": b["title"], "author": b.get("author", ""),
                "status": b.get("status", ""), "text_source": b.get("text_source", ""),
                "text_fetched": bool(int(b.get("text_fetched", 0) or 0)),
                "places_extracted": int(b.get("places_extracted", 0) or 0),
                "places_final": int(b.get("places_final", 0) or 0),
                "elapsed_sec": float(b.get("elapsed_sec", 0) or 0),
            }
            for b in _read_csv(self._books_path(), _BOOKS_HEADERS)
            if b.get("run_id") == rid
        ]
        return {**run_row, "books": books}

    def get_all_runs(self) -> List[Dict]:
        """获取所有运行记录"""
        return _read_csv(self._runs_path(), _RUNS_HEADERS)

    def get_stats(self) -> Dict[str, Any]:
        """获取全局统计"""
        books = _read_csv(self._books_path(), _BOOKS_HEADERS)
        total_books = len(books)
        total_fetched = sum(1 for b in books if int(b.get("text_fetched", 0) or 0))
        total_full = sum(1 for b in books if int(b.get("text_is_full", 0) or 0))
        total_completed = sum(1 for b in books if b.get("status") == "completed")
        total_places = sum(int(b.get("places_final", 0) or 0) for b in books)

        fetches = _read_csv(self._fetches_path(), _FETCHES_HEADERS)
        source_map: Dict[str, Dict] = {}
        for f in fetches:
            src = f.get("source", "unknown")
            if src not in source_map:
                source_map[src] = {"attempts": 0, "hits": 0}
            source_map[src]["attempts"] += 1
            if int(f.get("found", 0) or 0):
                source_map[src]["hits"] += 1
        source_stats = {
            src: {**v, "hit_rate": f"{v['hits'] / max(v['attempts'], 1) * 100:.0f}%"}
            for src, v in source_map.items()
        }

        return {
            "total_books": total_books,
            "text_fetched": total_fetched,
            "text_full": total_full,
            "fetch_rate": f"{total_fetched / max(total_books, 1) * 100:.0f}%",
            "completed": total_completed,
            "total_places": total_places,
            "source_stats": source_stats,
        }

    def print_dashboard(self) -> None:
        """打印追踪仪表盘"""
        stats = self.get_stats()
        print(f"\n{'═'*60}")
        print(f"  📊 Geolore Pipeline 追踪仪表盘")
        print(f"{'═'*60}")
        print(f"  总书目: {stats['total_books']}")
        print(f"  原文获取: {stats['text_fetched']} ({stats['fetch_rate']})")
        print(f"  全文获取: {stats['text_full']}")
        print(f"  处理完成: {stats['completed']}")
        print(f"  总地点数: {stats['total_places']}")
        print(f"\n  数据源命中率:")
        for src, st in stats.get("source_stats", {}).items():
            print(f"    {src}: {st['hits']}/{st['attempts']} ({st['hit_rate']})")
        print(f"{'═'*60}")

    def close(self):
        pass  # CSV 无需关闭连接

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
