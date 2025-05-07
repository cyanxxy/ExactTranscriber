#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "Starting build process..."

# Print Python version
python --version

# Print ffmpeg version (should be pre-installed in Render's environment)
echo "Checking for ffmpeg..."
which ffmpeg || echo "ffmpeg not found in PATH"
ffmpeg -version || echo "Could not get ffmpeg version"

# Upgrade pip and install dependencies
echo "Upgrading pip..."
pip install --upgrade pip

echo "Installing Python dependencies..."
pip install -r requirements.txt --no-cache-dir

echo "Build process completed successfully."
