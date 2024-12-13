#!/bin/bash

# Function to show usage
show_usage() {
    echo "Usage: $0 [--create|--delete]"
    echo "  --create    Create Ubuntu 24.10 toolbox container"
    echo "  --delete    Delete Ubuntu 24.10 toolbox container"
    exit 1
}

# Check if an argument is provided
if [ $# -eq 0 ]; then
    show_usage
fi

# Process command line arguments
case "$1" in
    --create)
        echo "Creating Ubuntu 24.10 toolbox container..."
        toolbox create --distro ubuntu --release 24.10
        echo "Run 'toolbox enter' to use the container"
        ;;
    --delete)
        echo "Deleting Ubuntu 24.10 toolbox container..."
        podman stop ubuntu-toolbox-24.10
        toolbox rm ubuntu-toolbox-24.10
        ;;
    *)
        show_usage
        ;;
esac

