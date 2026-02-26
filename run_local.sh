#!/usr/bin/env bash
# run_local.sh — Start all SmartToll services locally (Linux / macOS)
set -euo pipefail

echo "Setting up SmartToll to run locally..."

# 1. Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "IMPORTANT: Edit .env with your Kafka / Redis / Postgres credentials if not using the default Docker Compose stack."
fi

# Helper: create venv + install deps + start a service in the background
start_service() {
    local dir="$1"
    local cmd="$2"
    local name="$3"

    cd "$dir"
    if [ ! -d venv ]; then
        python3 -m venv venv
    fi
    # shellcheck source=/dev/null
    source venv/bin/activate
    pip install -q -r requirements.txt
    echo "Starting ${name}..."
    eval "$cmd" &
    local pid=$!
    echo "${name} PID: ${pid}"
    cd - > /dev/null
}

# 2. Start services in the background (infrastructure must already be running via docker compose)
start_service billing_service \
    "uvicorn app.main:app --reload --host 0.0.0.0 --port 8001" \
    "Billing Service"

start_service toll_processor \
    "python -m app.main" \
    "Toll Processor"

start_service obu_simulator \
    "python obu_simulator.py" \
    "OBU Simulator"

echo ""
echo "All services started in the background."
echo "  Billing API:       http://localhost:8001/docs"
echo "  Processor health:  http://localhost:8080/health/live"
echo "  Processor metrics: http://localhost:8081/"
echo ""
echo "To stop all services, press Ctrl-C or run: kill \$(jobs -p)"

wait
