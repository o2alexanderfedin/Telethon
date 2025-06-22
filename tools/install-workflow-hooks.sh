#!/bin/bash

# Install GitFlow + Kanban workflow hooks

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}Installing GitFlow + Kanban Workflow Hooks...${NC}"

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}Error: Not in a git repository!${NC}"
    exit 1
fi

GIT_DIR=$(git rev-parse --git-dir)
HOOKS_DIR="$GIT_DIR/hooks"

# List of hooks to install
HOOKS=(
    "pre-commit"
    "post-commit"
    "pre-push"
    "post-push"
    "post-checkout"
    "post-merge"
    "prepare-commit-msg"
    "post-flow-feature-start"
    "post-flow-feature-finish"
)

# Create hooks directory if it doesn't exist
mkdir -p "$HOOKS_DIR"

# Install each hook
for hook in "${HOOKS[@]}"; do
    SOURCE_FILE="$HOOKS_DIR/$hook"
    TARGET_FILE="$HOOKS_DIR/$hook"
    
    if [ -f "$SOURCE_FILE" ]; then
        # Backup existing hook if present
        if [ -f "$TARGET_FILE" ] && [ ! -f "$TARGET_FILE.backup" ]; then
            echo -e "${YELLOW}Backing up existing $hook hook...${NC}"
            mv "$TARGET_FILE" "$TARGET_FILE.backup"
        fi
        
        # Copy hook
        cp "$SOURCE_FILE" "$TARGET_FILE"
        chmod +x "$TARGET_FILE"
        echo -e "${GREEN}✅ Installed $hook hook${NC}"
    else
        echo -e "${YELLOW}⚠️  Source hook $hook not found${NC}"
    fi
done

# Create .claude directory for workflow tracking
mkdir -p .claude

# Create initial workflow configuration
if [ ! -f ".claude/workflow-config.env" ]; then
    cat > .claude/workflow-config.env << EOF
# Workflow Configuration
WORKFLOW_TYPE=gitflow+kanban
KANBAN_WIP_LIMIT_IN_PROGRESS=3
KANBAN_WIP_LIMIT_IN_REVIEW=2
KANBAN_WIP_LIMIT_TESTING=2
GITFLOW_FEATURE_PREFIX=feature/
GITFLOW_RELEASE_PREFIX=release/
GITFLOW_HOTFIX_PREFIX=hotfix/
GITFLOW_DEVELOP_BRANCH=develop
GITFLOW_MAIN_BRANCH=main
PROJECT_OWNER=o2alexanderfedin
PROJECT_NUMBER=1
ENABLE_COMMIT_HINTS=true
ENABLE_KANBAN_REMINDERS=true
ENABLE_GITFLOW_REMINDERS=true
EOF
    echo -e "${GREEN}✅ Created workflow configuration${NC}"
fi

# Add workflow status command to git aliases
echo -e "\n${BLUE}Adding git aliases...${NC}"
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

echo -e "${GREEN}✅ Added git aliases:${NC}"
echo -e "  • ${BLUE}git workflow${NC} - Show complete workflow status"
echo -e "  • ${BLUE}git next${NC} - Get next Kanban item"
echo -e "  • ${BLUE}git wip${NC} - Check WIP limits"
echo -e "  • ${BLUE}git blocked${NC} - List blocked items"
echo -e "  • ${BLUE}git ci-fix${NC} - Analyze and fix CI failures"
echo -e "  • ${BLUE}git ci-monitor${NC} - Real-time CI monitoring"
echo -e "  • ${BLUE}git validate${NC} - Validate GitFlow compliance"
echo -e "  • ${BLUE}git task-status${NC} - Update task status"
echo -e "  • ${BLUE}git feature-start${NC} - Start new feature (shortcut)"
echo -e "  • ${BLUE}git feature-finish${NC} - Finish feature (shortcut)"
echo -e "  • ${BLUE}git arch${NC} - Show architecture guidance for task"
echo -e "  • ${BLUE}git pr-status${NC} - Check all open PRs status"
echo -e "  • ${BLUE}git pr-merge${NC} - Merge PR with squash"

# Create a shell function for quick status
echo -e "\n${BLUE}Creating shell function...${NC}"
SHELL_RC=""
if [ -n "$ZSH_VERSION" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -n "$BASH_VERSION" ]; then
    SHELL_RC="$HOME/.bashrc"
fi

if [ -n "$SHELL_RC" ] && [ -f "$SHELL_RC" ]; then
    if ! grep -q "workflow-status" "$SHELL_RC"; then
        echo "" >> "$SHELL_RC"
        echo "# GitFlow + Kanban workflow status" >> "$SHELL_RC"
        echo "alias workflow-status='./tools/show-workflow-status.sh'" >> "$SHELL_RC"
        echo -e "${GREEN}✅ Added 'workflow-status' alias to $SHELL_RC${NC}"
        echo -e "${YELLOW}Run 'source $SHELL_RC' to activate${NC}"
    fi
fi

# Summary
echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Workflow Hooks Installation Complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo -e "\n${BLUE}Installed hooks will:${NC}"
echo -e "  • ${RED}ENFORCE${NC} GitFlow branching model"
echo -e "  • ${RED}BLOCK${NC} direct commits to main/develop"
echo -e "  • ${GREEN}AUTO-LINK${NC} features to Kanban tasks"
echo -e "  • ${GREEN}AUTO-UPDATE${NC} task status (In Progress → Done)"
echo -e "  • Track feature time and statistics"
echo -e "  • Monitor CI/CD and auto-fix failures"
echo -e "  • Provide continuous workflow guidance"

echo -e "\n${BLUE}Quick commands:${NC}"
echo -e "  • ${GREEN}git workflow${NC} - Full status dashboard"
echo -e "  • ${GREEN}git next${NC} - Get next task from Kanban"
echo -e "  • ${GREEN}git wip${NC} - Check your WIP limits"
echo -e "  • ${GREEN}./tools/show-workflow-status.sh${NC} - Detailed status"

echo -e "\n${YELLOW}Try it now:${NC} ${GREEN}git workflow${NC}"
echo ""