.PHONY: help clean clean-logs ensure-sif ensure-snap ensure-product ensure-runtime ensure-qsub run run-vm run-hpc status logs pull-sif pull-sif-generic pull-snap clean-snap-artifacts list-data down downloader uploader show-cache clean-hf-cache

SHELL := /usr/bin/env bash

# Manual mode switch: set WORLDSAR_MODE=vm or hpc at make time.
WORLDSAR_MODE ?= hpc
RUN_MODE ?= $(WORLDSAR_MODE)

# ---- VM defaults ----
VM_PROJECT_ROOT ?= .
VM_BASE_DIR ?= $(abspath $(VM_PROJECT_ROOT))
VM_DATA_DIR ?= $(VM_BASE_DIR)/phidown_data
VM_PY_SCRIPT_DIR ?= $(VM_BASE_DIR)/pyscripts
VM_SIF_DIR ?= $(VM_BASE_DIR)
VM_SIF_NAME ?= sarpyx.sif
VM_SIF_IMAGE ?= $(VM_SIF_DIR)/$(VM_SIF_NAME)
VM_SNAP_USER_DIR ?= $(VM_BASE_DIR)/.snap
VM_OUTPUT_DIR ?= $(VM_BASE_DIR)/OUT/worldsar_output
VM_TILES_DIR ?= $(VM_BASE_DIR)/OUT/tiles
VM_DB_DIR ?= $(VM_BASE_DIR)/OUT/DB
VM_WORKSPACE_PREFIX ?= /work
VM_GRID_PATH ?= $(VM_WORKSPACE_PREFIX)/grid/grid_10km.geojson
VM_GPT_MEMORY ?= 64G
VM_GPT_PARALLELISM ?= 16
VM_GPT_TIMEOUT ?= 3600
VM_PBS_QUEUE ?=
VM_PBS_WALLTIME ?=
VM_PBS_SELECT ?=

# ---- HPC defaults (adjust for your cluster/user) ----
HPC_PROJECT_ROOT ?= /lustre/projects/1001/rdelprete/WORLDSAR
HPC_BASE_DIR ?= $(abspath $(HPC_PROJECT_ROOT))
HPC_DATA_DIR ?= $(HPC_BASE_DIR)/phidown_data
HPC_PY_SCRIPT_DIR ?= $(HPC_BASE_DIR)/pyscripts
HPC_SIF_DIR ?= $(HPC_BASE_DIR)
HPC_SIF_NAME ?= sarpyx.sif
HPC_SIF_IMAGE ?= $(HPC_SIF_DIR)/$(HPC_SIF_NAME)
HPC_SNAP_USER_DIR ?= $(HPC_BASE_DIR)/.snap
HPC_OUTPUT_DIR ?= $(HPC_BASE_DIR)/OUT/worldsar_output
HPC_TILES_DIR ?= $(HPC_BASE_DIR)/OUT/tiles
HPC_DB_DIR ?= $(HPC_BASE_DIR)/OUT/DB
HPC_WORKSPACE_PREFIX ?= /work
HPC_GRID_PATH ?= $(HPC_WORKSPACE_PREFIX)/grid/grid_10km.geojson
HPC_GPT_MEMORY ?= 128G
HPC_GPT_PARALLELISM ?= 164
HPC_GPT_TIMEOUT ?= 7200
HPC_PBS_QUEUE ?= cpu_std
HPC_PBS_WALLTIME ?= 22:00:00
HPC_PBS_SELECT ?= select=1:ncpus=192:mem=160g

# ---- Effective runtime configuration ----
ifneq ($(filter vm hpc,$(WORLDSAR_MODE)),)
else
$(error WORLDSAR_MODE must be vm or hpc)
endif

