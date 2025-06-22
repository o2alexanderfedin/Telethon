#!/bin/bash

# Script to add documentation links to GitHub Project items (both issues and draft items)

set -e

# Configuration
PROJECT_NUMBER="2"
REPO_OWNER="o2alexanderfedin"
REPO_NAME="telethon-architecture-docs"
DOC_BASE_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}/blob/main/documentation/voice-transcription-feature"

echo "🔄 Adding documentation links to GitHub Project items..."

# Function to update an issue's body
update_issue_body() {
    local issue_id="$1"
    local new_body="$2"
    
    gh api graphql -f query='
    mutation($issueId: ID!, $body: String!) {
      updateIssue(input: {
        id: $issueId
        body: $body
      }) {
        issue {
          id
        }
      }
    }' -f issueId="$issue_id" -f body="$new_body" > /dev/null 2>&1 || return 1
}

# Function to update a draft issue's body
update_draft_issue_body() {
    local draft_id="$1"
    local new_body="$2"
    
    gh api graphql -f query='
    mutation($draftId: ID!, $body: String!) {
      updateProjectV2DraftIssue(input: {
        draftIssueId: $draftId
        body: $body
      }) {
        draftIssue {
          id
        }
      }
    }' -f draftId="$draft_id" -f body="$new_body" > /dev/null 2>&1 || return 1
}

