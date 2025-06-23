#!/bin/bash

# Script: get-next-kanban-item-fixed.sh
# Purpose: Fixed version to automatically select the next work item based on Kanban rules
# Usage: ./get-next-kanban-item-fixed.sh [--auto-assign]

set -euo pipefail

# Configuration
PROJECT_OWNER="o2alexanderfedin"
PROJECT_NUMBER=12
MAX_WIP=3

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Parse arguments
AUTO_ASSIGN=false
if [ "${1:-}" = "--auto-assign" ]; then
    AUTO_ASSIGN=true
fi

# First check for open PRs
echo -e "${PURPLE}🔍 Checking for open pull requests...${NC}"

# Get current user
CURRENT_USER=$(gh api user --jq '.login')

# Check for open PRs authored by current user
OPEN_PRS=$(gh pr list --author "$CURRENT_USER" --state open --json number,title,headRefName,isDraft,reviewDecision,statusCheckRollup)
PR_COUNT=$(echo "$OPEN_PRS" | jq 'length')

if [ "$PR_COUNT" -gt 0 ]; then
    echo -e "\n${RED}❌ You have $PR_COUNT open pull request(s) that need attention:${NC}"
    
    echo "$OPEN_PRS" | jq -r '.[] | 
        "  PR #\(.number): \(.title)" +
        "\n    Branch: \(.headRefName)" +
        "\n    Status: " + 
        (if .isDraft then "Draft" 
         elif .reviewDecision == "APPROVED" then "✅ Approved - Ready to merge!"
         elif .reviewDecision == "CHANGES_REQUESTED" then "❌ Changes requested"
         elif .statusCheckRollup.state == "FAILURE" then "❌ Checks failing"
         elif .statusCheckRollup.state == "PENDING" then "⏳ Checks running"
         else "👀 Awaiting review" end) +
        "\n"'
    
    echo -e "${YELLOW}⚠️  WORKFLOW RULE: Review and complete PRs before starting new work${NC}"
    echo -e "\n${BLUE}Required Actions:${NC}"
    
    # Check each PR status
    echo "$OPEN_PRS" | jq -r '.[] | 
        if .reviewDecision == "APPROVED" then
            "  • PR #\(.number): ${GREEN}Ready to merge!${NC} Run: ${GREEN}gh pr merge \(.number)${NC}"
        elif .reviewDecision == "CHANGES_REQUESTED" then
            "  • PR #\(.number): ${RED}Address review feedback${NC} - ${BLUE}gh pr view \(.number)${NC}"
        elif .statusCheckRollup.state == "FAILURE" then
            "  • PR #\(.number): ${RED}Fix failing checks${NC} - ${BLUE}git ci-fix${NC}"
        elif .isDraft then
            "  • PR #\(.number): ${YELLOW}Complete draft PR${NC} - ${BLUE}gh pr ready \(.number)${NC}"
        else
            "  • PR #\(.number): ${YELLOW}Request review${NC} - ${BLUE}gh pr view \(.number) --web${NC}"
        end' | while read line; do echo -e "$line"; done
    
    echo -e "\n${RED}Please complete your open PRs before taking new work.${NC}"
    echo -e "${BLUE}This ensures:${NC}"
    echo -e "  • Clean task completion"
    echo -e "  • No work in progress buildup"
    echo -e "  • Better code quality through reviews"
    echo -e "  • Faster feature delivery"
    
    # Still allow override if really needed
    if [ "${1:-}" = "--force" ]; then
        echo -e "\n${YELLOW}⚠️  --force flag detected. Proceeding anyway...${NC}"
    else
        echo -e "\n${YELLOW}To override (not recommended): ${NC}$0 --force"
        exit 1
    fi
fi

# Get project items using gh project item-list
echo -e "\n${BLUE}Fetching project information...${NC}"

# Count current WIP
CURRENT_WIP=$(gh project item-list $PROJECT_NUMBER --owner $PROJECT_OWNER --format json | jq '[.items[] | select(.status == "In Progress")] | length')
echo -e "Current WIP: ${YELLOW}$CURRENT_WIP${NC} / $MAX_WIP"

if [ "$CURRENT_WIP" -ge "$MAX_WIP" ]; then
    echo -e "${RED}❌ WIP limit reached! Complete current work before pulling new items.${NC}"
    echo -e "\nCurrent items in progress:"
    gh project item-list $PROJECT_NUMBER --owner $PROJECT_OWNER --format json | jq -r '.items[] | select(.status == "In Progress") | "  - #\(.content.number): \(.title)"'
    exit 1
fi

# Find next available Task (Todo or no status)
echo -e "\n${BLUE}Finding next available engineering task...${NC}"

