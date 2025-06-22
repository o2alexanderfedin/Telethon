#!/bin/bash

# Script: get-next-kanban-item.sh
# Purpose: Automatically select the next work item based on Kanban rules
# Usage: ./get-next-kanban-item.sh [--auto-assign]

set -euo pipefail

# Configuration
PROJECT_OWNER="o2alexanderfedin"
PROJECT_NUMBER="1"
MAX_WIP=3

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

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

# Get project ID
echo -e "\n${BLUE}Fetching project information...${NC}"
PROJECT_ID=$(gh api graphql -f query='
  query($owner: String!, $number: Int!) {
    user(login: $owner) {
      projectV2(number: $number) {
        id
      }
    }
  }' -f owner="$PROJECT_OWNER" -f number="$PROJECT_NUMBER" --jq '.data.user.projectV2.id')

# Get current WIP count
echo -e "${BLUE}Checking current Work In Progress...${NC}"
CURRENT_WIP=$(gh api graphql -f query='
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
  }' -f projectId="$PROJECT_ID" --jq '[.data.node.items.nodes[].fieldValues.nodes[] | select(.field.name == "Status" and .name == "In Progress")] | length')

echo -e "Current WIP: ${YELLOW}$CURRENT_WIP${NC} / $MAX_WIP"

if [ "$CURRENT_WIP" -ge "$MAX_WIP" ]; then
    echo -e "${RED}❌ WIP limit reached! Complete current work before pulling new items.${NC}"
    echo -e "\nCurrent items in progress:"
    gh api graphql -f query='
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
      }' -f projectId="$PROJECT_ID" --jq '.data.node.items.nodes[] | select(.fieldValues.nodes[] | select(.field.name == "Status" and .name == "In Progress")) | "\(.content.number): \(.content.title)"'
    exit 1
fi

# Check for blocked items
echo -e "\n${BLUE}Checking for blocked items...${NC}"
BLOCKED_ITEMS=$(gh api graphql -f query='
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
  }' -f projectId="$PROJECT_ID" --jq '[.data.node.items.nodes[] | select(.fieldValues.nodes[] | select(.field.name == "Dependency Status" and .name == "Blocked"))] | length')

if [ "$BLOCKED_ITEMS" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Found $BLOCKED_ITEMS blocked items that may need attention:${NC}"
    gh api graphql -f query='
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
      }' -f projectId="$PROJECT_ID" --jq '.data.node.items.nodes[] | select(.fieldValues.nodes[] | select(.field.name == "Dependency Status" and .name == "Blocked")) | "  - #\(.content.number): \(.content.title)"'
fi

# Find next available item
echo -e "\n${BLUE}Finding next available work item...${NC}"
NEXT_ITEM=$(gh api graphql -f query='
  query($projectId: ID!) {
    node(id: $projectId) {
      ... on ProjectV2 {
        items(first: 100) {
          nodes {
            id
            content {
              ... on Issue {
                number
                title
                body
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
                ... on ProjectV2ItemFieldNumberValue {
                  number
                  field {
                    ... on ProjectV2Field {
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
  select(
    (.fieldValues.nodes[] | select(.field.name == "Status" and .name == "Todo")) and
    ((.fieldValues.nodes[] | select(.field.name == "Dependency Status" and (.name == "Ready" or .name == "Partial"))) or 
     (.fieldValues.nodes | map(select(.field.name == "Dependency Status")) | length == 0))
  ) |
  {
    id: .id,
    number: .content.number,
    title: .content.title,
    body: .content.body,
    type: (.content.labels.nodes[] | select(.name | test("Type:")) | .name),
    priority: (.content.labels.nodes[] | select(.name | test("Priority:")) | .name),
    points: (.fieldValues.nodes[] | select(.field.name == "Story Points") | .number)
  }' | jq -s 'sort_by(.priority // "Priority: Medium", .points // 0) | reverse | first')

if [ -z "$NEXT_ITEM" ] || [ "$NEXT_ITEM" = "null" ]; then
    echo -e "${YELLOW}No available items found in Todo status with satisfied dependencies.${NC}"
    echo -e "\nSuggestions:"
    echo -e "  1. Check if there are items in 'Ready' status"
    echo -e "  2. Review blocked items to see if any can be unblocked"
    echo -e "  3. Check if all Todo items have unsatisfied dependencies"
    exit 0
fi

# Parse the next item
ITEM_NUMBER=$(echo "$NEXT_ITEM" | jq -r '.number')
ITEM_TITLE=$(echo "$NEXT_ITEM" | jq -r '.title')
ITEM_TYPE=$(echo "$NEXT_ITEM" | jq -r '.type // "Unknown"')
ITEM_PRIORITY=$(echo "$NEXT_ITEM" | jq -r '.priority // "Priority: Medium"')
ITEM_POINTS=$(echo "$NEXT_ITEM" | jq -r '.points // "Not set"')
ITEM_ID=$(echo "$NEXT_ITEM" | jq -r '.id')

echo -e "\n${GREEN}✅ Next recommended work item:${NC}"
echo -e "Issue #$ITEM_NUMBER: $ITEM_TITLE"
echo -e "Type: $ITEM_TYPE"
echo -e "Priority: $ITEM_PRIORITY"
echo -e "Story Points: $ITEM_POINTS"
echo -e "\nView details: ${BLUE}https://github.com/$PROJECT_OWNER/telethon-architecture-docs/issues/$ITEM_NUMBER${NC}"

# Auto-assign if requested
if [ "${1:-}" = "--auto-assign" ]; then
    echo -e "\n${BLUE}Auto-assigning item to 'In Progress'...${NC}"
    
    # Get Status field ID and In Progress option ID
    FIELD_DATA=$(gh api graphql -f query='
      query($projectId: ID!) {
        node(id: $projectId) {
          ... on ProjectV2 {
            fields(first: 20) {
              nodes {
                ... on ProjectV2SingleSelectField {
                  id
                  name
                  options {
                    id
                    name
                  }
                }
              }
            }
          }
        }
      }' -f projectId="$PROJECT_ID" --jq '.data.node.fields.nodes[] | select(.name == "Status")')
    
    FIELD_ID=$(echo "$FIELD_DATA" | jq -r '.id')
    IN_PROGRESS_ID=$(echo "$FIELD_DATA" | jq -r '.options[] | select(.name == "In Progress") | .id')
    
    # Update the item status
    gh api graphql -f query='
      mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $value: String!) {
        updateProjectV2ItemFieldValue(input: {
          projectId: $projectId,
          itemId: $itemId,
          fieldId: $fieldId,
          value: {
            singleSelectOptionId: $value
          }
        }) {
          projectV2Item {
            id
          }
        }
      }' -f projectId="$PROJECT_ID" -f itemId="$ITEM_ID" -f fieldId="$FIELD_ID" -f value="$IN_PROGRESS_ID" > /dev/null
    
    echo -e "${GREEN}✅ Item assigned to 'In Progress'${NC}"
    echo -e "\nRemember to:"
    echo -e "  - Read the full description and acceptance criteria"
    echo -e "  - Check linked documentation"
    echo -e "  - Create a feature branch for your work"
fi

echo -e "\n${BLUE}Happy coding! 🚀${NC}"