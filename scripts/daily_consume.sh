#!/bin/bash
# 每日 API 消耗任务快捷启动脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# 加载环境变量
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "⚠️  警告: 未找到 .env 文件，请先配置环境变量"
    echo "请在项目根目录创建 .env 文件并配置 API 密钥"
    exit 1
fi

# 显示菜单
echo "=========================================="
echo "  故实巡礼 · 每日任务管理"
echo "=========================================="
echo ""
echo "请选择要执行的任务："
echo "  1) 消耗 Gemini API 配额"
echo "  2) 消耗 Claude API 配额"
echo "  3) 下载 Anna's Archive 书籍"
echo "  4) 运行所有任务"
echo "  0) 退出"
echo ""
read -p "请输入选项 [0-4]: " choice

case $choice in
    1)
        echo ""
        echo "🚀 开始消耗 Gemini API..."
        python3 "$SCRIPT_DIR/consume_gemini_api.py"
        ;;
    2)
        echo ""
        echo "🚀 开始消耗 Claude API..."
        python3 "$SCRIPT_DIR/consume_claude_api.py"
        ;;
    3)
        echo ""
        echo "🚀 开始下载书籍..."
        python3 "$SCRIPT_DIR/consume_book_downloads.py"
        ;;
    4)
        echo ""
        echo "🚀 开始消耗 Gemini API..."
        python3 "$SCRIPT_DIR/consume_gemini_api.py"
        echo ""
        echo "🚀 开始消耗 Claude API..."
        python3 "$SCRIPT_DIR/consume_claude_api.py"
        echo ""
        echo "🚀 开始下载书籍..."
        python3 "$SCRIPT_DIR/consume_book_downloads.py"
        ;;
    0)
        echo "退出"
        exit 0
        ;;
    *)
        echo "❌ 无效选项"
        exit 1
        ;;
esac

echo ""
echo "✅ 任务完成！"
