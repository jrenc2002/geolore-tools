#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
故实巡礼 · 文学作品原文获取模块

从 Anna's Archive 获取小说/文学作品的全文。
作为全自动流水线的「原文获取层」，位于选题之后、地点提取之前。

数据源：
  Anna's Archive Fast Download API（唯一源）
  API: /dyn/api/fast_download.json?md5=HASH&key=SECRET_KEY
  搜索: /search?q=QUERY  (HTML 解析获取 md5)

流程：
  title + author → 搜索获取 md5 → API 获取下载链接 → 下载 epub/txt → 提取纯文本 → 缓存

需要环境变量 ANNAS_ARCHIVE_KEY 或在代码中配置。
"""

from __future__ import annotations

import io
import json
import os
import re
import time
import hashlib
import urllib.request
import urllib.error
import urllib.parse
import ssl
import zipfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from html.parser import HTMLParser

try:
    import requests as _requests
    import urllib3 as _urllib3
    _urllib3.disable_warnings(_urllib3.exceptions.InsecureRequestWarning)
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


# ─────────────────────────── 配置 ───────────────────────────

ANNAS_ARCHIVE_BASE = "https://annas-archive.gl"
ANNAS_ARCHIVE_API = f"{ANNAS_ARCHIVE_BASE}/dyn/api/fast_download.json"
ANNAS_ARCHIVE_KEY = os.environ.get(
    "ANNAS_ARCHIVE_KEY", "3ZtjzCpKzfxWBi6FcDu7i25EjUQ4K"
)

DEFAULT_CACHE_DIR = "output/.text_cache"
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# FlareSolverr：自动绕过 Cloudflare JS 质询
# 启动：docker run -d --name=flaresolverr -p 8191:8191 ghcr.io/flaresolverr/flaresolverr:latest
FLARESOLVERR_URL = os.environ.get("FLARESOLVERR_URL", "http://localhost:8191/v1")


# ─────────────────────────── 数据结构 ───────────────────────────


@dataclass
class TextResult:
    """原文获取结果"""

    title: str
    author: str
    source: str  # annas_archive | cache
    language: str  # zh | en | ja | fr | ...
    full_text: str  # 原文全文
    word_count: int  # 字/词数
    url: str = ""  # 原始来源 URL
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_full_text: bool = True  # True=完整全文, False=摘要/部分
    cached: bool = False  # 是否来自缓存

    def summary(self) -> str:
        src_label = {
            "annas_archive": "📕 Anna's Archive",
            "cache": "💾 本地缓存",
        }.get(self.source, self.source)
        status = "全文" if self.is_full_text else "摘要"
        return (
            f"{src_label} | {self.language} | "
            f"{self.word_count:,} {'字' if self.language == 'zh' else 'words'} | "
            f"{status}"
        )


# ─────────────────────────── HTML 工具 ───────────────────────────


class _HTMLTextExtractor(HTMLParser):
    """简易 HTML → 纯文本转换器"""

    def __init__(self):
        super().__init__()
        self._result: List[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "sup"):
            self._skip = True
        if tag in ("br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4"):
            self._result.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "sup"):
            self._skip = False
        if tag == "p":
            self._result.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self._result.append(data)

    def get_text(self) -> str:
        raw = "".join(self._result)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def _html_to_text(html: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(html)
    return parser.get_text()


# ─────────────────────────── HTTP 工具 ───────────────────────────


def _is_cloudflare_challenge(html: str) -> bool:
    """判断是否是 Cloudflare JS 质询页（152字节的 Verifying... 页）"""
    return len(html) < 500 and "Verifying your connection" in html


def _flaresolverr_get(url: str, timeout: int = 60) -> Optional[str]:
    """通过 FlareSolverr 绕过 Cloudflare，返回真实页面 HTML"""
    import json as _json
    payload = _json.dumps({
        "cmd": "request.get",
        "url": url,
        "maxTimeout": timeout * 1000,
    }).encode()
    req = urllib.request.Request(
        FLARESOLVERR_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout + 10) as resp:
            result = _json.loads(resp.read())
            if result.get("status") == "ok":
                return result["solution"]["response"]
            print(f"     ⚠️  FlareSolverr 返回非 ok: {result.get('message', '')}")
    except Exception as e:
        print(f"     ⚠️  FlareSolverr 不可用: {e}")
    return None


def _http_get(url: str, timeout: int = 30, retries: int = 2) -> Optional[str]:
    """HTTP GET，返回文本；优先用 FlareSolverr 绕过 Cloudflare 质询"""
    # 先尝试 FlareSolverr（Anna's Archive 会拦截普通 HTTP 请求）
    result = _flaresolverr_get(url, timeout=60)
    if result and not _is_cloudflare_challenge(result):
        return result

    # FlareSolverr 不可用时，回退到普通直连（非 Anna's Archive 域名适用）
    headers = {
        "User-Agent": BROWSER_UA,
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    ctx = ssl.create_default_context()
    ctx.set_alpn_protocols(["http/1.1"])  # urllib 不支持 h2，强制 HTTP/1.1
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ctx),
        urllib.request.ProxyHandler({}),
    )

    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with opener.open(req, timeout=timeout) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            if _is_cloudflare_challenge(html):
                print(f"     ⚠️  Cloudflare 拦截，FlareSolverr 也不可用")
                return None
            return html
        except Exception as e:
            if attempt < retries:
                time.sleep(1.5 * attempt)
            else:
                print(f"     ⚠️  HTTP GET 失败: {e}")
                return None
    return None


def _http_get_json(url: str, timeout: int = 30) -> Optional[Dict]:
    """HTTP GET → JSON（通过 FlareSolverr，处理 <pre> 包裹的 JSON 响应）"""
    text = _http_get(url, timeout=timeout)
    if not text:
        return None
    # FlareSolverr 用 Chrome 渲染，JSON 响应会被包在 <pre> 标签里
    pre_m = re.search(r"<pre[^>]*>(.*?)</pre>", text, re.DOTALL)
    if pre_m:
        text = pre_m.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _http_get_bytes(
    url: str,
    timeout: int = 60,
    max_retries: int = 3,
    max_size_mb: int = 100,
) -> Optional[bytes]:
    """
    HTTP GET，返回原始字节流（下载文件用）。
    优先使用 requests（支持真正的 connect+read 双超时），
    fallback 到 urllib（urllib 的 timeout 仅对建连有效，读取会卡死）。
    """
    headers = {
        "User-Agent": BROWSER_UA,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "identity",
    }
    max_bytes = max_size_mb * 1024 * 1024
    # timeout = (connect_timeout, read_timeout)
    req_timeout = (15, timeout)

    for attempt in range(max_retries):
        try:
            if _HAS_REQUESTS:
                # requests 的 timeout 对 connect 和 read 都有效，不会卡死
                resp = _requests.get(
                    url,
                    headers=headers,
                    timeout=req_timeout,
                    stream=True,
                    proxies={},       # 不走系统代理
                    verify=False,     # CDN 直链，跳过 SSL 验证避免握手卡顿
                )
                if resp.status_code in (403, 429, 503):
                    if attempt < max_retries - 1:
                        time.sleep(3 * (attempt + 1))
                        continue
                    print(f"     ⚠️  下载失败 HTTP {resp.status_code}: {url[:80]}")
                    return None
                cl = resp.headers.get("Content-Length")
                if cl and int(cl) > max_bytes:
                    print(f"     ⚠️  文件过大 ({int(cl)/1024/1024:.0f}MB > {max_size_mb}MB)，跳过")
                    return None
                chunks: List[bytes] = []
                total = 0
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > max_bytes:
                        print(f"     ⚠️  下载超限 ({total/1024/1024:.0f}MB)，中止")
                        return None
                    chunks.append(chunk)
                return b"".join(chunks)
            else:
                # fallback: urllib（注意：read 阶段 timeout 无效，可能卡住）
                ctx = ssl.create_default_context()
                ctx.set_alpn_protocols(["http/1.1"])
                opener = urllib.request.build_opener(
                    urllib.request.HTTPSHandler(context=ctx),
                    urllib.request.ProxyHandler({}),
                )
                req = urllib.request.Request(url, headers=headers)
                with opener.open(req, timeout=timeout) as r:
                    cl = r.headers.get("Content-Length")
                    if cl and int(cl) > max_bytes:
                        print(f"     ⚠️  文件过大 ({int(cl)/1024/1024:.0f}MB > {max_size_mb}MB)，跳过")
                        return None
                    chunks2: List[bytes] = []
                    total2 = 0
                    while True:
                        chunk2 = r.read(1024 * 1024)
                        if not chunk2:
                            break
                        total2 += len(chunk2)
                        if total2 > max_bytes:
                            print(f"     ⚠️  下载超限 ({total2/1024/1024:.0f}MB)，中止")
                            return None
                        chunks2.append(chunk2)
                    return b"".join(chunks2)
        except urllib.error.HTTPError as e:
            if e.code in (403, 429, 503) and attempt < max_retries - 1:
                time.sleep(3 * (attempt + 1))
                continue
            print(f"     ⚠️  下载失败 HTTP {e.code}: {url[:80]}")
            return None
        except Exception as e:
            err_str = str(e)
            # 超时类错误直接不重试，快速失败
            if any(kw in err_str.lower() for kw in ("timed out", "timeout", "read timeout", "connection")):
                print(f"     ⚠️  下载超时（{timeout}s），跳过该链接")
                return None
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            print(f"     ⚠️  下载异常: {e}")
            return None
    return None


# ─────────────────────────── 缓存 ───────────────────────────


def _cache_key(title: str, author: str) -> str:
    raw = f"{title.strip().lower()}|{author.strip().lower()}"
    return hashlib.md5(raw.encode()).hexdigest()


def _load_from_cache(
    title: str, author: str, cache_dir: str
) -> Optional[TextResult]:
    key = _cache_key(title, author)
    meta_path = os.path.join(cache_dir, f"{key}.meta.json")
    text_path = os.path.join(cache_dir, f"{key}.txt")

    if not os.path.exists(meta_path) or not os.path.exists(text_path):
        return None

    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        with open(text_path, "r", encoding="utf-8") as f:
            text = f.read()

        return TextResult(
            title=meta.get("title", title),
            author=meta.get("author", author),
            source="cache",
            language=meta.get("language", ""),
            full_text=text,
            word_count=meta.get("word_count", len(text)),
            url=meta.get("url", ""),
            metadata=meta.get("metadata", {}),
            is_full_text=meta.get("is_full_text", True),
            cached=True,
        )
    except Exception:
        return None


def _save_to_cache(result: TextResult, cache_dir: str) -> None:
    os.makedirs(cache_dir, exist_ok=True)
    key = _cache_key(result.title, result.author)

    meta = {
        "title": result.title,
        "author": result.author,
        "source": result.source,
        "language": result.language,
        "word_count": result.word_count,
        "url": result.url,
        "metadata": result.metadata,
        "is_full_text": result.is_full_text,
    }

    meta_path = os.path.join(cache_dir, f"{key}.meta.json")
    text_path = os.path.join(cache_dir, f"{key}.txt")

    try:
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(result.full_text)
    except Exception as e:
        print(f"     ⚠️  缓存保存失败: {e}")


# ─────────────────────────── Anna's Archive 搜索 ───────────────────────────


def _search_annas_md5(
    title: str, author: str = "", language: str = ""
) -> Optional[Dict]:
    """
    搜索 Anna's Archive，返回最佳匹配的
    {md5, title, author, ext, score} 信息。
    """
    query_parts = [title]
    if author:
        query_parts.append(author)
    query = " ".join(query_parts)

    lang_filter = {
        "zh": "zh",
        "en": "en",
        "ja": "ja",
        "fr": "fr",
        "de": "de",
        "es": "es",
        "it": "it",
        "pt": "pt",
        "ru": "ru",
    }.get(language, "")

    # 优先搜 epub/txt，再搜 pdf
    for ext_filter in ["epub,txt", "pdf", ""]:
        search_url = (
            f"{ANNAS_ARCHIVE_BASE}/search"
            f"?q={urllib.parse.quote(query)}"
            f"&ext={ext_filter}"
        )
        if lang_filter:
            search_url += f"&lang={lang_filter}"

        label = ext_filter if ext_filter else "all"
        print(f"  🔍 Anna's Archive 搜索 \"{query}\" [{label}]...")

        html = _http_get(search_url, timeout=20)
        if not html:
            continue

        candidates = _parse_search_results(html)
        if not candidates:
            print(f"     未找到 {label} 结果")
            continue

        best = _score_candidates(candidates, title, author, language)
        if not best:
            print(f"     无精确匹配 ({label})")
            continue

        print(
            f"     📖 最佳: 《{best['title'][:40]}》 "
            f"ext={best['ext']} score={best['score']}"
        )
        return best

    return None


def _parse_search_results(html: str) -> List[Dict]:
    """解析 Anna's Archive 搜索结果 HTML，提取 md5、标题、作者、格式"""
    candidates: List[Dict] = []
    blocks = re.split(
        r'<div class="flex[^"]*pt-3 pb-3 border-b[^"]*">', html
    )

    for block in blocks[1:]:
        md5_m = re.search(r'href="/md5/([0-9a-f]{32})"', block)
        if not md5_m:
            continue
        md5 = md5_m.group(1)

        # 纯文本
        text = re.sub(r"<[^>]+>", " ", block)
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"&#39;", "'", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"&quot;", '"', text)

        # [lang] 前的内容就是书目元数据
        lang_m = re.search(r"\[([a-z]{2,3})\]", text)
        meta_text = text[: lang_m.start()].strip() if lang_m else text[:300]
        lang = lang_m.group(1) if lang_m else ""

        # 文件扩展名
        fn_m = re.search(
            r"(?:lgli|zlib|libgen|ia|nexusstc|magzdb)/\S+\."
            r"([a-z0-9]{2,6})\b",
            text,
            re.IGNORECASE,
        )
        ext = fn_m.group(1).lower() if fn_m else "unknown"
        if ext == "unknown":
            dot_m = re.search(r"·\s*([A-Z0-9]{2,6})\s*·\s*[\d.]", text)
            if dot_m:
                ext = dot_m.group(1).lower()

        # 书名：找最后一个 .ext 之后的内容
        ext_matches = list(
            re.finditer(
                r"\.(?:epub|pdf|txt|mobi|azw3|djvu|fb2|cbz|cbr)\s+",
                meta_text,
                re.IGNORECASE,
            )
        )
        if ext_matches:
            title_text = meta_text[ext_matches[-1].end() :].strip()
        else:
            title_text = meta_text

        # 按多空格分隔
        segs = [
            s.strip()
            for s in re.split(r"\s{2,}", title_text)
            if s.strip() and len(s.strip()) > 1
        ]
        book_title = segs[0] if segs else title_text[:80].strip()
        book_author = segs[1] if len(segs) > 1 else ""
        book_title = re.sub(r"\s+\d{4}\s*$", "", book_title).strip()

        if len(book_title) < 2:
            continue

        candidates.append(
            {
                "md5": md5,
                "title": book_title,
                "author": book_author.strip(),
                "ext": ext,
                "lang": lang,
                "raw_meta": meta_text,
                "score": 0,
            }
        )

    return candidates


