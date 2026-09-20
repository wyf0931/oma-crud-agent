#!/bin/bash

# Info System Agent Operations Script
# Usage: ./bin/ops.sh {start|stop|restart|logs|status}

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Config
UV_CMD="$(command -v uv || true)"
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
PID_FILE=".oma.pid"
DATA_DIR="${DATA_DIR:-$PROJECT_ROOT/data}"
if [ -f "$PROJECT_ROOT/.env" ]; then
    ENV_DATA_DIR="$(awk -F= '$1 == "DATA_DIR" {print substr($0, index($0, "=") + 1); exit}' "$PROJECT_ROOT/.env")"
    if [ -n "$ENV_DATA_DIR" ]; then
        DATA_DIR="$ENV_DATA_DIR"
    fi
fi
case "$DATA_DIR" in
    ~/*) DATA_DIR="$HOME/${DATA_DIR#~/}" ;;
    /*) ;;
    *) DATA_DIR="$PROJECT_ROOT/$DATA_DIR" ;;
esac
LOG_DIR="$DATA_DIR/logs"
LOG_FILE="$LOG_DIR/oma.log"

# Default port
DEFAULT_PORT=8020
PORT=${DEFAULT_PORT}

# Parse arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --port)
                PORT="$2"
                shift 2
                ;;
            *)
                shift
                ;;
        esac
    done
}

# Get process on port
get_pid_on_port() {
    local port=$1
    lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | head -1
}

# Kill process on port
kill_port() {
    local port=$1
    local pid=$(get_pid_on_port "$port")
    if [ -n "$pid" ]; then
        echo -e "${YELLOW}Killing existing process on port $port (PID: $pid)${NC}"
        kill -9 "$pid" 2>/dev/null || true
        sleep 1
    fi
}

# Check if running
is_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        else
            rm -f "$PID_FILE"
            return 1
        fi
    fi
    return 1
}

# Start server
start_server() {
    echo -e "${BLUE}Starting Info System Agent...${NC}"

    if [ -z "$UV_CMD" ]; then
        echo -e "${RED}Error: uv is not installed or not on PATH${NC}"
        return 1
    fi

    # Kill existing process on port first
    kill_port "$PORT"

    # Check if PID file exists and process is running
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            # Check if it's on our target port
            local port_pid=$(get_pid_on_port "$PORT")
            if [ "$port_pid" = "$pid" ]; then
                echo -e "${YELLOW}Already running on port $PORT (PID: $pid)${NC}"
                return 1
            else
                # Different port, kill and restart
                echo -e "${YELLOW}Killing old process (PID: $pid)${NC}"
                kill "$pid" 2>/dev/null || true
            fi
        fi
        rm -f "$PID_FILE"
    fi

    # Ensure log directory exists
    mkdir -p "$LOG_DIR"

    # Get API key status
    if [ -f ".env" ]; then
        if grep -q "^DEEPSEEK_API_KEY=" .env 2>/dev/null; then
            if grep -q "^DEEPSEEK_API_KEY=$" .env 2>/dev/null; then
                echo -e "${RED}Error: DEEPSEEK_API_KEY is not set in .env${NC}"
                echo -e "${YELLOW}Get your API key from: https://platform.deepseek.com/api_keys${NC}"
                return 1
            fi
        fi
    fi

    # Start server in background. Prefer the project interpreter so the PID
    # file belongs to the actual Uvicorn process, not a temporary uv launcher.
    # Fall back to uv when the virtual environment has not been created yet.
    cd "$PROJECT_ROOT"
    if [ -x "$PYTHON_BIN" ]; then
        nohup "$PYTHON_BIN" -m uvicorn oma_info_system.api.app:app \
            --host 127.0.0.1 \
            --port "$PORT" \
            >> "$LOG_FILE" 2>&1 &
    else
        nohup "$UV_CMD" run python -m uvicorn oma_info_system.api.app:app \
            --host 127.0.0.1 \
            --port "$PORT" \
            >> "$LOG_FILE" 2>&1 &
    fi

    local pid=$!
    echo $pid > "$PID_FILE"

    # Wait for the application to become healthy instead of only checking
    # whether the launcher process is still alive.
    local attempt
    for attempt in $(seq 1 20); do
        if curl -fsS "http://127.0.0.1:$PORT/api/health" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Started successfully${NC}"
            echo -e "  PID: $pid"
            echo -e "  Port: $PORT"
            echo -e "  Log: $LOG_FILE"
            echo ""
            echo -e "${BLUE}Access: http://127.0.0.1:$PORT${NC}"
            return 0
        fi
        if ! kill -0 "$pid" 2>/dev/null; then
            break
        fi
        sleep 0.25
    done

    if kill -0 "$pid" 2>/dev/null; then
        echo -e "${RED}✗ Started but health check failed${NC}"
    else
        echo -e "${RED}✗ Failed to start${NC}"
    fi
    echo -e "${YELLOW}See recent logs with: $0 logs${NC}"
    kill "$pid" 2>/dev/null || true
    rm -f "$PID_FILE"
    return 1
}

# Stop server
stop_server() {
    echo -e "${BLUE}Stopping Info System Agent...${NC}"

    if is_running; then
        local pid=$(cat "$PID_FILE")
        kill "$pid" 2>/dev/null || true
        sleep 1

        if kill -0 "$pid" 2>/dev/null; then
            echo -e "${YELLOW}Force killing...${NC}"
            kill -9 "$pid" 2>/dev/null || true
        fi

        rm -f "$PID_FILE"
        echo -e "${GREEN}✓ Stopped${NC}"
        return 0
    else
        echo -e "${YELLOW}Not running${NC}"
        return 1
    fi
}

# Restart server
restart_server() {
    echo -e "${BLUE}Restarting Info System Agent...${NC}"
    stop_server || true
    sleep 1
    start_server
}

# Show logs
show_logs() {
    if [ -f "$LOG_FILE" ]; then
        echo -e "${BLUE}Showing logs (Ctrl+C to exit):${NC}"
        echo ""
        tail -f "$LOG_FILE"
    else
        echo -e "${YELLOW}Log file not found: $LOG_FILE${NC}"
        return 1
    fi
}

# Show status
show_status() {
    echo -e "${BLUE}Info System Agent Status${NC}"
    echo ""

    # Check if running
    if is_running; then
        local pid=$(cat "$PID_FILE")
        echo -e "  State: ${GREEN}Running${NC}"
        echo -e "  PID:   $pid"
        echo -e "  Port: $PORT"

        # Check if responding
        if command -v curl > /dev/null 2>&1; then
            if curl -s "http://127.0.0.1:$PORT/api/health" > /dev/null 2>&1; then
                echo -e "  Health: ${GREEN}OK${NC}"
            else
                echo -e "  Health: ${RED}Not responding${NC}"
            fi
        fi
    else
        echo -e "  State: ${YELLOW}Stopped${NC}"
    fi

    echo ""

    # Show recent logs if available
    if [ -f "$LOG_FILE" ]; then
        echo -e "${BLUE}Recent logs:${NC}"
        tail -5 "$LOG_FILE" 2>/dev/null || true
    fi
}

# Main
main() {
    local command=$1
    shift || true

    # Parse port argument
    parse_args "$@"

    case $command in
        start)
            start_server
            ;;
        stop)
            stop_server
            ;;
        restart)
            restart_server
            ;;
        logs)
            show_logs
            ;;
        status)
            show_status
            ;;
        *)
            echo "Usage: $0 {start|stop|restart|logs|status}"
            echo ""
            echo "Commands:"
            echo "  start           Start the server"
            echo "  stop            Stop the server"
            echo "  restart         Restart the server"
            echo "  logs            Show logs (tail -f)"
            echo "  status          Show server status"
            echo ""
            echo "Options:"
            echo "  --port PORT     Specify port (default: $DEFAULT_PORT)"
            echo ""
            echo "Examples:"
            echo "  $0 start                # Start on default port ($DEFAULT_PORT)"
            echo "  $0 start --port 9000    # Start on port 9000"
            echo "  $0 logs                 # View logs"
            echo "  $0 status               # Check status"
            exit 1
            ;;
    esac
}

main "$@"
