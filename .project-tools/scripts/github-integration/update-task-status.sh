#!/bin/bash

# Script: update-task-status.sh
# Purpose: Update task status in GitHub Project
# Usage: ./update-task-status.sh <issue-number> <status>

set -euo pipefail

# Arguments
ISSUE_NUMBER=$1
NEW_STATUS=$2

# Configuration
PROJECT_OWNER="o2alexanderfedin"
PROJECT_NUMBER="1"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Updating task #$ISSUE_NUMBER to status: $NEW_STATUS${NC}"

# Get project ID
PROJECT_ID=$(gh api graphql -f query='
  query($owner: String!, $number: Int!) {
    user(login: $owner) {
      projectV2(number: $number) {
        id
      }
    }
  }' -f owner="$PROJECT_OWNER" -f number="$PROJECT_NUMBER" --jq '.data.user.projectV2.id')

# Get field ID and options
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
STATUS_OPTION_ID=$(echo "$FIELD_DATA" | jq -r --arg status "$NEW_STATUS" '.options[] | select(.name == $status) | .id')

if [ -z "$STATUS_OPTION_ID" ]; then
    echo -e "${RED}❌ Status '$NEW_STATUS' not found${NC}"
    echo -e "${YELLOW}Available statuses:${NC}"
    echo "$FIELD_DATA" | jq -r '.options[].name' | sed 's/^/  - /'
    exit 1
fi

# Get item ID for the issue
ITEM_ID=$(gh api graphql -f query='
  query($projectId: ID!) {
    node(id: $projectId) {
      ... on ProjectV2 {
        items(first: 100) {
          nodes {
            id
            content {
              ... on Issue {
                number
              }
            }
          }
        }
      }
    }
  }' -f projectId="$PROJECT_ID" --jq --arg num "$ISSUE_NUMBER" '
  .data.node.items.nodes[] | 
  select(.content.number == ($num | tonumber)) | 
  .id')

if [ -z "$ITEM_ID" ]; then
    echo -e "${RED}❌ Task #$ISSUE_NUMBER not found in project${NC}"
    exit 1
fi

# Update the status
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
  }' -f projectId="$PROJECT_ID" -f itemId="$ITEM_ID" -f fieldId="$FIELD_ID" -f value="$STATUS_OPTION_ID" > /dev/null

echo -e "${GREEN}✅ Task #$ISSUE_NUMBER status updated to: $NEW_STATUS${NC}"

# If moving to Done, add completion report
if [ "$NEW_STATUS" = "Done" ]; then
    echo -e "${BLUE}Generating completion report...${NC}"
    
    # Gather feature information
    FEATURE_BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null || echo "unknown")
    FEATURE_NAME=${FEATURE_BRANCH#feature/}
    
    # Get commit statistics
    if [ -f ".claude/gitflow-status.env" ]; then
        source .claude/gitflow-status.env
        COMMIT_COUNT=${GITFLOW_COMMIT_COUNT:-0}
        START_DATE=${GITFLOW_STARTED_AT:-"Unknown"}
        
        # Calculate duration
        if [ -n "$GITFLOW_STARTED_AT" ]; then
            START_TS=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$GITFLOW_STARTED_AT" +%s 2>/dev/null || date -d "$GITFLOW_STARTED_AT" +%s 2>/dev/null || echo 0)
            END_TS=$(date +%s)
            DURATION_HOURS=$(( (END_TS - START_TS) / 3600 ))
            DURATION_DAYS=$(( DURATION_HOURS / 24 ))
            
            if [ $DURATION_DAYS -gt 0 ]; then
                DURATION="${DURATION_DAYS} days"
            else
                DURATION="${DURATION_HOURS} hours"
            fi
        else
            DURATION="Unknown"
        fi
    else
        COMMIT_COUNT=$(git rev-list --count develop..HEAD 2>/dev/null || echo "0")
        DURATION="Unknown"
        START_DATE="Unknown"
    fi
    
    # Get list of changed files
    CHANGED_FILES=$(git diff --name-only develop...HEAD 2>/dev/null | head -20)
    FILE_COUNT=$(git diff --name-only develop...HEAD 2>/dev/null | wc -l | tr -d ' ')
    
    # Get list of commits
    COMMIT_LIST=$(git log develop..HEAD --oneline 2>/dev/null | head -10)
    
    # Search for PRs
    RELATED_PRS=$(gh pr list --search "#$ISSUE_NUMBER" --json number,title,state,url --jq '.[]')
    
    # Create completion report
    COMPLETION_REPORT="## 🎉 Task Completed

### Summary
Feature branch: \`$FEATURE_BRANCH\`
Duration: **$DURATION** (started: $START_DATE)
Total commits: **$COMMIT_COUNT**
Files changed: **$FILE_COUNT**

### Work Completed
$(if [ -f ".claude/feature-plan-$FEATURE_NAME.md" ]; then
    grep -A 20 "## Implementation Plan" ".claude/feature-plan-$FEATURE_NAME.md" 2>/dev/null | grep -E "^- \[x\]|^[0-9]\." | head -10 || echo "- Feature implementation completed"
else
    echo "- Feature implementation completed as specified"
fi)

### Changes Made
#### Files Modified ($FILE_COUNT total)
\`\`\`
$(echo "$CHANGED_FILES" | head -10)
$([ $FILE_COUNT -gt 10 ] && echo "... and $((FILE_COUNT - 10)) more files")
\`\`\`

#### Commits ($COMMIT_COUNT total)
\`\`\`
$COMMIT_LIST
$([ $COMMIT_COUNT -gt 10 ] && echo "... and $((COMMIT_COUNT - 10)) more commits")
\`\`\`

### Pull Requests
$(if [ -n "$RELATED_PRS" ]; then
    echo "$RELATED_PRS" | jq -r '"- PR #\(.number): [\(.title)](\(.url)) (\(.state))"'
else
    echo "- No pull requests linked"
fi)

### Testing
- [ ] Unit tests passed
- [ ] Integration tests passed
- [ ] Manual testing completed

### Next Steps
- Review merged changes in develop branch
- Consider deployment planning
- Update documentation if needed

---
*Automated completion report generated by GitFlow+Kanban workflow*"
    
    # Add comment to issue
    echo -e "${BLUE}Adding completion report to task...${NC}"
    gh issue comment "$ISSUE_NUMBER" --body "$COMPLETION_REPORT"
    
    echo -e "${GREEN}✅ Completion report added to task #$ISSUE_NUMBER${NC}"
fi

# If moving to In Progress, show architecture docs and update tracking
if [ "$NEW_STATUS" = "In Progress" ]; then
    mkdir -p .claude
    echo "$ISSUE_NUMBER" > .claude/current-task.txt
    echo -e "${GREEN}✅ Linked task #$ISSUE_NUMBER to current work${NC}"
    
    # Get task details
    TASK_INFO=$(gh issue view "$ISSUE_NUMBER" --json title,body,labels)
    TASK_TITLE=$(echo "$TASK_INFO" | jq -r '.title')
    TASK_BODY=$(echo "$TASK_INFO" | jq -r '.body')
    
    echo -e "\n${BLUE}📚 Consulting Technical Architecture Documentation...${NC}"
    
    # Search for relevant architecture docs based on task title and body
    SEARCH_TERMS=$(echo "$TASK_TITLE $TASK_BODY" | tr '[:upper:]' '[:lower:]' | grep -oE '[a-z]+' | sort -u | head -10)
    
    # Find relevant documentation
    RELEVANT_DOCS=""
    for term in $SEARCH_TERMS; do
        # Skip common words
        if [[ ! "$term" =~ ^(the|and|for|with|from|this|that|have|will|should|must)$ ]]; then
            FOUND_DOCS=$(find docs -name "*.md" -type f -exec grep -l -i "$term" {} \; 2>/dev/null | head -5)
            if [ -n "$FOUND_DOCS" ]; then
                RELEVANT_DOCS="$RELEVANT_DOCS$FOUND_DOCS"$'\n'
            fi
        fi
    done
    
    # Remove duplicates and show top results
    UNIQUE_DOCS=$(echo "$RELEVANT_DOCS" | sort -u | grep -v "^$" | head -10)
    
    if [ -n "$UNIQUE_DOCS" ]; then
        echo -e "\n${GREEN}📖 Relevant Architecture Documentation:${NC}"
        echo "$UNIQUE_DOCS" | while read -r doc; do
            # Get document title
            DOC_TITLE=$(grep -m 1 "^# " "$doc" 2>/dev/null | sed 's/^# //' || basename "$doc" .md)
            echo -e "  ${BLUE}•${NC} $doc"
            echo -e "    ${YELLOW}$DOC_TITLE${NC}"
        done
        
        # Create architecture reference file
        cat > .claude/task-$ISSUE_NUMBER-arch-refs.md << EOF
# Architecture References for Task #$ISSUE_NUMBER

## Task: $TASK_TITLE

### Relevant Documentation
$(echo "$UNIQUE_DOCS" | while read -r doc; do
    if [ -n "$doc" ]; then
        DOC_TITLE=$(grep -m 1 "^# " "$doc" 2>/dev/null | sed 's/^# //' || basename "$doc" .md)
        echo "- [$DOC_TITLE]($doc)"
    fi
done)

### Key Architecture Considerations
$(if echo "$UNIQUE_DOCS" | grep -q "voice-transcription"; then
    echo "- Review Voice Transcription feature architecture"
    echo "- Check API design patterns in docs/features/voice-transcription/"
    echo "- Consider scalability requirements"
fi)

$(if echo "$UNIQUE_DOCS" | grep -q "protocol"; then
    echo "- Follow Telethon protocol specifications"
    echo "- Ensure compatibility with MTProto"
fi)

$(if echo "$UNIQUE_DOCS" | grep -q "client"; then
    echo "- Maintain client architecture patterns"
    echo "- Review event handling mechanisms"
fi)

### Implementation Guidelines
1. Review the linked documentation before starting
2. Follow existing patterns and conventions
3. Update documentation if architecture changes
4. Consider performance and scalability

### Notes
- Created: $(date)
- Feature Branch: $(git symbolic-ref --short HEAD 2>/dev/null || echo "Not on feature branch")
EOF
        
        echo -e "\n${GREEN}✅ Created architecture reference: .claude/task-$ISSUE_NUMBER-arch-refs.md${NC}"
        
        # Show quick summary
        echo -e "\n${PURPLE}💡 Key Architecture Points:${NC}"
        
        # Voice transcription specific
        if echo "$TASK_TITLE $TASK_BODY" | grep -qi "voice\|transcript\|audio\|speech"; then
            echo -e "  ${YELLOW}Voice Transcription Feature:${NC}"
            echo -e "    • Review: docs/features/voice-transcription/FEATURE-TECH-ARCHITECTURE.md"
            echo -e "    • Check API design patterns"
            echo -e "    • Consider quota management"
        fi
        
        # API related
        if echo "$TASK_TITLE $TASK_BODY" | grep -qi "api\|endpoint\|request"; then
            echo -e "  ${YELLOW}API Architecture:${NC}"
            echo -e "    • Follow RESTful conventions"
            echo -e "    • Implement proper error handling"
            echo -e "    • Add rate limiting if needed"
        fi
        
        # Database related
        if echo "$TASK_TITLE $TASK_BODY" | grep -qi "database\|storage\|persist"; then
            echo -e "  ${YELLOW}Data Architecture:${NC}"
            echo -e "    • Review data models"
            echo -e "    • Consider caching strategies"
            echo -e "    • Plan migration if schema changes"
        fi
    else
        echo -e "\n${YELLOW}⚠️  No specific architecture docs found. Review general documentation:${NC}"
        echo -e "  • docs/README.md - Overview"
        echo -e "  • docs/architecture/ - General architecture"
        echo -e "  • docs/features/ - Feature specifications"
    fi
    
    echo -e "\n${BLUE}💬 Adding task start comment...${NC}"
    
    # Add comment to issue about starting work
    START_COMMENT="## 🚀 Starting Work on Task

### Developer: $(git config user.name || echo "Unknown")
### Branch: \`$(git symbolic-ref --short HEAD 2>/dev/null || echo "Not on feature branch")\`
### Started: $(date)

### Architecture Documentation Reviewed
$(if [ -n "$UNIQUE_DOCS" ]; then
    echo "$UNIQUE_DOCS" | head -5 | while read -r doc; do
        if [ -n "$doc" ]; then
            echo "- ✅ $doc"
        fi
    done
else
    echo "- ⚠️  No specific architecture docs identified"
    echo "- 📚 Will review general documentation as needed"
fi)

### Implementation Plan
- [ ] Review task requirements
- [ ] Consult architecture documentation
- [ ] Implement solution following patterns
- [ ] Write/update tests
- [ ] Update documentation if needed

---
*Starting work - will provide completion report when done*"
    
    gh issue comment "$ISSUE_NUMBER" --body "$START_COMMENT"
    
    echo -e "${GREEN}✅ Added task start comment to #$ISSUE_NUMBER${NC}"
fi