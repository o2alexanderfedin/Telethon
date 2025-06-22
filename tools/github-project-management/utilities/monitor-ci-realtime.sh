#!/bin/bash

# Script: monitor-ci-realtime.sh
# Purpose: Real-time CI/CD monitoring with live updates
# Usage: ./monitor-ci-realtime.sh [commit-sha]

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Configuration
COMMIT_SHA=${1:-$(git rev-parse HEAD)}
REPO_OWNER=$(git remote get-url origin | sed -E 's/.*github.com[:/]([^/]+)\/.*/\1/')
REPO_NAME=$(git remote get-url origin | sed -E 's/.*github.com[:/][^/]+\/([^.]+)(\.git)?$/\1/')
REFRESH_INTERVAL=5

# Clear screen and show header
clear
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}              REAL-TIME CI/CD MONITOR                   ${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Repository:${NC} $REPO_OWNER/$REPO_NAME"
echo -e "${BLUE}Commit:${NC} ${COMMIT_SHA:0:7}"
echo -e "${BLUE}Monitoring started:${NC} $(date)"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Function to get status icon
get_status_icon() {
    case $1 in
        "completed") echo "✅" ;;
        "in_progress") echo "🔄" ;;
        "queued") echo "⏳" ;;
        "failed"|"failure") echo "❌" ;;
        "success") echo "✅" ;;
        "cancelled") echo "🚫" ;;
        "skipped") echo "⏭️" ;;
        *) echo "❓" ;;
    esac
}

# Function to format duration
format_duration() {
    local seconds=$1
    local minutes=$((seconds / 60))
    local remaining_seconds=$((seconds % 60))
    
    if [ $minutes -gt 0 ]; then
        echo "${minutes}m ${remaining_seconds}s"
    else
        echo "${seconds}s"
    fi
}

# Function to display progress bar
progress_bar() {
    local current=$1
    local total=$2
    local width=30
    
    if [ $total -eq 0 ]; then
        echo "[$(printf '%-*s' $width '')]"
        return
    fi
    
    local progress=$((current * width / total))
    local remaining=$((width - progress))
    
    echo -n "["
    printf '%*s' $progress | tr ' ' '█'
    printf '%*s' $remaining | tr ' ' '░'
    echo -n "]"
}

# Main monitoring loop
MONITOR_START=$(date +%s)
LAST_STATUS=""
AUTO_FIX_TRIGGERED=false

