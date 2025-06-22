#!/usr/bin/env bash
set -euo pipefail

# Script to convert all draft issues to repository issues

OWNER="o2alexanderfedin"
REPO="telethon-architecture-docs"
PROJECT_NUMBER=12

echo "🔄 Converting Draft Issues to Repository Issues..."
echo "==============================================="
echo ""

# Get repository ID
echo "📋 Getting repository information..."
REPO_ID=$(gh api graphql -f query='
  query($owner:String!, $repo:String!) {
    repository(owner:$owner, name:$repo) { id }
  }' \
  -F owner="$OWNER" \
  -F repo="$REPO" \
  --jq '.data.repository.id')

echo "✅ Repository ID: $REPO_ID"
echo ""

# Get project information
PROJECT_DATA=$(gh api graphql -H "GraphQL-Features: project_v2" \
  -f query='
    query($owner:String!, $projNum:Int!) {
      user(login:$owner) {
        projectV2(number:$projNum) { 
          id 
          title
        }
      }
    }' \
  -F owner="$OWNER" \
  -F projNum="$PROJECT_NUMBER")

PROJECT_ID=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.id')
PROJECT_TITLE=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.title')

echo "📊 Project: $PROJECT_TITLE (#$PROJECT_NUMBER)"
echo ""

# Function to convert draft to issue
convert_draft_to_issue() {
    local item_id=$1
    local title=$2
    local body=$3
    
    echo -n "Converting: $title... "
    
    # Convert draft to repository issue
    RESULT=$(gh api graphql -H "GraphQL-Features: project_v2" \
      -f query='
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
                } 
              } 
            }
          }
        }' \
      -F itemId="$item_id" \
      -F repoId="$REPO_ID" 2>&1)
    
    if [ $? -eq 0 ]; then
        ISSUE_NUMBER=$(echo "$RESULT" | jq -r '.data.convertProjectV2DraftIssueItemToIssue.item.content.number // empty')
        if [ -n "$ISSUE_NUMBER" ]; then
            echo "✅ Created issue #$ISSUE_NUMBER"
            return 0
        else
            echo "❌ Failed to get issue number"
            return 1
        fi
    else
        echo "❌ Conversion failed"
        echo "Error: $RESULT"
        return 1
    fi
}

echo "🔍 Finding draft issues..."
echo "========================"
echo ""

# Get all draft items
DRAFT_COUNT=0
CONVERTED_COUNT=0
FAILED_COUNT=0

# Query for draft items
DRAFTS_DATA=$(gh api graphql -H "GraphQL-Features: project_v2" \
  -f query='
    query($owner:String!, $projNum:Int!) {
      user(login:$owner) {
        projectV2(number:$projNum) {
          items(first: 100) {
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
                }
              }
            }
          }
        }
      }
    }' \
  -F owner="$OWNER" \
  -F projNum="$PROJECT_NUMBER")

# Process draft items
echo "$DRAFTS_DATA" | jq -c '.data.user.projectV2.items.nodes[]' | while read -r item; do
    ITEM_TYPE=$(echo "$item" | jq -r '.type')
    
    if [ "$ITEM_TYPE" = "DRAFT_ISSUE" ]; then
        ITEM_ID=$(echo "$item" | jq -r '.id')
        TITLE=$(echo "$item" | jq -r '.content.title // "Untitled Draft"')
        BODY=$(echo "$item" | jq -r '.content.body // ""')
        
        ((DRAFT_COUNT++))
        
        # Convert to repository issue
        if convert_draft_to_issue "$ITEM_ID" "$TITLE" "$BODY"; then
            ((CONVERTED_COUNT++))
        else
            ((FAILED_COUNT++))
        fi
        
        # Rate limiting
        sleep 0.5
    fi
done

echo ""
echo "✅ Conversion process complete!"
echo ""
echo "📊 Summary:"
echo "=========="
echo "Draft issues found: $DRAFT_COUNT"
echo "Successfully converted: $CONVERTED_COUNT"
echo "Failed conversions: $FAILED_COUNT"
echo ""

# Verify by checking for remaining drafts
echo "🔍 Checking for remaining draft issues..."
REMAINING_DRAFTS=$(gh api graphql -H "GraphQL-Features: project_v2" \
  -f query='
    query($owner:String!, $projNum:Int!) {
      user(login:$owner) {
        projectV2(number:$projNum) {
          items(first: 100) {
            nodes {
              type
            }
          }
        }
      }
    }' \
  -F owner="$OWNER" \
  -F projNum="$PROJECT_NUMBER" | \
  jq '[.data.user.projectV2.items.nodes[] | select(.type == "DRAFT_ISSUE")] | length')

echo "Remaining draft issues: $REMAINING_DRAFTS"

if [ "$REMAINING_DRAFTS" -eq 0 ]; then
    echo ""
    echo "✅ All draft issues have been converted to repository issues!"
else
    echo ""
    echo "⚠️  Some draft issues remain. You may need to:"
    echo "   - Check for permission issues"
    echo "   - Verify repository access"
    echo "   - Review failed conversions above"
fi