# Get Project ID
PROJECT_ID=$(gh api graphql -f query='
  query {
    user(login: "'$REPO_OWNER'") {
      projectV2(number: '$PROJECT_NUMBER') {
        id
      }
    }
  }' --jq '.data.user.projectV2.id')

echo "Found project ID: $PROJECT_ID"

# Change to project directory
cd /Users/alexanderfedin/Projects/demo/workspace/telethon-architecture-docs

# Read epics data
echo "📚 Reading epics data..."
EPICS_JSON=$(cat documentation/voice-transcription-feature/epics.json)

# Update each epic
echo "$EPICS_JSON" | jq -c '.[]' | while read -r epic; do
    ITEM_ID=$(echo "$epic" | jq -r '.id')
    TITLE=$(echo "$epic" | jq -r '.title')
    DOCS=$(echo "$epic" | jq -r '.documentation')
    
    echo "Processing Epic: $TITLE"
    
    # Build documentation section
    DOC_SECTION="## 📚 Documentation Links"
    
    # Add analysis link if exists
    if [ "$(echo "$DOCS" | jq -r '.analysis // empty')" != "" ]; then
        ANALYSIS_PATH=$(echo "$DOCS" | jq -r '.analysis')
        DOC_SECTION="$DOC_SECTION

- **Analysis**: [View Epic Analysis](${DOC_BASE_URL}/${ANALYSIS_PATH#./})"
    fi
    
    # Add technical link if exists
    if [ "$(echo "$DOCS" | jq -r '.technical // empty')" != "" ]; then
        TECH_PATH=$(echo "$DOCS" | jq -r '.technical')
        # Handle anchors
        if [[ "$TECH_PATH" == *"#"* ]]; then
            FILE_PATH="${TECH_PATH%%#*}"
            ANCHOR="${TECH_PATH#*#}"
            DOC_SECTION="$DOC_SECTION
- **Technical Architecture**: [View Technical Details](${DOC_BASE_URL}/${FILE_PATH#./}#${ANCHOR})"
        else
            DOC_SECTION="$DOC_SECTION
- **Technical Architecture**: [View Technical Details](${DOC_BASE_URL}/${TECH_PATH#./})"
        fi
    fi
    
    # Add sprint plan link if exists
    if [ "$(echo "$DOCS" | jq -r '.sprint_plan // empty')" != "" ]; then
        SPRINT_PATH=$(echo "$DOCS" | jq -r '.sprint_plan')
        DOC_SECTION="$DOC_SECTION
- **Sprint Plan**: [View Sprint Planning](${DOC_BASE_URL}/${SPRINT_PATH#./})"
    fi
    
    # Add API design link if exists
    if [ "$(echo "$DOCS" | jq -r '.api_design // empty')" != "" ]; then
        API_PATH=$(echo "$DOCS" | jq -r '.api_design')
        if [[ "$API_PATH" == *"#"* ]]; then
            FILE_PATH="${API_PATH%%#*}"
            ANCHOR="${API_PATH#*#}"
            DOC_SECTION="$DOC_SECTION
- **API Design**: [View API Details](${DOC_BASE_URL}/${FILE_PATH#./}#${ANCHOR})"
        else
            DOC_SECTION="$DOC_SECTION
- **API Design**: [View API Details](${DOC_BASE_URL}/${API_PATH#./})"
        fi
    fi
    
    # Add other links
    if [ "$(echo "$DOCS" | jq -r '.references // empty')" != "" ]; then
        REF_PATH=$(echo "$DOCS" | jq -r '.references')
        if [[ "$REF_PATH" == *"#"* ]]; then
            FILE_PATH="${REF_PATH%%#*}"
            ANCHOR="${REF_PATH#*#}"
            DOC_SECTION="$DOC_SECTION
- **Additional References**: [View References](${DOC_BASE_URL}/${FILE_PATH#./}#${ANCHOR})"
        else
            DOC_SECTION="$DOC_SECTION
- **Additional References**: [View References](${DOC_BASE_URL}/${REF_PATH#./})"
        fi
    fi
    
    if [ "$(echo "$DOCS" | jq -r '.caching // empty')" != "" ]; then
        CACHE_PATH=$(echo "$DOCS" | jq -r '.caching')
        if [[ "$CACHE_PATH" == *"#"* ]]; then
            FILE_PATH="${CACHE_PATH%%#*}"
            ANCHOR="${CACHE_PATH#*#}"
            DOC_SECTION="$DOC_SECTION
- **Caching Strategy**: [View Caching Details](${DOC_BASE_URL}/${FILE_PATH#./}#${ANCHOR})"
        else
            DOC_SECTION="$DOC_SECTION
- **Caching Strategy**: [View Caching Details](${DOC_BASE_URL}/${CACHE_PATH#./})"
        fi
    fi
    
    if [ "$(echo "$DOCS" | jq -r '.testing // empty')" != "" ]; then
        TEST_PATH=$(echo "$DOCS" | jq -r '.testing')
        if [[ "$TEST_PATH" == *"#"* ]]; then
            FILE_PATH="${TEST_PATH%%#*}"
            ANCHOR="${TEST_PATH#*#}"
            DOC_SECTION="$DOC_SECTION
- **Testing Strategy**: [View Testing Details](${DOC_BASE_URL}/${FILE_PATH#./}#${ANCHOR})"
        else
            DOC_SECTION="$DOC_SECTION
- **Testing Strategy**: [View Testing Details](${DOC_BASE_URL}/${TEST_PATH#./})"
        fi
    fi
    
    if [ "$(echo "$DOCS" | jq -r '.overview // empty')" != "" ]; then
        OVERVIEW_PATH=$(echo "$DOCS" | jq -r '.overview')
        DOC_SECTION="$DOC_SECTION
- **Overview**: [View Project Overview](${DOC_BASE_URL}/${OVERVIEW_PATH#./})"
    fi
    
    # Get current item content and type
    ITEM_DATA=$(gh api graphql -f query='
      query {
        node(id: "'$ITEM_ID'") {
          ... on ProjectV2Item {
            content {
              ... on Issue {
                id
                body
                __typename
              }
              ... on DraftIssue {
                id
                body
                __typename
              }
            }
          }
        }
      }' --jq '.data.node.content')
    
    CONTENT_TYPE=$(echo "$ITEM_DATA" | jq -r '.__typename')
    CONTENT_ID=$(echo "$ITEM_DATA" | jq -r '.id')
    CURRENT_BODY=$(echo "$ITEM_DATA" | jq -r '.body // ""')
    
    # Check if documentation section already exists
    if [[ "$CURRENT_BODY" == *"## 📚 Documentation Links"* ]]; then
        # Replace existing section - remove old documentation section
        NEW_BODY=$(echo "$CURRENT_BODY" | sed '/## 📚 Documentation Links/,/^## /{ /^## [^📚]/!d; }' | sed '/## 📚 Documentation Links/d')
        # Trim trailing newlines
        NEW_BODY=$(echo "$NEW_BODY" | sed -e :a -e '/^\n*$/{$d;N;ba' -e '}')
        NEW_BODY="$NEW_BODY

$DOC_SECTION"
    else
        # Append new section
        if [ -z "$CURRENT_BODY" ]; then
            NEW_BODY="$DOC_SECTION"
        else
            NEW_BODY="$CURRENT_BODY

$DOC_SECTION"
        fi
    fi
    
    # Update based on content type
    echo "✏️  Updating $TITLE ($CONTENT_TYPE)..."
    if [ "$CONTENT_TYPE" = "Issue" ]; then
        update_issue_body "$CONTENT_ID" "$NEW_BODY" && echo "✅ Updated" || echo "❌ Failed to update"
    elif [ "$CONTENT_TYPE" = "DraftIssue" ]; then
        update_draft_issue_body "$CONTENT_ID" "$NEW_BODY" && echo "✅ Updated" || echo "❌ Failed to update"
    else
        echo "❓ Unknown content type: $CONTENT_TYPE"
    fi
done

# Read user stories data
echo -e "\n📚 Reading user stories data..."
STORIES_JSON=$(cat documentation/voice-transcription-feature/user-stories.json)

# Update each user story
echo "$STORIES_JSON" | jq -c '.[]' | while read -r story; do
    ITEM_ID=$(echo "$story" | jq -r '.id')
    TITLE=$(echo "$story" | jq -r '.title')
    EPIC=$(echo "$story" | jq -r '.epic')
    DOC_PATH=$(echo "$story" | jq -r '.documentation')
    
    echo "Processing Story: $TITLE"
    
    # Build documentation section
    DOC_SECTION="## 📚 Documentation

**Parent Epic**: $EPIC"
    
    # Add implementation link
    if [[ "$DOC_PATH" == *"#"* ]]; then
        FILE_PATH="${DOC_PATH%%#*}"
        ANCHOR="${DOC_PATH#*#}"
        DOC_SECTION="$DOC_SECTION

**Implementation Details**: [View in Technical Architecture](${DOC_BASE_URL}/${FILE_PATH#./}#${ANCHOR})"
    else
        DOC_SECTION="$DOC_SECTION

**Implementation Details**: [View Documentation](${DOC_BASE_URL}/${DOC_PATH#./})"
    fi
    
    # Get current item content and type
    ITEM_DATA=$(gh api graphql -f query='
      query {
        node(id: "'$ITEM_ID'") {
          ... on ProjectV2Item {
            content {
              ... on Issue {
                id
                body
                __typename
              }
              ... on DraftIssue {
                id
                body
                __typename
              }
            }
          }
        }
      }' --jq '.data.node.content')
    
    CONTENT_TYPE=$(echo "$ITEM_DATA" | jq -r '.__typename')
    CONTENT_ID=$(echo "$ITEM_DATA" | jq -r '.id')
    CURRENT_BODY=$(echo "$ITEM_DATA" | jq -r '.body // ""')
    
    # Check if documentation section already exists
    if [[ "$CURRENT_BODY" == *"## 📚 Documentation"* ]]; then
        # Replace existing section
        NEW_BODY=$(echo "$CURRENT_BODY" | sed '/## 📚 Documentation/,/^## /{ /^## [^📚]/!d; }' | sed '/## 📚 Documentation/d')
        # Trim trailing newlines
        NEW_BODY=$(echo "$NEW_BODY" | sed -e :a -e '/^\n*$/{$d;N;ba' -e '}')
        NEW_BODY="$NEW_BODY

$DOC_SECTION"
    else
        # Append new section
        if [ -z "$CURRENT_BODY" ]; then
            NEW_BODY="$DOC_SECTION"
        else
            NEW_BODY="$CURRENT_BODY

$DOC_SECTION"
        fi
    fi
    
    # Update based on content type
    echo "✏️  Updating $TITLE ($CONTENT_TYPE)..."
    if [ "$CONTENT_TYPE" = "Issue" ]; then
        update_issue_body "$CONTENT_ID" "$NEW_BODY" && echo "✅ Updated" || echo "❌ Failed to update"
    elif [ "$CONTENT_TYPE" = "DraftIssue" ]; then
        update_draft_issue_body "$CONTENT_ID" "$NEW_BODY" && echo "✅ Updated" || echo "❌ Failed to update"
    else
        echo "❓ Unknown content type: $CONTENT_TYPE"
    fi
done

echo -e "\n✅ Documentation links added to all project items!"