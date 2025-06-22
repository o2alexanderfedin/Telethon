#!/bin/bash

# Script: check-wip-limits.sh
# Purpose: Check current WIP limits across all Kanban columns
# Usage: ./check-wip-limits.sh

set -euo pipefail

# Configuration
PROJECT_OWNER="o2alexanderfedin"
PROJECT_NUMBER="1"

# WIP Limits
WIP_LIMITS=(
    "In Progress:3"
    "In Review:2"
    "Testing:2"
)

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Get project ID
PROJECT_ID=$(gh api graphql -f query='
  query($owner: String!, $number: Int!) {
    user(login: $owner) {
      projectV2(number: $number) {
        id
      }
    }
  }' -f owner="$PROJECT_OWNER" -f number="$PROJECT_NUMBER" --jq '.data.user.projectV2.id')

echo -e "${BLUE}=== WIP Limit Status ===${NC}\n"

# Get all items with their status
ITEMS=$(gh api graphql -f query='
  query($projectId: ID!) {
    node(id: $projectId) {
      ... on ProjectV2 {
        items(first: 100) {
          nodes {
            content {
              ... on Issue {
                number
                title
              }
            }
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
  }' -f projectId="$PROJECT_ID")

# Check each WIP limit
for limit in "${WIP_LIMITS[@]}"; do
    IFS=':' read -r status max_count <<< "$limit"
    
    # Count items in this status
    count=$(echo "$ITEMS" | jq -r --arg status "$status" '
        [.data.node.items.nodes[] | 
         select(.fieldValues.nodes[] | 
         select(.field.name == "Status" and .name == $status))] | length')
    
    # Display status
    if [ "$count" -lt "$max_count" ]; then
        echo -e "${GREEN}✅ $status: $count/$max_count${NC}"
    elif [ "$count" -eq "$max_count" ]; then
        echo -e "${YELLOW}⚠️  $status: $count/$max_count (at limit)${NC}"
    else
        echo -e "${RED}❌ $status: $count/$max_count (OVER LIMIT!)${NC}"
    fi
    
    # Show items if at or over limit
    if [ "$count" -ge "$max_count" ]; then
        echo "$ITEMS" | jq -r --arg status "$status" '
            .data.node.items.nodes[] | 
            select(.fieldValues.nodes[] | 
            select(.field.name == "Status" and .name == $status)) | 
            "   - #\(.content.number): \(.content.title)"'
    fi
    echo
done

# Overall health check
TOTAL_WIP=$(echo "$ITEMS" | jq -r '
    [.data.node.items.nodes[] | 
     select(.fieldValues.nodes[] | 
     select(.field.name == "Status" and 
     (.name == "In Progress" or .name == "In Review" or .name == "Testing")))] | length')

echo -e "${BLUE}Total Active Items: $TOTAL_WIP${NC}"

if [ "$TOTAL_WIP" -gt 7 ]; then
    echo -e "${YELLOW}Consider focusing on completing work before starting new items.${NC}"
fi