#!/bin/bash

# Replace these variables with your values
PARENT_ISSUE_NODE_ID="PARENT_ISSUE_NODE_ID_HERE"
SUB_ISSUE_NODE_ID="SUB_ISSUE_NODE_ID_HERE"

# GitHub CLI command to execute the GraphQL mutation
gh api graphql -f query='
mutation($input: AddSubIssueInput!) {
  addSubIssue(input: $input) {
    parent {
      id
    }
    subIssue {
      id
    }
  }
}' -F input="{\"parentId\":\"$PARENT_ISSUE_NODE_ID\",\"subIssueId\":\"$SUB_ISSUE_NODE_ID\"}"