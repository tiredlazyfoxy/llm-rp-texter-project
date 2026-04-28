#!/bin/bash
set -e

MODE="all"
case "${1:-}" in
    --images) MODE="images" ;;
    --config) MODE="config" ;;
    --all|"") MODE="all" ;;
    *) echo "Usage: $0 [--images|--config|--all]"; exit 1 ;;
esac

if [ -z "$DOCKER_STORE" ]; then
    echo "ERROR: DOCKER_STORE environment variable is not set"
    exit 1
fi

STORE_DIR="$DOCKER_STORE/llmrp"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ ! -d "$STORE_DIR" ]; then
    echo "ERROR: Store directory does not exist: $STORE_DIR"
    exit 1
fi

if [ "$MODE" = "images" ] || [ "$MODE" = "all" ]; then
    API_ARCHIVE="$STORE_DIR/llmrp-api-latest.7z"
    GATE_ARCHIVE="$STORE_DIR/llmrp-gate-latest.7z"

    if [ ! -f "$API_ARCHIVE" ] || [ ! -f "$GATE_ARCHIVE" ]; then
        echo "ERROR: Could not find image archives in $STORE_DIR"
        exit 1
    fi

    echo "Loading llmrp-api..."
    7z x -so "$API_ARCHIVE" | docker load

    echo -e "\nLoading llmrp-gate..."
    7z x -so "$GATE_ARCHIVE" | docker load

    echo -e "\nImages loaded:"
    docker images | grep llmrp | head -4
fi

if [ "$MODE" = "config" ] || [ "$MODE" = "all" ]; then
    if [ -f "$STORE_DIR/docker-compose.yml" ]; then
        cp "$STORE_DIR/docker-compose.yml" "$SCRIPT_DIR/docker-compose.yml"
        echo "Copied docker-compose.yml to $SCRIPT_DIR"
    else
        echo "WARNING: docker-compose.yml not found in $STORE_DIR"
    fi
fi

echo -e "\nFetch complete!"
