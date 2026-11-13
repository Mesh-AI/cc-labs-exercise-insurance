#!/bin/bash

# Larkspur & Dene Policy Modernisation Workbench - Stop Script
# This script stops both the backend and frontend servers

set -e  # Exit on error

# Colors for output
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Stopping Larkspur & Dene Policy Modernisation Workbench...${NC}\n"

# Check if PID files exist
if [ -f /tmp/pas-backend.pid ]; then
    BACKEND_PID=$(cat /tmp/pas-backend.pid)
    if kill -0 $BACKEND_PID 2>/dev/null; then
        echo -e "${YELLOW}Stopping backend server (PID: $BACKEND_PID)${NC}"
        kill $BACKEND_PID
    fi
    rm -f /tmp/pas-backend.pid
fi

if [ -f /tmp/pas-frontend.pid ]; then
    FRONTEND_PID=$(cat /tmp/pas-frontend.pid)
    if kill -0 $FRONTEND_PID 2>/dev/null; then
        echo -e "${YELLOW}Stopping frontend server (PID: $FRONTEND_PID)${NC}"
        kill $FRONTEND_PID
    fi
    rm -f /tmp/pas-frontend.pid
fi

# Fallback: kill any remaining processes on the ports
echo -e "${YELLOW}Cleaning up any remaining processes...${NC}"

# Kill processes on port 8001 (backend)
BACKEND_PIDS=$(lsof -ti:8001 2>/dev/null || true)
if [ ! -z "$BACKEND_PIDS" ]; then
    echo "$BACKEND_PIDS" | xargs kill 2>/dev/null || true
fi

# Kill processes on port 3000 (frontend)
FRONTEND_PIDS=$(lsof -ti:3000 2>/dev/null || true)
if [ ! -z "$FRONTEND_PIDS" ]; then
    echo "$FRONTEND_PIDS" | xargs kill 2>/dev/null || true
fi

# Clean up log files
rm -f /tmp/pas-backend.log
rm -f /tmp/pas-frontend.log

echo -e "\n${GREEN}✓ All servers stopped successfully!${NC}"
