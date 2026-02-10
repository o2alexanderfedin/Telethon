#!/usr/bin/env bash
set -euo pipefail

# Debug Epic Creation Script
# Enhanced version with detailed logging and error handling

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
OWNER="o2alexanderfedin"
REPO="telethon-architecture-docs"
PROJECT_NUMBER=12
EPICS_FILE="/Users/alexanderfedin/Projects/demo/workspace/Telethon/docs/architecture/documentation/voice-transcription-feature/epics.json"

# Rate limiting configuration
MAX_RETRIES=3
RETRY_DELAY=2
CONVERSION_DELAY=1

# Debug mode
DEBUG=${DEBUG:-1}
VERBOSE=${VERBOSE:-1}

# Logging functions
debug_log() {
    if [ "$DEBUG" -eq 1 ]; then
        echo -e "${CYAN}[DEBUG]${NC} $1" >&2
    fi
}

verbose_log() {
    if [ "$VERBOSE" -eq 1 ]; then
        echo -e "${BLUE}[INFO]${NC} $1"
    fi
}

error_log() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success_log() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warn_log() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Function to check rate limits
check_rate_limits() {
    debug_log "Checking GitHub API rate limits..."
    
    RATE_LIMIT_INFO=$(gh api rate_limit 2>/dev/null || echo "")
    if [ -n "$RATE_LIMIT_INFO" ]; then
        REMAINING=$(echo "$RATE_LIMIT_INFO" | jq -r '.rate.remaining // 0')
        RESET_TIME=$(echo "$RATE_LIMIT_INFO" | jq -r '.rate.reset // 0')
        
        debug_log "Rate limit remaining: $REMAINING"
        
        if [ "$REMAINING" -lt 10 ]; then
            CURRENT_TIME=$(date +%s)
            WAIT_TIME=$((RESET_TIME - CURRENT_TIME + 10))
            
            if [ "$WAIT_TIME" -gt 0 ]; then
                warn_log "Rate limit low ($REMAINING remaining). Waiting ${WAIT_TIME}s..."
                sleep "$WAIT_TIME"
            fi
        fi
    else
        warn_log "Could not check rate limits. Proceeding with caution..."
    fi
}

# Function to make GraphQL request with retry logic
make_graphql_request() {
    local query="$1"
    local variables="$2"
    local description="$3"
    local attempt=1
    
    while [ $attempt -le $MAX_RETRIES ]; do
        debug_log "Attempt $attempt/$MAX_RETRIES: $description"
        
        check_rate_limits
        
        local result
        local exit_code
        
        result=$(gh api graphql -f query="$query" $variables 2>&1)
        exit_code=$?
        
        if [ $exit_code -eq 0 ]; then
            # Check for GraphQL errors
            local errors
            errors=$(echo "$result" | jq -r '.errors // empty' 2>/dev/null)
            
            if [ -n "$errors" ] && [ "$errors" != "null" ]; then
                error_log "GraphQL errors in $description:"
                echo "$result" | jq -r '.errors[] | "  - \(.message)"' 2>/dev/null || echo "$errors"
                
                # Check if it's a rate limit error
                if echo "$errors" | grep -q "rate limit\|secondary rate limit"; then
                    warn_log "Rate limit error detected. Waiting longer..."
                    sleep $((RETRY_DELAY * attempt * 2))
                    attempt=$((attempt + 1))
                    continue
                fi
                
                return 1
            fi
            
            echo "$result"
            return 0
        else
            error_log "HTTP error in $description (attempt $attempt):"
            echo "$result" >&2
            
            # Check if it's a rate limit error
            if echo "$result" | grep -q "rate limit\|secondary rate limit"; then
                warn_log "Rate limit error detected. Waiting longer..."
                sleep $((RETRY_DELAY * attempt * 2))
            else
                sleep $RETRY_DELAY
            fi
        fi
        
        attempt=$((attempt + 1))
    done
    
    error_log "Failed after $MAX_RETRIES attempts: $description"
    return 1
}

# Function to get project information
get_project_info() {
    verbose_log "Getting project information..."
    
    local query='
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
    }'
    
    make_graphql_request "$query" "-F owner=$OWNER -F projNum=$PROJECT_NUMBER" "get project info"
}

# Function to get repository ID
get_repository_id() {
    verbose_log "Getting repository ID..."
    
    local query='
    query($owner:String!, $repo:String!) {
      repository(owner:$owner, name:$repo) {
        id
      }
    }'
    
    make_graphql_request "$query" "-F owner=$OWNER -F repo=$REPO" "get repository ID"
}

