#!/bin/bash

# Project Tools Installer
# This script installs all project tools, hooks, and configurations

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}         PROJECT TOOLS INSTALLER                 ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}Error: Not in a git repository!${NC}"
    exit 1
fi

PROJECT_ROOT=$(git rev-parse --show-toplevel)
TOOLS_DIR="$PROJECT_ROOT/.project-tools"
GIT_DIR=$(git rev-parse --git-dir)
HOOKS_DIR="$GIT_DIR/hooks"

# 1. Install Git Hooks
echo -e "\n${YELLOW}1. Installing Git Hooks...${NC}"
for hook in "$TOOLS_DIR"/hooks/*; do
    if [ -f "$hook" ]; then
        hook_name=$(basename "$hook")
        target="$HOOKS_DIR/$hook_name"
        
        # Backup existing hook
        if [ -f "$target" ] && [ ! -f "$target.backup" ]; then
            echo -e "  Backing up existing $hook_name..."
            mv "$target" "$target.backup"
        fi
        
        cp "$hook" "$target"
        chmod +x "$target"
        echo -e "  ${GREEN}✅ Installed $hook_name${NC}"
    fi
done

# 2. Install Configuration Files
echo -e "\n${YELLOW}2. Installing Configuration Files...${NC}"
for config in "$TOOLS_DIR"/configs/*; do
    if [ -f "$config" ]; then
        config_name=$(basename "$config")
        
        # Skip workflow config
        if [[ "$config_name" == "workflow-config.env" ]]; then
            continue
        fi
        
        cp "$config" "$PROJECT_ROOT/$config_name"
        echo -e "  ${GREEN}✅ Installed $config_name${NC}"
    fi
done

# 3. Create .claude directory and copy rules
echo -e "\n${YELLOW}3. Setting up .claude directory...${NC}"
mkdir -p "$PROJECT_ROOT/.claude"

for rule in "$TOOLS_DIR"/rules/*; do
    if [ -f "$rule" ]; then
        rule_name=$(basename "$rule")
        cp "$rule" "$PROJECT_ROOT/.claude/$rule_name"
        echo -e "  ${GREEN}✅ Installed $rule_name${NC}"
    fi
done

# Copy workflow config if not exists
if [ ! -f "$PROJECT_ROOT/.claude/workflow-config.env" ] && [ -f "$TOOLS_DIR/configs/workflow-config.env" ]; then
    cp "$TOOLS_DIR/configs/workflow-config.env" "$PROJECT_ROOT/.claude/"
    echo -e "  ${GREEN}✅ Created workflow configuration${NC}"
fi

# 4. Create GitHub workflows directory
echo -e "\n${YELLOW}4. Installing GitHub Workflows...${NC}"
mkdir -p "$PROJECT_ROOT/.github/workflows"

for workflow in "$TOOLS_DIR"/workflows/*; do
    if [ -f "$workflow" ]; then
        workflow_name=$(basename "$workflow")
        cp "$workflow" "$PROJECT_ROOT/.github/workflows/$workflow_name"
        echo -e "  ${GREEN}✅ Installed $workflow_name${NC}"
    fi
done

# 5. Create tools directory structure
echo -e "\n${YELLOW}5. Setting up tools directory...${NC}"
mkdir -p "$PROJECT_ROOT/tools/github-project-management/utilities"

# Copy workflow scripts
cp "$TOOLS_DIR/scripts/workflow"/*.sh "$PROJECT_ROOT/tools/" 2>/dev/null || true

# Copy GitHub integration scripts
for script in "$TOOLS_DIR/scripts/github-integration/workflow"/*.sh; do
    if [ -f "$script" ]; then
        script_name=$(basename "$script")
        cp "$script" "$PROJECT_ROOT/tools/github-project-management/utilities/$script_name"
    fi
done

# Copy project management scripts
for script in "$TOOLS_DIR/scripts/github-integration/project-management"/*.sh; do
    if [ -f "$script" ]; then
        script_name=$(basename "$script")
        cp "$script" "$PROJECT_ROOT/tools/github-project-management/utilities/$script_name"
    fi
done

# Copy CI/CD scripts
for script in "$TOOLS_DIR/scripts/ci-cd"/*.sh; do
    if [ -f "$script" ]; then
        script_name=$(basename "$script")
        cp "$script" "$PROJECT_ROOT/tools/github-project-management/utilities/$script_name"
    fi
done

echo -e "  ${GREEN}✅ Tools directory structure created${NC}"

# 6. Set up Git aliases
echo -e "\n${YELLOW}6. Setting up Git aliases...${NC}"
git config alias.workflow "!bash ./tools/show-workflow-status.sh"
git config alias.next "!bash ./tools/github-project-management/utilities/get-next-kanban-item.sh"
git config alias.wip "!bash ./tools/github-project-management/utilities/check-wip-limits.sh"
git config alias.blocked "!bash ./tools/github-project-management/utilities/list-blocked-items.sh"
git config alias.ci-fix "!bash ./tools/github-project-management/utilities/fix-ci-failures.sh"
git config alias.ci-monitor "!bash ./tools/github-project-management/utilities/monitor-ci-realtime.sh"
git config alias.validate "!bash ./tools/github-project-management/utilities/validate-gitflow.sh"
git config alias.task-status "!bash ./tools/github-project-management/utilities/update-task-status.sh"
git config alias.feature-start "flow feature start"
git config alias.feature-finish "flow feature finish"
git config alias.feature-list "flow feature list"
git config alias.arch "!bash ./tools/github-project-management/utilities/show-architecture-guidance.sh"
git config alias.pr-status "!bash ./tools/github-project-management/utilities/check-pr-status.sh"
git config alias.pr-merge "pr merge --squash --delete-branch"

echo -e "  ${GREEN}✅ Git aliases configured${NC}"

# 7. Make all scripts executable
echo -e "\n${YELLOW}7. Making scripts executable...${NC}"
find "$PROJECT_ROOT/tools" -name "*.sh" -exec chmod +x {} \;
echo -e "  ${GREEN}✅ All scripts are now executable${NC}"

# 8. Create CLAUDE.md if it doesn't exist
if [ ! -f "$PROJECT_ROOT/CLAUDE.md" ]; then
    echo -e "\n${YELLOW}8. Creating CLAUDE.md...${NC}"
    echo "# CLAUDE.md - Project Reference" > "$PROJECT_ROOT/CLAUDE.md"
    echo "" >> "$PROJECT_ROOT/CLAUDE.md"
    echo "This project uses automated tools and workflows. Run \`.project-tools/install.sh\` to set up." >> "$PROJECT_ROOT/CLAUDE.md"
    echo -e "  ${GREEN}✅ Created CLAUDE.md${NC}"
fi

# Summary
echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Project Tools Installation Complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo -e "\n${BLUE}Installed components:${NC}"
echo -e "  • Git hooks for workflow enforcement"
echo -e "  • Linting configurations"
echo -e "  • GitHub Actions workflows"
echo -e "  • Project management scripts"
echo -e "  • Git aliases for quick commands"

echo -e "\n${BLUE}Quick commands:${NC}"
echo -e "  • ${GREEN}git workflow${NC} - Show workflow status"
echo -e "  • ${GREEN}git next${NC} - Get next task"
echo -e "  • ${GREEN}git flow feature start <name>${NC} - Start new feature"

echo -e "\n${YELLOW}Next steps:${NC}"
echo -e "  1. Review the installed hooks and scripts"
echo -e "  2. Configure your GitHub project settings in .claude/workflow-config.env"
echo -e "  3. Start using GitFlow: ${GREEN}git flow init${NC}"

echo ""