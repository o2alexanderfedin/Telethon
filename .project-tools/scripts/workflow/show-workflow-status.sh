#!/bin/bash

# Show comprehensive workflow status (GitFlow + Kanban)

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

# Header
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}                 WORKFLOW STATUS DASHBOARD                ${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# GitFlow Status
echo -e "\n${PURPLE}📌 GitFlow Status${NC}"
echo -e "${BLUE}─────────────────${NC}"

CURRENT_BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null)
echo -e "Current branch: ${YELLOW}$CURRENT_BRANCH${NC}"

if [[ "$CURRENT_BRANCH" =~ ^feature/ ]]; then
    FEATURE_NAME=${CURRENT_BRANCH#feature/}
    echo -e "Type: ${GREEN}Feature Branch${NC}"
    echo -e "Feature: ${YELLOW}$FEATURE_NAME${NC}"
    
    # Check for GitFlow status file
    if [ -f ".claude/gitflow-status.env" ]; then
        source .claude/gitflow-status.env
        echo -e "Started: $GITFLOW_STARTED_AT"
        echo -e "Description: ${CYAN}$FEATURE_DESCRIPTION${NC}"
        
        # Calculate time on feature
        if [ -n "$GITFLOW_STARTED_AT" ]; then
            START_TIMESTAMP=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$GITFLOW_STARTED_AT" +%s 2>/dev/null || date -d "$GITFLOW_STARTED_AT" +%s 2>/dev/null)
            NOW_TIMESTAMP=$(date +%s)
            DAYS_ELAPSED=$(( (NOW_TIMESTAMP - START_TIMESTAMP) / 86400 ))
            echo -e "Days active: ${YELLOW}$DAYS_ELAPSED${NC}"
        fi
    fi
    
    # Commits on feature
    COMMITS=$(git rev-list --count develop..HEAD 2>/dev/null || echo "0")
    echo -e "Commits: ${YELLOW}$COMMITS${NC}"
    
    echo -e "\n${BLUE}Next GitFlow actions:${NC}"
    echo -e "  • Push: ${GREEN}git push origin $CURRENT_BRANCH${NC}"
    echo -e "  • Create PR: ${GREEN}gh pr create${NC}"
    echo -e "  • Finish: ${GREEN}git flow feature finish $FEATURE_NAME${NC}"
    
elif [[ "$CURRENT_BRANCH" =~ ^release/ ]]; then
    echo -e "Type: ${YELLOW}Release Branch${NC}"
    VERSION=${CURRENT_BRANCH#release/}
    echo -e "Version: ${YELLOW}$VERSION${NC}"
    echo -e "\n${RED}Remember:${NC} Only bug fixes!"
    
elif [[ "$CURRENT_BRANCH" =~ ^hotfix/ ]]; then
    echo -e "Type: ${RED}Hotfix Branch${NC}"
    VERSION=${CURRENT_BRANCH#hotfix/}
    echo -e "Version: ${YELLOW}$VERSION${NC}"
    echo -e "\n${RED}URGENT:${NC} Fix and finish ASAP!"
    
elif [[ "$CURRENT_BRANCH" == "develop" ]]; then
    echo -e "Type: ${BLUE}Development Branch${NC}"
    echo -e "\n${BLUE}You can start:${NC}"
    echo -e "  • New feature: ${GREEN}git flow feature start <name>${NC}"
    echo -e "  • New release: ${GREEN}git flow release start <version>${NC}"
    
elif [[ "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "master" ]]; then
    echo -e "Type: ${RED}Production Branch${NC}"
    echo -e "\n${YELLOW}⚠️  Be careful! Only hotfixes here.${NC}"
fi

# Kanban Status
echo -e "\n${PURPLE}📊 Kanban Status${NC}"
echo -e "${BLUE}────────────────${NC}"

# Check for current task
if [ -f ".claude/current-task.txt" ]; then
    CURRENT_TASK=$(cat .claude/current-task.txt)
    echo -e "Current task: ${GREEN}#$CURRENT_TASK${NC}"
    
    # Show architecture guidance hint
    echo -e "\n${BLUE}Architecture Guidance:${NC}"
    echo -e "  View guidance: ${GREEN}./tools/github-project-management/utilities/show-architecture-guidance.sh${NC}"
    echo -e "  Or: ${GREEN}git arch${NC} (if alias configured)"
fi

# Get WIP status
PROJECT_OWNER="o2alexanderfedin"
PROJECT_NUMBER="1"

if command -v gh &> /dev/null; then
    # Get project ID
    PROJECT_ID=$(gh api graphql -f query='
      query($owner: String!, $number: Int!) {
        user(login: $owner) {
          projectV2(number: $number) {
            id
          }
        }
      }' -f owner="$PROJECT_OWNER" -f number="$PROJECT_NUMBER" --jq '.data.user.projectV2.id' 2>/dev/null)
    
    if [ -n "$PROJECT_ID" ]; then
        # Count items by status
        WIP_DATA=$(gh api graphql -f query='
          query($projectId: ID!) {
            node(id: $projectId) {
              ... on ProjectV2 {
                items(first: 100) {
                  nodes {
                    fieldValues(first: 20) {
                      nodes {
                        ... on ProjectV2ItemFieldSingleSelectValue {
                          name
                          field {
                            ... on ProjectV2SingleSelectField {
                              name
                            }
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }' -f projectId="$PROJECT_ID" 2>/dev/null)
        
        if [ -n "$WIP_DATA" ]; then
            IN_PROGRESS=$(echo "$WIP_DATA" | jq '[.data.node.items.nodes[]?.fieldValues.nodes[]? | select(.field.name == "Status" and .name == "In Progress")] | length' 2>/dev/null || echo "0")
            IN_REVIEW=$(echo "$WIP_DATA" | jq '[.data.node.items.nodes[]?.fieldValues.nodes[]? | select(.field.name == "Status" and .name == "In Review")] | length' 2>/dev/null || echo "0")
            BLOCKED=$(echo "$WIP_DATA" | jq '[.data.node.items.nodes[]?.fieldValues.nodes[]? | select(.field.name == "Dependency Status" and .name == "Blocked")] | length' 2>/dev/null || echo "0")
            
            echo -e "\nWork in Progress:"
            echo -e "  In Progress: ${YELLOW}$IN_PROGRESS${NC}/3"
            echo -e "  In Review: ${YELLOW}$IN_REVIEW${NC}/2"
            if [ "$BLOCKED" -gt 0 ]; then
                echo -e "  Blocked: ${RED}$BLOCKED items${NC}"
            fi
            
            # Recommendations
            echo -e "\n${BLUE}Recommendations:${NC}"
            if [ "$IN_PROGRESS" -ge 3 ]; then
                echo -e "  ${YELLOW}⚠️  At WIP limit! Focus on completing current work.${NC}"
            elif [ "$IN_PROGRESS" -eq 0 ]; then
                echo -e "  ${GREEN}✅ No active work. Get next item:${NC}"
                echo -e "     ${BLUE}./tools/github-project-management/utilities/get-next-kanban-item.sh${NC}"
            else
                echo -e "  ${GREEN}✅ WIP healthy. Can take more work if needed.${NC}"
            fi
            
            if [ "$BLOCKED" -gt 0 ]; then
                echo -e "  ${RED}🚫 Check blocked items:${NC}"
                echo -e "     ${BLUE}./tools/github-project-management/utilities/list-blocked-items.sh${NC}"
            fi
        fi
    fi
else
    echo -e "${YELLOW}GitHub CLI not available${NC}"
fi

# Pull Request Status
echo -e "\n${PURPLE}🔀 Pull Request Status${NC}"
echo -e "${BLUE}──────────────────────${NC}"

# Check for open PRs
CURRENT_USER=$(gh api user --jq '.login' 2>/dev/null || echo "")
if [ -n "$CURRENT_USER" ]; then
    OPEN_PRS=$(gh pr list --author "$CURRENT_USER" --state open --json number,title,reviewDecision,isDraft 2>/dev/null || echo "[]")
    PR_COUNT=$(echo "$OPEN_PRS" | jq 'length')
    
    if [ "$PR_COUNT" -gt 0 ]; then
        echo -e "${YELLOW}Open PRs: $PR_COUNT${NC}"
        echo "$OPEN_PRS" | jq -r '.[] | 
            "  #\(.number): " + 
            (if .isDraft then "📝 Draft"
             elif .reviewDecision == "APPROVED" then "✅ Ready to merge!"
             elif .reviewDecision == "CHANGES_REQUESTED" then "❌ Changes requested"
             else "👀 Awaiting review" end)' | head -3
        
        if [ "$PR_COUNT" -gt 3 ]; then
            echo -e "  ... and $((PR_COUNT - 3)) more"
        fi
        
        echo -e "\n${RED}⚠️  Complete PRs before new work!${NC}"
    else
        echo -e "${GREEN}✅ No open PRs${NC}"
    fi
fi

# Quick Actions
echo -e "\n${PURPLE}⚡ Quick Actions${NC}"
echo -e "${BLUE}────────────────${NC}"
echo -e "1. Check PR status:   ${GREEN}git pr-status${NC}"
echo -e "2. Get next task:     ${GREEN}git next${NC}"
echo -e "3. Check WIP limits:  ${GREEN}git wip${NC}"
echo -e "4. List blocked:      ${GREEN}git blocked${NC}"
echo -e "5. Create feature:    ${GREEN}git flow feature start <name>${NC}"
echo -e "6. Create PR:         ${GREEN}gh pr create${NC}"

# Git Status Summary
echo -e "\n${PURPLE}📝 Git Status${NC}"
echo -e "${BLUE}─────────────${NC}"
MODIFIED=$(git status --porcelain | grep -c "^ M" || true)
UNTRACKED=$(git status --porcelain | grep -c "^??" || true)
STAGED=$(git status --porcelain | grep -c "^[AM]" || true)

if [ "$MODIFIED" -gt 0 ] || [ "$UNTRACKED" -gt 0 ] || [ "$STAGED" -gt 0 ]; then
    [ "$STAGED" -gt 0 ] && echo -e "Staged: ${GREEN}$STAGED files${NC}"
    [ "$MODIFIED" -gt 0 ] && echo -e "Modified: ${YELLOW}$MODIFIED files${NC}"
    [ "$UNTRACKED" -gt 0 ] && echo -e "Untracked: ${RED}$UNTRACKED files${NC}"
else
    echo -e "${GREEN}✅ Working directory clean${NC}"
fi

# Footer
echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Ready to code! 🚀${NC}"
echo ""