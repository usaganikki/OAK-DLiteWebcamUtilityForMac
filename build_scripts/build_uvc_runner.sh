#!/bin/bash

# Script to build uvc_handler.py into a single executable using PyInstaller

# Exit on error
set -e

# Project root directory (assuming this script is in build_scripts)
PROJECT_ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
SRC_DIR="$PROJECT_ROOT_DIR/src"
OUTPUT_DIR="$PROJECT_ROOT_DIR/dist"
SCRIPT_NAME="uvc_handler.py"
EXECUTABLE_NAME="uvc_runner"

echo "Starting build process for $SCRIPT_NAME..."

# Ensure PyInstaller is installed
if ! command -v pyinstaller &> /dev/null
then
    echo "PyInstaller could not be found. Please install it first."
    echo "You can typically install it using: pip install pyinstaller"
    exit 1
fi

echo "Project Root: $PROJECT_ROOT_DIR"
echo "Source Directory: $SRC_DIR"
echo "Output Directory: $OUTPUT_DIR"

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

echo "Running PyInstaller..."
# Re-running PyInstaller command generation without --windowed
pyinstaller --name "$EXECUTABLE_NAME" \
            --onefile \
            --specpath "$PROJECT_ROOT_DIR/build_scripts" \
            --distpath "$OUTPUT_DIR" \
            --workpath "$PROJECT_ROOT_DIR/build" \
            "$SRC_DIR/$SCRIPT_NAME"

echo "Build completed. Executable should be in $OUTPUT_DIR/$EXECUTABLE_NAME"

echo "Build script created at build_scripts/build_uvc_runner.sh"
