# Workflow Rules for Telethon Voice Transcription Development

## GitHub Project Management Rules

### RULE 1: Always Use Shell Scripts
- **What**: Use shell scripts from `/Users/alexanderfedin/Projects/demo/tools/github-project-management/utilities/` for ALL GitHub project operations
- **Why**: Ensures consistency, maintainability, and automation across the workflow
- **Scripts to use**:
  - `get-next-kanban-item-simple.sh` - Get next Task from kanban board
  - `update-task-status-simple.sh` - Update task status
  - `check-pr-status.sh` - Check pull request status
  - Other utilities as needed

### RULE 2: Task Types
- **Work on Tasks, not User Stories or Epics**
- Tasks are the actual engineering work items
- User Stories are high-level features
- Epics are collections of User Stories

### RULE 3: Single-Step Workflow
- Use `--auto-assign` flag to:
  1. Find next available Task
  2. Update status to "In Progress" 
  3. Create feature branch
  4. Save task information
- All in one command: `./get-next-kanban-item-simple.sh --auto-assign`

### RULE 4: Task Status Flow
- `Todo` or `No Status` → `In Progress` → `In Review` → `Done`
- Never skip status updates
- Always update status when changing work state

## Development Rules

### RULE 5: Git Flow
- Always work on feature branches
- Branch naming: `feature/<task-description>`
- Never commit directly to `main` or `develop`

### RULE 6: Testing
- Write tests for all new functionality
- Run tests before committing
- Ensure all tests pass before creating PR

### RULE 7: Error Handling
- Use the Voice Transcription Error Framework
- Handle all error cases explicitly
- Provide user-friendly error messages

## Command Reference

```bash
# Get next task and start working
/Users/alexanderfedin/Projects/demo/tools/github-project-management/utilities/get-next-kanban-item-simple.sh --auto-assign

# Update task status manually
/Users/alexanderfedin/Projects/demo/tools/github-project-management/utilities/update-task-status-simple.sh <task-number> "<status>"

# Check PR status
/Users/alexanderfedin/Projects/demo/tools/github-project-management/utilities/check-pr-status.sh
```