def _score_candidates(
    candidates: List[Dict],
    title: str,
    author: str,
    lang_code: str,
) -> Optional[Dict]:
    """对搜索结果打分，返回最佳匹配"""
    title_lower = title.lower().strip()
    author_lower = author.lower().strip()
    ext_priority = {
        "txt": 3,
        "epub": 2,
        "pdf": 1,
        "mobi": 1,
        "azw3": 1,
        "fb2": 1,
        "djvu": 0,
    }

    # 不相关内容的关键词（降分）
    irrelevant_keywords = [
        "乐谱", "分谱", "总谱", "曲谱", "琴谱",  # 音乐乐谱
        "作曲", "编曲", "配器", "交响乐", "管弦乐",
        "score", "sheet music", "musical score",
        "教材", "习题", "试卷", "答案", "解析",  # 教辅材料
        "textbook", "workbook", "exercise",
        "词典", "字典", "辞典", "手册",  # 工具书
        "dictionary", "handbook", "manual",
    ]

    for c in candidates:
        score = 0
        c_title = c["title"].lower().strip()
        raw_meta = c.get("raw_meta", "").lower()
        ext = c["ext"]

        # 检查不相关关键词（严重降分）
        has_irrelevant = False
        for keyword in irrelevant_keywords:
            if keyword in c_title or keyword in raw_meta:
                has_irrelevant = True
                score -= 200  # 严重降分，基本排除
                break

        if has_irrelevant:
            c["score"] = score
            continue

        # 标题匹配
        if title_lower == c_title:
            score += 100
        elif title_lower in c_title:
            score += 70
        elif c_title in title_lower and len(c_title) >= 3:
            score += 50
        elif title_lower in raw_meta:
            score += 40

        # 作者匹配
        if author_lower:
            author_parts = author_lower.split()
            author_last = author_parts[-1] if author_parts else ""
            c_author = c["author"].lower()
            if author_lower in c_author or c_author in author_lower:
                score += 25
            elif author_last and len(author_last) >= 3 and author_last in raw_meta:
                score += 15

        # 语言 + 格式
        if lang_code and c.get("lang") == lang_code:
            score += 5
        score += ext_priority.get(ext, 0) * 5

        c["score"] = score

    valid = [c for c in candidates if c["score"] >= 20]
    if not valid:
        return None
    valid.sort(key=lambda x: -x["score"])
    return valid[0]


