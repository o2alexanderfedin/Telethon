#!/bin/bash

# add-draft-items.sh
# Adds draft items to a GitHub Project (no repository needed)
# Usage: ./add-draft-items.sh <project-number> <items-file> [--org organization]

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check parameters
if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <project-number> <items-file> [--org <organization>]"
    echo ""
    echo "Items file should be JSON format:"
    echo '[
  {
    "title": "Epic: Feature Name",
    "body": "Description and acceptance criteria",
    "type": "Epic",
    "priority": "High",
    "sprint": "Backlog",
    "points": "8"
  },
  {
    "title": "User Story Title",
    "body": "As a user, I want...",
    "type": "User Story",
    "priority": "Medium",
    "sprint": "Sprint 1",
    "points": "3"
  }
]'
    echo ""
    echo "Example: $0 12 my-items.json"
    exit 1
fi

PROJECT_NUMBER="$1"
ITEMS_FILE="$2"
OWNER_TYPE="user"
OWNER=$(gh api user --jq .login)

# Check for organization flag
if [ "$#" -ge 4 ] && [ "$3" = "--org" ]; then
    OWNER="$4"
    OWNER_TYPE="organization"
fi

# Check if items file exists
if [ ! -f "$ITEMS_FILE" ]; then
    echo -e "${RED}❌ Items file not found: $ITEMS_FILE${NC}"
    exit 1
fi

echo -e "${BLUE}Adding draft items to project #$PROJECT_NUMBER${NC}"
echo ""

