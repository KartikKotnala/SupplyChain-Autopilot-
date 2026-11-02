#!/usr/bin/env bash
# SupplyChain Autopilot - One-Command Local Development Launcher
set -e

# Change directory to script's directory
cd "$(dirname "$0")"

echo "=========================================================="
echo " Starting SupplyChain Autopilot v1.0 Services"
echo "=========================================================="

# Check virtualenv
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e packages/contracts
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

# Ensure database is seeded
echo "1. Checking database seed data..."
PYTHONPATH=. python data/seed/seed_data.py > /dev/null 2>&1 || true

# Function to kill child processes on exit (Ctrl+C)
cleanup() {
    echo ""
    echo "Stopping all services..."
    kill $(jobs -p) 2>/dev/null || true
    echo "All services stopped."
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# 1. Start CrewAI A2A Service on port 8001
echo "2. Starting CrewAI A2A Service on http://127.0.0.1:8001 ..."
PYTHONPATH=. uvicorn services.crewai_service.server:app --port 8001 --log-level warning &
PID_CREWAI=$!

# 2. Start FastAPI Backend on port 8000
echo "3. Starting FastAPI Backend on http://127.0.0.1:8000 ..."
PYTHONPATH=. uvicorn services.backend.app.main:app --port 8000 --log-level warning &
PID_BACKEND=$!

# Wait 2 seconds for backend services to spin up
sleep 2

# 3. Start Frontend Dashboard on port 3000
echo "4. Starting React 18 Management Dashboard on http://localhost:3000 ..."
cd frontend
npm run dev -- --host

# Wait for background jobs
wait
