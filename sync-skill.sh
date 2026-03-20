#!/usr/bin/env bash
# ============================================================
# 同步脚本 — 将 GitHub 仓库的 SKILL.md 同步到 Hermes skills 目录
# 用法: bash sync-skill.sh
#
# 建议配合 git post-push hook 使用（见下方注释）
# ============================================================

set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_NAME="weekly-fund-report"
TARGET_DIR="$HOME/.hermes/skills/$SKILL_NAME"

echo "📦 同步 SKILL.md → $TARGET_DIR"

mkdir -p "$TARGET_DIR"

# 同步 SKILL.md
cp "$REPO_DIR/SKILL.md" "$TARGET_DIR/SKILL.md"

# 同步配置模板（脱敏版本）
mkdir -p "$TARGET_DIR/references"
cp "$REPO_DIR/README.md" "$TARGET_DIR/README.md"
cp "$REPO_DIR/requirements.txt" "$TARGET_DIR/requirements.txt"

echo "✅ 同步完成: $TARGET_DIR"
echo "   - SKILL.md"
echo "   - README.md"
echo "   - requirements.txt"

# ============================================================
# 可选：自动设置为 git post-push hook
# 运行一次即可（会创建 .git/hooks/post-push）：
#
#   cat >> "$(dirname "$0")/.git/hooks/post-push" << 'EOF'
#   #!/usr/bin/env bash
#   bash "$(dirname "$0")/../../sync-skill.sh"
#   EOF
#   chmod +x "$(dirname "$0")/.git/hooks/post-push"
#
# 之后每次 `git push` 会自动执行此脚本
# ============================================================
