#!/usr/bin/env bash
set -euo pipefail

# Script to clear/remove status field for ALL issues (set to "No Status")

OWNER="o2alexanderfedin"
REPO="telethon-architecture-docs"
PROJECT_NUMBER=12

echo "🔄 Clearing Status Field for ALL Issues (No Status)..."
echo "===================================================="
echo ""

# Get project configuration
echo "📋 Loading project configuration..."
PROJECT_DATA=$(gh api graphql -H "GraphQL-Features: project_v2" \
  -f query='
    query($owner:String!, $projNum:Int!) {
      user(login:$owner) {
        projectV2(number:$projNum) { 
          id 
          fields(first: 30) {
            nodes {
              ... on ProjectV2SingleSelectField {
                id
                name
              }
            }
          }
        }
      }
    }' \
  -F owner="$OWNER" \
  -F projNum="$PROJECT_NUMBER")

PROJECT_ID=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.id')

# Find Status field (built-in)
STATUS_FIELD_ID=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name == "Status") | .id // empty')

echo "✅ Configuration loaded"
echo ""

# Function to clear status field
clear_item_status() {
    local item_id=$1
    local issue_number=$2
    local issue_type=$3
    
    if [ -n "$STATUS_FIELD_ID" ]; then
        # Clear the field by setting value to null
        gh api graphql -H "GraphQL-Features: project_v2" \
          -f query='
            mutation($projId:ID!, $itemId:ID!, $fieldId:ID!) {
              clearProjectV2ItemFieldValue(input: {
                projectId: $projId,
                itemId: $itemId,
                fieldId: $fieldId
              }) {
                projectV2Item {
                  id
                }
              }
            }' \
          -F projId="$PROJECT_ID" \
          -F itemId="$item_id" \
          -F fieldId="$STATUS_FIELD_ID" > /dev/null 2>&1
        
        echo "  ✅ #$issue_number ($issue_type) - Status cleared (No Status)"
        return 0
    fi
    return 1
}

echo "📝 Clearing status for all project items..."
echo "=========================================="
echo ""

# Get all items with pagination support
CURSOR=""
HAS_NEXT_PAGE="true"
TOTAL_COUNT=0
UPDATED_COUNT=0

# Count by type
declare -a TYPE_COUNTS
TYPE_COUNTS[0]=0  # Epic
TYPE_COUNTS[1]=0  # User Story
TYPE_COUNTS[2]=0  # Task
TYPE_COUNTS[3]=0  # Other

