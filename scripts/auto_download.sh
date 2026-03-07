#!/usr/bin/env zsh
# ─────────────────────────────────────────────────
# 故实巡礼 · 自动下载脚本
# 持续下载书籍直到 API 配额耗尽或队列为空
#
# 用法：
#   ./auto_download.sh                    # 下载直到配额用完
#   ./auto_download.sh --min-quota 5      # 保留 5 次配额
#   ./auto_download.sh --max-rounds 3     # 最多运行 3 轮
# ─────────────────────────────────────────────────

TOOLS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="/Users/jrenc/.pyenv/versions/3.11.5/bin/python"
SCRIPT="$TOOLS_DIR/scripts/daily_book_harvest.py"

# 默认参数
MIN_QUOTA=0
MAX_ROUNDS=999
DELAY=3

# 解析参数
while [[ $# -gt 0 ]]; do
  case $1 in
    --min-quota)
      MIN_QUOTA="$2"
      shift 2
      ;;
    --max-rounds)
      MAX_ROUNDS="$2"
      shift 2
      ;;
    --delay)
      DELAY="$2"
      shift 2
      ;;
    *)
      echo "未知参数: $1"
      echo "用法: $0 [--min-quota N] [--max-rounds N] [--delay N]"
      exit 1
      ;;
  esac
done

echo "════════════════════════════════════════════════════════════"
echo "📚 故实巡礼 · 自动下载脚本"
echo "════════════════════════════════════════════════════════════"
echo "  最小保留配额: $MIN_QUOTA 次"
echo "  最大运行轮数: $MAX_ROUNDS 轮"
echo "  轮次间延迟: $DELAY 秒"
echo "════════════════════════════════════════════════════════════"
echo ""

cd "$TOOLS_DIR"

round=1
total_success=0
total_failed=0

while [[ $round -le $MAX_ROUNDS ]]; do
  echo ""
  echo "────────────────────────────────────────────────────────────"
  echo "🔄 第 $round 轮下载"
  echo "────────────────────────────────────────────────────────────"

  # 运行下载脚本
  output=$("$PYTHON" -u "$SCRIPT" --download-only 2>&1)
  exit_code=$?

  echo "$output"

  # 检查是否有下载成功
  success_count=$(echo "$output" | grep "✅ 成功下载:" | sed 's/.*✅ 成功下载: \([0-9]*\) 本.*/\1/')
  failed_count=$(echo "$output" | grep "❌ 下载失败:" | sed 's/.*❌ 下载失败: \([0-9]*\) 本.*/\1/')

  if [[ -n "$success_count" ]]; then
    total_success=$((total_success + success_count))
  fi

  if [[ -n "$failed_count" ]]; then
    total_failed=$((total_failed + failed_count))
  fi

  # 提取配额信息（从最后一次 API 调用）
  quota_left=$(echo "$output" | grep "📊 配额:" | tail -1 | sed 's/.*📊 配额: \([0-9]*\)\/[0-9]* 次\/天.*/\1/')

  if [[ -n "$quota_left" ]]; then
    echo ""
    echo "📊 当前剩余配额: $quota_left 次"

    # 检查是否达到最小配额
    if [[ $quota_left -le $MIN_QUOTA ]]; then
      echo ""
      echo "⚠️  配额已达到最小保留值 ($MIN_QUOTA)，停止下载"
      break
    fi
  fi

  # 检查是否还有待下载书籍
  if echo "$output" | grep -q "待下载队列.*共 0 本"; then
    echo ""
    echo "✅ 所有书籍已下载完成！"
    break
  fi

  # 检查是否本轮没有成功下载任何书籍
  if [[ "$success_count" == "0" ]] && [[ "$failed_count" != "0" ]]; then
    echo ""
    echo "⚠️  本轮全部失败，可能是网络问题，停止下载"
    break
  fi

  round=$((round + 1))

  # 如果还有下一轮，延迟一下
  if [[ $round -le $MAX_ROUNDS ]]; then
    echo ""
    echo "⏳ 等待 $DELAY 秒后继续..."
    sleep $DELAY
  fi
done

echo ""
echo "════════════════════════════════════════════════════════════"
echo "🎉 自动下载完成！"
echo "════════════════════════════════════════════════════════════"
echo "  运行轮数: $((round - 1)) 轮"
echo "  总计成功: $total_success 本"
echo "  总计失败: $total_failed 本"
if [[ -n "$quota_left" ]]; then
  echo "  剩余配额: $quota_left 次"
fi
echo "════════════════════════════════════════════════════════════"
