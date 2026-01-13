#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据清洗器 - 使用 LLM 批量凝练 synopsis

输入: JSON 数组 [{title, address, story: [...]}]
输出: JSON 数组 [{title, address, synopsis}]

特点:
- 批量处理，减少 API 调用次数
- 支持断点续传 (--resume)
- 并发请求，提高效率
- 自动重试失败的批次

使用示例:
  python cleaner.py \\
    --input merged.json \\
    --output cleaned.json \\
    --system-file prompts/cleaning.md \\
    --api-key YOUR_KEY

环境变量:
  OPENAI_API_KEY: API 密钥
  OPENAI_BASE_URL: API 基础 URL (默认 https://api.openai.com/v1)
  OPENAI_MODEL: 模型名称 (默认 gpt-4o-mini)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


def read_text(path: str) -> str:
    """读取文本文件"""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def read_json(path: str) -> Any:
    """读取 JSON 文件"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dir(path: str) -> None:
    """确保目录存在"""
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def chunk_list(items: List[Any], size: int) -> List[List[Any]]:
    """将列表分成固定大小的批次"""
    return [items[i:i + size] for i in range(0, len(items), size)]


@dataclass
class APIConfig:
    """API 配置"""
    base_url: str
    api_key: str
    model: str
    timeout: float


class RateLimiter:
    """简单的速率限制器"""
    
    def __init__(self, rps: Optional[float]):
        self.enabled = bool(rps) and rps > 0
        self.interval = 1.0 / rps if self.enabled else 0.0
        self._last = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        if not self.enabled:
            return
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            if elapsed < self.interval:
                await asyncio.sleep(self.interval - elapsed)
            self._last = time.monotonic()


def strip_code_fences(s: str) -> str:
    """移除 Markdown 代码块标记"""
    s = s.strip()
    if s.startswith("```"):
        lines = s.splitlines()
        if len(lines) >= 2 and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
    return s


def extract_json_array(s: str) -> Optional[str]:
    """从文本中提取 JSON 数组"""
    s = strip_code_fences(s)
    first = s.find("[")
    last = s.rfind("]")
    
    if first == -1 or last == -1 or last <= first:
        return None
        
    candidate = s[first:last + 1]
    try:
        json.loads(candidate)
        return candidate
    except json.JSONDecodeError:
        pass
        
    # 尝试逐字符匹配
    depth = 0
    start = -1
    for i, ch in enumerate(s):
        if ch == "[":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0 and start != -1:
                segment = s[start:i + 1]
                try:
                    json.loads(segment)
                    return segment
                except json.JSONDecodeError:
                    continue
    return None


def sanitize_items(obj: Any) -> List[Dict[str, Any]]:
    """验证和清理输出项"""
    if not isinstance(obj, list):
        return []
        
    cleaned: List[Dict[str, Any]] = []
    for item in obj:
        if not isinstance(item, dict):
            continue
            
        title = item.get("title")
        address = item.get("address")
        synopsis = item.get("synopsis")
        
        if not all(isinstance(x, str) for x in [title, address, synopsis]):
            continue
            
        title = title.strip()
        address = address.strip()
        synopsis = synopsis.strip()
        
        if title and address and synopsis:
            cleaned.append({
                "title": title,
                "address": address,
                "synopsis": synopsis
            })
            
    return cleaned


def parse_output(text: str) -> List[Dict[str, Any]]:
    """解析模型输出"""
    arr_text = extract_json_array(text)
    if arr_text:
        try:
            return sanitize_items(json.loads(arr_text))
        except json.JSONDecodeError:
            pass
    try:
        return sanitize_items(json.loads(strip_code_fences(text)))
    except json.JSONDecodeError:
        return []


def append_jsonl(path: str, obj: Dict[str, Any]) -> None:
    """追加一行到 JSONL 文件"""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def load_done_batches(path: str) -> set:
    """加载已完成的批次索引"""
    done = set()
    if not os.path.exists(path):
        return done
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    bi = obj.get("batchIndex")
                    if isinstance(bi, int):
                        done.add(bi)
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    return done


async def call_api(
    session, 
    config: APIConfig, 
    messages: List[Dict[str, Any]]
) -> str:
    """调用 OpenAI 兼容 API"""
    url = config.base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.model,
        "messages": messages,
        "temperature": 0,
    }
    
    async with session.post(url, headers=headers, json=payload) as resp:
        body = await resp.text()
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status}: {body[:400]}")
        try:
            data = json.loads(body)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON: {e}")
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        return str(msg.get("content") or choice.get("text") or "")


async def run_batches(
    config: APIConfig,
    system_prompt: str,
    items: List[Dict[str, Any]],
    batch_size: int,
    batch_jsonl: str,
    output_json: str,
    max_concurrency: int,
    retries: int,
    rate_limit: Optional[float],
    resume: bool,
    quiet: bool,
) -> None:
    """运行批量清洗"""
    ensure_dir(batch_jsonl)
    ensure_dir(output_json)

    batches = chunk_list(items, batch_size)
    total = len(batches)
    done = load_done_batches(batch_jsonl) if resume else set()

    sem = asyncio.Semaphore(max_concurrency)
    limiter = RateLimiter(rate_limit)
    write_lock = asyncio.Lock()

    import aiohttp
    timeout = aiohttp.ClientTimeout(total=config.timeout)

    def log(msg: str) -> None:
        if not quiet:
            ts = time.strftime("%H:%M:%S")
            print(f"[{ts}] {msg}", flush=True)

    async def append_safe(path: str, obj: Dict[str, Any]) -> None:
        async with write_lock:
            append_jsonl(path, obj)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async def worker(batch_idx: int, batch_items: List[Dict[str, Any]]) -> None:
            if resume and batch_idx in done:
                log(f"SKIP batch {batch_idx + 1}/{total} (已完成)")
                return

            tag = f"batch_{batch_idx + 1:04d}"
            
            for attempt in range(1, retries + 1):
                try:
                    async with sem:
                        await limiter.wait()
                        log(f"→ {tag} size={len(batch_items)} attempt {attempt}/{retries}")
                        
                        messages = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": json.dumps(batch_items, ensure_ascii=False)},
                        ]
                        
                        content = await call_api(session, config, messages)
                        arr = parse_output(content)
                        
                        await append_safe(batch_jsonl, {
                            "batchIndex": batch_idx,
                            "inputCount": len(batch_items),
                            "output": arr
                        })
                        
                        log(f"✓ {tag} output={len(arr)}")
                    return
                    
                except Exception as e:
                    if attempt >= retries:
                        await append_safe(batch_jsonl + ".errors.jsonl", {
                            "batchIndex": batch_idx,
                            "error": str(e)
                        })
                        log(f"✗ {tag} 失败: {str(e)[:200]}")
                        return
                    backoff = 2 ** (attempt - 1)
                    log(f"! {tag} 重试 in {backoff}s: {str(e)[:200]}")
                    await asyncio.sleep(backoff)

        await asyncio.gather(*(
            worker(i, b) for i, b in enumerate(batches)
        ))

    # 聚合结果
    results_by_batch: Dict[int, List[Dict[str, Any]]] = {}
    for line in open(batch_jsonl, "r", encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            bi = obj.get("batchIndex")
            out = obj.get("output")
            if isinstance(bi, int) and isinstance(out, list):
                results_by_batch[bi] = sanitize_items(out)
        except json.JSONDecodeError:
            continue

    merged: List[Dict[str, Any]] = []
    for i in range(total):
        batch_items = results_by_batch.get(i)
        if batch_items:
            merged.extend(batch_items)

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"✓ 清洗完成: {output_json} ({len(merged)} 条记录)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="使用 LLM 批量清洗数据，凝练 synopsis"
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("OPENAI_API_KEY", "")
    )
    parser.add_argument(
        "--system-file",
        required=True,
        help="系统提示词文件路径 (如 prompts/cleaning.md)"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="输入 JSON 文件路径 (合并后的数据)"
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="输出 JSON 文件路径 (清洗后的数据)"
    )
    parser.add_argument(
        "--batch-jsonl",
        required=True,
        help="批次结果 JSONL 文件路径 (用于断点续传)"
    )
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--max-concurrency", type=int, default=8)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--rate-limit", type=float, default=None)
    parser.add_argument("--resume", action="store_true", help="从上次中断处继续")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if not args.api_key:
        raise SystemExit("错误: 需要 API key (--api-key 或环境变量 OPENAI_API_KEY)")
    if not os.path.exists(args.system_file):
        raise SystemExit(f"错误: 系统提示词文件不存在: {args.system_file}")
    if not os.path.exists(args.input):
        raise SystemExit(f"错误: 输入文件不存在: {args.input}")

    system_prompt = read_text(args.system_file)
    items = read_json(args.input)
    
    if not isinstance(items, list):
        raise SystemExit("错误: 输入 JSON 必须是数组")

    config = APIConfig(
        base_url=args.base_url,
        api_key=args.api_key,
        model=args.model,
        timeout=args.timeout,
    )

    print(f"API: {config.base_url}")
    print(f"模型: {config.model}")
    print(f"输入: {args.input} ({len(items)} 条)")
    print(f"批次大小: {args.batch_size}")
    print(f"并发数: {args.max_concurrency}")

    asyncio.run(run_batches(
        config=config,
        system_prompt=system_prompt,
        items=items,
        batch_size=args.batch_size,
        batch_jsonl=args.batch_jsonl,
        output_json=args.output,
        max_concurrency=args.max_concurrency,
        retries=args.retries,
        rate_limit=args.rate_limit,
        resume=args.resume,
        quiet=args.quiet,
    ))


if __name__ == "__main__":
    main()
