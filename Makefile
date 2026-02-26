.PHONY: help clean clean-logs ensure-sif ensure-snap ensure-product run run-vm status logs pull-sif pull-sif-generic pull-snap clean-snap-artifacts list-data down downloader uploader show-cache clean-hf-cache

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
SNAP_USER_DIR ?= $(PROJECT_ROOT)/.snap
SNAP_ARCHIVE_URL ?= https://huggingface.co/datasets/WORLDSAR/Support/resolve/main/snap_userdir.tar.gz
SNAP_TMP_DIR ?= $(PROJECT_ROOT)/.tmp/snap
SNAP_ARCHIVE_NAME ?= snap_userdir.tar.gz
RUN_TS_FMT ?= +%Y%m%d_%H%M%S

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
	@echo "  make run [SIF_IMAGE=./sarpyx.sif] [MAIN_SCRIPT=main.sh] - Submit job to queue"
	@echo "  make run-vm PRODUCT=<name> [SIF_IMAGE=./sarpyx.sif] [MAIN_SCRIPT=main.sh] - Run locally (no qsub)"
	@echo "  make down PRODUCT=<name> - Download SAR product into \$(PHIDOWN_DATA_DIR)"
	@echo "  make status       - Check current job status"
	@echo "  make logs         - View recent log files"
	@echo "  make clean        - Remove all output files"
	@echo "  make pull-sif     - Pull/update Singularity container (HF cache on scratch)"
	@echo "  make pull-snap    - Download and extract .snap userdir into project root"
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
	bash scripts/downloader_uv.sh "$(PRODUCT)"

ensure-sif:
	@if [ ! -f "$(SIF_IMAGE)" ]; then \
		echo "SIF image not found: $(SIF_IMAGE). Pulling from $(SIF_REPO)..."; \
		$(MAKE) pull-sif; \
	fi

ensure-snap:
	@if [ ! -d "$(SNAP_USER_DIR)" ]; then \
		echo "SNAP userdir not found: $(SNAP_USER_DIR). Pulling from Hugging Face..."; \
		$(MAKE) pull-snap; \
	fi

ensure-product:
	@if [ -z "$(PRODUCT)" ]; then \
		echo "Error: PRODUCT not specified."; \
		echo "Usage: make run PRODUCT=<product_name>"; \
		echo "Usage: make run-vm PRODUCT=<product_name>"; \
		exit 1; \
	fi

clean:
	@echo "Cleaning output directory..."
	rm -rf "$(OUTPUT_DIR)" "$(TILES_DIR)" "$(DB_DIR)"

