#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
APP_NAME="OakWebcamApp"
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
MAIN_SCRIPT="${SCRIPT_DIR}/../src/menu_bar_app.py"
UVC_RUNNER_SCRIPT="${SCRIPT_DIR}/build_uvc_runner.sh"
UVC_RUNNER_PATH="${SCRIPT_DIR}/../dist/uvc_runner" # Changed from UVC_RUNNER_NAME and updated path
# ICON_FILE="assets/app_icon.icns" # Uncomment when icon is available

# --- Build ---

echo "Starting build process for ${APP_NAME}.app..."

# 1. Clean up previous builds
echo "Cleaning up previous build directories..."
rm -rf dist build "${APP_NAME}.spec"

# 2. Build uvc_runner
echo "Building uvc_runner..."
if [ -f "${UVC_RUNNER_SCRIPT}" ]; then
    bash "${UVC_RUNNER_SCRIPT}"
    # Ensure uvc_runner is in the expected location for PyInstaller
    if [ ! -f "${UVC_RUNNER_PATH}" ]; then
        echo "Error: ${UVC_RUNNER_PATH} not found after running ${UVC_RUNNER_SCRIPT}. Please check the script."
        exit 1
    fi
    echo "${UVC_RUNNER_PATH} built successfully."
else
    echo "Error: ${UVC_RUNNER_SCRIPT} not found."
    exit 1
fi

# 3. Run PyInstaller
echo "Running PyInstaller to build ${APP_NAME}.app..."

PYINSTALLER_CMD="pyinstaller --noconfirm --windowed --name \"${APP_NAME}\""

# Add uvc_runner to the bundle
# PyInstaller's --add-data syntax is <SRC>:<DEST_IN_BUNDLE>
# For .app bundles on macOS, files often go into Contents/MacOS or Contents/Resources
PYINSTALLER_CMD+=" --add-data \"${UVC_RUNNER_PATH}:.\"" # Adds uvc_runner to the root of the app bundle's internal structure
PYINSTALLER_CMD+=" --add-data \"${SCRIPT_DIR}/../src/uvc_handler.py:.\"" # Adds uvc_handler.py to the same location

# Add icon (commented out)
# if [ -f "${ICON_FILE}" ]; then
# PYINSTALLER_CMD+=" --icon \"${ICON_FILE}\""
# else
# echo "Warning: Icon file ${ICON_FILE} not found. Building without icon."
# fi

PYINSTALLER_CMD+=" \"${MAIN_SCRIPT}\""

eval $PYINSTALLER_CMD

# 4. Post-build steps (if any)
# For example, moving the .app to a specific location or zipping it.
echo "Moving ${APP_NAME}.app to app/ directory..."
mkdir -p "${SCRIPT_DIR}/app" # app ディレクトリがなければ作成
mv "./dist/${APP_NAME}.app" "${SCRIPT_DIR}/app/" # dist から ../app へ移動


echo "Build process finished."
