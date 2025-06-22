#!/bin/bash

# Script to delete all project items without Type field set

set -e

# Configuration
PROJECT_NUMBER="12"
REPO_OWNER="o2alexanderfedin"

echo "🧹 Cleaning up project items without Type field set..."

# Get Project ID and Type field ID
PROJECT_DATA=$(gh api graphql -f query='
  query {
    user(login: "'$REPO_OWNER'") {
      projectV2(number: '$PROJECT_NUMBER') {
        id
        field(name: "Type") {
          ... on ProjectV2SingleSelectField {
            id
          }
        }
      }
    }
  }')

PROJECT_ID=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.id')
TYPE_FIELD_ID=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.field.id')

echo "Project ID: $PROJECT_ID"
echo "Type field ID: $TYPE_FIELD_ID"

# Get all items and check their Type field
echo -e "\n🔍 Finding items without Type field set...\n"

ITEMS=$(gh api graphql -f query='
  query {
    node(id: "'$PROJECT_ID'") {
      ... on ProjectV2 {
        items(first: 100) {
          nodes {
            id
            content {
              ... on DraftIssue {
                title
              }
              ... on Issue {
                title
                number
              }
            }
            fieldValueByName(name: "Type") {
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
              }
            }
          }
        }
      }
    }
  }' --jq '.data.node.items.nodes[] | select(.fieldValueByName == null or .fieldValueByName.name == null)')

# Count items to delete
ITEM_COUNT=$(echo "$ITEMS" | jq -s 'length')

if [ "$ITEM_COUNT" -eq 0 ]; then
    echo "✅ No items found without Type field set. Nothing to delete."
    exit 0
fi

echo "Found $ITEM_COUNT items without Type field set:"
echo "$ITEMS" | jq -r '.content.title' | head -20
if [ "$ITEM_COUNT" -gt 20 ]; then
    echo "... and $((ITEM_COUNT - 20)) more"
fi

# Confirm deletion
echo -e "\n⚠️  WARNING: This will delete $ITEM_COUNT items from the project!"
read -p "Are you sure you want to proceed? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Deletion cancelled."
    exit 0
fi

# Delete items
echo -e "\n🗑️  Deleting items...\n"

echo "$ITEMS" | jq -r '.id' | while read -r item_id; do
    TITLE=$(echo "$ITEMS" | jq -r --arg id "$item_id" 'select(.id == $id) | .content.title')
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

echo -e "\n✅ Cleanup complete!"
echo "Deleted $ITEM_COUNT items without Type field set."