clean-logs:
	@echo "Cleaning log files..."
	rm -rf "$(LOG_DIR)"/*.o* "$(LOG_DIR)"/*.e* "$(LOG_DIR)"/*.stdout.log "$(LOG_DIR)"/*.stderr.log

run: ensure-sif ensure-snap
	@echo "Submitting job to queue..."
	cd "$(LOG_DIR)" && qsub ../"$(MAIN_SCRIPT)"
	@echo "Use 'make status' to check job status"

run-vm: ensure-product ensure-sif ensure-snap
	@echo "Running job locally (no qsub)..."
	mkdir -p "$(LOG_DIR)"
	@run_ts="$$(date $(RUN_TS_FMT))"; \
	prod_base="$$(basename "$(PRODUCT)")"; \
	stdout_log="$(LOG_DIR)/$${run_ts}_$${prod_base}.stdout.log"; \
	stderr_log="$(LOG_DIR)/$${run_ts}_$${prod_base}.stderr.log"; \
	echo "VM stdout log: $$stdout_log"; \
	echo "VM stderr log: $$stderr_log"; \
	BASE_DIR="." \
	SIF_IMAGE="./$(SIF_NAME)" \
	bash "./$(MAIN_SCRIPT)" "$(PRODUCT)" \
	  > >(tee "$$stdout_log") \
	  2> >(tee "$$stderr_log" >&2)

status:
	@qstat -u "$(PBS_USER)"

logs:
	@echo "Recent log files:"
	@ls -lht "$(LOG_DIR)"/*.stdout.log "$(LOG_DIR)"/*.stderr.log "$(LOG_DIR)"/*.o* "$(LOG_DIR)"/*.e* 2>/dev/null | head -10 || echo "No log files found"

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
	rm -rf "$(PROJECT_ROOT)/.tmp"

pull-sif-generic:
	@echo "Pulling Singularity container to project root with local .tmp folder for caching..."
	TMP_DIR="$(PROJECT_ROOT)/.tmp"; \
	HF_HOME_DIR="$$TMP_DIR/hf"; \
	HF_HUB_CACHE_DIR="$$HF_HOME_DIR/hub"; \
	HF_XET_CACHE_DIR="$$HF_HOME_DIR/xet"; \
	HF_ASSETS_CACHE_DIR="$$HF_HOME_DIR/assets"; \
	HF_TMPDIR_DIR="$$HF_HOME_DIR/tmp"; \
	mkdir -p "$$TMP_DIR" "$$HF_HUB_CACHE_DIR" "$$HF_XET_CACHE_DIR" "$$HF_ASSETS_CACHE_DIR" "$$HF_TMPDIR_DIR"; \
	HF_HOME="$$HF_HOME_DIR" \
	HF_HUB_CACHE="$$HF_HUB_CACHE_DIR" \
	HF_XET_CACHE="$$HF_XET_CACHE_DIR" \
	HF_ASSETS_CACHE="$$HF_ASSETS_CACHE_DIR" \
	TMPDIR="$$HF_TMPDIR_DIR" \
	HF_HUB_DISABLE_XET=1 \
	hf download "$(SIF_REPO)" "$(SIF_NAME)" \
		--repo-type dataset \
		--cache-dir "$$HF_HUB_CACHE_DIR" \
		--local-dir "$(PROJECT_ROOT)"
	rm -rf "$(PROJECT_ROOT)/.tmp"

pull-snap:
	@echo "Downloading SNAP userdir archive from Hugging Face..."
	@command -v curl >/dev/null 2>&1 || { echo "Error: 'curl' not found in PATH"; exit 1; }
	TMP_DIR="$(SNAP_TMP_DIR)"; \
	ARCHIVE="$$TMP_DIR/$(SNAP_ARCHIVE_NAME)"; \
	EXTRACT_DIR="$$TMP_DIR/extract"; \
	cleanup() { rm -rf "$$TMP_DIR"; }; \
	trap cleanup EXIT; \
	rm -rf "$$TMP_DIR"; \
	mkdir -p "$$EXTRACT_DIR"; \
	curl -L -f --retry 3 --retry-delay 5 -o "$$ARCHIVE" "$(SNAP_ARCHIVE_URL)"; \
	tar -xzf "$$ARCHIVE" -C "$$EXTRACT_DIR"; \
	rm -rf "$(SNAP_USER_DIR)"; \
	if [ -d "$$EXTRACT_DIR/.snap" ]; then \
		mv "$$EXTRACT_DIR/.snap" "$(SNAP_USER_DIR)"; \
	elif [ -d "$$EXTRACT_DIR/snap_userdir/.snap" ]; then \
		mv "$$EXTRACT_DIR/snap_userdir/.snap" "$(SNAP_USER_DIR)"; \
	else \
		FOUND_SNAP="$$(find "$$EXTRACT_DIR" -type d -name '.snap' | head -n 1)"; \
		if [ -z "$$FOUND_SNAP" ]; then \
			echo "Error: '.snap' directory not found after extracting $(SNAP_ARCHIVE_NAME)"; \
			exit 1; \
		fi; \
		mv "$$FOUND_SNAP" "$(SNAP_USER_DIR)"; \
	fi; \
	trap - EXIT; \
	cleanup; \
	echo "SNAP userdir ready: $(SNAP_USER_DIR)"

clean-snap-artifacts:
	@echo "Cleaning SNAP download artifacts..."
	rm -rf "$(SNAP_TMP_DIR)"

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