# Function to create draft item
create_draft_item() {
    local title="$1"
    local body="$2"
    
    verbose_log "Creating draft item: $title"
    
    local query='
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
    }'
    
    make_graphql_request "$query" "-F projectId=$PROJECT_ID -F title=$title -F body=$body" "create draft item"
}

# Function to update item field
update_item_field() {
    local item_id="$1"
    local field_id="$2"
    local option_id="$3"
    local field_name="$4"
    
    if [ -z "$field_id" ] || [ -z "$option_id" ]; then
        debug_log "Skipping field update for $field_name: missing field_id or option_id"
        return 0
    fi
    
    debug_log "Updating field $field_name for item $item_id"
    
    local query='
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
    }'
    
    make_graphql_request "$query" "-F projectId=$PROJECT_ID -F itemId=$item_id -F fieldId=$field_id -F optionId=$option_id" "update field $field_name"
}

# Function to convert draft to issue
convert_draft_to_issue() {
    local item_id="$1"
    local title="$2"
    
    verbose_log "Converting draft to issue: $title"
    
    # Add extra delay before conversion
    sleep $CONVERSION_DELAY
    
    local query='
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
    }'
    
    make_graphql_request "$query" "-F itemId=$item_id -F repoId=$REPO_ID" "convert draft to issue"
}

# Extract field information
extract_field_id() {
    local field_name="$1"
    echo "$PROJECT_INFO" | jq -r ".data.user.projectV2.fields.nodes[] | select(.name == \"$field_name\") | .id"
}

extract_option_id() {
    local field_name="$1"
    local option_name="$2"
    echo "$PROJECT_INFO" | jq -r ".data.user.projectV2.fields.nodes[] | select(.name == \"$field_name\") | .options[]? | select(.name == \"$option_name\") | .id"
}

