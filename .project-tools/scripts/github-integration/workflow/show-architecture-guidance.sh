#!/bin/bash

# Script: show-architecture-guidance.sh
# Purpose: Display architecture guidance for current task
# Usage: ./show-architecture-guidance.sh [task-number]

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Get task number
if [ $# -eq 1 ]; then
    TASK_NUMBER=$1
elif [ -f ".claude/current-task.txt" ]; then
    TASK_NUMBER=$(cat .claude/current-task.txt)
else
    echo -e "${RED}No task specified or linked${NC}"
    echo -e "Usage: $0 <task-number>"
    exit 1
fi

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}           ARCHITECTURE GUIDANCE FOR TASK #$TASK_NUMBER           ${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Get task details
TASK_INFO=$(gh issue view "$TASK_NUMBER" --json title,body,labels 2>/dev/null)
if [ $? -ne 0 ]; then
    echo -e "${RED}Could not fetch task #$TASK_NUMBER${NC}"
    exit 1
fi

TASK_TITLE=$(echo "$TASK_INFO" | jq -r '.title')
TASK_TYPE=$(echo "$TASK_INFO" | jq -r '.labels[] | select(.name | startswith("Type:")) | .name' | head -1)

echo -e "\n${PURPLE}📌 Task: ${YELLOW}$TASK_TITLE${NC}"
echo -e "${PURPLE}Type: ${YELLOW}${TASK_TYPE:-Unknown}${NC}"

# Architecture principles based on task type
echo -e "\n${PURPLE}🏗️ Architecture Principles to Follow:${NC}"

# General principles (always shown)
echo -e "\n${BLUE}SOLID Principles:${NC}"
echo -e "  ${GREEN}S${NC} - Single Responsibility: Each class/function should have one reason to change"
echo -e "  ${GREEN}O${NC} - Open/Closed: Open for extension, closed for modification"
echo -e "  ${GREEN}L${NC} - Liskov Substitution: Subtypes must be substitutable for base types"
echo -e "  ${GREEN}I${NC} - Interface Segregation: Many specific interfaces are better than one general"
echo -e "  ${GREEN}D${NC} - Dependency Inversion: Depend on abstractions, not concretions"

echo -e "\n${BLUE}Clean Code Practices:${NC}"
echo -e "  • ${GREEN}KISS${NC} - Keep It Simple, Stupid"
echo -e "  • ${GREEN}DRY${NC} - Don't Repeat Yourself"
echo -e "  • ${GREEN}YAGNI${NC} - You Aren't Gonna Need It"
echo -e "  • Use meaningful names"
echo -e "  • Functions should do one thing"
echo -e "  • Keep functions small (<20 lines)"
echo -e "  • Avoid deep nesting (max 3 levels)"

# Task type specific guidance
if [[ "$TASK_TYPE" == *"Feature"* ]] || [[ "$TASK_TITLE" =~ [Ff]eature ]]; then
    echo -e "\n${PURPLE}🌟 Feature Development Guidelines:${NC}"
    echo -e "  1. ${YELLOW}Design first${NC} - Create high-level design before coding"
    echo -e "  2. ${YELLOW}API contracts${NC} - Define interfaces before implementation"
    echo -e "  3. ${YELLOW}Test-driven${NC} - Write tests alongside features"
    echo -e "  4. ${YELLOW}Documentation${NC} - Update docs as you code"
    
    # Feature-specific patterns
    echo -e "\n${BLUE}Recommended Patterns:${NC}"
    echo -e "  • ${GREEN}Factory Pattern${NC} - For object creation"
    echo -e "  • ${GREEN}Strategy Pattern${NC} - For algorithm variations"
    echo -e "  • ${GREEN}Observer Pattern${NC} - For event handling"
    
elif [[ "$TASK_TYPE" == *"Bug"* ]] || [[ "$TASK_TITLE" =~ [Bb]ug|[Ff]ix ]]; then
    echo -e "\n${PURPLE}🐛 Bug Fix Guidelines:${NC}"
    echo -e "  1. ${YELLOW}Root cause${NC} - Find and fix the cause, not symptoms"
    echo -e "  2. ${YELLOW}Regression test${NC} - Add test to prevent recurrence"
    echo -e "  3. ${YELLOW}Minimal change${NC} - Fix only what's broken"
    echo -e "  4. ${YELLOW}Document${NC} - Explain the fix in comments"
    
