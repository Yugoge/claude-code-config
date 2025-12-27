#!/bin/bash
# 文件引用检测脚本 - 用于 /clean 命令
# 检测文件是否在项目中被引用（包括文档、代码、配置文件等）

set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 使用说明
usage() {
    cat <<EOF
用法: $0 <file-to-check> [project-root]

检测文件是否在项目中被引用

参数:
  file-to-check    要检查的文件路径（相对或绝对）
  project-root     项目根目录（默认：当前目录）

示例:
  $0 scripts/test-migration.sh
  $0 tests/test_old.py /root/my-project

输出:
  - 引用位置列表
  - Git 历史分析
  - 引用类型分类（功能性 vs 历史性）
  - 删除/归档建议

退出码:
  0 - 文件无引用（安全删除）
  1 - 文件有引用（不应删除） 或 被功能性引用（必须保留）
  2 - 仅被历史性文档引用（建议归档）
  3 - 错误
EOF
    exit 3
}

# 参数检查
if [[ $# -lt 1 ]]; then
    usage
fi

TARGET_FILE="$1"
PROJECT_ROOT="${2:-.}"

# 确保项目根目录存在
if [[ ! -d "$PROJECT_ROOT" ]]; then
    echo -e "${RED}错误: 项目目录不存在: $PROJECT_ROOT${NC}" >&2
    exit 3
fi

cd "$PROJECT_ROOT"

# 确保文件存在
if [[ ! -f "$TARGET_FILE" ]]; then
    echo -e "${RED}错误: 文件不存在: $TARGET_FILE${NC}" >&2
    exit 3
fi

# 获取文件名（用于搜索引用）
FILENAME=$(basename "$TARGET_FILE")
FILENAME_NO_EXT="${FILENAME%.*}"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📋 文件引用检测报告${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "文件: ${YELLOW}$TARGET_FILE${NC}"
echo -e "项目: ${YELLOW}$PROJECT_ROOT${NC}"
echo ""

# ============================================
# 1. Git 历史分析
# ============================================
echo -e "${BLUE}## 1. Git 历史分析${NC}"
echo ""

if git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
    # 文件创建时间
    FILE_CREATED=$(git log --diff-filter=A --follow --format=%aI -1 -- "$TARGET_FILE" 2>/dev/null || echo "未知")

    # 最后修改时间
    FILE_MODIFIED=$(git log -1 --format=%aI -- "$TARGET_FILE" 2>/dev/null || echo "未知")

    # 提交次数
    COMMIT_COUNT=$(git log --follow --oneline -- "$TARGET_FILE" 2>/dev/null | wc -l)

    # 最后提交信息
    LAST_COMMIT=$(git log -1 --format="%h - %s (%ar)" -- "$TARGET_FILE" 2>/dev/null || echo "无提交历史")

    echo -e "  创建时间: ${GREEN}$FILE_CREATED${NC}"
    echo -e "  最后修改: ${GREEN}$FILE_MODIFIED${NC}"
    echo -e "  提交次数: ${GREEN}$COMMIT_COUNT${NC}"
    echo -e "  最后提交: ${GREEN}$LAST_COMMIT${NC}"

    # 判断是否为一次性文件
    if [[ $COMMIT_COUNT -le 2 ]]; then
        echo -e "  ${YELLOW}⚠️  提交次数较少 (≤2)，可能是一次性文件${NC}"
    fi
else
    echo -e "  ${YELLOW}⚠️  不是 Git 仓库，跳过 Git 分析${NC}"
fi

echo ""

# ============================================
# 2. 文档引用检查
# ============================================
echo -e "${BLUE}## 2. 文档引用检查 (.md, .txt, README, etc.)${NC}"
echo ""

MD_REFS=$(grep -r "$FILENAME" . \
    --include="*.md" \
    --include="*.txt" \
    --include="README*" \
    --exclude-dir=.git \
    --exclude-dir=node_modules \
    --exclude-dir=venv \
    --exclude-dir=.venv \
    --exclude-dir=__pycache__ \
    --exclude-dir=.pytest_cache \
    --exclude-dir=docs/archive \
    2>/dev/null || true)

if [[ -n "$MD_REFS" ]]; then
    echo -e "  ${RED}❌ 发现文档引用:${NC}"
    echo "$MD_REFS" | while IFS= read -r line; do
        echo -e "    ${YELLOW}$line${NC}"
    done
    DOC_REF_FOUND=1
else
    echo -e "  ${GREEN}✅ 无文档引用${NC}"
    DOC_REF_FOUND=0
fi

echo ""

# ============================================
# 3. 代码引用检查
# ============================================
echo -e "${BLUE}## 3. 代码引用检查 (.py, .js, .ts, .sh, etc.)${NC}"
echo ""

CODE_REFS=$(grep -r "$FILENAME" . \
    --include="*.py" \
    --include="*.js" \
    --include="*.ts" \
    --include="*.tsx" \
    --include="*.sh" \
    --include="*.bash" \
    --include="*.go" \
    --include="*.rs" \
    --exclude-dir=.git \
    --exclude-dir=node_modules \
    --exclude-dir=venv \
    --exclude-dir=.venv \
    --exclude-dir=__pycache__ \
    --exclude-dir=.pytest_cache \
    --exclude-dir=dist \
    --exclude-dir=build \
    --exclude="$TARGET_FILE" \
    2>/dev/null || true)

if [[ -n "$CODE_REFS" ]]; then
    echo -e "  ${RED}❌ 发现代码引用:${NC}"
    echo "$CODE_REFS" | while IFS= read -r line; do
        echo -e "    ${YELLOW}$line${NC}"
    done
    CODE_REF_FOUND=1
else
    echo -e "  ${GREEN}✅ 无代码引用${NC}"
    CODE_REF_FOUND=0
fi

echo ""

# ============================================
# 4. 配置文件引用检查
# ============================================
echo -e "${BLUE}## 4. 配置文件引用检查 (settings.json, package.json, Makefile, etc.)${NC}"
echo ""

CONFIG_FILES=(
    ".claude/settings.json"
    "$HOME/.claude/settings.json"
    "package.json"
    "Makefile"
    "makefile"
    "pyproject.toml"
    "setup.py"
    "tox.ini"
    ".github/workflows/*.yml"
    ".github/workflows/*.yaml"
    ".gitlab-ci.yml"
)

CONFIG_REF_FOUND=0

for config_pattern in "${CONFIG_FILES[@]}"; do
    # 使用 find 处理通配符
    if [[ "$config_pattern" == *"*"* ]]; then
        mapfile -t found_files < <(find . -path "./$config_pattern" 2>/dev/null)
    else
        found_files=("$config_pattern")
    fi

    for config_file in "${found_files[@]}"; do
        if [[ -f "$config_file" ]]; then
            if grep -q "$FILENAME" "$config_file" 2>/dev/null; then
                echo -e "  ${RED}❌ 在 $config_file 中发现引用:${NC}"
                grep -n "$FILENAME" "$config_file" | while IFS= read -r line; do
                    echo -e "    ${YELLOW}$line${NC}"
                done
                CONFIG_REF_FOUND=1
            fi
        fi
    done
done

if [[ $CONFIG_REF_FOUND -eq 0 ]]; then
    echo -e "  ${GREEN}✅ 无配置文件引用${NC}"
fi

echo ""

# ============================================
# 5. 脚本相互引用检查（source/exec）
# ============================================
echo -e "${BLUE}## 5. 脚本相互引用检查 (source, exec, . )${NC}"
echo ""

if [[ "$FILENAME" == *.sh ]] || [[ "$FILENAME" == *.bash ]]; then
    SCRIPT_REFS=$(grep -rE "(source|\.|\bexec)\s+.*$FILENAME_NO_EXT" . \
        --include="*.sh" \
        --include="*.bash" \
        --exclude-dir=.git \
        --exclude="$TARGET_FILE" \
        2>/dev/null || true)

    if [[ -n "$SCRIPT_REFS" ]]; then
        echo -e "  ${RED}❌ 发现脚本引用:${NC}"
        echo "$SCRIPT_REFS" | while IFS= read -r line; do
            echo -e "    ${YELLOW}$line${NC}"
        done
        SCRIPT_REF_FOUND=1
    else
        echo -e "  ${GREEN}✅ 无脚本引用${NC}"
        SCRIPT_REF_FOUND=0
    fi
else
    echo -e "  ${YELLOW}⊘ 非脚本文件，跳过${NC}"
    SCRIPT_REF_FOUND=0
fi

echo ""

# ============================================
# 6. 导入引用检查（Python import, JS require/import）
# ============================================
echo -e "${BLUE}## 6. 导入引用检查 (import, require, use)${NC}"
echo ""

if [[ "$FILENAME" == *.py ]] || [[ "$FILENAME" == *.js ]] || [[ "$FILENAME" == *.ts ]]; then
    IMPORT_REFS=$(grep -rE "(import|require|use|from).*$FILENAME_NO_EXT" . \
        --include="*.py" \
        --include="*.js" \
        --include="*.ts" \
        --include="*.tsx" \
        --exclude-dir=.git \
        --exclude-dir=node_modules \
        --exclude-dir=venv \
        --exclude-dir=__pycache__ \
        --exclude="$TARGET_FILE" \
        2>/dev/null || true)

    if [[ -n "$IMPORT_REFS" ]]; then
        echo -e "  ${RED}❌ 发现导入引用:${NC}"
        echo "$IMPORT_REFS" | while IFS= read -r line; do
            echo -e "    ${YELLOW}$line${NC}"
        done
        IMPORT_REF_FOUND=1
    else
        echo -e "  ${GREEN}✅ 无导入引用${NC}"
        IMPORT_REF_FOUND=0
    fi
else
    echo -e "  ${YELLOW}⊘ 非 Python/JS/TS 文件，跳过${NC}"
    IMPORT_REF_FOUND=0
fi

echo ""

# ============================================
# 7. 文件修改时间检查
# ============================================
echo -e "${BLUE}## 7. 文件修改时间检查${NC}"
echo ""

FILE_MTIME=$(stat -c %Y "$TARGET_FILE" 2>/dev/null || stat -f %m "$TARGET_FILE" 2>/dev/null)
CURRENT_TIME=$(date +%s)
DAYS_SINCE_MODIFIED=$(( (CURRENT_TIME - FILE_MTIME) / 86400 ))

echo -e "  最后修改: ${GREEN}${DAYS_SINCE_MODIFIED} 天前${NC}"

if [[ $DAYS_SINCE_MODIFIED -lt 7 ]]; then
    echo -e "  ${YELLOW}⚠️  最近 7 天内修改过，建议谨慎删除${NC}"
    RECENT_MODIFIED=1
else
    echo -e "  ${GREEN}✅ 超过 7 天未修改${NC}"
    RECENT_MODIFIED=0
fi

echo ""

# ============================================
# 8. 引用类型分类 (功能性 vs 历史性)
# ============================================
echo -e "${BLUE}## 8. 引用类型分类${NC}"
echo ""

# 检测功能性引用 (commands, agents, scripts 中的引用)
FUNCTIONAL_REF_FOUND=0

if [[ -n "$MD_REFS" ]]; then
    # 检查是否在 .claude/commands/, .claude/agents/, scripts/ 中被引用
    FUNCTIONAL_REFS=$(echo "$MD_REFS" | grep -E "\.claude/commands/|\.claude/agents/|scripts/.*\.(sh|py)" || true)

    if [[ -n "$FUNCTIONAL_REFS" ]]; then
        echo -e "  ${RED}❌ 发现功能性引用 (commands/agents/scripts):${NC}"
        echo "$FUNCTIONAL_REFS" | while IFS= read -r line; do
            echo -e "    ${YELLOW}$line${NC}"
        done
        FUNCTIONAL_REF_FOUND=1
    fi
fi

if [[ $CODE_REF_FOUND -eq 1 ]] || [[ $CONFIG_REF_FOUND -eq 1 ]] || [[ $SCRIPT_REF_FOUND -eq 1 ]] || [[ $IMPORT_REF_FOUND -eq 1 ]]; then
    FUNCTIONAL_REF_FOUND=1
fi

if [[ $FUNCTIONAL_REF_FOUND -eq 1 ]]; then
    echo -e "  ${RED}⚠️  文件被功能性引用 (commands/agents/scripts/code)${NC}"
    echo -e "  ${RED}→ 这是功能性文档/脚本，不能删除或归档${NC}"
else
    # 检查是否仅被历史文档引用
    if [[ $DOC_REF_FOUND -eq 1 ]]; then
        # 检查是否被 docs/ 或 reports/ 或历史性 .md 文件引用
        HISTORICAL_REFS=$(echo "$MD_REFS" | grep -E "docs/|reports/|chats/|.*-report\.md|.*-summary\.md|.*-plan\.md" || true)

        if [[ -n "$HISTORICAL_REFS" ]]; then
            echo -e "  ${YELLOW}⚠️  仅被历史性文档引用 (docs/reports/chats):${NC}"
            echo "$HISTORICAL_REFS" | head -5 | while IFS= read -r line; do
                echo -e "    ${YELLOW}$line${NC}"
            done
            echo -e "  ${YELLOW}→ 这是历史性文档，可以归档${NC}"
        fi
    else
        echo -e "  ${GREEN}✅ 无任何引用${NC}"
    fi
fi

echo ""

# ============================================
# 9. 综合评估与建议
# ============================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}## 📊 综合评估${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 计算引用总数
TOTAL_REFS=$((DOC_REF_FOUND + CODE_REF_FOUND + CONFIG_REF_FOUND + SCRIPT_REF_FOUND + IMPORT_REF_FOUND))

echo -e "引用统计:"
echo -e "  - 文档引用: $([ $DOC_REF_FOUND -eq 1 ] && echo "${RED}是${NC}" || echo "${GREEN}否${NC}")"
echo -e "  - 代码引用: $([ $CODE_REF_FOUND -eq 1 ] && echo "${RED}是${NC}" || echo "${GREEN}否${NC}")"
echo -e "  - 配置引用: $([ $CONFIG_REF_FOUND -eq 1 ] && echo "${RED}是${NC}" || echo "${GREEN}否${NC}")"
echo -e "  - 脚本引用: $([ $SCRIPT_REF_FOUND -eq 1 ] && echo "${RED}是${NC}" || echo "${GREEN}否${NC}")"
echo -e "  - 导入引用: $([ $IMPORT_REF_FOUND -eq 1 ] && echo "${RED}是${NC}" || echo "${GREEN}否${NC}")"
echo -e "  - ${YELLOW}功能性引用: $([ $FUNCTIONAL_REF_FOUND -eq 1 ] && echo "${RED}是 (不能删除)${NC}" || echo "${GREEN}否${NC}")${NC}"
echo ""

# 删除建议 (考虑功能性引用)
if [[ $FUNCTIONAL_REF_FOUND -eq 1 ]]; then
    echo -e "${RED}❌ 删除建议: 不能删除${NC}"
    echo -e "   理由: 被 commands/agents/scripts 功能性引用"
    echo -e "   ${YELLOW}→ 这是功能性文档/脚本，必须保留${NC}"
    EXIT_CODE=1
elif [[ $TOTAL_REFS -eq 0 ]] && [[ $RECENT_MODIFIED -eq 0 ]]; then
    echo -e "${GREEN}✅ 删除建议: 安全删除${NC}"
    echo -e "   理由: 无任何引用，且超过 7 天未修改"
    EXIT_CODE=0
elif [[ $TOTAL_REFS -eq 0 ]] && [[ $RECENT_MODIFIED -eq 1 ]]; then
    echo -e "${YELLOW}⚠️  删除建议: 谨慎删除${NC}"
    echo -e "   理由: 无引用，但最近修改过"
    EXIT_CODE=0
elif [[ $DOC_REF_FOUND -eq 1 ]] && [[ $CODE_REF_FOUND -eq 0 ]] && [[ $CONFIG_REF_FOUND -eq 0 ]]; then
    echo -e "${YELLOW}📦 归档建议: 可以归档${NC}"
    echo -e "   理由: 仅被历史性文档引用，无功能性引用"
    echo -e "   ${YELLOW}→ 建议移动到 docs/archive/ 或相应归档目录${NC}"
    EXIT_CODE=2  # 新的退出码: 2 = 建议归档
else
    echo -e "${RED}❌ 删除建议: 不建议删除${NC}"
    echo -e "   理由: 存在引用，删除可能导致问题"
    EXIT_CODE=1
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

exit $EXIT_CODE
