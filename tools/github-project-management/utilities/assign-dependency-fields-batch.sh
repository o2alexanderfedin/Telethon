#!/usr/bin/env bash
set -euo pipefail

# Batch script to assign dependency fields - Phase 1 only
# Run multiple scripts for different phases to avoid timeout

OWNER="o2alexanderfedin"
REPO="telethon-architecture-docs"
PROJECT_NUMBER=12
PHASE="${1:-1}"  # Default to Phase 1

echo "🔗 Assigning Dependency Fields - Phase $PHASE"
echo "==========================================="
echo ""

# Get project configuration
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

# Get field and option IDs
get_field_id() {
    echo "$PROJECT_DATA" | jq -r --arg name "$1" '.data.user.projectV2.fields.nodes[] | select(.name == $name) | .id'
}

get_option_id() {
    local field_name=$1
    local option_name=$2
    echo "$PROJECT_DATA" | jq -r --arg field "$field_name" --arg option "$option_name" \
      '.data.user.projectV2.fields.nodes[] | select(.name == $field) | .options[] | select(.name == $option) | .id'
}

PHASE_FIELD_ID=$(get_field_id "Implementation Phase")
DEP_STATUS_FIELD_ID=$(get_field_id "Dependency Status")
PARALLEL_FIELD_ID=$(get_field_id "Parallelization")
RISK_FIELD_ID=$(get_field_id "Dependency Risk")

