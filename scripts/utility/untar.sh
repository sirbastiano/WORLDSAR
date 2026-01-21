#!/bin/bash

# Load environment variables from .env file:
if [ -f .env ]; then
        export $(grep -v '^#' .env | xargs)
fi
# get filepath of current file 
CURRENT_FILE_PATH="$(realpath "$0")"
# go up one directory
BASE_DIR="$(dirname "$(dirname "$CURRENT_FILE_PATH")")"


tar -xvf $1 -C ${download_dir}