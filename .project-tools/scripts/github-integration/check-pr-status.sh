#!/bin/bash

# Script: check-pr-status.sh
# Purpose: Check status of all open PRs and provide guidance
# Usage: ./check-pr-status.sh

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}                 PULL REQUEST STATUS                   ${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Get current user
CURRENT_USER=$(gh api user --jq '.login')
echo -e "${BLUE}User: ${YELLOW}$CURRENT_USER${NC}"

# Get all open PRs
OPEN_PRS=$(gh pr list --author "$CURRENT_USER" --state open --json number,title,headRefName,baseRefName,isDraft,reviewDecision,statusCheckRollup,createdAt,updatedAt,url)
PR_COUNT=$(echo "$OPEN_PRS" | jq 'length')

if [ "$PR_COUNT" -eq 0 ]; then
    echo -e "\n${GREEN}✅ No open pull requests!${NC}"
    echo -e "${BLUE}You're ready to start new work with: ${GREEN}git next${NC}"
    exit 0
fi

echo -e "\n${PURPLE}📋 Open Pull Requests: ${YELLOW}$PR_COUNT${NC}"

# Process each PR
echo "$OPEN_PRS" | jq -r '.[] | @base64' | while IFS= read -r pr_data; do
    # Decode PR data
    PR=$(echo "$pr_data" | base64 --decode)
    
    # Extract fields
    NUMBER=$(echo "$PR" | jq -r '.number')
    TITLE=$(echo "$PR" | jq -r '.title')
    BRANCH=$(echo "$PR" | jq -r '.headRefName')
    BASE=$(echo "$PR" | jq -r '.baseRefName')
    IS_DRAFT=$(echo "$PR" | jq -r '.isDraft')
    REVIEW=$(echo "$PR" | jq -r '.reviewDecision // "PENDING"')
    CHECKS=$(echo "$PR" | jq -r '.statusCheckRollup.state // "UNKNOWN"')
    URL=$(echo "$PR" | jq -r '.url')
    CREATED=$(echo "$PR" | jq -r '.createdAt')
    UPDATED=$(echo "$PR" | jq -r '.updatedAt')
    
    # Calculate age
    CREATED_TS=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$CREATED" +%s 2>/dev/null || date -d "$CREATED" +%s 2>/dev/null || echo 0)
    NOW_TS=$(date +%s)
    AGE_HOURS=$(( (NOW_TS - CREATED_TS) / 3600 ))
    AGE_DAYS=$(( AGE_HOURS / 24 ))
    
    # Display PR header
    echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${PURPLE}PR #$NUMBER:${NC} $TITLE"
    echo -e "${BLUE}Branch:${NC} $BRANCH → $BASE"
    echo -e "${BLUE}Age:${NC} $AGE_DAYS days"
    echo -e "${BLUE}URL:${NC} $URL"
    
    # Determine status and required actions
    if [ "$IS_DRAFT" = "true" ]; then
        echo -e "${YELLOW}📝 Status: DRAFT${NC}"
        echo -e "${BLUE}Action Required:${NC}"
        echo -e "  1. Complete implementation"
        echo -e "  2. Mark as ready: ${GREEN}gh pr ready $NUMBER${NC}"
        
    elif [ "$REVIEW" = "APPROVED" ]; then
        if [ "$CHECKS" = "SUCCESS" ] || [ "$CHECKS" = "UNKNOWN" ]; then
            echo -e "${GREEN}✅ Status: APPROVED & READY TO MERGE${NC}"
            echo -e "${BLUE}Action Required:${NC}"
            echo -e "  • Merge now: ${GREEN}gh pr merge $NUMBER${NC}"
            echo -e "  • Or merge with squash: ${GREEN}gh pr merge $NUMBER --squash${NC}"
        else
            echo -e "${YELLOW}⚠️  Status: APPROVED but CHECKS FAILING${NC}"
            echo -e "${BLUE}Action Required:${NC}"
            echo -e "  1. Fix failing checks: ${GREEN}git ci-fix${NC}"
            echo -e "  2. View details: ${GREEN}gh pr checks $NUMBER${NC}"
        fi
        
    elif [ "$REVIEW" = "CHANGES_REQUESTED" ]; then
        echo -e "${RED}❌ Status: CHANGES REQUESTED${NC}"
        echo -e "${BLUE}Action Required:${NC}"
        echo -e "  1. View feedback: ${GREEN}gh pr view $NUMBER${NC}"
        echo -e "  2. Address comments"
        echo -e "  3. Push fixes: ${GREEN}git push${NC}"
        echo -e "  4. Re-request review: ${GREEN}gh pr review $NUMBER --request${NC}"
        
    elif [ "$CHECKS" = "FAILURE" ]; then
        echo -e "${RED}❌ Status: CHECKS FAILING${NC}"
        echo -e "${BLUE}Action Required:${NC}"
        echo -e "  1. View failures: ${GREEN}gh pr checks $NUMBER${NC}"
        echo -e "  2. Fix issues: ${GREEN}git ci-fix${NC}"
        echo -e "  3. Push fixes: ${GREEN}git push${NC}"
        
    elif [ "$CHECKS" = "PENDING" ]; then
        echo -e "${YELLOW}⏳ Status: CHECKS RUNNING${NC}"
        echo -e "${BLUE}Action Required:${NC}"
        echo -e "  • Monitor progress: ${GREEN}gh pr checks $NUMBER --watch${NC}"
        echo -e "  • Or wait for completion"
        
    else
        echo -e "${YELLOW}👀 Status: AWAITING REVIEW${NC}"
        echo -e "${BLUE}Action Required:${NC}"
        if [ $AGE_DAYS -gt 3 ]; then
            echo -e "  • ${RED}PR is $AGE_DAYS days old!${NC}"
        fi
        echo -e "  • Request review: ${GREEN}gh pr view $NUMBER --web${NC}"
        echo -e "  • Or ping reviewers in comments"
    fi
    
    # Show linked task if exists
    TASK_REF=$(echo "$TITLE" | grep -oE "#[0-9]+" || echo "$TITLE" | grep -oE "Fixes #[0-9]+" || echo "")
    if [ -n "$TASK_REF" ]; then
        echo -e "${BLUE}Linked Task:${NC} $TASK_REF"
    fi
done

# Summary and recommendations
echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${PURPLE}📊 Summary:${NC}"

# Count by status
APPROVED=$(echo "$OPEN_PRS" | jq '[.[] | select(.reviewDecision == "APPROVED")] | length')
CHANGES_REQ=$(echo "$OPEN_PRS" | jq '[.[] | select(.reviewDecision == "CHANGES_REQUESTED")] | length')
DRAFT=$(echo "$OPEN_PRS" | jq '[.[] | select(.isDraft == true)] | length')
FAILING=$(echo "$OPEN_PRS" | jq '[.[] | select(.statusCheckRollup.state == "FAILURE")] | length')

echo -e "  • Total Open PRs: ${YELLOW}$PR_COUNT${NC}"
[ $APPROVED -gt 0 ] && echo -e "  • Ready to merge: ${GREEN}$APPROVED${NC}"
[ $CHANGES_REQ -gt 0 ] && echo -e "  • Changes requested: ${RED}$CHANGES_REQ${NC}"
[ $DRAFT -gt 0 ] && echo -e "  • Drafts: ${YELLOW}$DRAFT${NC}"
[ $FAILING -gt 0 ] && echo -e "  • Failing checks: ${RED}$FAILING${NC}"

echo -e "\n${PURPLE}💡 Recommendations:${NC}"
if [ $APPROVED -gt 0 ]; then
    echo -e "  ${GREEN}➤ Merge approved PRs first!${NC}"
elif [ $CHANGES_REQ -gt 0 ]; then
    echo -e "  ${RED}➤ Address review feedback${NC}"
elif [ $FAILING -gt 0 ]; then
    echo -e "  ${RED}➤ Fix failing CI/CD checks${NC}"
else
    echo -e "  ${YELLOW}➤ Follow up on reviews${NC}"
fi

echo -e "\n${BLUE}Workflow Rule:${NC}"
echo -e "Complete all PRs before starting new work (${GREEN}git next${NC})"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"