# ─────────────────────────── Anna's Archive API 下载 ───────────────────────────


def _download_via_api(md5: str) -> Optional[Tuple[bytes, str]]:
    """
    通过 Anna's Archive Fast Download API 下载文件。

    Returns:
        (file_bytes, download_url) 或 None
    """
    api_url = f"{ANNAS_ARCHIVE_API}?md5={md5}&key={ANNAS_ARCHIVE_KEY}"
    print(f"  🔑 调用 API (md5={md5[:12]}...)...")

    data = _http_get_json(api_url, timeout=20)
    if not data:
        print("     ⚠️  API 请求失败")
        return None

    download_url = data.get("download_url")
    error = data.get("error")

    if error:
        print(f"     ⚠️  API 错误: {error}")
        return None

    if not download_url:
        print("     ⚠️  API 未返回下载链接")
        return None

    # 打印配额信息
    info = data.get("account_fast_download_info", {})
    left = info.get("downloads_left", "?")
    total = info.get("downloads_per_day", "?")
    print(f"     📊 配额: {left}/{total} 次/天")

    # 下载文件（60s read timeout，使用 requests 确保不卡死）
    print(f"     ⬇️  下载: {download_url[:80]}...")
    file_bytes = _http_get_bytes(download_url, timeout=60)
    if not file_bytes:
        return None

    print(f"     ✅ 下载完成: {len(file_bytes):,} 字节")
    return file_bytes, download_url


