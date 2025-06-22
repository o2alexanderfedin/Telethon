#!/bin/bash

# Script: list-blocked-items.sh
# Purpose: List all blocked items with their blocking reasons
# Usage: ./list-blocked-items.sh

set -euo pipefail

# Configuration
PROJECT_OWNER="o2alexanderfedin"
PROJECT_NUMBER="1"

# Colors
RED='\033[0;31m'
YELLOW='\033[1;33m'
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

echo -e "${RED}=== Blocked Items ===${NC}\n"

# Get blocked items
BLOCKED=$(gh api graphql -f query='
  query($projectId: ID!) {
    node(id: $projectId) {
      ... on ProjectV2 {
        items(first: 100) {
          nodes {
            content {
              ... on Issue {
                number
                title
                body
                comments(last: 5) {
                  nodes {
                    body
                    createdAt
                  }
                }
                labels(first: 10) {
                  nodes {
                    name
                  }
                }
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
  }' -f projectId="$PROJECT_ID" --jq '
  .data.node.items.nodes[] |
  select(.fieldValues.nodes[] | select(.field.name == "Dependency Status" and .name == "Blocked")) |
  {
    number: .content.number,
    title: .content.title,
    body: .content.body,
    type: (.content.labels.nodes[] | select(.name | test("Type:")) | .name),
    priority: (.content.labels.nodes[] | select(.name | test("Priority:")) | .name),
    lastComment: (.content.comments.nodes | last | .body // "No recent comments")
  }')

if [ -z "$BLOCKED" ]; then
    echo -e "${BLUE}No blocked items found! 🎉${NC}"
    exit 0
fi

# Display blocked items
echo "$BLOCKED" | jq -r '. | 
    "Issue #\(.number): \(.title)\n" +
    "Type: \(.type // "Not specified")\n" +
    "Priority: \(.priority // "Not specified")\n" +
    "\nBlocking Reason (from description or last comment):\n" +
    if (.body | test("block|depend|wait"; "i")) then
        (.body | split("\n") | map(select(test("block|depend|wait"; "i"))) | first // "See issue for details")
    else
        "Check comments or update description with blocking reason"
    end +
    "\n\n---\n"'

# Summary
BLOCKED_COUNT=$(echo "$BLOCKED" | jq -s 'length')
echo -e "${YELLOW}Total blocked items: $BLOCKED_COUNT${NC}"

# Suggestions
echo -e "\n${BLUE}Suggestions to unblock:${NC}"
echo "1. Review dependencies and see if any are now complete"
echo "2. Check if blocked items can be partially started"
echo "3. Communicate with team members working on dependencies"
echo "4. Consider re-prioritizing or breaking down blocked items"