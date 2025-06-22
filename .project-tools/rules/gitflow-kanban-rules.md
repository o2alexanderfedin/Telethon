# GitFlow + Kanban Workflow Rules

## 🚨 MANDATORY RULES

### 1. Branch Protection
- **NEVER** commit directly to `main` or `develop`
- **ALWAYS** use GitFlow commands to create branches
- **BLOCKED**: Any commits outside GitFlow branches will be rejected

### 2. Feature Workflow
```bash
# Starting a feature (REQUIRED)
git flow feature start <feature-name>
# This will:
# - Create feature/<feature-name> branch
# - Search for related tasks
# - Auto-link if single match found
# - Update task status to "In Progress"

# Finishing a feature (REQUIRED)
git flow feature finish <feature-name>
# This will:
# - Merge to develop
# - Delete feature branch
# - Update linked task to "Done"
# - Archive feature statistics
```

### 3. Task Linking Rules
- **Every feature MUST have a linked task**
- **Task status MUST be "In Progress" before commits**
- **Task status MUST be updated to "Done" on finish**
- **Commits without linked tasks will show warnings**
- **Architecture docs are shown when task starts**
- **Completion reports are added when task finishes**

### 4. Pull Request Rules
- **PRs are automatically created on first push**
- **PRs MUST be completed before starting new work**
- **`git next` checks for open PRs and blocks if found**
- **Complete workflow: Push → PR → Review → Merge → Finish**

## 📋 WORKFLOW STEPS

### Starting New Work
1. **Check available tasks**: `git next`
2. **Start feature**: `git flow feature start <name>`
3. **Link task** (if not auto-linked): `echo '<task-number>' > .claude/current-task.txt`
4. **Task status updates**: 
   - Automatically set to "In Progress"
   - Relevant architecture docs are displayed
   - Start comment added to task with implementation plan
5. **Review architecture**: Check generated `.claude/task-<number>-arch-refs.md`

### During Development
1. **Make changes**: Edit files as needed
2. **Commit regularly**: Include task reference (e.g., "Refs #123")
3. **Push to remote**: `git push -u origin feature/<name>`
4. **PR automatically created**: Post-push hook creates PR with task reference
5. **Monitor PR status**: `git pr-status` to check progress

### Pull Request Phase
1. **Review PR status**: `git pr-status`
2. **Address feedback**: Make requested changes
3. **Fix CI failures**: `git ci-fix` if needed
4. **Get approval**: Request reviews as needed
5. **Merge PR**: `git pr-merge <number>` when approved

### Completing Work
1. **Ensure PR is merged**: Check with `git pr-status`
2. **Finish feature**: `git flow feature finish <name>`
3. **Task updates**: 
   - Automatically marked as "Done"
   - Detailed completion report added with:
     - Work summary and duration
     - Files changed and commits made
     - Linked PRs and next steps
4. **Cleanup**: Tracking files removed, stats archived
5. **Next task**: Run `git next` for next item (only allowed with no open PRs)

## 🔍 ENFORCEMENT MECHANISMS

### Pre-commit Hook
- ✅ Checks if on GitFlow branch
- ✅ Blocks commits to main/develop
- ✅ Verifies task is linked
- ✅ Updates task to "In Progress" if needed
- ✅ Tracks commit count and timing

### Post-checkout Hook
- ✅ Shows branch-specific guidance
- ✅ Warns about non-GitFlow branches
- ✅ Displays linked task info
- ✅ Shows feature age/staleness
- ✅ Provides next action hints

### Post-flow-feature-start Hook
- ✅ Searches for related tasks by name
- ✅ Auto-links single matching task
- ✅ Updates task status to "In Progress"
- ✅ Shows relevant architecture documentation
- ✅ Adds start comment to task with plan
- ✅ Creates feature tracking files
- ✅ Generates feature plan template

### Post-flow-feature-finish Hook
- ✅ Updates task status to "Done"
- ✅ Generates detailed completion report
- ✅ Adds report as task comment
- ✅ Archives feature statistics
- ✅ Checks for open PRs
- ✅ Cleans up tracking files
- ✅ Shows completion summary

