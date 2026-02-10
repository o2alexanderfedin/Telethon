#!/usr/bin/env bash
set -euo pipefail

# Minimal test script to create a single epic
# This script tests the epic creation process step by step

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
OWNER="o2alexanderfedin"
REPO="telethon-architecture-docs"
PROJECT_NUMBER=12

echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}      SINGLE EPIC CREATION TEST         ${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""

# Test epic data
TEST_TITLE="Test Epic: API Integration"
TEST_BODY="This is a test epic to verify the creation and conversion process works correctly.

## Objectives
- Test draft creation
- Test field assignment
- Test conversion to repository issue

## Success Criteria
- Draft item created successfully
- Type field set to 'Epic'
- Successfully converted to repository issue"

echo "Test epic: $TEST_TITLE"
echo ""

# Step 1: Check GitHub CLI authentication
echo -e "${YELLOW}Step 1: Checking GitHub CLI authentication...${NC}"
if ! gh auth status > /dev/null 2>&1; then
    echo -e "${RED}❌ GitHub CLI not authenticated${NC}"
    echo "Please run: gh auth login"
    exit 1
fi
echo -e "${GREEN}✅ GitHub CLI authenticated${NC}"
echo ""

# Step 2: Get project information
echo -e "${YELLOW}Step 2: Getting project information...${NC}"
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
    echo "Error: $PROJECT_INFO"
    exit 1
fi

PROJECT_ID=$(echo "$PROJECT_INFO" | jq -r '.data.user.projectV2.id')
PROJECT_TITLE=$(echo "$PROJECT_INFO" | jq -r '.data.user.projectV2.title')

if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "null" ]; then
    echo -e "${RED}❌ Could not extract project ID${NC}"
    echo "Response: $PROJECT_INFO"
    exit 1
fi

echo -e "${GREEN}✅ Project: $PROJECT_TITLE${NC}"
echo "   Project ID: $PROJECT_ID"
echo ""

# Step 3: Get repository information
echo -e "${YELLOW}Step 3: Getting repository information...${NC}"
REPO_INFO=$(gh api graphql -f query='
query($owner:String!, $repo:String!) {
  repository(owner:$owner, name:$repo) {
    id
  }
}' -F owner="$OWNER" -F repo="$REPO" 2>&1)

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to get repository information${NC}"
    echo "Error: $REPO_INFO"
    exit 1
fi

REPO_ID=$(echo "$REPO_INFO" | jq -r '.data.repository.id')

if [ -z "$REPO_ID" ] || [ "$REPO_ID" = "null" ]; then
    echo -e "${RED}❌ Could not extract repository ID${NC}"
    echo "Response: $REPO_INFO"
    exit 1
fi

echo -e "${GREEN}✅ Repository: $REPO${NC}"
echo "   Repository ID: $REPO_ID"
echo ""

# Step 4: Extract field information
echo -e "${YELLOW}Step 4: Extracting field information...${NC}"
TYPE_FIELD_ID=$(echo "$PROJECT_INFO" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name == "Type") | .id')
EPIC_OPTION_ID=$(echo "$PROJECT_INFO" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name == "Type") | .options[]? | select(.name == "Epic") | .id')

echo "   Type Field ID: ${TYPE_FIELD_ID:-'NOT FOUND'}"
echo "   Epic Option ID: ${EPIC_OPTION_ID:-'NOT FOUND'}"

if [ -z "$TYPE_FIELD_ID" ]; then
    echo -e "${YELLOW}⚠️  Type field not found. Available fields:${NC}"
    echo "$PROJECT_INFO" | jq -r '.data.user.projectV2.fields.nodes[].name' | sed 's/^/     - /'
fi

if [ -z "$EPIC_OPTION_ID" ] && [ -n "$TYPE_FIELD_ID" ]; then
    echo -e "${YELLOW}⚠️  Epic option not found. Available Type options:${NC}"
    echo "$PROJECT_INFO" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name == "Type") | .options[]?.name' | sed 's/^/     - /'
fi
echo ""

# Step 5: Create draft item
echo -e "${YELLOW}Step 5: Creating draft item...${NC}"
DRAFT_RESULT=$(gh api graphql -f query='
mutation($projectId:ID!, $title:String!, $body:String!) {
  addProjectV2DraftIssue(input: {
    projectId: $projectId
    title: $title
    body: $body
  }) {
    projectV2Item {
      id
    }
  }
}' -F projectId="$PROJECT_ID" -F title="$TEST_TITLE" -F body="$TEST_BODY" 2>&1)

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to create draft item${NC}"
    echo "Error: $DRAFT_RESULT"
    exit 1
fi

ITEM_ID=$(echo "$DRAFT_RESULT" | jq -r '.data.addProjectV2DraftIssue.projectV2Item.id')

if [ -z "$ITEM_ID" ] || [ "$ITEM_ID" = "null" ]; then
    echo -e "${RED}❌ Failed to extract item ID${NC}"
    echo "Response: $DRAFT_RESULT"
    exit 1
fi

echo -e "${GREEN}✅ Draft item created${NC}"
echo "   Item ID: $ITEM_ID"
echo ""

# Step 6: Set type to Epic (if possible)
if [ -n "$TYPE_FIELD_ID" ] && [ -n "$EPIC_OPTION_ID" ]; then
    echo -e "${YELLOW}Step 6: Setting type to Epic...${NC}"
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
    }' -F projectId="$PROJECT_ID" -F itemId="$ITEM_ID" -F fieldId="$TYPE_FIELD_ID" -F optionId="$EPIC_OPTION_ID" 2>&1)
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Type set to Epic${NC}"
    else
        echo -e "${YELLOW}⚠️  Failed to set type to Epic${NC}"
        echo "Error: $TYPE_RESULT"
    fi