# ─────────────────────────── 文本提取 ───────────────────────────


def _extract_text_from_epub(data: bytes) -> Optional[str]:
    """从 epub 字节流提取纯文本（epub = ZIP + XHTML）"""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()

            # 通过 content.opf 确定阅读顺序
            opf_file = next(
                (n for n in names if n.endswith(".opf")), None
            )
            ordered_items: List[str] = []

            if opf_file:
                opf_content = zf.read(opf_file).decode(
                    "utf-8", errors="replace"
                )
                spine_m = re.search(
                    r"<spine[^>]*>(.*?)</spine>", opf_content, re.DOTALL
                )
                if spine_m:
                    idrefs = re.findall(
                        r'idref="([^"]+)"', spine_m.group(1)
                    )
                    id_to_href: Dict[str, str] = {}
                    for item_m in re.finditer(
                        r'<item[^>]+id="([^"]+)"[^>]+href="([^"]+)"',
                        opf_content,
                    ):
                        id_to_href[item_m.group(1)] = item_m.group(2)
                    # href 在 id 前面的情况
                    for item_m in re.finditer(
                        r'<item[^>]+href="([^"]+)"[^>]+id="([^"]+)"',
                        opf_content,
                    ):
                        id_to_href[item_m.group(2)] = item_m.group(1)

                    base_dir = (
                        opf_file.rsplit("/", 1)[0] + "/"
                        if "/" in opf_file
                        else ""
                    )
                    for idref in idrefs:
                        href = id_to_href.get(idref, "")
                        if href:
                            if href.startswith("/"):
                                full_path = href.lstrip("/")
                            else:
                                full_path = base_dir + href
                            full_path = full_path.split("#")[0]
                            if full_path in names:
                                ordered_items.append(full_path)

            # fallback：按文件名排序
            if not ordered_items:
                ordered_items = sorted(
                    n
                    for n in names
                    if re.search(r"\.(xhtml|html|htm)$", n, re.IGNORECASE)
                )

            parts: List[str] = []
            for path in ordered_items:
                try:
                    raw = zf.read(path).decode("utf-8", errors="replace")
                    text = _html_to_text(raw)
                    if len(text.strip()) > 30:
                        parts.append(text.strip())
                except Exception:
                    continue

            return "\n\n".join(parts) if parts else None

    except (zipfile.BadZipFile, Exception) as e:
        print(f"     ⚠️  EPUB 解析失败: {e}")
        return None


