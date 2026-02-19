


.PHONY: help clean run status logs pull-sif list-data down downloader uploader


# Default target
help:
	@echo "WORLDSAR Makefile Commands:"
	@echo "  make run          - Submit job to queue and watch status"
	@echo "  make down PRODUCT=<name> - Download SAR product"
	@echo "  make status       - Check current job status"
	@echo "  make logs         - View recent log files"
	@echo "  make clean        - Remove all output files"
	@echo "  make pull-sif     - Pull/update Singularity container"
	@echo "  make list-data    - List available SAR data"

down:
	@if [ -z "$(PRODUCT)" ]; then \
		echo "Error: PRODUCT not specified. Usage: make down PRODUCT=<product_name>"; \
		exit 1; \
	fi
	@echo "Downloading product: $(PRODUCT)"
	/lustre/projects/1001/rdelprete/service/down.sh $(PRODUCT) /lustre/projects/1001/rdelprete/WORLDSAR/phidown_data

clean:
	@echo "Cleaning output directory..."
	rm -rf //lustre/projects/1001/rdelprete/WORLDSAR/OUT/worldsar_output/*
	rm -rf //lustre/projects/1001/rdelprete/WORLDSAR/OUT/tiles/*
	rm -rf //lustre/projects/1001/rdelprete/WORLDSAR/OUT/DB/*

clean-logs:
	@echo "Cleaning log files..."
	rm -rf /lustre/projects/1001/rdelprete/logs/*.o* /lustre/projects/1001/rdelprete/logs/*

run:
	@echo "Submitting job to queue..."
	cd /lustre/projects/1001/rdelprete/logs && qsub /lustre/projects/1001/rdelprete/WORLDSAR/main.sh
	@echo "Use 'make status' to check job status"

status:
	@qstat -u u10010007

logs:
	@echo "Recent log files:"
	@ls -lht /lustre/projects/1001/rdelprete/logs/*.o* /lustre/projects/1001/rdelprete/logs/*.e* 2>/dev/null | head -10 || echo "No log files found"

pull-sif:
	@echo "Pulling Singularity container..."
	bash scripts/pull_sif.sh

list-data:
	@echo "Available SAR data:"
	@ls -lh phidown_data/


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