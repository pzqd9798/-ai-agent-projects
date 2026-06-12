#!/usr/bin/env bash
# Release Note 质量验证脚本
# 用法: bash verify-checklist.sh <release-note-file>
# 退出码: 0 = 通过, 非 0 = 存在不合格项

set -euo pipefail

RELEASE_NOTE="${1:-release-notes.md}"

if [ ! -f "$RELEASE_NOTE" ]; then
  echo "❌ 文件不存在: $RELEASE_NOTE"
  exit 1
fi

CONTENT=$(cat "$RELEASE_NOTE")
PASS=0
FAIL=0

check() {
  local label="$1"
  local pattern="$2"
  if echo "$CONTENT" | grep -qE "$pattern"; then
    echo "  ✅ $label"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $label — 未通过"
    FAIL=$((FAIL + 1))
  fi
}

echo "📋 验证 Release Note: $RELEASE_NOTE"
echo ""

# 1. 版本号
check "包含版本号 (X.Y.Z 或 vX.Y.Z)" 'v?[0-9]+\.[0-9]+\.[0-9]+'

# 2. 日期
check "包含日期 (YYYY-MM-DD)" '[0-9]{4}-[0-9]{2}-[0-9]{2}'

# 3. Features 分类
check "包含 Features / 新功能 分类" '(Features|新功能|feat)'

# 4. Bug Fixes 分类
check "包含 Bug Fixes / 修复 分类" '(Bug Fixes|Bug 修复|修复)'

# 5. Breaking Changes 标记（如果有则必须有醒目格式）
if echo "$CONTENT" | grep -qE 'BREAKING|breaking|破坏性'; then
  check "Breaking Changes 有醒目标记 (⚠️ 或 粗体)" '(⚠️|\*\*)'
fi

# 6. 非空内容
check "内容非空（超过 50 字符）" '.{50,}'

# 7. Markdown 标题
check "至少有一个 H1 或 H2 标题" '^#{1,2} '

# 8. 贡献者列表（至少所有分类后有分隔和署名区）
check "包含贡献者或 --- 分隔线" '(Contributors|贡献者|---)'

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━"
echo "结果: $PASS 通过, $FAIL 未通过"

if [ "$FAIL" -gt 0 ]; then
  echo ""
  echo "🔧 修复建议："
  echo "  - 确保版本号格式为 X.Y.Z"
  echo "  - 确保日期格式为 YYYY-MM-DD"
  echo "  - 确保有 Features 和 Bug Fixes 分类"
  echo "  - 确保 Breaking Changes 有 ⚠️ 标记"
  echo "  - 确保内容足够详细（> 50 字符）"
  exit 1
fi

echo "✅ 所有检查通过！"
exit 0
