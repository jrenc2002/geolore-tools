#!/usr/bin/env zsh
# ─────────────────────────────────────────────────
# 故实巡礼 · 快速下载脚本
# 一键下载所有待下载书籍，直到配额用完
# ─────────────────────────────────────────────────

cd "$(dirname "$0")/.."

echo "📚 开始自动下载..."
echo ""

/Users/jrenc/.pyenv/versions/3.11.5/bin/python -u scripts/daily_book_harvest.py --download-only

echo ""
echo "✅ 下载完成！"
