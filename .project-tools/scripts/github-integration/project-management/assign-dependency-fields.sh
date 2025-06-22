#!/usr/bin/env bash
set -euo pipefail

# Script to assign dependency tracking fields to all user stories
# Based on the user story dependencies analysis document

OWNER="o2alexanderfedin"
REPO="telethon-architecture-docs"
PROJECT_NUMBER=12

echo "🔗 Assigning Dependency Fields to User Stories..."
echo "==============================================="
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

# Get field IDs
PHASE_FIELD_ID=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name == "Implementation Phase") | .id')
DEP_STATUS_FIELD_ID=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name == "Dependency Status") | .id')
PARALLEL_FIELD_ID=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name == "Parallelization") | .id')
RISK_FIELD_ID=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name == "Dependency Risk") | .id')

# Get option IDs for each field
# Implementation Phase options
PHASE_1=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name == "Implementation Phase") | .options[] | select(.name == "Phase 1") | .id')
PHASE_2=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name == "Implementation Phase") | .options[] | select(.name == "Phase 2") | .id')
PHASE_3=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name == "Implementation Phase") | .options[] | select(.name == "Phase 3") | .id')
PHASE_4=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name == "Implementation Phase") | .options[] | select(.name == "Phase 4") | .id')
PHASE_5=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name == "Implementation Phase") | .options[] | select(.name == "Phase 5") | .id')

# Dependency Status options
STATUS_READY=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name == "Dependency Status") | .options[] | select(.name == "Ready") | .id')
STATUS_BLOCKED=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name == "Dependency Status") | .options[] | select(.name == "Blocked") | .id')
STATUS_PARTIAL=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name == "Dependency Status") | .options[] | select(.name == "Partial") | .id')
STATUS_UNKNOWN=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name == "Dependency Status") | .options[] | select(.name == "Unknown") | .id')

# Parallelization options
PARALLEL_SEQ=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name == "Parallelization") | .options[] | select(.name == "Sequential") | .id')
PARALLEL_PAR=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name == "Parallelization") | .options[] | select(.name == "Parallel") | .id')
PARALLEL_IND=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name == "Parallelization") | .options[] | select(.name == "Independent") | .id')
PARALLEL_COND=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name == "Parallelization") | .options[] | select(.name == "Conditional") | .id')

# Dependency Risk options
RISK_CRITICAL=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name == "Dependency Risk") | .options[] | select(.name == "Critical") | .id')
RISK_HIGH=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name == "Dependency Risk") | .options[] | select(.name == "High") | .id')
RISK_MEDIUM=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name == "Dependency Risk") | .options[] | select(.name == "Medium") | .id')
RISK_LOW=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name == "Dependency Risk") | .options[] | select(.name == "Low") | .id')

echo "✅ Configuration loaded"
echo ""

# Function to update a single field
update_field() {
    local item_id=$1
    local field_id=$2
    local option_id=$3
    
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
}