### Post-push Hook
- ✅ Automatically creates PR on first feature push
- ✅ Links PR to task with "Fixes #123"
- ✅ Adds PR checklist for code quality
- ✅ Monitors CI/CD status
- ✅ Attempts auto-fixes for failures

## 📊 KANBAN INTEGRATION

### WIP Limits
- **In Progress**: Max 3 items
- **In Review**: Max 2 items
- **Testing**: Max 2 items

### Task Selection Priority
1. Blocked items you can unblock
2. Items blocking others
3. Highest priority + story points
4. Oldest ready items

### Status Transitions
- **Todo → In Progress**: When feature starts
- **In Progress → In Review**: When PR created
- **In Review → Testing**: When PR approved
- **Testing → Done**: When feature finished

## 🎯 BEST PRACTICES

### Feature Naming
- Use descriptive names: `user-authentication`, not `feature1`
- Match task titles when possible
- Use kebab-case (lowercase with hyphens)

### Commit Messages
```
<type>(<scope>): <subject>

Refs #<task-number>

<body>
```

Types: feat, fix, docs, style, refactor, test, chore

### Time Management
- Features auto-track duration
- Check stale features (>3 days no commits)
- Review feature stats on completion

### Task Hygiene
- One task per feature (usually)
- Update task description with implementation notes
- Link PRs to tasks using "Fixes #123"

## 🚫 PROHIBITED ACTIONS

1. **Direct commits to main/develop**
   - Use release/hotfix for main
   - Use features for develop

2. **Working without GitFlow**
   - No custom branch names
   - No direct branching

3. **Unlinked features**
   - Every feature needs a task
   - Link within first commit

4. **Skipping status updates**
   - Task must be "In Progress"
   - Must be "Done" on finish

5. **Starting new work with open PRs**
   - All PRs must be completed
   - `git next` enforces this rule
   - Use `git pr-status` to check

6. **Finishing feature without merged PR**
   - PR must be merged to develop first
   - Then run feature finish

## 🛠️ TROUBLESHOOTING

### "Not on a GitFlow branch" error
```bash
git stash                          # Save changes
git checkout develop               # Go to develop
git flow feature start <name>      # Start feature
git stash pop                      # Restore changes
```

### Task not auto-linking
```bash
# Manually link
echo '<task-number>' > .claude/current-task.txt

# Update status
./tools/github-project-management/utilities/update-task-status.sh <task-number> "In Progress"
```

### Feature finish fails
```bash
# Check for conflicts
git status

# Resolve conflicts
git add .
git commit

# Retry finish
git flow feature finish <name>
```

## 📈 METRICS TRACKED

- Feature duration (start to finish)
- Commit count per feature
- Time between commits
- Task completion rate
- Feature cycle time

## 🎮 QUICK COMMANDS

```bash
git workflow    # Full status dashboard
git next        # Get next task
git wip         # Check WIP limits
git blocked     # List blocked items
git ci-monitor  # Watch CI/CD status
```

## 🔄 WORKFLOW DIAGRAM

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Get Task   │────▶│Start Feature │────▶│Link to Task  │
│  (git next) │     │ (git flow)   │     │(auto/manual) │
└─────────────┘     └──────────────┘     └──────────────┘
                            │
                            ▼
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   Review    │◀────│  Push Code   │◀────│   Develop    │
│(Auto PR)    │     │ (git push)   │     │  (commits)   │
└─────────────┘     └──────────────┘     └──────────────┘
        │                                         ▲
        ▼                                         │
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│Merge PR     │────▶│Finish Feature│────▶│  Task→Done   │
│(git pr-merge)│    │ (git flow)   │     │   (auto)     │
└─────────────┘     └──────────────┘     └──────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │  Next Task   │
                    │  (git next)  │
                    └──────────────┘
```

---

**Remember**: These rules ensure quality, traceability, and team coordination. Following them makes development smoother and more predictable!