def _validate_text(text: str, min_chars: int = 500) -> bool:
    """验证提取的文本是真实可读内容，而非二进制乱码。

    检查：
    1. 长度满足最小字符数
    2. 前 3000 字符中可打印字符比例 > 85%
    """
    if len(text) < min_chars:
        return False
    sample = text[:3000]
    printable = sum(
        1 for c in sample if c.isprintable() or c in "\n\r\t"
    )
    return (printable / len(sample)) > 0.85


def _extract_text_from_txt(data: bytes) -> Optional[str]:
    """从文本文件字节流提取（含可读性验证，防止 binary 乱码通过）"""
    for encoding in ("utf-8", "gb18030", "latin-1"):
        try:
            text = data.decode(encoding)
            if len(text) > 100 and _validate_text(text):
                return text
        except (UnicodeDecodeError, Exception):
            continue
    return None


def _extract_text_from_pdf(data: bytes) -> Optional[str]:
    """
    从 PDF 提取文本。
    优先使用 pdfplumber（如果安装了），否则简单正则提取。
    """
    # 尝试 pdfplumber
    try:
        import pdfplumber  # type: ignore

        with pdfplumber.open(io.BytesIO(data)) as pdf:
            parts = []
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    parts.append(t)
            if parts:
                return "\n\n".join(parts)
    except ImportError:
        pass
    except Exception:
        pass

    # fallback: 正则提取
    try:
        raw = data.decode("latin-1", errors="replace")
        parts: List[str] = []
        for block in re.finditer(r"BT(.*?)ET", raw, re.DOTALL):
            for s in re.finditer(r"\(([^)]{1,500})\)", block.group(1)):
                t = s.group(1)
                readable = re.sub(
                    r"\\[0-9]{3}|\\[nrtbf\\()]", " ", t
                )
                readable = re.sub(
                    r"[^\x20-\x7e\u4e00-\u9fff]", "", readable
                ).strip()
                if len(readable) > 3:
                    parts.append(readable)
        return " ".join(parts) if parts else None
    except Exception:
        return None