else
    echo -e "${YELLOW}Step 6: Skipping type assignment (field/option not available)${NC}"
fi
echo ""

# Step 7: Convert to repository issue
echo -e "${YELLOW}Step 7: Converting to repository issue...${NC}"
echo "This is the step that typically hangs. Adding detailed error handling..."

# Add a small delay before conversion
sleep 1

CONVERT_RESULT=$(timeout 30 gh api graphql -f query='
mutation($itemId:ID!, $repoId:ID!) {
  convertProjectV2DraftIssueItemToIssue(input:{
    itemId: $itemId,
    repositoryId: $repoId
  }) {
    item {
      content {
        ... on Issue {
          number
          id
          title
          url
        }
      }
    }
  }
}' -F itemId="$ITEM_ID" -F repoId="$REPO_ID" 2>&1)

CONVERT_EXIT_CODE=$?

if [ $CONVERT_EXIT_CODE -eq 124 ]; then
    echo -e "${RED}❌ Conversion timed out after 30 seconds${NC}"
    echo "This suggests the conversion is hanging as described."
    echo ""
    echo -e "${YELLOW}Debugging information:${NC}"
    echo "   Item ID: $ITEM_ID"
    echo "   Repository ID: $REPO_ID"
    echo "   Project ID: $PROJECT_ID"
    echo ""
    echo -e "${YELLOW}Possible causes:${NC}"
    echo "   - GraphQL API rate limiting"
    echo "   - Repository permissions issue"
    echo "   - GitHub API temporary issue"
    echo "   - Item in invalid state for conversion"
    
    # Try to get more info about the item
    echo ""
    echo -e "${YELLOW}Checking item status...${NC}"
    ITEM_STATUS=$(gh api graphql -f query='
    query($owner:String!, $projNum:Int!) {
      user(login:$owner) {
        projectV2(number:$projNum) {
          items(first: 20) {
            nodes {
              id
              type
              content {
                ... on DraftIssue {
                  title
                  body
                }
                ... on Issue {
                  number
                  title
                }
              }
            }
          }
        }
      }
    }' -F owner="$OWNER" -F projNum="$PROJECT_NUMBER" 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        ITEM_INFO=$(echo "$ITEM_STATUS" | jq -r ".data.user.projectV2.items.nodes[] | select(.id == \"$ITEM_ID\")")
        if [ -n "$ITEM_INFO" ]; then
            ITEM_TYPE=$(echo "$ITEM_INFO" | jq -r '.type')
            echo "   Item type: $ITEM_TYPE"
            
            if [ "$ITEM_TYPE" = "DRAFT_ISSUE" ]; then
                echo -e "${GREEN}   ✅ Item is still a draft (ready for conversion)${NC}"
            else
                echo -e "${YELLOW}   ⚠️  Item type is not DRAFT_ISSUE${NC}"
            fi
        else
            echo -e "${RED}   ❌ Could not find item in project${NC}"
        fi
    fi
    
    exit 1
elif [ $CONVERT_EXIT_CODE -ne 0 ]; then
    echo -e "${RED}❌ Conversion failed${NC}"
    echo "Error: $CONVERT_RESULT"
    exit 1
fi

ISSUE_NUMBER=$(echo "$CONVERT_RESULT" | jq -r '.data.convertProjectV2DraftIssueItemToIssue.item.content.number // empty')
ISSUE_URL=$(echo "$CONVERT_RESULT" | jq -r '.data.convertProjectV2DraftIssueItemToIssue.item.content.url // empty')

if [ -n "$ISSUE_NUMBER" ]; then
    echo -e "${GREEN}✅ Successfully converted to issue #$ISSUE_NUMBER${NC}"
    if [ -n "$ISSUE_URL" ]; then
        echo "   Issue URL: $ISSUE_URL"
    fi
else
    echo -e "${RED}❌ Failed to extract issue number${NC}"
    echo "Response: $CONVERT_RESULT"
    exit 1
fi

echo ""
echo -e "${BLUE}=========================================${NC}"
echo -e "${GREEN}✅ SINGLE EPIC TEST COMPLETED SUCCESSFULLY!${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""
echo "The test epic was successfully:"
echo "  1. Created as a draft item"
echo "  2. Configured with Epic type (if possible)"
echo "  3. Converted to a repository issue"
echo ""
echo "This confirms the process works. You can now run the full epic creation script."