# Main execution
main() {
    echo -e "${BLUE}=========================================${NC}"
    echo -e "${BLUE}       DEBUG EPIC CREATION SCRIPT       ${NC}"
    echo -e "${BLUE}=========================================${NC}"
    echo ""
    
    # Check if epics file exists
    if [ ! -f "$EPICS_FILE" ]; then
        error_log "Epics file not found: $EPICS_FILE"
        exit 1
    fi
    
    verbose_log "Using epics file: $EPICS_FILE"
    verbose_log "Owner: $OWNER"
    verbose_log "Repository: $REPO"
    verbose_log "Project: #$PROJECT_NUMBER"
    echo ""
    
    # Step 1: Get project information
    echo -e "${YELLOW}Step 1: Getting project information...${NC}"
    PROJECT_INFO=$(get_project_info)
    if [ $? -ne 0 ]; then
        error_log "Failed to get project information"
        exit 1
    fi
    
    PROJECT_ID=$(echo "$PROJECT_INFO" | jq -r '.data.user.projectV2.id')
    PROJECT_TITLE=$(echo "$PROJECT_INFO" | jq -r '.data.user.projectV2.title')
    
    if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "null" ]; then
        error_log "Could not extract project ID"
        debug_log "Project info response: $PROJECT_INFO"
        exit 1
    fi
    
    success_log "Project: $PROJECT_TITLE (ID: $PROJECT_ID)"
    echo ""
    
    # Step 2: Get repository ID
    echo -e "${YELLOW}Step 2: Getting repository information...${NC}"
    REPO_INFO=$(get_repository_id)
    if [ $? -ne 0 ]; then
        error_log "Failed to get repository information"
        exit 1
    fi
    
    REPO_ID=$(echo "$REPO_INFO" | jq -r '.data.repository.id')
    if [ -z "$REPO_ID" ] || [ "$REPO_ID" = "null" ]; then
        error_log "Could not extract repository ID"
        debug_log "Repository info response: $REPO_INFO"
        exit 1
    fi
    
    success_log "Repository: $REPO (ID: $REPO_ID)"
    echo ""
    
    # Step 3: Extract field IDs
    echo -e "${YELLOW}Step 3: Extracting field configurations...${NC}"
    TYPE_FIELD_ID=$(extract_field_id "Type")
    EPIC_OPTION_ID=$(extract_option_id "Type" "Epic")
    
    debug_log "Type Field ID: $TYPE_FIELD_ID"
    debug_log "Epic Option ID: $EPIC_OPTION_ID"
    
    if [ -z "$TYPE_FIELD_ID" ]; then
        warn_log "Type field not found in project"
    fi
    
    if [ -z "$EPIC_OPTION_ID" ]; then
        warn_log "Epic option not found in Type field"
    fi
    
    echo ""
    
    # Step 4: Process epics
    echo -e "${YELLOW}Step 4: Processing epics...${NC}"
    
    TOTAL=0
    SUCCESS=0
    FAILED=0
    
    # Read and process each epic
    while IFS= read -r epic; do
        EPIC_TITLE=$(echo "$epic" | jq -r '.title')
        EPIC_ID=$(echo "$epic" | jq -r '.id // empty')
        
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
        
        # Step 4a: Create draft item
        echo -n "  Creating draft item... "
        DRAFT_RESULT=$(create_draft_item "$EPIC_TITLE" "$EPIC_BODY")
        if [ $? -ne 0 ]; then
            echo -e "${RED}❌ Failed${NC}"
            error_log "Failed to create draft item"
            FAILED=$((FAILED + 1))
            continue
        fi
        
        ITEM_ID=$(echo "$DRAFT_RESULT" | jq -r '.data.addProjectV2DraftIssue.projectV2Item.id')
        if [ -z "$ITEM_ID" ] || [ "$ITEM_ID" = "null" ]; then
            echo -e "${RED}❌ Failed to get item ID${NC}"
            debug_log "Draft result: $DRAFT_RESULT"
            FAILED=$((FAILED + 1))
            continue
        fi
        
        echo -e "${GREEN}✅ Created (ID: $ITEM_ID)${NC}"
        
        # Step 4b: Set type to Epic
        if [ -n "$TYPE_FIELD_ID" ] && [ -n "$EPIC_OPTION_ID" ]; then
            echo -n "  Setting type to Epic... "
            TYPE_RESULT=$(update_item_field "$ITEM_ID" "$TYPE_FIELD_ID" "$EPIC_OPTION_ID" "Type")
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}✅${NC}"
            else
                echo -e "${YELLOW}⚠️  Failed to set type${NC}"
            fi
        else
            echo -e "  ${YELLOW}⚠️  Skipping type setting (field/option not found)${NC}"
        fi
        
        # Step 4c: Convert to repository issue
        echo -n "  Converting to repository issue... "
        CONVERT_RESULT=$(convert_draft_to_issue "$ITEM_ID" "$EPIC_TITLE")
        if [ $? -ne 0 ]; then
            echo -e "${RED}❌ Conversion failed${NC}"
            error_log "Failed to convert draft to issue"
            debug_log "Item ID: $ITEM_ID"
            debug_log "Repository ID: $REPO_ID"
            FAILED=$((FAILED + 1))
            continue
        fi
        
        ISSUE_NUMBER=$(echo "$CONVERT_RESULT" | jq -r '.data.convertProjectV2DraftIssueItemToIssue.item.content.number // empty')
        ISSUE_URL=$(echo "$CONVERT_RESULT" | jq -r '.data.convertProjectV2DraftIssueItemToIssue.item.content.url // empty')
        
        if [ -n "$ISSUE_NUMBER" ]; then
            echo -e "${GREEN}✅ Created issue #$ISSUE_NUMBER${NC}"
            if [ -n "$ISSUE_URL" ]; then
                verbose_log "Issue URL: $ISSUE_URL"
            fi
            SUCCESS=$((SUCCESS + 1))
        else
            echo -e "${RED}❌ Failed to get issue number${NC}"
            debug_log "Convert result: $CONVERT_RESULT"
            FAILED=$((FAILED + 1))
        fi
        
        # Rate limiting delay
        sleep 0.5
        
    done < <(jq -c '.[]' "$EPICS_FILE")
    
    # Final summary
    echo ""
    echo -e "${BLUE}=========================================${NC}"
    echo -e "${GREEN}✅ EPIC CREATION COMPLETE!${NC}"
    echo -e "${BLUE}=========================================${NC}"
    echo -e "Total epics processed: $TOTAL"
    echo -e "Successfully created: ${GREEN}$SUCCESS${NC}"
    if [ $FAILED -gt 0 ]; then
        echo -e "Failed: ${RED}$FAILED${NC}"
    fi
    echo ""
    echo -e "${YELLOW}Project URL:${NC}"
    echo "https://github.com/users/$OWNER/projects/$PROJECT_NUMBER"
    echo -e "${BLUE}=========================================${NC}"
}

# Run main function
main "$@"