ifeq ($(WORLDSAR_MODE),hpc)
BASE_DIR ?= $(HPC_BASE_DIR)
DATA_DIR ?= $(HPC_DATA_DIR)
PY_SCRIPT_DIR ?= $(HPC_PY_SCRIPT_DIR)
SIF_DIR ?= $(HPC_SIF_DIR)
SIF_NAME ?= $(HPC_SIF_NAME)
SIF_IMAGE ?= $(HPC_SIF_IMAGE)
SNAP_USER_DIR ?= $(HPC_SNAP_USER_DIR)
OUTPUT_DIR ?= $(HPC_OUTPUT_DIR)
TILES_DIR ?= $(HPC_TILES_DIR)
DB_DIR ?= $(HPC_DB_DIR)
WORKSPACE_PREFIX ?= $(HPC_WORKSPACE_PREFIX)
GRID_PATH ?= $(HPC_GRID_PATH)
GPT_MEMORY ?= $(HPC_GPT_MEMORY)
GPT_PARALLELISM ?= $(HPC_GPT_PARALLELISM)
GPT_TIMEOUT ?= $(HPC_GPT_TIMEOUT)
PBS_QUEUE ?= $(HPC_PBS_QUEUE)
PBS_WALLTIME ?= $(HPC_PBS_WALLTIME)
PBS_SELECT ?= $(HPC_PBS_SELECT)
else
BASE_DIR ?= $(VM_BASE_DIR)
DATA_DIR ?= $(VM_DATA_DIR)
PY_SCRIPT_DIR ?= $(VM_PY_SCRIPT_DIR)
SIF_DIR ?= $(VM_SIF_DIR)
SIF_NAME ?= $(VM_SIF_NAME)
SIF_IMAGE ?= $(VM_SIF_IMAGE)
SNAP_USER_DIR ?= $(VM_SNAP_USER_DIR)
OUTPUT_DIR ?= $(VM_OUTPUT_DIR)
TILES_DIR ?= $(VM_TILES_DIR)
DB_DIR ?= $(VM_DB_DIR)
WORKSPACE_PREFIX ?= $(VM_WORKSPACE_PREFIX)
GRID_PATH ?= $(VM_GRID_PATH)
GPT_MEMORY ?= $(VM_GPT_MEMORY)
GPT_PARALLELISM ?= $(VM_GPT_PARALLELISM)
GPT_TIMEOUT ?= $(VM_GPT_TIMEOUT)
PBS_QUEUE ?=
PBS_WALLTIME ?=
PBS_SELECT ?=
endif

PROJECT_ROOT ?= $(BASE_DIR)
SNAP_ARCHIVE_URL ?= https://huggingface.co/datasets/WORLDSAR/Support/resolve/main/snap_userdir.tar.gz
SNAP_TMP_DIR ?= $(BASE_DIR)/.tmp/snap
SNAP_ARCHIVE_NAME ?= snap_userdir.tar.gz
MAIN_SCRIPT ?= main.sh
SIF_REPO ?= WORLDSAR/support
LOG_DIR ?= $(BASE_DIR)/logs
PHIDOWN_DATA_DIR ?= $(BASE_DIR)/phidown_data
PBS_USER ?= $(USER)
RUN_TS_FMT ?= +%Y%m%d_%H%M%S

# Hugging Face cache & temp locations (move off HOME quota)
# Override on command line if needed:
#   make pull-sif HF_HOME=/lustre/project/.../hf
HF_HOME ?= /lustre/scratch/1000/WorldSAR
HF_HUB_CACHE ?= $(HF_HOME)/hub
HF_XET_CACHE ?= $(HF_HOME)/xet
HF_ASSETS_CACHE ?= $(HF_HOME)/assets
HF_TMPDIR ?= $(HF_HOME)/tmp
HF_UPLOAD_NUM_WORKERS ?= 1

# Optional: disable Xet if it causes trouble (set to 1 to disable)
# HF_HUB_DISABLE_XET ?= 1

export HF_HOME HF_HUB_CACHE HF_XET_CACHE HF_ASSETS_CACHE
export TMPDIR := $(HF_TMPDIR)
export HF_HUB_DISABLE_XET

