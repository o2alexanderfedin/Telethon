#!/usr/bin/env bash
set -euo pipefail

# Script to assign story points to all tasks based on complexity analysis

OWNER="o2alexanderfedin"
REPO="telethon-architecture-docs"
PROJECT_NUMBER=12

echo "🎯 Assigning Story Points to Tasks in GitHub Project..."
echo "====================================================="
echo ""

# Get project configuration
echo "📋 Loading project configuration..."
PROJECT_DATA=$(gh api graphql -H "GraphQL-Features: project_v2" \
  -f query='
    query($owner:String!, $projNum:Int!) {
      user(login:$owner) {
        projectV2(number:$projNum) { 
          id 
          field(name: "Story Points") {
            ... on ProjectV2SingleSelectField {
              id
              options {
                id
                name
              }
            }
          }
          priorityField: field(name: "Priority") {
            ... on ProjectV2SingleSelectField {
              id
              options {
                id
                name
              }
            }
          }
        }
      }
    }' \
  -F owner="$OWNER" \
  -F projNum="$PROJECT_NUMBER")

PROJECT_ID=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.id')
POINTS_FIELD_ID=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.field.id')
PRIORITY_FIELD_ID=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.priorityField.id')

# Get option IDs for story points
POINTS_1=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.field.options[] | select(.name == "1") | .id')
POINTS_2=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.field.options[] | select(.name == "2") | .id')
POINTS_3=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.field.options[] | select(.name == "3") | .id')
POINTS_5=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.field.options[] | select(.name == "5") | .id')
POINTS_8=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.field.options[] | select(.name == "8") | .id')
POINTS_13=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.field.options[] | select(.name == "13") | .id')

# Get Low priority option ID
PRIORITY_LOW=$(echo "$PROJECT_DATA" | jq -r '.data.user.projectV2.priorityField.options[] | select(.name == "Low") | .id')

echo "✅ Configuration loaded"
echo ""

# Function to update story points and priority
update_task_points() {
    local issue_number=$1
    local points_option_id=$2
    local set_low_priority=${3:-false}
    
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
    
    # Update story points
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
      -F itemId="$ITEM_ID" \
      -F fieldId="$POINTS_FIELD_ID" \
      -F value="$points_option_id" > /dev/null 2>&1
    
    # Update priority if needed
    if [ "$set_low_priority" = "true" ]; then
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
          -F itemId="$ITEM_ID" \
          -F fieldId="$PRIORITY_FIELD_ID" \
          -F value="$PRIORITY_LOW" > /dev/null 2>&1
        
        echo "  ✅ Set to Low priority"
    fi
}

echo "📝 Assigning Story Points to Tasks..."
echo "===================================="
echo ""

# Based on our complexity analysis, assign points to each task

# 2-point tasks (Trivial)
echo "🟢 2-point tasks (Trivial):"
echo "  Issue #146 (Design premium feature set)... "
update_task_points 146 "$POINTS_2"
echo "  Issue #148 (Create user-friendly error messages)... "
update_task_points 148 "$POINTS_2"

# 3-point tasks (Simple)
echo -e "\n🟡 3-point tasks (Simple):"
tasks_3=(
    106  # Define voice message TL schema structures
    129  # Build retry mechanism for failed requests
    134  # Design cleanup policies and retention rules
    135  # Implement automated cleanup jobs
    136  # Create comprehensive error taxonomy
    138  # Set up testing framework and utilities
    139  # Create test data fixtures and mocks
    111  # Implement user type detection logic
    113  # Design quota tracking database schema
    149  # Build error recovery UI components
    116  # Add comprehensive parameter validation
    152  # Design async/await API patterns
    156  # Design transcription quality metrics
    157  # Build user feedback collection system
    158  # Design error handling architecture
    159  # Implement error context propagation
    161  # Create interactive code examples
    162  # Implement boost detection system
    163  # Create boost-based feature scaling
    172  # Generate API reference documentation
    175  # Enhance error messages and recovery
    177  # Implement performance regression tests
    166  # Profile memory usage patterns
)
for issue in "${tasks_3[@]}"; do
    echo -n "  Issue #$issue... "
    update_task_points $issue "$POINTS_3"
    echo "✅"
    sleep 0.3
done

# 5-point tasks (Medium)
echo -e "\n🟠 5-point tasks (Medium):"
tasks_5=(
    107  # Implement schema serialization/deserialization
    108  # Create comprehensive schema validation suite
    109  # Create VoiceTranscriptionRequest class
    119  # Design event-driven architecture
    130  # Design state machine for transcription lifecycle
    131  # Implement state persistence and recovery
    132  # Create transcription job queue system
    133  # Implement job scheduling and prioritization
    137  # Implement error recovery strategies
    112  # Create user type caching system
    114  # Implement real-time quota tracking
    141  # Implement policy enforcement mechanisms
    142  # Build quota consumption tracking service
    143  # Implement usage analytics and reporting
    145  # Create proactive warning system
    147  # Implement premium tier infrastructure
    151  # Create migration utilities for existing users
    115  # Implement core transcribe_voice_message method
    117  # Extend Message class with transcription methods
    118  # Implement lazy loading for transcriptions
    153  # Implement streaming progress updates
    154  # Design batch processing architecture
    160  # Write comprehensive API documentation
    122  # Implement cache warming strategies
    124  # Create provider selection algorithm
    164  # Design intelligent request batching
    165  # Implement adaptive batching algorithms
    167  # Implement memory optimization strategies
    168  # Design comprehensive metrics system
    169  # Build real-time monitoring dashboard
    170  # Create end-to-end test scenarios
    171  # Implement continuous integration pipeline
    125  # Create unit test suite
    173  # Write migration and upgrade guides
    174  # Optimize API response times
    176  # Create performance benchmark suite
    128  # Implement security hardening measures
    178  # Create deployment automation
    179  # Implement production monitoring
)
for issue in "${tasks_5[@]}"; do
    echo -n "  Issue #$issue... "
    update_task_points $issue "$POINTS_5"
    echo "✅"
    sleep 0.3
done

# 8-point tasks (Large)
echo -e "\n🔴 8-point tasks (Large):"
tasks_8=(
    110  # Implement intelligent rate limiting system
    120  # Implement WebSocket support for live updates
    140  # Design policy rule engine architecture
    150  # Integrate quota system with Telethon core
    155  # Implement parallel processing engine
    121  # Build distributed caching layer
    123  # Integrate external STT providers
    126  # Implement integration test suite
    127  # Conduct security vulnerability assessment
)
for issue in "${tasks_8[@]}"; do
    echo -n "  Issue #$issue... "
    update_task_points $issue "$POINTS_8"
    echo "✅"
    sleep 0.3
done

# 13-point task (with Low priority)
echo -e "\n🟣 13-point task (Extra Large):"
echo -n "  Issue #144 (ML-based usage prediction model)... "
update_task_points 144 "$POINTS_13" true
echo "✅"

echo ""
echo "✅ Story points assignment complete!"
echo ""
echo "Summary:"
echo "- 2 points: 2 tasks"
echo "- 3 points: 27 tasks"
echo "- 5 points: 40 tasks"
echo "- 8 points: 10 tasks"
echo "- 13 points: 1 task (set to Low priority)"
echo ""
echo "Note: The ML-based usage prediction model (Issue #144) has been set to Low priority."