# Update function
update_story() {
    local issue_number=$1
    local phase=$2
    local status=$3
    local parallel=$4
    local risk=$5
    
    echo -n "  #$issue_number... "
    
    # Get item ID
    ITEM_ID=$(gh api graphql -H "GraphQL-Features: project_v2" \
      -f query='
        query($owner:String!, $repo:String!, $number:Int!) {
          repository(owner:$owner, name:$repo) {
            issue(number:$number) {
              projectItems(first:1) {
                nodes { id }
              }
            }
          }
        }' \
      -F owner="$OWNER" \
      -F repo="$REPO" \
      -F number="$issue_number" 2>/dev/null | \
      jq -r '.data.repository.issue.projectItems.nodes[0].id // empty')
    
    if [ -z "$ITEM_ID" ]; then
        echo "❌ Not in project"
        return
    fi
    
    # Create a single mutation with all field updates
    gh api graphql -H "GraphQL-Features: project_v2" \
      -f query='
        mutation(
          $projId:ID!, $itemId:ID!,
          $phaseFieldId:ID!, $phaseValue:String!,
          $statusFieldId:ID!, $statusValue:String!,
          $parallelFieldId:ID!, $parallelValue:String!,
          $riskFieldId:ID!, $riskValue:String!
        ) {
          phase: updateProjectV2ItemFieldValue(input: {
            projectId: $projId, itemId: $itemId, fieldId: $phaseFieldId,
            value: { singleSelectOptionId: $phaseValue }
          }) { projectV2Item { id } }
          
          status: updateProjectV2ItemFieldValue(input: {
            projectId: $projId, itemId: $itemId, fieldId: $statusFieldId,
            value: { singleSelectOptionId: $statusValue }
          }) { projectV2Item { id } }
          
          parallel: updateProjectV2ItemFieldValue(input: {
            projectId: $projId, itemId: $itemId, fieldId: $parallelFieldId,
            value: { singleSelectOptionId: $parallelValue }
          }) { projectV2Item { id } }
          
          risk: updateProjectV2ItemFieldValue(input: {
            projectId: $projId, itemId: $itemId, fieldId: $riskFieldId,
            value: { singleSelectOptionId: $riskValue }
          }) { projectV2Item { id } }
        }' \
      -F projId="$PROJECT_ID" \
      -F itemId="$ITEM_ID" \
      -F phaseFieldId="$PHASE_FIELD_ID" \
      -F phaseValue="$(get_option_id "Implementation Phase" "$phase")" \
      -F statusFieldId="$DEP_STATUS_FIELD_ID" \
      -F statusValue="$(get_option_id "Dependency Status" "$status")" \
      -F parallelFieldId="$PARALLEL_FIELD_ID" \
      -F parallelValue="$(get_option_id "Parallelization" "$parallel")" \
      -F riskFieldId="$RISK_FIELD_ID" \
      -F riskValue="$(get_option_id "Dependency Risk" "$risk")" > /dev/null 2>&1
    
    echo "✅"
    sleep 0.2  # Small delay to avoid rate limits
}

case $PHASE in
    1)
        echo "🟣 Phase 1: Foundation - Core Infrastructure"
        echo "-------------------------------------------"
        update_story 69 "Phase 1" "Ready" "Sequential" "Critical"
        update_story 75 "Phase 1" "Ready" "Sequential" "Critical"
        update_story 76 "Phase 1" "Ready" "Sequential" "Critical"
        update_story 70 "Phase 1" "Blocked" "Sequential" "High"
        update_story 71 "Phase 1" "Blocked" "Sequential" "Medium"
        update_story 72 "Phase 1" "Blocked" "Sequential" "Medium"
        update_story 73 "Phase 1" "Blocked" "Sequential" "Medium"
        update_story 74 "Phase 1" "Blocked" "Conditional" "Low"
        ;;
    2)
        echo "🔵 Phase 2: User Management - Quota System"
        echo "-----------------------------------------"
        update_story 77 "Phase 2" "Blocked" "Sequential" "High"
        update_story 78 "Phase 2" "Blocked" "Sequential" "High"
        update_story 84 "Phase 2" "Blocked" "Sequential" "Critical"
        update_story 79 "Phase 2" "Blocked" "Sequential" "Medium"
        update_story 80 "Phase 2" "Blocked" "Sequential" "Medium"
        update_story 82 "Phase 2" "Blocked" "Conditional" "Low"
        update_story 83 "Phase 2" "Blocked" "Conditional" "Low"
        update_story 81 "Phase 2" "Blocked" "Parallel" "Low"
        ;;
    3)
        echo "🟢 Phase 3: High-Level API - Client Integration"
        echo "----------------------------------------------"
        update_story 85 "Phase 3" "Blocked" "Sequential" "High"
        update_story 86 "Phase 3" "Blocked" "Sequential" "High"
        update_story 87 "Phase 3" "Blocked" "Conditional" "Medium"
        update_story 88 "Phase 3" "Blocked" "Conditional" "Medium"
        update_story 91 "Phase 3" "Blocked" "Conditional" "Medium"
        update_story 89 "Phase 3" "Blocked" "Parallel" "Low"
        update_story 90 "Phase 3" "Blocked" "Parallel" "Low"
        update_story 92 "Phase 3" "Blocked" "Parallel" "Low"
        ;;
    4)
        echo "🟠 Phase 4: Advanced Features - Optimization"
        echo "-------------------------------------------"
        update_story 93 "Phase 4" "Blocked" "Parallel" "Low"
        update_story 98 "Phase 4" "Blocked" "Parallel" "Low"
        update_story 95 "Phase 4" "Blocked" "Independent" "Low"
        update_story 94 "Phase 4" "Blocked" "Parallel" "Low"
        update_story 96 "Phase 4" "Blocked" "Parallel" "Low"
        update_story 97 "Phase 4" "Blocked" "Parallel" "Low"
        update_story 99 "Phase 4" "Blocked" "Conditional" "Medium"
        ;;
    5)
        echo "🔴 Phase 5: Testing, Documentation & Polish"
        echo "------------------------------------------"
        update_story 100 "Phase 5" "Blocked" "Sequential" "Medium"
        update_story 104 "Phase 5" "Blocked" "Sequential" "High"
        update_story 103 "Phase 5" "Blocked" "Conditional" "Medium"
        update_story 102 "Phase 5" "Blocked" "Parallel" "Low"
        update_story 101 "Phase 5" "Blocked" "Parallel" "Low"
        update_story 105 "Phase 5" "Blocked" "Sequential" "Critical"
        ;;
    *)
        echo "❌ Invalid phase number. Use 1-5"
        exit 1
        ;;
esac

echo ""
echo "✅ Phase $PHASE dependency fields assigned!"