def _clean_text(text: str) -> str:
    """清理电子书文本"""
    # HTML 实体
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#\d+;", "", text)
    text = re.sub(r"&[a-z]+;", "", text)

    # 去版权页（前50行）
    lines = text.split("\n")
    clean_lines = []
    for i, line in enumerate(lines):
        if i < 50 and re.search(
            r"copyright|all rights reserved|published by|isbn|first published",
            line,
            re.IGNORECASE,
        ):
            continue
        clean_lines.append(line)

    text = "\n".join(clean_lines)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


# ─────────────────────────── 语言工具 ───────────────────────────


def _normalize_lang_code(lang: str) -> str:
    lang = lang.lower().strip()
    mapping = {
        "chinese": "zh",
        "中文": "zh",
        "chi": "zh",
        "zho": "zh",
        "english": "en",
        "英文": "en",
        "eng": "en",
        "japanese": "ja",
        "日文": "ja",
        "jpn": "ja",
        "french": "fr",
        "法文": "fr",
        "fre": "fr",
        "fra": "fr",
        "german": "de",
        "德文": "de",
        "ger": "de",
        "deu": "de",
        "spanish": "es",
        "西班牙文": "es",
        "spa": "es",
        "russian": "ru",
        "俄文": "ru",
        "rus": "ru",
        "italian": "it",
        "意大利文": "it",
        "ita": "it",
        "portuguese": "pt",
        "葡萄牙文": "pt",
        "por": "pt",
        "korean": "ko",
        "韩文": "ko",
        "kor": "ko",
        "turkish": "tr",
        "土耳其文": "tr",
        "tur": "tr",
        "arabic": "ar",
        "阿拉伯文": "ar",
        "ara": "ar",
        "greek": "el",
        "古希腊文": "grc",
        "gre": "el",
    }
    return mapping.get(lang, lang[:2] if len(lang) >= 2 else lang)


