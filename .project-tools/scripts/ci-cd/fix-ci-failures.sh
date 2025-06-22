#!/bin/bash

# Script: fix-ci-failures.sh
# Purpose: Comprehensive CI/CD failure analysis and automated fixing
# Usage: ./fix-ci-failures.sh [--auto-fix] [--create-pr]

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
AUTO_FIX=${1:-false}
CREATE_PR=${2:-false}

# Get repository info
REPO_OWNER=$(git remote get-url origin | sed -E 's/.*github.com[:/]([^/]+)\/.*/\1/')
REPO_NAME=$(git remote get-url origin | sed -E 's/.*github.com[:/][^/]+\/([^.]+)(\.git)?$/\1/')
CURRENT_BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null)

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}                  CI/CD FAILURE ANALYZER                  ${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Function to get latest workflow runs
get_failed_runs() {
    echo -e "\n${BLUE}Fetching recent workflow runs...${NC}"
    gh run list --branch "$CURRENT_BRANCH" --status failure --limit 5 --json databaseId,name,conclusion,createdAt,headSha
}

# Function to analyze specific run
analyze_run() {
    local run_id=$1
    echo -e "\n${BLUE}Analyzing run $run_id...${NC}"
    
    # Get run details
    RUN_INFO=$(gh run view "$run_id" --json jobs,name,conclusion,headSha)
    
    # Get failed jobs
    FAILED_JOBS=$(echo "$RUN_INFO" | jq -r '.jobs[] | select(.conclusion == "failure")')
    
    echo "$FAILED_JOBS" | jq -r '.name' | while read -r JOB_NAME; do
        echo -e "\n${RED}Failed Job: ${YELLOW}$JOB_NAME${NC}"
        
        # Get job logs
        LOGS=$(gh run view "$run_id" --job "$(echo "$FAILED_JOBS" | jq -r --arg name "$JOB_NAME" 'select(.name == $name) | .databaseId')" --log 2>/dev/null || echo "")
        
        # Analyze failure type
        analyze_failure_type "$JOB_NAME" "$LOGS"
    done
}

# Function to analyze failure type and suggest fixes
analyze_failure_type() {
    local job_name=$1
    local logs=$2
    local fixes_applied=false
    
    # Detect common failure patterns
    if echo "$logs" | grep -q "ESLint\|prettier\|lint"; then
        echo -e "${YELLOW}Type: Linting failure${NC}"
        if [ "$AUTO_FIX" = "--auto-fix" ]; then
            fix_linting_issues
            fixes_applied=true
        else
            echo -e "${BLUE}Fix: Run 'npm run lint:fix' or './fix-ci-failures.sh --auto-fix'${NC}"
        fi
        
    elif echo "$logs" | grep -q "Test failed\|FAIL\|AssertionError"; then
        echo -e "${YELLOW}Type: Test failure${NC}"
        extract_test_failures "$logs"
        
    elif echo "$logs" | grep -q "Module not found\|Cannot find module\|dependency"; then
        echo -e "${YELLOW}Type: Missing dependency${NC}"
        if [ "$AUTO_FIX" = "--auto-fix" ]; then
            fix_dependency_issues
            fixes_applied=true
        else
            echo -e "${BLUE}Fix: Run 'npm install' or check package.json${NC}"
        fi
        
    elif echo "$logs" | grep -q "TypeScript error\|TS[0-9]\+"; then
        echo -e "${YELLOW}Type: TypeScript error${NC}"
        extract_typescript_errors "$logs"
        
    elif echo "$logs" | grep -q "security\|vulnerability\|audit"; then
        echo -e "${YELLOW}Type: Security vulnerability${NC}"
        if [ "$AUTO_FIX" = "--auto-fix" ]; then
            fix_security_issues
            fixes_applied=true
        else
            echo -e "${BLUE}Fix: Run 'npm audit fix' or update dependencies${NC}"
        fi
        
    elif echo "$logs" | grep -q "Dockerfile\|docker build"; then
        echo -e "${YELLOW}Type: Docker build failure${NC}"
        extract_docker_errors "$logs"
        
    elif echo "$logs" | grep -q "markdownlint"; then
        echo -e "${YELLOW}Type: Markdown formatting${NC}"
        if [ "$AUTO_FIX" = "--auto-fix" ]; then
            fix_markdown_issues
            fixes_applied=true
        else
            echo -e "${BLUE}Fix: Run 'markdownlint --fix **/*.md'${NC}"
        fi
    else
        echo -e "${YELLOW}Type: Unknown failure${NC}"
        echo -e "${BLUE}Review logs manually with: gh run view <run-id> --log${NC}"
    fi
    
    return $([ "$fixes_applied" = true ] && echo 0 || echo 1)
}

# Fixing functions
fix_linting_issues() {
    echo -e "${GREEN}Applying linting fixes...${NC}"
    
    if [ -f "package.json" ]; then
        if grep -q '"lint:fix"' package.json; then
            npm run lint:fix
        elif grep -q '"eslint"' package.json; then
            npx eslint . --fix
        elif grep -q '"prettier"' package.json; then
            npx prettier --write .
        fi
    fi
    
    # Python linting
    if [ -f "requirements.txt" ] || [ -f "setup.py" ]; then
        if command -v black &> /dev/null; then
            black .
        fi
        if command -v isort &> /dev/null; then
            isort .
        fi
    fi
}

fix_dependency_issues() {
    echo -e "${GREEN}Fixing dependency issues...${NC}"
    
    if [ -f "package-lock.json" ]; then
        rm -f package-lock.json
        npm install
    elif [ -f "yarn.lock" ]; then
        rm -f yarn.lock
        yarn install
    elif [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
    fi
}

fix_security_issues() {
    echo -e "${GREEN}Fixing security vulnerabilities...${NC}"
    
    if [ -f "package.json" ]; then
        npm audit fix --force
    elif [ -f "yarn.lock" ]; then
        yarn audit fix
    fi
}

fix_markdown_issues() {
    echo -e "${GREEN}Fixing markdown formatting...${NC}"
    
    if command -v markdownlint &> /dev/null; then
        markdownlint --fix "**/*.md"
    else
        echo -e "${YELLOW}Installing markdownlint...${NC}"
        npm install -g markdownlint-cli
        markdownlint --fix "**/*.md"
    fi
}

# Extract specific error information
extract_test_failures() {
    local logs=$1
    echo -e "\n${BLUE}Test Failures:${NC}"
    echo "$logs" | grep -E "(FAIL|✗|●)" | head -10
    
    # Create test fix guide
    cat > .claude/test-fix-guide.md << EOF
# Test Failure Guide

## Failed Tests:
$(echo "$logs" | grep -E "FAIL|✗" | sed 's/^/- /')

## How to debug:
1. Run tests locally: \`npm test -- --verbose\`
2. Run specific test: \`npm test -- <test-name>\`
3. Debug mode: \`npm test -- --detectOpenHandles\`

## Common fixes:
- Update snapshots: \`npm test -- -u\`
- Clear cache: \`npm test -- --clearCache\`
- Check test environment setup
EOF
}

extract_typescript_errors() {
    local logs=$1
    echo -e "\n${BLUE}TypeScript Errors:${NC}"
    echo "$logs" | grep -E "TS[0-9]+:" | head -10
    
    # Common TS fixes
    echo -e "\n${YELLOW}Common fixes:${NC}"
    echo -e "- Check type definitions: ${BLUE}npm install @types/<package>${NC}"
    echo -e "- Update tsconfig.json settings"
    echo -e "- Run: ${BLUE}npx tsc --noEmit${NC} to check locally"
}

extract_docker_errors() {
    local logs=$1
    echo -e "\n${BLUE}Docker Build Errors:${NC}"
    echo "$logs" | grep -E "Step [0-9]+/|ERROR" | tail -10
    
    echo -e "\n${YELLOW}Common fixes:${NC}"
    echo -e "- Check Dockerfile syntax"
    echo -e "- Verify base image exists"
    echo -e "- Test locally: ${BLUE}docker build .${NC}"
}

# Main execution
echo -e "\n${PURPLE}📊 Recent Failed Runs:${NC}"
FAILED_RUNS=$(get_failed_runs)

if [ -z "$FAILED_RUNS" ] || [ "$FAILED_RUNS" = "[]" ]; then
    echo -e "${GREEN}✅ No recent failures on branch '$CURRENT_BRANCH'${NC}"
    exit 0
fi

# Display failed runs
echo "$FAILED_RUNS" | jq -r '.[] | "\(.databaseId) - \(.name) (\(.createdAt))"'

# Analyze most recent failure
LATEST_RUN_ID=$(echo "$FAILED_RUNS" | jq -r '.[0].databaseId')
echo -e "\n${BLUE}Analyzing most recent failure (Run ID: $LATEST_RUN_ID)...${NC}"

analyze_run "$LATEST_RUN_ID"

# If auto-fix was applied, check for changes
if [ "$AUTO_FIX" = "--auto-fix" ] && ! git diff --quiet; then
    echo -e "\n${GREEN}✅ Fixes applied!${NC}"
    
    # Show what changed
    echo -e "\n${BLUE}Changes made:${NC}"
    git diff --stat
    
    if [ "$CREATE_PR" = "--create-pr" ]; then
        # Create fix branch and PR
        FIX_BRANCH="fix/ci-failures-$(date +%Y%m%d-%H%M%S)"
        git checkout -b "$FIX_BRANCH"
        git add -A
        git commit -m "fix: automated CI/CD fixes

- Fixed linting issues
- Updated dependencies
- Resolved security vulnerabilities
- Fixed markdown formatting

Fixes failures from run: #$LATEST_RUN_ID"
        
        git push -u origin "$FIX_BRANCH"
        
        gh pr create \
            --title "Fix: CI/CD failures from run #$LATEST_RUN_ID" \
            --body "## Automated CI/CD Fixes

This PR contains automated fixes for CI/CD failures.

### Run Information:
- Run ID: #$LATEST_RUN_ID
- Branch: $CURRENT_BRANCH

### Fixes Applied:
$(git diff --stat)

### Next Steps:
1. Review the changes
2. Ensure all tests pass
3. Merge when ready

---
🤖 Generated by fix-ci-failures.sh" \
            --base "$CURRENT_BRANCH"
            
        git checkout "$CURRENT_BRANCH"
    else
        echo -e "\n${YELLOW}To create a PR with these fixes, run:${NC}"
        echo -e "${BLUE}./fix-ci-failures.sh --auto-fix --create-pr${NC}"
    fi
fi

# Summary
echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${PURPLE}📋 Summary:${NC}"
echo -e "- Repository: ${YELLOW}$REPO_OWNER/$REPO_NAME${NC}"
echo -e "- Branch: ${YELLOW}$CURRENT_BRANCH${NC}"
echo -e "- Failed runs analyzed: ${YELLOW}$(echo "$FAILED_RUNS" | jq length)${NC}"

echo -e "\n${BLUE}Useful commands:${NC}"
echo -e "- Re-run failed jobs: ${GREEN}gh run rerun $LATEST_RUN_ID --failed${NC}"
echo -e "- Watch run status: ${GREEN}gh run watch $LATEST_RUN_ID${NC}"
echo -e "- View full logs: ${GREEN}gh run view $LATEST_RUN_ID --log${NC}"

if [ "$AUTO_FIX" != "--auto-fix" ]; then
    echo -e "\n${YELLOW}To automatically fix issues, run:${NC}"
    echo -e "${GREEN}./fix-ci-failures.sh --auto-fix${NC}"
fi

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"