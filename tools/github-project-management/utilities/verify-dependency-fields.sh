#!/usr/bin/env bash
set -euo pipefail

# Script to verify dependency fields were assigned correctly

OWNER="o2alexanderfedin"
PROJECT_NUMBER=12

echo "🔍 Verifying Dependency Field Assignments..."
echo "=========================================="
echo ""

# Get a sample of issues from each phase
SAMPLE_ISSUES=(69 77 85 93 100)  # One from each phase

for issue_num in "${SAMPLE_ISSUES[@]}"; do
    echo -n "Checking issue #$issue_num... "
    
    # Get issue data with project fields
    ISSUE_DATA=$(gh api graphql -H "GraphQL-Features: project_v2" \
      -f query='
        query($owner:String!, $projNum:Int!) {
          user(login:$owner) {
            projectV2(number:$projNum) {
              items(first:100) {
                nodes {
                  content {
                    ... on Issue {
                      number
                      title
                    }
                  }
                  fieldValues(first:20) {
                    nodes {
                      ... on ProjectV2ItemFieldSingleSelectValue {
                        name
                        field {
                          ... on ProjectV2SingleSelectField {
                            name
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }' \
      -F owner="$OWNER" \
      -F projNum="$PROJECT_NUMBER" | \
      jq --arg num "$issue_num" '.data.user.projectV2.items.nodes[] | select(.content.number == ($num | tonumber))')
    
    if [ -z "$ISSUE_DATA" ]; then
        echo "❌ Not found"
        continue
    fi
    
    # Extract field values
    TITLE=$(echo "$ISSUE_DATA" | jq -r '.content.title')
    PHASE=$(echo "$ISSUE_DATA" | jq -r '.fieldValues.nodes[] | select(.field.name == "Implementation Phase") | .name // "Not set"')
    STATUS=$(echo "$ISSUE_DATA" | jq -r '.fieldValues.nodes[] | select(.field.name == "Dependency Status") | .name // "Not set"')
    PARALLEL=$(echo "$ISSUE_DATA" | jq -r '.fieldValues.nodes[] | select(.field.name == "Parallelization") | .name // "Not set"')
    RISK=$(echo "$ISSUE_DATA" | jq -r '.fieldValues.nodes[] | select(.field.name == "Dependency Risk") | .name // "Not set"')
    
    echo "✅"
    echo "  Title: $TITLE"
    echo "  Phase: $PHASE"
    echo "  Status: $STATUS"
    echo "  Parallelization: $PARALLEL"
    echo "  Risk: $RISK"
    echo ""
done

echo "📊 Overall Summary:"
echo "=================="

# Get counts by phase
echo ""
echo "Issues by Implementation Phase:"
gh api graphql -H "GraphQL-Features: project_v2" \
  -f query='
    query($owner:String!, $projNum:Int!) {
      user(login:$owner) {
        projectV2(number:$projNum) {
          items(first:100) {
            nodes {
              fieldValues(first:20) {
                nodes {
                  ... on ProjectV2ItemFieldSingleSelectValue {
                    name
                    field {
                      ... on ProjectV2SingleSelectField {
                        name
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }' \
  -F owner="$OWNER" \
  -F projNum="$PROJECT_NUMBER" | \
  jq -r '.data.user.projectV2.items.nodes[].fieldValues.nodes[] | select(.field.name == "Implementation Phase") | .name' | \
  sort | uniq -c | sort -nr

echo ""
echo "Issues by Dependency Status:"
gh api graphql -H "GraphQL-Features: project_v2" \
  -f query='
    query($owner:String!, $projNum:Int!) {
      user(login:$owner) {
        projectV2(number:$projNum) {
          items(first:100) {
            nodes {
              fieldValues(first:20) {
                nodes {
                  ... on ProjectV2ItemFieldSingleSelectValue {
                    name
                    field {
                      ... on ProjectV2SingleSelectField {
                        name
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }' \
  -F owner="$OWNER" \
  -F projNum="$PROJECT_NUMBER" | \
  jq -r '.data.user.projectV2.items.nodes[].fieldValues.nodes[] | select(.field.name == "Dependency Status") | .name' | \
  sort | uniq -c | sort -nr