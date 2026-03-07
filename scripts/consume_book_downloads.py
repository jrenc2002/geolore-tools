#!/usr/bin/env python3
"""
每日消耗书籍下载额度脚本 - Anna's Archive
使用方法: python consume_book_downloads.py
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.common.config import _load_dotenv
from src.textsource.fetcher import fetch_full_text

# 加载环境变量
_load_dotenv()

# 配置
DOWNLOAD_DIR = Path(os.getenv("ANNAS_ARCHIVE_DOWNLOAD_DIR", "~/Downloads/daily_books")).expanduser()
TARGET_DOWNLOADS = int(os.getenv("ANNAS_ARCHIVE_TARGET_DOWNLOADS", "5"))  # 先测试 5 本
DELAY_BETWEEN_DOWNLOADS = 3  # 下载间隔（秒）


def generate_book_list():
    """生成多样化的书籍列表（测试用）"""
    books = [
        # 英文经典
        {"title": "The Great Gatsby", "author": "F. Scott Fitzgerald", "language": "en"},
        {"title": "1984", "author": "George Orwell", "language": "en"},
        {"title": "Pride and Prejudice", "author": "Jane Austen", "language": "en"},
        {"title": "To Kill a Mockingbird", "author": "Harper Lee", "language": "en"},
        {"title": "The Catcher in the Rye", "author": "J.D. Salinger", "language": "en"},

        # 中文经典
        {"title": "活着", "author": "余华", "language": "zh"},
        {"title": "平凡的世界", "author": "路遥", "language": "zh"},
        {"title": "三体", "author": "刘慈欣", "language": "zh"},
        {"title": "围城", "author": "钱钟书", "language": "zh"},
        {"title": "白鹿原", "author": "陈忠实", "language": "zh"},
    ]
    return books


def init_download_dir():
    """初始化下载目录"""
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    print(f"下载目录: {DOWNLOAD_DIR}")


def save_book_text(title: str, author: str, text: str) -> bool:
    """保存书籍文本到文件"""
    try:
        # 创建安全的文件名
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_title = safe_title.replace(' ', '_')

        filename = f"{safe_title}_{author}.txt"
        filepath = DOWNLOAD_DIR / filename

        # 如果文件已存在，跳过
        if filepath.exists():
            print(f"⊙ 文件已存在，跳过: {filename}")
            return True

        # 保存文件
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text)

        file_size = filepath.stat().st_size / (1024 * 1024)  # MB
        print(f"✓ 保存成功: {filename} ({file_size:.2f} MB)")
        return True

    except Exception as e:
        print(f"✗ 保存失败: {str(e)}")
        return False


def consume_downloads():
    """消耗下载额度"""
    print(f"开始消耗书籍下载额度 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"来源: Anna's Archive")
    print(f"目标: {TARGET_DOWNLOADS} 本书籍\n")

    init_download_dir()

    success_count = 0
    error_count = 0
    books = generate_book_list()[:TARGET_DOWNLOADS]

    print("=" * 60)
    print("开始下载书籍")
    print("=" * 60)

    for i, book in enumerate(books, 1):
        try:
            title = book["title"]
            author = book["author"]
            language = book.get("language", "en")

            print(f"\n[{i}/{len(books)}] 下载: 《{title}》 - {author}")

            # 使用 fetcher 下载
            result = fetch_full_text(
                title=title,
                author=author,
                language=language,
                cache_dir=str(DOWNLOAD_DIR / ".cache"),
                use_cache=True,
            )

            if result and result.full_text:
                # 保存到文件
                if save_book_text(title, author, result.full_text):
                    success_count += 1
                else:
                    error_count += 1
            else:
                error_count += 1
                print(f"✗ 下载失败: 《{title}》")

            # 避免触发速率限制
            if i < len(books):
                time.sleep(DELAY_BETWEEN_DOWNLOADS)

        except Exception as e:
            error_count += 1
            print(f"✗ 错误: {str(e)}")
            time.sleep(DELAY_BETWEEN_DOWNLOADS * 2)

    print(f"\n{'=' * 60}")
    print(f"完成! 成功: {success_count}, 失败: {error_count}")
    print(f"下载目录: {DOWNLOAD_DIR}")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    try:
        consume_downloads()
    except KeyboardInterrupt:
        print("\n\n用户中断执行")
    except Exception as e:
        print(f"\n执行失败: {str(e)}")

