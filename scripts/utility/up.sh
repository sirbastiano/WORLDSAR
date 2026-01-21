#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# This script uploads the dataset to Hugging Face using the CLI.
# Ensure you have the Hugging Face CLI installed and authenticated
# Load environment variables from .env file:
if [ -f .env ]; then
        export $(grep -v '^#' .env | xargs)
fi

source ${venv_path}/bin/activate

# ========== Main Script Execution =========
echo "🚀 Starting dataset upload to Hugging Face..."
echo "🔑 Authenticated as: $(hf auth whoami)"

echo "⬆️  Starting upload..."
if hf upload-large-folder "$1" "$2" --repo-type=dataset; then
    echo "✅ Upload completed successfully!"
    echo "🌐 Dataset available at: https://huggingface.co/datasets/$1"
else
    echo "❌ Upload failed. Please check the error messages above."
    exit 1
fi