# Default target
help:
	@echo "WORLDSAR Makefile Commands:"
	@echo "  WORLDSAR_MODE=vm|hpc (default: vm)"
	@echo "  make run [PRODUCT=<name_or_path>] [WORLDSAR_MODE=vm|hpc] [SIF_IMAGE=...] [MAIN_SCRIPT=main.sh] - Run with selected mode"
	@echo "    In both modes PRODUCT is passed via environment (-v to qsub in HPC), no positional args are sent to main.sh."
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
			echo "Usage: make run PRODUCT=<product_name_or_abs_path>"; \
			exit 1; \
	fi

ensure-runtime: ensure-product ensure-sif ensure-snap

ensure-qsub:
	@command -v qsub >/dev/null 2>&1 || { \
		echo "ERROR: qsub is not available in this environment."; \
		echo "Set WORLDSAR_MODE=vm or load scheduler environment."; \
		exit 1; \
	}

clean:
	@echo "Cleaning output directory..."
	rm -rf "$(OUTPUT_DIR)" "$(TILES_DIR)" "$(DB_DIR)"

clean-logs:
	@echo "Cleaning log files..."
	rm -rf "$(LOG_DIR)"/*.o* "$(LOG_DIR)"/*.e* "$(LOG_DIR)"/*.stdout.log "$(LOG_DIR)"/*.stderr.log

run: ensure-runtime
	@if [ "$(WORLDSAR_MODE)" = "hpc" ]; then \
		$(MAKE) run-hpc; \
	else \
		$(MAKE) run-vm; \
	fi

run-hpc: ensure-runtime ensure-qsub
	@echo "Submitting HPC job via qsub..."
	@mkdir -p "$(LOG_DIR)"
	@cd "$(LOG_DIR)" && qsub \
		$(if $(PBS_QUEUE),-q "$(PBS_QUEUE)",) \
		$(if $(PBS_WALLTIME),-l walltime="$(PBS_WALLTIME)",) \
		$(if $(PBS_SELECT),-l "$(PBS_SELECT)",) \
		-v PRODUCT="$(PRODUCT)",WORLDSAR_MODE="$(WORLDSAR_MODE)",RUN_MODE="$(RUN_MODE)",BASE_DIR="$(BASE_DIR)",DATA_DIR="$(DATA_DIR)",PY_SCRIPT_DIR="$(PY_SCRIPT_DIR)",SIF_IMAGE="$(SIF_IMAGE)",OUTPUT_PATH="$(OUTPUT_DIR)",OUTPUT_DIR="$(OUTPUT_DIR)",CUTS_OUTDIR="$(TILES_DIR)",TILES_DIR="$(TILES_DIR)",DB_DIR="$(DB_DIR)",SNAP_USER_DIR="$(SNAP_USER_DIR)",WORKSPACE_PREFIX="$(WORKSPACE_PREFIX)",GRID_PATH="$(GRID_PATH)",GRID_HOST_DIR="",SCRIPT_DIR="$(BASE_DIR)/scripts",GPT_MEMORY="$(GPT_MEMORY)",GPT_PARALLELISM="$(GPT_PARALLELISM)",GPT_TIMEOUT="$(GPT_TIMEOUT)" \
		../"$(MAIN_SCRIPT)"
	@echo "Use 'make status' to check job status"

run-vm: ensure-runtime
	@echo "Running locally in VM mode (no qsub)..."
	@mkdir -p "$(LOG_DIR)"
	@run_ts="$$(date $(RUN_TS_FMT))"; \
	prod_base="$$(basename "$(PRODUCT)")"; \
	stdout_log="$(LOG_DIR)/$${run_ts}_$${prod_base}.stdout.log"; \
	stderr_log="$(LOG_DIR)/$${run_ts}_$${prod_base}.stderr.log"; \
	echo "VM stdout log: $$stdout_log"; \
	echo "VM stderr log: $$stderr_log"; \
	BASE_DIR="$(BASE_DIR)" \
	DATA_DIR="$(DATA_DIR)" \
	PY_SCRIPT_DIR="$(PY_SCRIPT_DIR)" \
	SIF_IMAGE="$(SIF_IMAGE)" \
	OUTPUT_PATH="$(OUTPUT_DIR)" \
	OUTPUT_DIR="$(OUTPUT_DIR)" \
	CUTS_OUTDIR="$(TILES_DIR)" \
	DB_DIR="$(DB_DIR)" \
	SNAP_USER_DIR="$(SNAP_USER_DIR)" \
	WORKSPACE_PREFIX="$(WORKSPACE_PREFIX)" \
	GPT_MEMORY="$(GPT_MEMORY)" \
	GPT_PARALLELISM="$(GPT_PARALLELISM)" \
	GPT_TIMEOUT="$(GPT_TIMEOUT)" \
	WORLDSAR_MODE="$(WORLDSAR_MODE)" \
	RUN_MODE="$(RUN_MODE)" \
	SIF_NAME="$(SIF_NAME)" \
	GRID_PATH="$(GRID_PATH)" \
	PRODUCT="$(PRODUCT)" \
	bash "./$(MAIN_SCRIPT)" \
	  > >(tee "$$stdout_log") \
	  2> >(tee "$$stderr_log" >&2)

status:
	@if [ "$(WORLDSAR_MODE)" = "hpc" ]; then \
		qstat -u "$(PBS_USER)"; \
	else \
		echo "INFO: status checks PBS jobs only; you selected VM mode."; \
		echo "For local runs, inspect logs in $(LOG_DIR) and process exit codes."; \
	fi

logs:
	@if [ "$(WORLDSAR_MODE)" = "hpc" ]; then \
		echo "Recent scheduler logs/logs:"; \
		ls -lht "$(LOG_DIR)"/*.stdout.log "$(LOG_DIR)"/*.stderr.log "$(LOG_DIR)"/*.o* "$(LOG_DIR)"/*.e* 2>/dev/null | head -10 || echo "No log files found"; \
	else \
		echo "Recent local run logs:"; \
		ls -lht "$(LOG_DIR)"/*.stdout.log "$(LOG_DIR)"/*.stderr.log 2>/dev/null | head -10 || echo "No local log files found"; \
	fi

# --- Hugging Face / SIF pull with scratch cache ---
pull-sif:
	@echo "Pulling Singularity container from Hugging Face..."
	@echo "HF_HOME=$(HF_HOME)"
	@echo "HF_HUB_CACHE=$(HF_HUB_CACHE)"
	@echo "HF_XET_CACHE=$(HF_XET_CACHE)"
	@echo "TMPDIR=$(HF_TMPDIR)"
	mkdir -p "$(SIF_DIR)" "$(HF_HUB_CACHE)" "$(HF_XET_CACHE)" "$(HF_ASSETS_CACHE)" "$(HF_TMPDIR)"
	export MALLOC_ARENA_MAX=2 && hf download "$(SIF_REPO)" "$(SIF_NAME)" \
		--repo-type dataset \
		--cache-dir "$(HF_HUB_CACHE)" \
		--max-workers "$(HF_UPLOAD_NUM_WORKERS)" \
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
	MALLOC_ARENA_MAX=2 && \
		hf download "$(SIF_REPO)" "$(SIF_NAME)" \
		--repo-type dataset \
		--cache-dir "$$HF_HUB_CACHE_DIR" \
		--max-workers "$(HF_UPLOAD_NUM_WORKERS)" \
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
	@# SpaceHPC uploads need single-worker mode to avoid HF client issues on shared filesystems.
	HF_UPLOAD_NUM_WORKERS="$(HF_UPLOAD_NUM_WORKERS)" bash scripts/uploader.sh

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