while true; do
    # Get current time
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - MONITOR_START))
    
    # Get workflow runs for this commit
    RUNS=$(gh api repos/$REPO_OWNER/$REPO_NAME/commits/$COMMIT_SHA/check-runs 2>/dev/null || echo '{"total_count": 0}')
    
    # Parse run information
    TOTAL_RUNS=$(echo "$RUNS" | jq '.total_count // 0')
    
    if [ $TOTAL_RUNS -gt 0 ]; then
        # Count by status
        COMPLETED=$(echo "$RUNS" | jq '[.check_runs[] | select(.status == "completed")] | length')
        IN_PROGRESS=$(echo "$RUNS" | jq '[.check_runs[] | select(.status == "in_progress")] | length')
        QUEUED=$(echo "$RUNS" | jq '[.check_runs[] | select(.status == "queued")] | length')
        
        # Count by conclusion
        SUCCESS=$(echo "$RUNS" | jq '[.check_runs[] | select(.conclusion == "success")] | length')
        FAILURE=$(echo "$RUNS" | jq '[.check_runs[] | select(.conclusion == "failure")] | length')
        CANCELLED=$(echo "$RUNS" | jq '[.check_runs[] | select(.conclusion == "cancelled")] | length')
        
        # Clear and redraw
        clear
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${CYAN}              REAL-TIME CI/CD MONITOR                   ${NC}"
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${BLUE}Repository:${NC} $REPO_OWNER/$REPO_NAME"
        echo -e "${BLUE}Commit:${NC} ${COMMIT_SHA:0:7}"
        echo -e "${BLUE}Elapsed:${NC} $(format_duration $ELAPSED)"
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        
        # Overall progress
        echo -e "\n${BOLD}Overall Progress:${NC}"
        echo -n "  "
        progress_bar $COMPLETED $TOTAL_RUNS
        echo " $COMPLETED/$TOTAL_RUNS"
        
        # Status summary
        echo -e "\n${BOLD}Status Summary:${NC}"
        [ $SUCCESS -gt 0 ] && echo -e "  ${GREEN}✅ Success:${NC} $SUCCESS"
        [ $IN_PROGRESS -gt 0 ] && echo -e "  ${CYAN}🔄 Running:${NC} $IN_PROGRESS"
        [ $QUEUED -gt 0 ] && echo -e "  ${YELLOW}⏳ Queued:${NC} $QUEUED"
        [ $FAILURE -gt 0 ] && echo -e "  ${RED}❌ Failed:${NC} $FAILURE"
        [ $CANCELLED -gt 0 ] && echo -e "  ${PURPLE}🚫 Cancelled:${NC} $CANCELLED"
        
        # Individual checks
        echo -e "\n${BOLD}Individual Checks:${NC}"
        echo "$RUNS" | jq -r '.check_runs[] | "\(.status)|\(.conclusion // "pending")|\(.name)|\(.started_at // "pending")|\(.completed_at // "pending")"' | while IFS='|' read -r status conclusion name started completed; do
            icon=$(get_status_icon "$status")
            
            # Calculate duration
            duration=""
            if [ "$status" = "completed" ] && [ "$started" != "pending" ] && [ "$completed" != "pending" ]; then
                start_ts=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$started" +%s 2>/dev/null || date -d "$started" +%s 2>/dev/null || echo 0)
                end_ts=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$completed" +%s 2>/dev/null || date -d "$completed" +%s 2>/dev/null || echo 0)
                if [ $start_ts -gt 0 ] && [ $end_ts -gt 0 ]; then
                    duration=" ($(format_duration $((end_ts - start_ts))))"
                fi
            elif [ "$status" = "in_progress" ] && [ "$started" != "pending" ]; then
                start_ts=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$started" +%s 2>/dev/null || date -d "$started" +%s 2>/dev/null || echo 0)
                if [ $start_ts -gt 0 ]; then
                    duration=" ($(format_duration $((CURRENT_TIME - start_ts))))"
                fi
            fi
            
            # Color based on conclusion
            if [ "$conclusion" = "failure" ]; then
                echo -e "  $icon ${RED}$name${NC}$duration"
            elif [ "$conclusion" = "success" ]; then
                echo -e "  $icon ${GREEN}$name${NC}$duration"
            elif [ "$status" = "in_progress" ]; then
                echo -e "  $icon ${CYAN}$name${NC}$duration ${CYAN}[Running]${NC}"
            else
                echo -e "  $icon ${YELLOW}$name${NC}$duration"
            fi
        done
        
        # Check if all completed
        if [ $COMPLETED -eq $TOTAL_RUNS ]; then
            echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            
            if [ $FAILURE -gt 0 ]; then
                echo -e "${RED}${BOLD}❌ CI/CD FAILED!${NC}"
                echo -e "\n${YELLOW}Failed checks:${NC}"
                echo "$RUNS" | jq -r '.check_runs[] | select(.conclusion == "failure") | "  - \(.name)"'
                
                # Offer auto-fix if not already triggered
                if [ "$AUTO_FIX_TRIGGERED" = false ]; then
                    echo -e "\n${BLUE}Options:${NC}"
                    echo -e "  1. Run auto-fix: ${GREEN}./fix-ci-failures.sh --auto-fix${NC}"
                    echo -e "  2. View logs: ${GREEN}gh run view --log${NC}"
                    echo -e "  3. Re-run failed: ${GREEN}gh run rerun --failed${NC}"
                    
                    # Ask for auto-fix
                    echo -e "\n${YELLOW}Auto-fix failures? (y/n):${NC} "
                    read -t 10 -n 1 response || response="n"
                    if [ "$response" = "y" ]; then
                        echo -e "\n${BLUE}Running auto-fix...${NC}"
                        ./tools/github-project-management/utilities/fix-ci-failures.sh --auto-fix
                        AUTO_FIX_TRIGGERED=true
                    fi
                fi
            else
                echo -e "${GREEN}${BOLD}✅ ALL CHECKS PASSED!${NC}"
                echo -e "\n${GREEN}Great job! Your code is ready.${NC}"
            fi
            
            echo -e "\n${BLUE}Total duration:${NC} $(format_duration $ELAPSED)"
            echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            break
        fi
        
        # Status line
        echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${BLUE}Refreshing every ${REFRESH_INTERVAL}s... Press Ctrl+C to stop${NC}"
        
    else
        # No runs yet
        echo -e "\n${YELLOW}⏳ Waiting for CI/CD to start...${NC}"
        echo -e "${BLUE}Elapsed:${NC} $(format_duration $ELAPSED)"
    fi
    
    # Store current status
    CURRENT_STATUS="C:$COMPLETED|P:$IN_PROGRESS|Q:$QUEUED|S:$SUCCESS|F:$FAILURE"
    
    # Notify on status change
    if [ "$CURRENT_STATUS" != "$LAST_STATUS" ] && [ -n "$LAST_STATUS" ]; then
        # Play notification sound if available
        if command -v afplay &> /dev/null; then
            afplay /System/Library/Sounds/Pop.aiff 2>/dev/null || true
        elif command -v paplay &> /dev/null; then
            paplay /usr/share/sounds/freedesktop/stereo/message.oga 2>/dev/null || true
        fi
    fi
    
    LAST_STATUS="$CURRENT_STATUS"
    
    # Wait before refresh
    sleep $REFRESH_INTERVAL
done

# Exit message
echo -e "\n${GREEN}Monitoring complete!${NC}"
echo -e "${BLUE}Run 'gh run list' to see all runs${NC}\n"