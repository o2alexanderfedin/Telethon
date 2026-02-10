#!/usr/bin/env bash
set -euo pipefail

# Direct Epic Creation Script
# Creates epics directly as repository issues, then adds them to the project
# This bypasses the draft creation and conversion step that's causing issues

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
OWNER="o2alexanderfedin"
REPO="Telethon"
PROJECT_NUMBER=12
EPICS_FILE="/Users/alexanderfedin/Projects/demo/workspace/Telethon/docs/architecture/documentation/voice-transcription-feature/epics.json"

# Rate limiting configuration
CREATION_DELAY=2

echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}       DIRECT EPIC CREATION SCRIPT      ${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""

# Check if epics file exists
if [ ! -f "$EPICS_FILE" ]; then
    echo -e "${RED}❌ Epics file not found: $EPICS_FILE${NC}"
    exit 1
fi

echo "Configuration:"
echo "  Owner: $OWNER"
echo "  Repository: $REPO"  
echo "  Project: #$PROJECT_NUMBER"
echo "  Epics file: $EPICS_FILE"
echo ""

# Step 1: Get project information
echo -e "${YELLOW}Step 1: Getting project information...${NC}"
PROJECT_INFO=$(gh api graphql -f query='
query($owner:String!, $projNum:Int!) {
  user(login:$owner) {
    projectV2(number:$projNum) {
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
}' -F owner="$OWNER" -F projNum="$PROJECT_NUMBER" 2>&1)

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to get project information${NC}"
    echo "$PROJECT_INFO"
    exit 1
fi

PROJECT_ID=$(echo "$PROJECT_INFO" | jq -r '.data.user.projectV2.id')
PROJECT_TITLE=$(echo "$PROJECT_INFO" | jq -r '.data.user.projectV2.title')

if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "null" ]; then
    echo -e "${RED}❌ Could not extract project ID${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Project: $PROJECT_TITLE (ID: $PROJECT_ID)${NC}"

# Extract field IDs
TYPE_FIELD_ID=$(echo "$PROJECT_INFO" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name == "Type") | .id')
EPIC_OPTION_ID=$(echo "$PROJECT_INFO" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name == "Type") | .options[]? | select(.name == "Epic") | .id')

echo "  Type Field ID: ${TYPE_FIELD_ID:-'NOT FOUND'}"
echo "  Epic Option ID: ${EPIC_OPTION_ID:-'NOT FOUND'}"
echo ""

# Function to create repository issue
create_repository_issue() {
    local title="$1"
    local body="$2"
    
    echo -n "  Creating repository issue... "
    
    ISSUE_RESULT=$(gh api repos/"$OWNER"/"$REPO"/issues \
        --method POST \
        --field title="$title" \
        --field body="$body" \
        --field labels='["epic"]' 2>&1)
    
    if [ $? -eq 0 ]; then
        ISSUE_NUMBER=$(echo "$ISSUE_RESULT" | jq -r '.number')
        ISSUE_NODE_ID=$(echo "$ISSUE_RESULT" | jq -r '.node_id')
        echo -e "${GREEN}✅ Issue #$ISSUE_NUMBER${NC}"
        echo "$ISSUE_NODE_ID"
        return 0
    else
        echo -e "${RED}❌ Failed${NC}"
        echo "Error: $ISSUE_RESULT" >&2
        return 1
    fi
}

# Function to add issue to project
add_issue_to_project() {
    local issue_node_id="$1"
    local issue_number="$2"
    
    echo -n "  Adding to project... "
    
    ADD_RESULT=$(gh api graphql -f query='
    mutation($projectId:ID!, $contentId:ID!) {
      addProjectV2ItemByContentId(input: {
        projectId: $projectId
        contentId: $contentId
      }) {
        item {
          id
        }
      }
    }' -F projectId="$PROJECT_ID" -F contentId="$issue_node_id" 2>&1)
    
    if [ $? -eq 0 ]; then
        ITEM_ID=$(echo "$ADD_RESULT" | jq -r '.data.addProjectV2ItemByContentId.item.id')
        if [ -n "$ITEM_ID" ] && [ "$ITEM_ID" != "null" ]; then
            echo -e "${GREEN}✅ Added (Item ID: $ITEM_ID)${NC}"
            echo "$ITEM_ID"
            return 0
        else
            echo -e "${RED}❌ Failed to get item ID${NC}"
            return 1
        fi
    else
        echo -e "${RED}❌ Failed${NC}"
        echo "Error: $ADD_RESULT" >&2
        return 1
    fi
}

# Function to set item type to Epic
set_item_type() {
    local item_id="$1"
    
    if [ -z "$TYPE_FIELD_ID" ] || [ -z "$EPIC_OPTION_ID" ]; then
        echo -e "  ${YELLOW}⚠️  Skipping type setting (field/option not found)${NC}"
        return 0
    fi
    
    echo -n "  Setting type to Epic... "
    
    TYPE_RESULT=$(gh api graphql -f query='
    mutation($projectId:ID!, $itemId:ID!, $fieldId:ID!, $optionId:String!) {
      updateProjectV2ItemFieldValue(input: {
        projectId: $projectId
        itemId: $itemId
        fieldId: $fieldId
        value: {
          singleSelectOptionId: $optionId
        }
      }) {
        projectV2Item {
          id
        }
      }
    }' -F projectId="$PROJECT_ID" -F itemId="$item_id" -F fieldId="$TYPE_FIELD_ID" -F optionId="$EPIC_OPTION_ID" 2>&1)
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️  Failed${NC}"
        return 1
    fi
}

# Step 2: Process epics
echo -e "${YELLOW}Step 2: Processing epics...${NC}"

TOTAL=0
SUCCESS=0
FAILED=0

# Read and process each epic
while IFS= read -r epic; do
    EPIC_TITLE=$(echo "$epic" | jq -r '.title')
    
    if [ -z "$EPIC_TITLE" ]; then
        continue
    fi
    
    TOTAL=$((TOTAL + 1))
    echo ""
    echo -e "${CYAN}Processing Epic $TOTAL: $EPIC_TITLE${NC}"
    echo "----------------------------------------"
    
    # Create epic body from documentation references
    EPIC_BODY="Epic: $EPIC_TITLE"$'\n\n'
    
    # Add documentation links if available
    ANALYSIS_DOC=$(echo "$epic" | jq -r '.documentation.analysis // empty')
    if [ -n "$ANALYSIS_DOC" ]; then
        EPIC_BODY="${EPIC_BODY}📋 Analysis: $ANALYSIS_DOC"$'\n'
    fi
    
    TECHNICAL_DOC=$(echo "$epic" | jq -r '.documentation.technical // empty')
    if [ -n "$TECHNICAL_DOC" ]; then
        EPIC_BODY="${EPIC_BODY}🏗️ Technical: $TECHNICAL_DOC"$'\n'
    fi
    
    EPIC_BODY="${EPIC_BODY}"$'\n'"This epic was created as part of the Voice Transcription feature implementation."
    
    # Create repository issue
    ISSUE_NODE_ID=$(create_repository_issue "$EPIC_TITLE" "$EPIC_BODY")
    if [ $? -ne 0 ]; then
        FAILED=$((FAILED + 1))
        continue
    fi
    
    ISSUE_NUMBER=$(gh api graphql -f query='
    query($nodeId:ID!) {
      node(id: $nodeId) {
        ... on Issue {
          number
        }
      }
    }' -F nodeId="$ISSUE_NODE_ID" --jq '.data.node.number' 2>/dev/null)
    
    # Add to project
    ITEM_ID=$(add_issue_to_project "$ISSUE_NODE_ID" "$ISSUE_NUMBER")
    if [ $? -ne 0 ]; then
        echo -e "  ${YELLOW}⚠️  Issue created but not added to project${NC}"
        FAILED=$((FAILED + 1))
        continue
    fi
    
    # Set type to Epic
    set_item_type "$ITEM_ID"
    
    echo -e "  ${GREEN}✅ Epic successfully created and configured${NC}"
    SUCCESS=$((SUCCESS + 1))
    
    # Rate limiting delay
    sleep $CREATION_DELAY
    
done < <(jq -c '.[]' "$EPICS_FILE")

# Final summary
echo ""
echo -e "${BLUE}=========================================${NC}"
echo -e "${GREEN}✅ DIRECT EPIC CREATION COMPLETE!${NC}"
echo -e "${BLUE}=========================================${NC}"
echo -e "Total epics processed: $TOTAL"
echo -e "Successfully created: ${GREEN}$SUCCESS${NC}"
if [ $FAILED -gt 0 ]; then
    echo -e "Failed: ${RED}$FAILED${NC}"
fi
echo ""
echo -e "${YELLOW}Project URL:${NC}"
echo "https://github.com/users/$OWNER/projects/$PROJECT_NUMBER"
echo ""
echo -e "${YELLOW}Repository Issues:${NC}"
echo "https://github.com/$OWNER/$REPO/issues"
echo -e "${BLUE}=========================================${NC}"