# Get available items
AVAILABLE_ITEMS=$(gh project item-list $PROJECT_NUMBER --owner $PROJECT_OWNER --format json | jq -r '.items[] | 
  select(
    (.status == null or .status == "" or .status == "Todo") and
    (.type == "Task") and
    (.content.state == "OPEN" or .content.state == "open")
  ) | 
  {
    number: .content.number,
    title: .title,
    type: .type,
    priority: .priority,
    points: .["story Points"],
    depStatus: .["dependency Status"],
    labels: .labels
  }')

# Filter for items with ready dependencies
NEXT_ITEM=$(echo "$AVAILABLE_ITEMS" | jq -s '
  map(select(
    .depStatus == "Ready" or 
    .depStatus == null or 
    .depStatus == ""
  )) | 
  sort_by(
    (if .priority == "Critical" then 0
     elif .priority == "High" then 1
     elif .priority == "Medium" then 2
     else 3 end),
    (.points // 999)
  ) | 
  first')

if [ -z "$NEXT_ITEM" ] || [ "$NEXT_ITEM" = "null" ]; then
    echo -e "${YELLOW}No available items found with satisfied dependencies.${NC}"
    echo -e "\nSuggestions:"
    echo -e "  1. Check if there are items in 'Ready' status"
    echo -e "  2. Review blocked items to see if any can be unblocked"
    echo -e "  3. Check if all Todo items have unsatisfied dependencies"
    
    # Show some blocked items if any
    echo -e "\n${BLUE}Blocked items:${NC}"
    gh project item-list $PROJECT_NUMBER --owner $PROJECT_OWNER --format json | jq -r '.items[] | 
      select(."dependency Status" == "Blocked") | 
      "  - #\(.content.number): \(.title)"' | head -5
    exit 0
fi

# Display the next item
ISSUE_NUMBER=$(echo "$NEXT_ITEM" | jq -r '.number')
ISSUE_TITLE=$(echo "$NEXT_ITEM" | jq -r '.title')
ISSUE_TYPE=$(echo "$NEXT_ITEM" | jq -r '.type // "Unknown"')
ISSUE_PRIORITY=$(echo "$NEXT_ITEM" | jq -r '.priority // "Medium"')
ISSUE_POINTS=$(echo "$NEXT_ITEM" | jq -r '.points // "?"')

echo -e "\n${GREEN}📋 Next recommended work item:${NC}"
echo -e "  Issue: #$ISSUE_NUMBER"
echo -e "  Title: $ISSUE_TITLE"
echo -e "  Type: $ISSUE_TYPE"
echo -e "  Priority: $ISSUE_PRIORITY"
echo -e "  Story Points: $ISSUE_POINTS"

# Show issue details
echo -e "\n${BLUE}Issue details:${NC}"
gh issue view $ISSUE_NUMBER --repo o2alexanderfedin/telethon-architecture-docs

# Auto-assign if requested
if [ "$AUTO_ASSIGN" = true ]; then
    echo -e "\n${YELLOW}🔄 Auto-assigning issue #$ISSUE_NUMBER to $CURRENT_USER...${NC}"
    
    # Get the project item ID for updating
    ITEM_ID=$(gh project item-list $PROJECT_NUMBER --owner $PROJECT_OWNER --format json | jq -r ".items[] | select(.content.number == $ISSUE_NUMBER) | .id")
    
    if [ -n "$ITEM_ID" ] && [ "$ITEM_ID" != "null" ]; then
        # Update status to "In Progress" using GitHub CLI
        echo -e "${BLUE}Updating status to 'In Progress'...${NC}"
        
        # Find the Status field ID
        STATUS_FIELD_ID=$(gh project field-list $PROJECT_NUMBER --owner $PROJECT_OWNER --format json | jq -r '.fields[] | select(.name == "Status") | .id')
        
        if [ -n "$STATUS_FIELD_ID" ] && [ "$STATUS_FIELD_ID" != "null" ]; then
            # Update the item status
            gh project item-edit --project-id $PROJECT_NUMBER --id "$ITEM_ID" --field-id "$STATUS_FIELD_ID" --single-select-option-id "In Progress" 2>/dev/null || {
                echo -e "${YELLOW}Note: Could not update status automatically. Please update manually in the project board.${NC}"
            }
        fi
        
        echo -e "${GREEN}✅ Issue #$ISSUE_NUMBER assigned and moved to 'In Progress'${NC}"
        echo -e "\n${BLUE}To start working on this issue:${NC}"
        echo -e "  1. Create a feature branch: ${GREEN}git flow feature start issue-$ISSUE_NUMBER${NC}"
        echo -e "  2. Review the issue details above"
        echo -e "  3. Check the technical architecture documentation"
        echo -e "  4. Begin implementation"
    else
        echo -e "${RED}❌ Could not find project item ID for issue #$ISSUE_NUMBER${NC}"
    fi
else
    echo -e "\n${BLUE}To work on this issue:${NC}"
    echo -e "  1. Run with --auto-assign flag: ${GREEN}$0 --auto-assign${NC}"
    echo -e "  2. Or manually assign and move to 'In Progress' in the project board"
fi