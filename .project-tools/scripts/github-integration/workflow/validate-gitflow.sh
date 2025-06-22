#!/bin/bash

# Script: validate-gitflow.sh
# Purpose: Validate current branch follows GitFlow and provide guidance
# Usage: ./validate-gitflow.sh

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Get current branch
CURRENT_BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null || echo "")

if [ -z "$CURRENT_BRANCH" ]; then
    echo -e "${RED}❌ Not in a git repository${NC}"
    exit 1
fi

echo -e "${BLUE}Current branch: ${YELLOW}$CURRENT_BRANCH${NC}"

# Check GitFlow compliance
VALID_BRANCH=true
BRANCH_TYPE=""

if [[ "$CURRENT_BRANCH" == "main" ]] || [[ "$CURRENT_BRANCH" == "master" ]]; then
    BRANCH_TYPE="production"
    echo -e "${RED}⚠️  On PRODUCTION branch${NC}"
    echo -e "${YELLOW}Direct commits not allowed!${NC}"
    VALID_BRANCH=false
    
elif [[ "$CURRENT_BRANCH" == "develop" ]]; then
    BRANCH_TYPE="develop"
    echo -e "${BLUE}📌 On DEVELOP branch${NC}"
    echo -e "${YELLOW}Direct commits discouraged${NC}"
    
elif [[ "$CURRENT_BRANCH" =~ ^feature/ ]]; then
    BRANCH_TYPE="feature"
    FEATURE_NAME=${CURRENT_BRANCH#feature/}
    echo -e "${GREEN}✅ Valid feature branch: ${YELLOW}$FEATURE_NAME${NC}"
    
elif [[ "$CURRENT_BRANCH" =~ ^release/ ]]; then
    BRANCH_TYPE="release"
    RELEASE_VERSION=${CURRENT_BRANCH#release/}
    echo -e "${GREEN}✅ Valid release branch: ${YELLOW}$RELEASE_VERSION${NC}"
    
elif [[ "$CURRENT_BRANCH" =~ ^hotfix/ ]]; then
    BRANCH_TYPE="hotfix"
    HOTFIX_VERSION=${CURRENT_BRANCH#hotfix/}
    echo -e "${GREEN}✅ Valid hotfix branch: ${YELLOW}$HOTFIX_VERSION${NC}"
    
elif [[ "$CURRENT_BRANCH" =~ ^bugfix/ ]]; then
    BRANCH_TYPE="bugfix"
    BUGFIX_NAME=${CURRENT_BRANCH#bugfix/}
    echo -e "${GREEN}✅ Valid bugfix branch: ${YELLOW}$BUGFIX_NAME${NC}"
    
else
    VALID_BRANCH=false
    echo -e "${RED}❌ NON-GITFLOW BRANCH!${NC}"
    echo -e "${YELLOW}Branch '$CURRENT_BRANCH' doesn't follow GitFlow conventions${NC}"
fi

# Provide guidance based on branch type
echo -e "\n${PURPLE}📋 Branch Guidelines:${NC}"

case "$BRANCH_TYPE" in
    "production")
        echo -e "${RED}You should not be working directly on main/master!${NC}"
        echo -e "\n${BLUE}Allowed operations:${NC}"
        echo -e "  • Merge from release: ${GREEN}git flow release finish <version>${NC}"
        echo -e "  • Merge from hotfix: ${GREEN}git flow hotfix finish <version>${NC}"
        echo -e "\n${BLUE}To start new work:${NC}"
        echo -e "  1. ${GREEN}git checkout develop${NC}"
        echo -e "  2. ${GREEN}git flow feature start <name>${NC}"
        ;;
        
    "develop")
        echo -e "${BLUE}Develop branch is for integration${NC}"
        echo -e "\n${BLUE}Recommended actions:${NC}"
        echo -e "  • Start feature: ${GREEN}git flow feature start <name>${NC}"
        echo -e "  • Start release: ${GREEN}git flow release start <version>${NC}"
        echo -e "  • List features: ${GREEN}git flow feature list${NC}"
        ;;
        
    "feature")
        echo -e "${GREEN}You're on a feature branch - great!${NC}"
        
        # Check for linked task
        if [ -f ".claude/current-task.txt" ]; then
            TASK_NUMBER=$(cat .claude/current-task.txt)
            echo -e "📌 Linked task: ${GREEN}#$TASK_NUMBER${NC}"
        else
            echo -e "${YELLOW}⚠️  No task linked${NC}"
            echo -e "Link a task: ${GREEN}git next${NC} or ${GREEN}echo '<number>' > .claude/current-task.txt${NC}"
        fi
        
        echo -e "\n${BLUE}Feature workflow:${NC}"
        echo -e "  1. Make changes and commit"
        echo -e "  2. Push: ${GREEN}git push -u origin $CURRENT_BRANCH${NC}"
        echo -e "  3. Create PR: ${GREEN}gh pr create${NC}"
        echo -e "  4. Finish: ${GREEN}git flow feature finish $FEATURE_NAME${NC}"
        ;;
        
    "release")
        echo -e "${YELLOW}Release branch - production preparation${NC}"
        echo -e "\n${BLUE}Allowed changes:${NC}"
        echo -e "  • Bug fixes only"
        echo -e "  • Version bumps"
        echo -e "  • Documentation updates"
        echo -e "\n${BLUE}When ready:${NC}"
        echo -e "  ${GREEN}git flow release finish $RELEASE_VERSION${NC}"
        ;;
        
    "hotfix")
        echo -e "${RED}Hotfix branch - urgent production fix${NC}"
        echo -e "\n${BLUE}Guidelines:${NC}"
        echo -e "  • Fix critical issues only"
        echo -e "  • Minimal changes"
        echo -e "  • Test thoroughly"
        echo -e "\n${BLUE}When ready:${NC}"
        echo -e "  ${GREEN}git flow hotfix finish $HOTFIX_VERSION${NC}"
        ;;
        
    *)
        echo -e "${RED}Invalid branch - cannot provide guidance${NC}"
        echo -e "\n${BLUE}How to fix:${NC}"
        echo -e "  1. ${GREEN}git stash${NC} (save your changes)"
        echo -e "  2. ${GREEN}git checkout develop${NC}"
        echo -e "  3. ${GREEN}git flow feature start <descriptive-name>${NC}"
        echo -e "  4. ${GREEN}git stash pop${NC} (restore changes)"
        ;;
esac

# Check for uncommitted changes
if ! git diff-index --quiet HEAD -- 2>/dev/null; then
    echo -e "\n${YELLOW}📝 Uncommitted changes detected${NC}"
fi

# Show GitFlow status
echo -e "\n${PURPLE}🌳 GitFlow Status:${NC}"
echo -e "Active features:"
git flow feature list 2>/dev/null | sed 's/^/  /' || echo "  No active features"

if [ "$VALID_BRANCH" = false ]; then
    echo -e "\n${RED}❌ ACTION REQUIRED: Switch to a valid GitFlow branch${NC}"
    exit 1
else
    echo -e "\n${GREEN}✅ Branch follows GitFlow conventions${NC}"
fi