# Function to get project info
get_project_info() {
    local query
    if [ "$OWNER_TYPE" = "organization" ]; then
        query="organization(login: \"$OWNER\")"
    else
        query="user(login: \"$OWNER\")"
    fi
    
    gh api graphql -f query="
    query {
      $query {
        projectV2(number: $PROJECT_NUMBER) {
          id
          title
          fields(first: 20) {
            nodes {
              ... on ProjectV2Field {
                id
                name
              }
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
    }"
}

echo -n "Getting project information... "
PROJECT_INFO=$(get_project_info)
PROJECT_ID=$(echo "$PROJECT_INFO" | jq -r ".data.$OWNER_TYPE.projectV2.id")
PROJECT_TITLE=$(echo "$PROJECT_INFO" | jq -r ".data.$OWNER_TYPE.projectV2.title")

if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "null" ]; then
    echo -e "${RED}❌ Failed to find project${NC}"
    exit 1
fi

echo -e "${GREEN}✅${NC}"
echo "Project: $PROJECT_TITLE"

# Extract field IDs
extract_field_id() {
    echo "$PROJECT_INFO" | jq -r ".data.$OWNER_TYPE.projectV2.fields.nodes[] | select(.name == \"$1\") | .id"
}

extract_option_id() {
    local field_name=$1
    local option_name=$2
    echo "$PROJECT_INFO" | jq -r ".data.$OWNER_TYPE.projectV2.fields.nodes[] | select(.name == \"$field_name\") | .options[] | select(.name == \"$option_name\") | .id"
}

# Get field IDs
TYPE_FIELD_ID=$(extract_field_id "Type")
PRIORITY_FIELD_ID=$(extract_field_id "Priority")
SPRINT_FIELD_ID=$(extract_field_id "Sprint")
STATUS_FIELD_ID=$(extract_field_id "Status")
POINTS_FIELD_ID=$(extract_field_id "Story Points")

# Function to create a draft item
create_draft_item() {
    local title=$1
    local body=$2
    
    ITEM_ID=$(gh api graphql -f query="
    mutation {
      addProjectV2DraftIssue(input: {
        projectId: \"$PROJECT_ID\"
        title: \"$title\"
        body: \"$body\"
      }) {
        projectV2Item {
          id
        }
      }
    }" --jq '.data.addProjectV2DraftIssue.projectV2Item.id' 2>&1)
    
    if [ $? -eq 0 ]; then
        echo "$ITEM_ID"
    else
        echo ""
    fi
}

# Function to update item field
update_item_field() {
    local item_id=$1
    local field_id=$2
    local option_id=$3
    
    if [ -z "$field_id" ] || [ -z "$option_id" ]; then
        return 1
    fi
    
    gh api graphql -f query="
    mutation {
      updateProjectV2ItemFieldValue(input: {
        projectId: \"$PROJECT_ID\"
        itemId: \"$item_id\"
        fieldId: \"$field_id\"
        value: {
          singleSelectOptionId: \"$option_id\"
        }
      }) {
        projectV2Item {
          id
        }
      }
    }" > /dev/null 2>&1
}

# Read and process items
echo -e "${YELLOW}Creating draft items...${NC}"

TOTAL=0
SUCCESS=0
FAILED=0

# Read JSON file and process each item
while IFS= read -r item; do
    TITLE=$(echo "$item" | jq -r '.title // empty')
    BODY=$(echo "$item" | jq -r '.body // empty')
    TYPE=$(echo "$item" | jq -r '.type // "Task"')
    PRIORITY=$(echo "$item" | jq -r '.priority // "Medium"')
    SPRINT=$(echo "$item" | jq -r '.sprint // "Backlog"')
    POINTS=$(echo "$item" | jq -r '.points // "3"')
    
    if [ -z "$TITLE" ]; then
        continue
    fi
    
    TOTAL=$((TOTAL + 1))
    echo -n "[$TOTAL] Creating: $TITLE... "
    
    # Create the draft item
    ITEM_ID=$(create_draft_item "$TITLE" "$BODY")
    
    if [ -z "$ITEM_ID" ]; then
        echo -e "${RED}❌ Failed${NC}"
        FAILED=$((FAILED + 1))
        continue
    fi
    
    echo -n "configuring... "
    
    # Set field values
    if [ -n "$TYPE_FIELD_ID" ]; then
        TYPE_OPTION=$(extract_option_id "Type" "$TYPE")
        update_item_field "$ITEM_ID" "$TYPE_FIELD_ID" "$TYPE_OPTION"
    fi
    
    if [ -n "$PRIORITY_FIELD_ID" ]; then
        PRIORITY_OPTION=$(extract_option_id "Priority" "$PRIORITY")
        update_item_field "$ITEM_ID" "$PRIORITY_FIELD_ID" "$PRIORITY_OPTION"
    fi
    
    if [ -n "$SPRINT_FIELD_ID" ]; then
        SPRINT_OPTION=$(extract_option_id "Sprint" "$SPRINT")
        update_item_field "$ITEM_ID" "$SPRINT_FIELD_ID" "$SPRINT_OPTION"
    fi
    
    if [ -n "$STATUS_FIELD_ID" ]; then
        STATUS_OPTION=$(extract_option_id "Status" "Todo")
        update_item_field "$ITEM_ID" "$STATUS_FIELD_ID" "$STATUS_OPTION"
    fi
    
    if [ -n "$POINTS_FIELD_ID" ]; then
        POINTS_OPTION=$(extract_option_id "Story Points" "$POINTS")
        update_item_field "$ITEM_ID" "$POINTS_FIELD_ID" "$POINTS_OPTION"
    fi
    
    echo -e "${GREEN}✅${NC}"
    SUCCESS=$((SUCCESS + 1))
    
    # Small delay to avoid rate limits
    sleep 0.3
done < <(jq -c '.[]' "$ITEMS_FILE")

# Summary
echo ""
echo -e "${BLUE}=========================================${NC}"
echo -e "${GREEN}✅ IMPORT COMPLETE!${NC}"
echo -e "${BLUE}=========================================${NC}"
echo -e "Total items: $TOTAL"
echo -e "Successfully created: ${GREEN}$SUCCESS${NC}"
if [ $FAILED -gt 0 ]; then
    echo -e "Failed: ${RED}$FAILED${NC}"
fi
echo ""
echo -e "${YELLOW}Project URL:${NC}"
if [ "$OWNER_TYPE" = "organization" ]; then
    echo "https://github.com/orgs/$OWNER/projects/$PROJECT_NUMBER"
else
    echo "https://github.com/users/$OWNER/projects/$PROJECT_NUMBER"
fi
echo -e "${BLUE}=========================================${NC}"