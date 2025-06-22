#!/usr/bin/env bash
set -euo pipefail

# Script to reset status field for all tasks to a default value

OWNER="o2alexanderfedin"
REPO="telethon-architecture-docs"
PROJECT_NUMBER=12

echo "🔄 Resetting Status Field for All Tasks..."
echo "========================================"
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
                options {
                  id
                  name
                }
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

# Get Todo option ID for Status field
TODO_ID=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name == "Status") | .options[] | select(.name == "Todo") | .id // empty')

echo "✅ Configuration loaded"
echo ""

# Function to update status field
update_task_status() {
    local item_id=$1
    local task_number=$2
    local field_id=$3
    local option_id=$4
    local field_name=$5
    
    if [ -n "$field_id" ] && [ -n "$option_id" ]; then
        gh api graphql -H "GraphQL-Features: project_v2" \
          -f query='
            mutation($projId:ID!, $itemId:ID!, $fieldId:ID!, $value:String!) {
              updateProjectV2ItemFieldValue(input: {
                projectId: $projId,
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
            }' \
          -F projId="$PROJECT_ID" \
          -F itemId="$item_id" \
          -F fieldId="$field_id" \
          -F value="$option_id" > /dev/null 2>&1
        
        echo "  ✅ #$task_number - $field_name reset to Todo"
    fi
}

echo "📝 Resetting status for all tasks..."
echo "==================================="
echo ""

# Get all tasks (items with Type = Task)
TASKS_DATA=$(gh api graphql -H "GraphQL-Features: project_v2" \
  -f query='
    query($owner:String!, $projNum:Int!) {
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
    }' \
  -F owner="$OWNER" \
  -F projNum="$PROJECT_NUMBER")

# Process tasks in batches
echo "Processing tasks..."
TASK_COUNT=0
UPDATED_COUNT=0

# Extract tasks and update status
echo "$TASKS_DATA" | jq -c '.data.user.projectV2.items.nodes[]' | while read -r item; do
    # Check if it's a Task
    IS_TASK=$(echo "$item" | jq -r '.fieldValues.nodes[] | select(.field.name == "Type" and .name == "Task") | .name // empty')
    
    if [ "$IS_TASK" = "Task" ]; then
        ITEM_ID=$(echo "$item" | jq -r '.id')
        TASK_NUMBER=$(echo "$item" | jq -r '.content.number // "unknown"')
        TASK_TITLE=$(echo "$item" | jq -r '.content.title // "Draft Task"')
        
        ((TASK_COUNT++))
        
        echo -n "Task #$TASK_NUMBER: $TASK_TITLE"
        echo ""
        
        # Update Status field if it exists
        if [ -n "$STATUS_FIELD_ID" ] && [ -n "$TODO_ID" ]; then
            update_task_status "$ITEM_ID" "$TASK_NUMBER" "$STATUS_FIELD_ID" "$TODO_ID" "Status"
            ((UPDATED_COUNT++))
        fi
        
        # Small delay to avoid rate limits
        sleep 0.1
    fi
done

# Check if we need to get more pages
HAS_NEXT_PAGE=$(echo "$TASKS_DATA" | jq -r '.data.user.projectV2.items.pageInfo.hasNextPage')
CURSOR=$(echo "$TASKS_DATA" | jq -r '.data.user.projectV2.items.pageInfo.endCursor')

# Get remaining tasks if there are more pages
while [ "$HAS_NEXT_PAGE" = "true" ]; do
    echo "Getting next page of tasks..."
    
    TASKS_DATA=$(gh api graphql -H "GraphQL-Features: project_v2" \
      -f query='
        query($owner:String!, $projNum:Int!, $cursor:String!) {
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
        }' \
      -F owner="$OWNER" \
      -F projNum="$PROJECT_NUMBER" \
      -F cursor="$CURSOR")
    
    # Process this batch
    echo "$TASKS_DATA" | jq -c '.data.user.projectV2.items.nodes[]' | while read -r item; do
        IS_TASK=$(echo "$item" | jq -r '.fieldValues.nodes[] | select(.field.name == "Type" and .name == "Task") | .name // empty')
        
        if [ "$IS_TASK" = "Task" ]; then
            ITEM_ID=$(echo "$item" | jq -r '.id')
            TASK_NUMBER=$(echo "$item" | jq -r '.content.number // "unknown"')
            TASK_TITLE=$(echo "$item" | jq -r '.content.title // "Draft Task"')
            
            ((TASK_COUNT++))
            
            echo -n "Task #$TASK_NUMBER: $TASK_TITLE"
            echo ""
            
            # Update status field
            if [ -n "$STATUS_FIELD_ID" ] && [ -n "$TODO_ID" ]; then
                update_task_status "$ITEM_ID" "$TASK_NUMBER" "$STATUS_FIELD_ID" "$TODO_ID" "Status"
                ((UPDATED_COUNT++))
            fi
            
            sleep 0.1
        fi
    done
    
    HAS_NEXT_PAGE=$(echo "$TASKS_DATA" | jq -r '.data.user.projectV2.items.pageInfo.hasNextPage')
    CURSOR=$(echo "$TASKS_DATA" | jq -r '.data.user.projectV2.items.pageInfo.endCursor')
done

echo ""
echo "✅ Status reset complete!"
echo ""
echo "Summary:"
echo "- Total tasks found: $TASK_COUNT"
echo "- Status fields updated: $((UPDATED_COUNT > 0 ? UPDATED_COUNT : TASK_COUNT))"
echo ""

# Show current status distribution
echo "📊 Verifying status distribution..."
echo ""

if [ -n "$STATUS_FIELD_ID" ]; then
    echo "Status field distribution:"
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
      sort | uniq -c | sort -nr
fi

echo ""
echo "All tasks have been reset to 'Todo' status!"