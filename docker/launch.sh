#!/bin/bash
# Helper script for Docker operations - Colibri G1 Digital Twin
# Phase 6: Sim2Sim ROS2 Integration
#
# Usage:
#   ./docker/launch.sh build        # Build Docker image
#   ./docker/launch.sh sim2sim      # Run sim2sim
#   ./docker/launch.sh rviz         # Launch RViz2
#   ./docker/launch.sh enter        # Interactive shell
#   ./docker/launch.sh stop         # Stop containers

set -e

# Get project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCKER_COMPOSE_FILE="$PROJECT_ROOT/docker/docker-compose.yaml"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Print colored message
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Enable X11 forwarding
enable_x11() {
    print_info "Enabling X11 forwarding..."
    xhost +local:docker > /dev/null 2>&1 || {
        print_warning "Failed to enable X11 forwarding (xhost command failed)"
        print_warning "GUI may not work. Continuing anyway..."
    }
}

# Build Docker image
build() {
    print_info "Building Docker image..."
    print_info "This may take 30-60 minutes on first build..."

    cd "$PROJECT_ROOT"
    docker-compose -f "$DOCKER_COMPOSE_FILE" build

    print_success "Docker image built successfully!"
    print_info "Image name: colibri_g1_ros2:latest"
}

# Run sim2sim
sim2sim() {
    enable_x11
    print_info "Starting Sim2Sim ROS2..."
    print_info "Press Ctrl+C to stop"
    echo ""

    cd "$PROJECT_ROOT"
    docker-compose -f "$DOCKER_COMPOSE_FILE" up isaac_sim_ros2
}

# Run RViz2
rviz() {
    enable_x11
    print_info "Starting RViz2..."

    cd "$PROJECT_ROOT"
    docker-compose -f "$DOCKER_COMPOSE_FILE" run --rm isaac_sim_ros2 rviz
}

# Test ROS2 connection
test_ros2() {
    print_info "Starting ROS2 connection test..."

    cd "$PROJECT_ROOT"
    docker-compose -f "$DOCKER_COMPOSE_FILE" run --rm isaac_sim_ros2 test_ros2
}

# Enter container shell
enter() {
    print_info "Entering container shell..."
    print_info "Type 'exit' to return"
    echo ""

    cd "$PROJECT_ROOT"
    docker-compose -f "$DOCKER_COMPOSE_FILE" run --rm isaac_sim_ros2 bash
}

# Stop containers
stop() {
    print_info "Stopping containers..."

    cd "$PROJECT_ROOT"
    docker-compose -f "$DOCKER_COMPOSE_FILE" down

    print_success "Containers stopped"
}

# Clean up (remove images, volumes)
clean() {
    print_warning "This will remove Docker images and volumes!"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Cleaning up..."
        cd "$PROJECT_ROOT"
        docker-compose -f "$DOCKER_COMPOSE_FILE" down --rmi all --volumes
        print_success "Cleanup complete"
    else
        print_info "Cleanup cancelled"
    fi
}

# Show logs
logs() {
    print_info "Showing container logs..."
    print_info "Press Ctrl+C to stop"
    echo ""

    cd "$PROJECT_ROOT"
    docker-compose -f "$DOCKER_COMPOSE_FILE" logs -f
}

# Show help
help() {
    echo "Colibri G1 Digital Twin - Docker Helper Script"
    echo ""
    echo "Usage: $0 {command}"
    echo ""
    echo "Commands:"
    echo "  build       Build Docker image (takes 30-60 min first time)"
    echo "  sim2sim     Run sim2sim with ROS2 bridge"
    echo "  rviz        Launch RViz2 visualization"
    echo "  test_ros2   Test ROS2 connection (without Isaac Sim)"
    echo "  enter       Enter container interactive shell"
    echo "  stop        Stop running containers"
    echo "  logs        Show container logs"
    echo "  clean       Remove Docker images and volumes (caution!)"
    echo "  help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 build        # Build image"
    echo "  $0 sim2sim      # Run simulation"
    echo "  $0 enter        # Debug in shell"
    echo ""
    echo "Quick Start:"
    echo "  1. ./docker/launch.sh build"
    echo "  2. ./docker/launch.sh sim2sim"
    echo "  3. (In another terminal) ./docker/launch.sh rviz"
    echo ""
}

# Main command handler
case "$1" in
    build)
        build
        ;;
    sim2sim)
        sim2sim
        ;;
    rviz)
        rviz
        ;;
    test_ros2)
        test_ros2
        ;;
    enter)
        enter
        ;;
    stop)
        stop
        ;;
    logs)
        logs
        ;;
    clean)
        clean
        ;;
    help|--help|-h)
        help
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        help
        exit 1
        ;;
esac

# TODO Phase 6.1: Add status command (show running containers, GPU usage, etc.)
# TODO Phase 6.2: Add backup/restore commands for logs and checkpoints
