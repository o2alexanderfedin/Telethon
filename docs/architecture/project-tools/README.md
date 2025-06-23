# Project Tools

This directory contains all the development tools, scripts, hooks, and configurations for the Telethon Architecture Documentation project. These tools enforce coding standards, automate workflows, and ensure project quality.

## 📁 Directory Structure

```
.project-tools/
├── configs/          # Configuration files for linting and formatting
├── hooks/            # Git hooks for workflow enforcement
├── rules/            # Workflow and project rules
├── scripts/          # Automation scripts
├── workflows/        # GitHub Actions CI/CD workflows
├── install.sh        # One-click installer for all tools
└── README.md         # This file
```

## 🚀 Quick Start

To install all project tools:

```bash
./.project-tools/install.sh
```

This will:
- Install Git hooks
- Set up configuration files
- Configure Git aliases
- Create necessary directories
- Make all scripts executable

## 📂 Components

### 1. Configurations (`configs/`)

| File | Purpose |
|------|---------|
| `.markdownlint.json` | Markdown linting rules |
| `.yamllint.yml` | YAML linting configuration |
| `.shellcheckrc` | Shell script linting rules |
| `cspell.json` | Spell checking dictionary |
| `.editorconfig` | Cross-editor formatting |
| `.prettierrc` | Code formatting rules |
| `.prettierignore` | Files to ignore for Prettier |
| `workflow-config.env` | Workflow environment settings |

### 2. Git Hooks (`hooks/`)

| Hook | Trigger | Purpose |
|------|---------|---------|
| `pre-commit` | Before commit | Enforces GitFlow, blocks main/develop commits |
| `post-commit` | After commit | Updates tracking, shows reminders |
| `pre-push` | Before push | Final validations |
| `post-push` | After push | CI/CD monitoring, PR creation |
| `post-checkout` | After branch switch | Shows branch guidance |
| `post-flow-feature-start` | After feature start | Links tasks, shows architecture |
| `post-flow-feature-finish` | After feature finish | Updates task status, cleanup |

### 3. Rules (`rules/`)

- **`gitflow-kanban-rules.md`** - Comprehensive GitFlow + Kanban workflow rules
- **`kanban-workflow.rules`** - Kanban-specific configurations
- **`code-principles.rules`** - SOLID, KISS, DRY, Clean Code enforcement
- **`code-review-checklist.md`** - Systematic review process
- **`pre-commit.rules`** - Pre-commit validation rules
- **`commit-msg.rules`** - Commit message standards
- **`pre-push.rules`** - Pre-push validation rules

### 4. Scripts (`scripts/`)

#### Workflow Scripts (`scripts/workflow/`)
- `install-workflow-hooks.sh` - Installs GitFlow hooks
- `show-workflow-status.sh` - Displays comprehensive status

#### GitHub Integration (`scripts/github-integration/`)

**Project Management:**
- `add-draft-items.sh` - Add draft items to project
- `convert-drafts-to-issues.sh` - Convert drafts to issues
- `update-task-status.sh` - Update task status
- `assign-story-points.sh` - Assign story points
- `assign-dependency-fields.sh` - Manage dependencies

**Workflow:**
- `get-next-kanban-item.sh` - Get next task to work on
- `check-wip-limits.sh` - Check work-in-progress limits
- `list-blocked-items.sh` - List blocked tasks
- `check-pr-status.sh` - Check pull request status
- `validate-gitflow.sh` - Validate GitFlow compliance
- `show-architecture-guidance.sh` - Show relevant architecture docs

#### CI/CD Scripts (`scripts/ci-cd/`)
- `fix-ci-failures.sh` - Analyze and fix CI failures
- `monitor-ci-realtime.sh` - Real-time CI monitoring

### 5. Workflows (`workflows/`)

- **`ci.yml`** - Comprehensive CI pipeline with:
  - Multiple linters (ShellCheck, Markdownlint, etc.)
  - Security scanning
  - Test coverage
  - Build verification
  - Documentation checks

- **`cd.yml`** - CD pipeline with:
  - Environment-specific deployments
  - Manual approval for production
  - Rollback capability
  - Deployment tracking

## 🎯 Git Aliases

After installation, these Git aliases are available:

| Alias | Command | Description |
|-------|---------|-------------|
| `git workflow` | Show workflow status | Complete status dashboard |
| `git next` | Get next task | Find next Kanban item |
| `git wip` | Check WIP limits | Verify work-in-progress |
| `git blocked` | List blocked items | Show blocked tasks |
| `git ci-fix` | Fix CI failures | Analyze and fix CI |
| `git ci-monitor` | Monitor CI | Real-time CI status |
| `git validate` | Validate GitFlow | Check branch compliance |
| `git arch` | Architecture guide | Show relevant docs |
| `git pr-status` | PR status | Check all open PRs |

## 🔧 Configuration

### Project Settings

Edit `.claude/workflow-config.env`:

```bash
PROJECT_OWNER=your-github-username
PROJECT_NUMBER=your-project-number
KANBAN_WIP_LIMIT_IN_PROGRESS=3
KANBAN_WIP_LIMIT_IN_REVIEW=2
```

### Linting Rules

Customize linting by editing:
- `.markdownlint.json` for Markdown
- `.shellcheckrc` for Shell scripts
- `cspell.json` for spell checking

## 📋 Workflow Overview

1. **Start Feature**: `git flow feature start feature-name`
   - Automatically links to task
   - Shows architecture guidance
   - Updates task to "In Progress"

2. **Develop**: Make commits on feature branch
   - Pre-commit hooks ensure quality
   - Commit count tracked

3. **Push**: `git push -u origin feature/feature-name`
   - Auto-creates PR on first push
   - Monitors CI/CD status
   - Attempts auto-fixes for failures

4. **Complete**: `git flow feature finish feature-name`
   - Updates task to "Done"
   - Adds completion report
   - Cleans up tracking

## 🚨 Important Rules

1. **No direct commits** to main or develop branches
2. **All features** must use GitFlow
3. **Tasks must be linked** to features
4. **PRs must be completed** before new work
5. **Follow SOLID principles** in all code

## 🐛 Troubleshooting

### Hook not triggering
```bash
chmod +x .git/hooks/hook-name
```

### Task not linking
```bash
echo 'task-number' > .claude/current-task.txt
```

### CI failing
```bash
git ci-fix  # Analyzes and suggests fixes
```

## 📚 Documentation

For more details on specific components:
- GitFlow rules: `.project-tools/rules/gitflow-kanban-rules.md`
- Code principles: `.project-tools/rules/code-principles.rules`
- CI/CD setup: `.project-tools/workflows/`

## 🤝 Contributing

1. Use the installed tools and follow the workflow
2. All changes must pass CI checks
3. Follow the code review checklist
4. Update documentation as needed

---

**Note**: This toolset is designed to work with GitHub Projects v2 and requires the GitHub CLI (`gh`) to be installed and authenticated.