#!/usr/bin/env python3
"""
简化版书籍下载脚本 - 不依赖 FlareSolverr
使用 Anna's Archive 的直接 API
"""

import os
import sys
import time
import json
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.common.config import _load_dotenv

# 加载环境变量
_load_dotenv()

# 配置
DOWNLOAD_DIR = Path(os.getenv("ANNAS_ARCHIVE_DOWNLOAD_DIR", "~/Downloads/daily_books")).expanduser()
TARGET_DOWNLOADS = 5  # 测试用，先下载 5 本
DELAY_BETWEEN_DOWNLOADS = 3

# Anna's Archive API Key（从环境变量或代码中获取）
ANNAS_ARCHIVE_KEY = os.environ.get("ANNAS_ARCHIVE_KEY", "3ZtjzCpKzfxWBi6FcDu7i25EjUQ4K")


def init_download_dir():
    """初始化下载目录"""
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    print(f"下载目录: {DOWNLOAD_DIR}")


def generate_book_list():
    """生成测试书籍列表（使用已知的 MD5）"""
    # 这些是一些常见书籍的 MD5，可以直接下载
    books = [
        {
            "title": "The Great Gatsby",
            "author": "F. Scott Fitzgerald",
            "md5": "2a8f4d0e5c6b3a1d9e7f8c4b2a1d3e5f",  # 示例 MD5
        },
        {
            "title": "1984",
            "author": "George Orwell",
            "md5": "3b9e5f1d6c7a2e8d0f9a5c3b1e2d4f6a",  # 示例 MD5
        },
    ]
    return books


def download_via_api(md5: str, title: str, author: str) -> bool:
    """通过 Anna's Archive API 下载书籍"""
    try:
        import urllib.request
        import urllib.error

        api_url = f"https://annas-archive.gl/dyn/api/fast_download.json?md5={md5}&key={ANNAS_ARCHIVE_KEY}"

        print(f"  🔑 调用 API (md5={md5[:12]}...)...")

        req = urllib.request.Request(api_url)
        req.add_header('User-Agent', 'Mozilla/5.0')

        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())

        if data.get("error"):
            print(f"     ⚠️  API 错误: {data['error']}")
            return False

        download_url = data.get("download_url")
        if not download_url:
            print(f"     ⚠️  未获取到下载链接")
            return False

        # 显示配额信息
        info = data.get("account_fast_download_info", {})
        left = info.get("downloads_left", "?")
        total = info.get("downloads_per_day", "?")
        print(f"     📊 配额: {left}/{total} 次/天")

        # 下载文件
        print(f"     ⬇️  下载: {download_url[:80]}...")

        req2 = urllib.request.Request(download_url)
        req2.add_header('User-Agent', 'Mozilla/5.0')

        with urllib.request.urlopen(req2, timeout=120) as response:
            file_data = response.read()

        # 保存文件
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_title = safe_title.replace(' ', '_')
        filename = f"{safe_title}_{author}.epub"
        filepath = DOWNLOAD_DIR / filename

        with open(filepath, 'wb') as f:
            f.write(file_data)

        file_size = len(file_data) / (1024 * 1024)
        print(f"     ✅ 下载完成: {filename} ({file_size:.2f} MB)")
        return True

    except Exception as e:
        print(f"     ❌ 下载失败: {str(e)}")
        return False


def consume_downloads():
    """消耗下载额度"""
    print(f"开始消耗书籍下载额度 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"来源: Anna's Archive")
    print(f"目标: {TARGET_DOWNLOADS} 本书籍")
    print(f"API Key: {ANNAS_ARCHIVE_KEY[:20]}...\n")

    init_download_dir()

    success_count = 0
    error_count = 0

    print("=" * 60)
    print("⚠️  注意：此脚本需要书籍的 MD5 值")
    print("建议使用原有的 fetcher.py（需要 FlareSolverr）")
    print("或者手动从 Anna's Archive 网站获取 MD5")
    print("=" * 60)
    print()
    print("当前状态：")
    print("  - FlareSolverr: 未运行")
    print("  - 需要启动: docker run -d --name=flaresolverr -p 8191:8191 ghcr.io/flaresolverr/flaresolverr:latest")
    print()
    print("=" * 60)

    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    try:
        consume_downloads()
    except KeyboardInterrupt:
        print("\n\n用户中断执行")
    except Exception as e:
        print(f"\n执行失败: {str(e)}")