def _detect_language_from_title(title: str) -> str:
    cjk = sum(1 for c in title if "\u4e00" <= c <= "\u9fff")
    jpn = sum(1 for c in title if "\u3040" <= c <= "\u30ff")
    total = max(len(title), 1)
    if cjk / total > 0.3:
        return "zh"
    if jpn / total > 0.2:
        return "ja"
    return "en"


# ─────────────────────────── 主入口 ───────────────────────────


def fetch_full_text(
    title: str,
    author: str = "",
    language: str = "",
    cache_dir: str = DEFAULT_CACHE_DIR,
    use_cache: bool = True,
    sources: Optional[List[str]] = None,
    min_length: int = 1000,
) -> Optional[TextResult]:
    """
    从 Anna's Archive 获取作品全文。

    Args:
        title: 作品名称
        author: 作者名（可选）
        language: 语言代码（zh/en/ja/fr...），空则自动检测
        cache_dir: 缓存目录
        use_cache: 是否使用缓存
        sources: 忽略（保留参数兼容性）
        min_length: 有效结果的最小字符数

    Returns:
        TextResult 或 None
    """
    if not language:
        language = _detect_language_from_title(title)
    lang_code = _normalize_lang_code(language)

    print(f"\n  {'─' * 50}")
    print(f"  📚 原文获取: 《{title}》{author} [{lang_code}]")
    print(f"  {'─' * 50}")

    # ① 检查缓存
    if use_cache:
        cached = _load_from_cache(title, author, cache_dir)
        if cached and len(cached.full_text) >= min_length and cached.is_full_text:
            print(f"  💾 缓存命中: {cached.summary()}")
            return cached

    # ② 搜索 Anna's Archive 获取 md5
    match = _search_annas_md5(title, author, lang_code)
    if not match:
        print(f"\n  ❌ Anna's Archive 未找到 《{title}》")
        return None

    md5 = match["md5"]
    ext = match["ext"]

    # ③ 调用 API 下载
    dl_result = _download_via_api(md5)
    if not dl_result:
        print(f"\n  ❌ 下载失败: 《{title}》")
        return None

    file_bytes, download_url = dl_result

    # ④ 根据格式提取文本
    # 先通过 magic bytes 修正 ext，避免 Anna's Archive 返回 ext 与实际文件类型不符
    actual_ext = ext
    if file_bytes[:4] == b"PK\x03\x04":  # ZIP magic → epub/mobi/etc.
        if ext not in ("epub", "zip"):
            print(f"     ℹ️  文件头为 ZIP，修正 ext: {ext!r} → 'epub'")
            actual_ext = "epub"
    elif file_bytes[:4] == b"%PDF":  # PDF magic
        if ext != "pdf":
            print(f"     ℹ️  文件头为 PDF，修正 ext: {ext!r} → 'pdf'")
            actual_ext = "pdf"

    full_text = None
    if actual_ext == "epub":
        full_text = _extract_text_from_epub(file_bytes)
    elif actual_ext == "txt":
        full_text = _extract_text_from_txt(file_bytes)
    elif actual_ext == "pdf":
        full_text = _extract_text_from_pdf(file_bytes)
    else:
        # 未知格式：先试 epub，再试 txt
        if file_bytes[:4] == b"PK\x03\x04":
            full_text = _extract_text_from_epub(file_bytes)
        if not full_text:
            full_text = _extract_text_from_txt(file_bytes)

    # 统一验证：确保提取到的是真实可读文本，而非 binary 乱码
    if full_text and not _validate_text(full_text, min_chars=min_length):
        print(
            f"  ⚠️  文本验证失败（可读字符比例过低），丢弃 "
            f"({actual_ext}, {len(full_text):,} 字符）"
        )
        full_text = None

    if not full_text or len(full_text) < min_length:
        print(
            f"  ⚠️  文本提取失败或内容过短 "
            f"({actual_ext}, {len(full_text or '')} 字符)"
        )
        return None

    # ⑤ 清理
    full_text = _clean_text(full_text)
    word_count = (
        len(full_text) if lang_code == "zh" else len(full_text.split())
    )

    result = TextResult(
        title=title,
        author=author,
        source="annas_archive",
        language=lang_code,
        full_text=full_text,
        word_count=word_count,
        url=f"{ANNAS_ARCHIVE_BASE}/md5/{md5}",
        metadata={
            "md5": md5,
            "ext": ext,
            "annas_title": match.get("title", ""),
        },
        is_full_text=True,
    )

    # ⑥ 缓存
    if use_cache:
        _save_to_cache(result, cache_dir)

    print(f"\n  ✅ 最终结果: {result.summary()}")
    return result


def fetch_full_text_batch(
    works: List[Dict[str, str]],
    cache_dir: str = DEFAULT_CACHE_DIR,
    delay: float = 2.0,
) -> List[Optional[TextResult]]:
    """
    批量获取多部作品的原文。

    Args:
        works: 作品列表，每个元素含 title, author, language(可选)
        cache_dir: 缓存目录
        delay: 每部作品间的延迟（秒）
    """
    results: List[Optional[TextResult]] = []

    for i, work in enumerate(works):
        title = work.get("title", "")
        author = work.get("author", "")
        language = work.get("language", "")

        print(f"\n{'━' * 60}")
        print(f"  [{i + 1}/{len(works)}] 《{title}》— {author}")
        print(f"{'━' * 60}")

        result = fetch_full_text(
            title=title,
            author=author,
            language=language,
            cache_dir=cache_dir,
        )
        results.append(result)

        if i < len(works) - 1:
            time.sleep(delay)

    found = sum(1 for r in results if r)
    full = sum(1 for r in results if r and r.is_full_text)
    print(f"\n  📊 批量获取完成: {found}/{len(works)} 找到 ({full} 全文)")

    return results
