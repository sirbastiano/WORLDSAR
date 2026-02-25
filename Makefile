.PHONY: help clean clean-logs ensure-sif run status logs pull-sif list-data down downloader uploader show-cache clean-hf-cache

SHELL := /usr/bin/env bash

PROJECT_ROOT ?= .
SIF_DIR ?= $(PROJECT_ROOT)
SIF_NAME ?= sarpyx.sif
SIF_IMAGE ?= $(SIF_DIR)/$(SIF_NAME)
SIF_REPO ?= WORLDSAR/support
MAIN_SCRIPT ?= main.sh
LOG_DIR ?= $(PROJECT_ROOT)/logs
PHIDOWN_DATA_DIR ?= $(PROJECT_ROOT)/phidown_data
OUTPUT_DIR ?= $(PROJECT_ROOT)/OUT/worldsar_output
TILES_DIR ?= $(PROJECT_ROOT)/OUT/tiles
DB_DIR ?= $(PROJECT_ROOT)/OUT/DB
PBS_USER ?= $(USER)

# Hugging Face cache & temp locations (move off HOME quota)
# Override on command line if needed:
#   make pull-sif HF_HOME=/lustre/project/.../hf
HF_HOME ?= /lustre/scratch/1000/WorldSAR
HF_HUB_CACHE ?= $(HF_HOME)/hub
HF_XET_CACHE ?= $(HF_HOME)/xet
HF_ASSETS_CACHE ?= $(HF_HOME)/assets
HF_TMPDIR ?= $(HF_HOME)/tmp

# Optional: disable Xet if it causes trouble (set to 1 to disable)
# HF_HUB_DISABLE_XET ?= 1

export HF_HOME HF_HUB_CACHE HF_XET_CACHE HF_ASSETS_CACHE
export TMPDIR := $(HF_TMPDIR)
export HF_HUB_DISABLE_XET

# Default target
help:
	@echo "WORLDSAR Makefile Commands:"
	@echo "  make run [SIF_IMAGE=./sarpyx.sif] [MAIN_SCRIPT=main.sh] - Submit job to queue (downloads SIF if missing)"
	@echo "  make down PRODUCT=<name> - Download SAR product into \$(PHIDOWN_DATA_DIR)"
	@echo "  make status       - Check current job status"
	@echo "  make logs         - View recent log files"
	@echo "  make clean        - Remove all output files"
	@echo "  make pull-sif     - Pull/update Singularity container (HF cache on scratch)"
	@echo "  make list-data    - List available local SAR data"
	@echo "  make clean-logs   - Remove scheduler logs matching the current directory pattern"
	@echo "  make show-cache   - Show HF cache locations"
	@echo "  make clean-hf-cache - Prune HF cache (safe cleanup)"

down:
	@if [ -z "$(PRODUCT)" ]; then \
		echo "Error: PRODUCT not specified. Usage: make down PRODUCT=<product_name>"; \
		exit 1; \
	fi
	@echo "Downloading product: $(PRODUCT)"
	bash scripts/downloader.sh "$(PRODUCT)"

ensure-sif:
	@if [ ! -f "$(SIF_IMAGE)" ]; then \
		echo "SIF image not found: $(SIF_IMAGE). Pulling from $(SIF_REPO)..."; \
		$(MAKE) pull-sif; \
	fi

clean:
	@echo "Cleaning output directory..."
	rm -rf "$(OUTPUT_DIR)" "$(TILES_DIR)" "$(DB_DIR)"

clean-logs:
	@echo "Cleaning log files..."
	rm -rf "$(LOG_DIR)"/*.o* "$(LOG_DIR)"/*.e*

run: ensure-sif
	@echo "Submitting job to queue..."
	mkdir -p "$(LOG_DIR)"
	cd "$(LOG_DIR)" && qsub ../"$(MAIN_SCRIPT)"
	@echo "Use 'make status' to check job status"

status:
	@qstat -u "$(PBS_USER)"

logs:
	@echo "Recent log files:"
	@ls -lht "$(LOG_DIR)"/*.o* "$(LOG_DIR)"/*.e* 2>/dev/null | head -10 || echo "No log files found"

# --- Hugging Face / SIF pull with scratch cache ---
pull-sif:
	@echo "Pulling Singularity container from Hugging Face..."
	@echo "HF_HOME=$(HF_HOME)"
	@echo "HF_HUB_CACHE=$(HF_HUB_CACHE)"
	@echo "HF_XET_CACHE=$(HF_XET_CACHE)"
	@echo "TMPDIR=$(HF_TMPDIR)"
	mkdir -p "$(SIF_DIR)" "$(HF_HUB_CACHE)" "$(HF_XET_CACHE)" "$(HF_ASSETS_CACHE)" "$(HF_TMPDIR)"
	hf download "$(SIF_REPO)" "$(SIF_NAME)" \
		--repo-type dataset \
		--cache-dir "$(HF_HUB_CACHE)" \
		--local-dir "$(SIF_DIR)"

list-data:
	@echo "Available SAR data:"
	@ls -lh "$(PHIDOWN_DATA_DIR)"/

downloader:
	@if [ -z "$(PRODUCT)" ]; then \
		echo "Error: PRODUCT not specified. Usage: make downloader PRODUCT=<product_name>"; \
		exit 1; \
	fi
	@echo "Downloading product from Hugging Face: $(PRODUCT)"
	bash scripts/downloader.sh "$(PRODUCT)"

uploader:
	@echo "Uploading products to Hugging Face..."
	bash scripts/uploader.sh

show-cache:
	@echo "HF_HOME=$(HF_HOME)"
	@echo "HF_HUB_CACHE=$(HF_HUB_CACHE)"
	@echo "HF_XET_CACHE=$(HF_XET_CACHE)"
	@echo "HF_ASSETS_CACHE=$(HF_ASSETS_CACHE)"
	@echo "TMPDIR=$(HF_TMPDIR)"
	@echo "HF_HUB_DISABLE_XET=$(HF_HUB_DISABLE_XET)"

clean-hf-cache:
	@echo "Pruning Hugging Face cache under $(HF_HOME)..."
	@command -v hf >/dev/null 2>&1 || { echo "Error: 'hf' CLI not found in PATH"; exit 1; }
	@mkdir -p "$(HF_HOME)" "$(HF_HUB_CACHE)" "$(HF_XET_CACHE)" "$(HF_ASSETS_CACHE)" "$(HF_TMPDIR)"
	hf cache prune || true