elif [[ "$TASK_TYPE" == *"Refactor"* ]] || [[ "$TASK_TITLE" =~ [Rr]efactor ]]; then
    echo -e "\n${PURPLE}♻️ Refactoring Guidelines:${NC}"
    echo -e "  1. ${YELLOW}Small steps${NC} - Refactor incrementally"
    echo -e "  2. ${YELLOW}Test coverage${NC} - Ensure tests exist before refactoring"
    echo -e "  3. ${YELLOW}No behavior change${NC} - Refactoring shouldn't change functionality"
    echo -e "  4. ${YELLOW}Clean as you go${NC} - Leave code better than you found it"
    
    echo -e "\n${BLUE}Refactoring Patterns:${NC}"
    echo -e "  • ${GREEN}Extract Method${NC} - Break large functions"
    echo -e "  • ${GREEN}Extract Class${NC} - Split responsibilities"
    echo -e "  • ${GREEN}Replace Magic Numbers${NC} - Use named constants"
    echo -e "  • ${GREEN}Simplify Conditionals${NC} - Reduce complexity"
fi

# Voice transcription specific
if echo "$TASK_TITLE" | grep -qi "voice\|transcript\|audio\|speech"; then
    echo -e "\n${PURPLE}🎤 Voice Transcription Architecture:${NC}"
    echo -e "  • Follow modular design in ${GREEN}docs/features/voice-transcription/${NC}"
    echo -e "  • Implement proper ${YELLOW}quota management${NC}"
    echo -e "  • Use ${YELLOW}async/await${NC} for API calls"
    echo -e "  • Handle ${YELLOW}rate limiting${NC} gracefully"
    echo -e "  • Consider ${YELLOW}caching${NC} transcriptions"
fi

# Code quality checklist
echo -e "\n${PURPLE}✅ Code Quality Checklist:${NC}"
echo -e "  [ ] No code duplication (DRY)"
echo -e "  [ ] Clear variable/function names"
echo -e "  [ ] Functions < 20 lines"
echo -e "  [ ] Classes follow SRP"
echo -e "  [ ] Proper error handling"
echo -e "  [ ] Unit tests written"
echo -e "  [ ] Documentation updated"
echo -e "  [ ] No hardcoded values"
echo -e "  [ ] Consistent code style"

# Architecture documentation links
echo -e "\n${PURPLE}📚 Key Documentation:${NC}"

# Find most relevant docs
if [ -f ".claude/task-$TASK_NUMBER-arch-refs.md" ]; then
    echo -e "${GREEN}Task-specific references found:${NC}"
    grep -E "^- \[" ".claude/task-$TASK_NUMBER-arch-refs.md" | head -5
else
    echo -e "  • ${BLUE}General:${NC} docs/architecture/"
    echo -e "  • ${BLUE}Features:${NC} docs/features/"
    echo -e "  • ${BLUE}API:${NC} docs/api/"
fi

# Design patterns reference
echo -e "\n${PURPLE}🎯 Design Pattern Quick Reference:${NC}"
echo -e "\n${BLUE}Creational:${NC}"
echo -e "  • ${GREEN}Singleton${NC} - One instance (use sparingly)"
echo -e "  • ${GREEN}Factory${NC} - Create objects without specifying class"
echo -e "  • ${GREEN}Builder${NC} - Construct complex objects step by step"

echo -e "\n${BLUE}Structural:${NC}"
echo -e "  • ${GREEN}Adapter${NC} - Make incompatible interfaces work together"
echo -e "  • ${GREEN}Facade${NC} - Simplified interface to complex subsystem"
echo -e "  • ${GREEN}Decorator${NC} - Add responsibilities dynamically"

echo -e "\n${BLUE}Behavioral:${NC}"
echo -e "  • ${GREEN}Observer${NC} - Notify multiple objects of state changes"
echo -e "  • ${GREEN}Strategy${NC} - Encapsulate algorithms"
echo -e "  • ${GREEN}Command${NC} - Encapsulate requests as objects"

# Final reminder
echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Remember: ${NC}"
echo -e "  • ${GREEN}Think before coding${NC} - Design your solution"
echo -e "  • ${GREEN}Keep it simple${NC} - Avoid over-engineering"
echo -e "  • ${GREEN}Test as you go${NC} - Don't leave testing for later"
echo -e "  • ${GREEN}Document intent${NC} - Code shows how, comments show why"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"