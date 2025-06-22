#!/bin/bash

# Script to delete all draft issues from the project

set -e

# Configuration
PROJECT_NUMBER="12"
REPO_OWNER="o2alexanderfedin"

echo "🗑️  Deleting all draft issues from Voice Transcription project..."

# Get Project ID
PROJECT_ID=$(gh api graphql -f query='
  query {
    user(login: "'$REPO_OWNER'") {
      projectV2(number: '$PROJECT_NUMBER') {
        id
      }
    }
  }' --jq '.data.user.projectV2.id')

echo "Project ID: $PROJECT_ID"

# Get all draft issues
echo -e "\n🔍 Finding draft issues...\n"

DRAFT_ITEMS=$(gh api graphql -f query='
  query {
    node(id: "'$PROJECT_ID'") {
      ... on ProjectV2 {
        items(first: 100) {
          nodes {
            id
            content {
              ... on DraftIssue {
                title
                __typename
              }
              ... on Issue {
                __typename
              }
            }
          }
        }
      }
    }
  }' --jq '.data.node.items.nodes[] | select(.content.__typename == "DraftIssue")')

# Count draft items
ITEM_COUNT=$(echo "$DRAFT_ITEMS" | jq -s 'length')

if [ "$ITEM_COUNT" -eq 0 ]; then
    echo "✅ No draft issues found. Nothing to delete."
    exit 0
fi

echo "Found $ITEM_COUNT draft issues:"
echo "$DRAFT_ITEMS" | jq -r '.content.title' | head -20
if [ "$ITEM_COUNT" -gt 20 ]; then
    echo "... and $((ITEM_COUNT - 20)) more"
fi

# Confirm deletion
echo -e "\n⚠️  WARNING: This will delete $ITEM_COUNT draft issues from the project!"
echo "This action cannot be undone."
read -p "Are you sure you want to proceed? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Deletion cancelled."
    exit 0
fi

# Delete draft items
echo -e "\n🗑️  Deleting draft issues...\n"

echo "$DRAFT_ITEMS" | jq -r '.id' | while read -r item_id; do
    TITLE=$(echo "$DRAFT_ITEMS" | jq -r --arg id "$item_id" 'select(.id == $id) | .content.title')
    echo -n "Deleting: $TITLE... "
    
    RESULT=$(gh api graphql -f query='
    mutation {
      deleteProjectV2Item(input: {
        projectId: "'$PROJECT_ID'"
        itemId: "'$item_id'"
      }) {
        deletedItemId
      }
    }' 2>&1)
    
    if [[ "$RESULT" == *"deletedItemId"* ]]; then
        echo "✅"
    else
        echo "❌ Failed"
    fi
    
    sleep 0.2  # Rate limiting
done

echo -e "\n✅ Draft issue cleanup complete!"
echo "Deleted $ITEM_COUNT draft issues."