while [ "$HAS_NEXT_PAGE" = "true" ]; do
    # Build query with or without cursor
    if [ -z "$CURSOR" ]; then
        ITEMS_QUERY='query($owner:String!, $projNum:Int!) {
          user(login:$owner) {
            projectV2(number:$projNum) {
              items(first: 100) {
                nodes {
                  id
                  content {
                    ... on Issue {
                      number
                      title
                    }
                  }
                  fieldValues(first: 10) {
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
                pageInfo {
                  hasNextPage
                  endCursor
                }
              }
            }
          }
        }'
        
        ITEMS_DATA=$(gh api graphql -H "GraphQL-Features: project_v2" \
          -f query="$ITEMS_QUERY" \
          -F owner="$OWNER" \
          -F projNum="$PROJECT_NUMBER")
    else
        ITEMS_QUERY='query($owner:String!, $projNum:Int!, $cursor:String!) {
          user(login:$owner) {
            projectV2(number:$projNum) {
              items(first: 100, after: $cursor) {
                nodes {
                  id
                  content {
                    ... on Issue {
                      number
                      title
                    }
                  }
                  fieldValues(first: 10) {
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
                pageInfo {
                  hasNextPage
                  endCursor
                }
              }
            }
          }
        }'
        
        ITEMS_DATA=$(gh api graphql -H "GraphQL-Features: project_v2" \
          -f query="$ITEMS_QUERY" \
          -F owner="$OWNER" \
          -F projNum="$PROJECT_NUMBER" \
          -F cursor="$CURSOR")
    fi
    
    # Process items
    echo "$ITEMS_DATA" | jq -c '.data.user.projectV2.items.nodes[]' | while read -r item; do
        ITEM_ID=$(echo "$item" | jq -r '.id')
        ISSUE_NUMBER=$(echo "$item" | jq -r '.content.number // "unknown"')
        ISSUE_TITLE=$(echo "$item" | jq -r '.content.title // "Draft Item"')
        
        # Get the Type field value
        ISSUE_TYPE=$(echo "$item" | jq -r '.fieldValues.nodes[] | select(.field.name == "Type") | .name // "Unknown"')
        
        # Skip if no content (empty item)
        if [ "$ISSUE_NUMBER" = "unknown" ] && [ "$ISSUE_TITLE" = "Draft Item" ]; then
            continue
        fi
        
        ((TOTAL_COUNT++))
        
        echo "Processing #$ISSUE_NUMBER: $ISSUE_TITLE"
        
        # Clear status
        if clear_item_status "$ITEM_ID" "$ISSUE_NUMBER" "$ISSUE_TYPE"; then
            ((UPDATED_COUNT++))
            
            # Count by type
            case "$ISSUE_TYPE" in
                "Epic") ((TYPE_COUNTS[0]++)) ;;
                "User Story") ((TYPE_COUNTS[1]++)) ;;
                "Task") ((TYPE_COUNTS[2]++)) ;;
                *) ((TYPE_COUNTS[3]++)) ;;
            esac
        fi
        
        # Small delay to avoid rate limits
        sleep 0.1
    done
    
    # Get pagination info
    HAS_NEXT_PAGE=$(echo "$ITEMS_DATA" | jq -r '.data.user.projectV2.items.pageInfo.hasNextPage')
    CURSOR=$(echo "$ITEMS_DATA" | jq -r '.data.user.projectV2.items.pageInfo.endCursor')
    
    if [ "$HAS_NEXT_PAGE" = "true" ]; then
        echo ""
        echo "Getting next page of items..."
        echo ""
    fi
done

echo ""
echo "✅ Status clearing complete!"
echo ""
echo "📊 Summary:"
echo "==========="
echo "Total items processed: $TOTAL_COUNT"
echo "Items cleared: $UPDATED_COUNT"
echo ""
echo "By Type:"
echo "- Epics: ${TYPE_COUNTS[0]}"
echo "- User Stories: ${TYPE_COUNTS[1]}"
echo "- Tasks: ${TYPE_COUNTS[2]}"
echo "- Other: ${TYPE_COUNTS[3]}"
echo ""

# Show current status distribution
echo "📈 Current Status Distribution:"
echo "=============================="

# Count items with no status
NO_STATUS_COUNT=$(gh api graphql -H "GraphQL-Features: project_v2" \
  -f query='
    query($owner:String!, $projNum:Int!) {
      user(login:$owner) {
        projectV2(number:$projNum) {
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
    }' \
  -F owner="$OWNER" \
  -F projNum="$PROJECT_NUMBER" | \
  jq '[.data.user.projectV2.items.nodes[] | select(.fieldValues.nodes | map(select(.field.name == "Status")) | length == 0)] | length')

echo "Items with No Status: $NO_STATUS_COUNT"

# Show any remaining items with status
echo ""
echo "Items still with Status:"
gh api graphql -H "GraphQL-Features: project_v2" \
  -f query='
    query($owner:String!, $projNum:Int!) {
      user(login:$owner) {
        projectV2(number:$projNum) {
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
    }' \
  -F owner="$OWNER" \
  -F projNum="$PROJECT_NUMBER" | \
  jq -r '.data.user.projectV2.items.nodes[].fieldValues.nodes[] | select(.field.name == "Status") | .name' | \
  sort | uniq -c | sort -nr || echo "  None (all cleared)"

echo ""
echo "All issues have been cleared to 'No Status'!"