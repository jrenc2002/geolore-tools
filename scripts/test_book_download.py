#!/usr/bin/env python3
"""
测试书籍下载功能
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.textsource.fetcher import fetch_full_text

def test_download():
    """测试下载单本书"""
    print("=" * 60)
    print("测试 Anna's Archive 书籍下载")
    print("=" * 60)

    # 测试一本简单的英文书
    result = fetch_full_text(
        title="The Great Gatsby",
        author="F. Scott Fitzgerald",
        language="en",
        cache_dir="output/.text_cache",
        use_cache=True,
    )

    if result:
        print(f"\n✅ 下载成功!")
        print(f"   标题: {result.title}")
        print(f"   作者: {result.author}")
        print(f"   语言: {result.language}")
        print(f"   字数: {result.word_count:,}")
        print(f"   来源: {result.source}")
        print(f"   文本长度: {len(result.full_text):,} 字符")
        print(f"   前100字: {result.full_text[:100]}...")
        return True
    else:
        print("\n❌ 下载失败")
        return False

if __name__ == "__main__":
    try:
        success = test_download()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