# Function to update all dependency fields for a story
update_story_dependencies() {
    local issue_number=$1
    local phase_option=$2
    local status_option=$3
    local parallel_option=$4
    local risk_option=$5
    
    # Get project item ID
    ITEM_DATA=$(gh api graphql -H "GraphQL-Features: project_v2" \
      -f query='
        query($owner:String!, $repo:String!, $number:Int!) {
          repository(owner:$owner, name:$repo) {
            issue(number:$number) {
              projectItems(first:1) {
                nodes {
                  id
                }
              }
            }
          }
        }' \
      -F owner="$OWNER" \
      -F repo="$REPO" \
      -F number="$issue_number" 2>/dev/null)
    
    ITEM_ID=$(echo "$ITEM_DATA" | jq -r '.data.repository.issue.projectItems.nodes[0].id // empty')
    
    if [ -z "$ITEM_ID" ]; then
        echo "  ❌ Issue #$issue_number not in project"
        return
    fi
    
    # Update all fields
    update_field "$ITEM_ID" "$PHASE_FIELD_ID" "$phase_option"
    update_field "$ITEM_ID" "$DEP_STATUS_FIELD_ID" "$status_option"
    update_field "$ITEM_ID" "$PARALLEL_FIELD_ID" "$parallel_option"
    update_field "$ITEM_ID" "$RISK_FIELD_ID" "$risk_option"
    
    echo "  ✅ Updated"
}

echo "📝 Assigning Dependency Fields by Phase..."
echo "========================================"
echo ""

# Phase 1: Foundation (Epic 1)
echo "🟣 Phase 1: Foundation - Core Infrastructure"
echo "-------------------------------------------"

# Critical foundation stories that block everything
echo "Updating critical foundation stories..."
echo -n "  #69 TL Schema Definitions... "
update_story_dependencies 69 "$PHASE_1" "$STATUS_READY" "$PARALLEL_SEQ" "$RISK_CRITICAL"

echo -n "  #75 Error Handling Framework... "
update_story_dependencies 75 "$PHASE_1" "$STATUS_READY" "$PARALLEL_SEQ" "$RISK_CRITICAL"

echo -n "  #76 Basic Testing Infrastructure... "
update_story_dependencies 76 "$PHASE_1" "$STATUS_READY" "$PARALLEL_SEQ" "$RISK_CRITICAL"

echo -n "  #70 Basic Request Implementation... "
update_story_dependencies 70 "$PHASE_1" "$STATUS_BLOCKED" "$PARALLEL_SEQ" "$RISK_HIGH"

echo -n "  #71 Update Handling System... "
update_story_dependencies 71 "$PHASE_1" "$STATUS_BLOCKED" "$PARALLEL_SEQ" "$RISK_MEDIUM"

echo -n "  #72 Transcription State Management... "
update_story_dependencies 72 "$PHASE_1" "$STATUS_BLOCKED" "$PARALLEL_SEQ" "$RISK_MEDIUM"

echo -n "  #73 Basic Transcription Manager... "
update_story_dependencies 73 "$PHASE_1" "$STATUS_BLOCKED" "$PARALLEL_SEQ" "$RISK_MEDIUM"

echo -n "  #74 Automatic Cleanup System... "
update_story_dependencies 74 "$PHASE_1" "$STATUS_BLOCKED" "$PARALLEL_COND" "$RISK_LOW"

echo ""

# Phase 2: User Management (Epic 2)
echo "🔵 Phase 2: User Management - Quota System"
echo "-----------------------------------------"

echo -n "  #77 User Type Detection System... "
update_story_dependencies 77 "$PHASE_2" "$STATUS_BLOCKED" "$PARALLEL_SEQ" "$RISK_HIGH"

echo -n "  #78 Quota Tracking Infrastructure... "
update_story_dependencies 78 "$PHASE_2" "$STATUS_BLOCKED" "$PARALLEL_SEQ" "$RISK_HIGH"

echo -n "  #84 Integration with Core Infrastructure... "
update_story_dependencies 84 "$PHASE_2" "$STATUS_BLOCKED" "$PARALLEL_SEQ" "$RISK_CRITICAL"

echo -n "  #79 Policy Engine Implementation... "
update_story_dependencies 79 "$PHASE_2" "$STATUS_BLOCKED" "$PARALLEL_SEQ" "$RISK_MEDIUM"

echo -n "  #80 Quota Consumption Management... "
update_story_dependencies 80 "$PHASE_2" "$STATUS_BLOCKED" "$PARALLEL_SEQ" "$RISK_MEDIUM"

echo -n "  #82 Premium User Experience... "
update_story_dependencies 82 "$PHASE_2" "$STATUS_BLOCKED" "$PARALLEL_COND" "$RISK_LOW"

echo -n "  #83 Error Handling and User Feedback... "
update_story_dependencies 83 "$PHASE_2" "$STATUS_BLOCKED" "$PARALLEL_COND" "$RISK_LOW"

echo -n "  #81 Usage Prediction and Warnings... "
update_story_dependencies 81 "$PHASE_2" "$STATUS_BLOCKED" "$PARALLEL_PAR" "$RISK_LOW"

echo ""

# Phase 3: High-Level API (Epic 3)
echo "🟢 Phase 3: High-Level API - Client Integration"
echo "----------------------------------------------"

echo -n "  #85 Basic Transcription Method... "
update_story_dependencies 85 "$PHASE_3" "$STATUS_BLOCKED" "$PARALLEL_SEQ" "$RISK_HIGH"

echo -n "  #86 Message Object Integration... "
update_story_dependencies 86 "$PHASE_3" "$STATUS_BLOCKED" "$PARALLEL_SEQ" "$RISK_HIGH"

echo -n "  #87 Event System for Transcription Progress... "
update_story_dependencies 87 "$PHASE_3" "$STATUS_BLOCKED" "$PARALLEL_COND" "$RISK_MEDIUM"

echo -n "  #88 Progress Callbacks and Async Patterns... "
update_story_dependencies 88 "$PHASE_3" "$STATUS_BLOCKED" "$PARALLEL_COND" "$RISK_MEDIUM"

echo -n "  #91 Comprehensive Error Handling... "
update_story_dependencies 91 "$PHASE_3" "$STATUS_BLOCKED" "$PARALLEL_COND" "$RISK_MEDIUM"

echo -n "  #89 Batch Transcription Support... "
update_story_dependencies 89 "$PHASE_3" "$STATUS_BLOCKED" "$PARALLEL_PAR" "$RISK_LOW"

echo -n "  #90 Quality Rating System... "
update_story_dependencies 90 "$PHASE_3" "$STATUS_BLOCKED" "$PARALLEL_PAR" "$RISK_LOW"

echo -n "  #92 Documentation and Examples... "
update_story_dependencies 92 "$PHASE_3" "$STATUS_BLOCKED" "$PARALLEL_PAR" "$RISK_LOW"

echo ""

# Phase 4: Advanced Features (Epic 4) - Can run parallel
echo "🟠 Phase 4: Advanced Features - Optimization (PARALLEL)"
echo "-----------------------------------------------------"

echo -n "  #93 Intelligent Caching System... "
update_story_dependencies 93 "$PHASE_4" "$STATUS_BLOCKED" "$PARALLEL_PAR" "$RISK_LOW"

echo -n "  #98 Performance Monitoring and Metrics... "
update_story_dependencies 98 "$PHASE_4" "$STATUS_BLOCKED" "$PARALLEL_PAR" "$RISK_LOW"

echo -n "  #95 External STT Fallback System... "
update_story_dependencies 95 "$PHASE_4" "$STATUS_BLOCKED" "$PARALLEL_IND" "$RISK_LOW"

echo -n "  #94 Supergroup Boost Integration... "
update_story_dependencies 94 "$PHASE_4" "$STATUS_BLOCKED" "$PARALLEL_PAR" "$RISK_LOW"

echo -n "  #96 Request Batching Optimization... "
update_story_dependencies 96 "$PHASE_4" "$STATUS_BLOCKED" "$PARALLEL_PAR" "$RISK_LOW"

echo -n "  #97 Memory Usage Optimization... "
update_story_dependencies 97 "$PHASE_4" "$STATUS_BLOCKED" "$PARALLEL_PAR" "$RISK_LOW"

echo -n "  #99 Integration and Testing... "
update_story_dependencies 99 "$PHASE_4" "$STATUS_BLOCKED" "$PARALLEL_COND" "$RISK_MEDIUM"

echo ""

# Phase 5: Testing & Polish (Epic 5)
echo "🔴 Phase 5: Testing, Documentation & Polish"
echo "------------------------------------------"

echo -n "  #100 Comprehensive Test Coverage... "
update_story_dependencies 100 "$PHASE_5" "$STATUS_BLOCKED" "$PARALLEL_SEQ" "$RISK_MEDIUM"

echo -n "  #104 Security Audit and Hardening... "
update_story_dependencies 104 "$PHASE_5" "$STATUS_BLOCKED" "$PARALLEL_SEQ" "$RISK_HIGH"

echo -n "  #103 Performance Benchmarking... "
update_story_dependencies 103 "$PHASE_5" "$STATUS_BLOCKED" "$PARALLEL_COND" "$RISK_MEDIUM"

echo -n "  #102 User Experience Polish... "
update_story_dependencies 102 "$PHASE_5" "$STATUS_BLOCKED" "$PARALLEL_PAR" "$RISK_LOW"

echo -n "  #101 Complete API Documentation... "
update_story_dependencies 101 "$PHASE_5" "$STATUS_BLOCKED" "$PARALLEL_PAR" "$RISK_LOW"

echo -n "  #105 Production Deployment Readiness... "
update_story_dependencies 105 "$PHASE_5" "$STATUS_BLOCKED" "$PARALLEL_SEQ" "$RISK_CRITICAL"

echo ""
echo "✅ Dependency fields assignment complete!"
echo ""
echo "Summary:"
echo "- Phase 1: 8 stories (3 critical, must start first)"
echo "- Phase 2: 8 stories (includes moved #84)"
echo "- Phase 3: 8 stories (depends on Phase 1 & 2)"
echo "- Phase 4: 7 stories (can run parallel with Phase 3)"
echo "- Phase 5: 6 stories (final testing and polish)"
echo ""
echo "Critical Path Items (Risk=Critical):"
echo "- #69 TL Schema Definitions"
echo "- #75 Error Handling Framework"
echo "- #76 Basic Testing Infrastructure"
echo "- #84 Integration with Core Infrastructure"
echo "- #105 Production Deployment Readiness"
echo ""
echo "Note: All stories start as 'Blocked' except the 3 foundation stories that are 'Ready'"