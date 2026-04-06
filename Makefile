# ==============================================================================
# 🏛️ PROJECT: ADS-B Research Grid
# 📂 FILE:    Makefile
# 🔢 VERSION: 6.1.0 (macOS Compatible & Path Fixes)
# ==============================================================================

.PHONY: help report clean-docs check all setup deploy gnss dashboard logging tower

VENV_DIR = venv
PYTHON   = $(VENV_DIR)/bin/python3
ANSIBLE  = $(VENV_DIR)/bin/ansible-playbook
ANSIBLE_ADHOC = $(VENV_DIR)/bin/ansible

INVENTORY = infra/ansible/inventory/hosts.prod
VAULT     = .vault_pass

# Default Report Window (Can be overridden: make report WINDOW=48)
WINDOW ?= 24

# --- 1. CORE OPERATIONS ---

help:
	@echo "📡 ADS-B Research Grid Control Center"
	@echo "--------------------------------------------------------"
	@echo "  --- OPERATIONS (Infra) ---"
	@echo "  make setup      - 📦 Install dependencies"
	@echo "  make deploy     - 🚀 Configure all sensors (Ansible)"
	@echo ""
	@echo "  --- INFRASTRUCTURE (Ops) ---"
	@echo "  make check        - 🏥 Check Connectivity"
	@echo "  make dashboard    - 📊 Update Grafana Dashboards"
	@echo "  make logging      - 🪵 Update Logstash Pipeline"
	@echo "  make tower        - 🗼 Provision Tower Core services"
	@echo ""
	@echo "  --- DATA SCIENCE (Tier 1) ---"
	@echo "  make fetch        - 📥 Download, Heal & Merge logs from grid"
	@echo "  make consolidate  - 🧹 Self-Heal fragmented sensor logs"
	@echo "  make ml           - 🧪 Run Ensemble Anomaly Detection (IsoForest + LOF)"
	@echo "  make ghosts       - 👻 Generate Forensic Maps (Ghost Hunt)"
	@echo "  make gnss         - 🛰️  Run Hardware Certification (D12)"
	@echo "  make report       - 📊 Generate Academic Report (Default: Last 24h)"
	@echo "                      Usage: make report WINDOW=48"
	@echo "                      Usage: make report WINDOW=all"
	@echo "  make clean-docs   - 🧹 Archive old reports"
	@echo "  make all          - 🔁 Run Full Pipeline (Fetch -> ML -> Report)"
	@echo "--------------------------------------------------------"

setup:
	@echo "[INIT] 📦 Setting up Virtual Environment..."
	@python3 -m venv $(VENV_DIR)
	@$(VENV_DIR)/bin/pip install -r requirements.txt
	@echo "[INIT] ✅ Environment Ready."

deploy:
	@echo "[OPS] 🚀 Deploying Configuration to Grid (Full Site)..."
	@$(ANSIBLE) -i $(INVENTORY) infra/ansible/playbooks/site.yml --vault-password-file $(VAULT)

check:
	@echo "[OPS] 🏥 Checking Grid Connectivity..."
	@$(ANSIBLE) -i $(INVENTORY) infra/ansible/playbooks/ping.yml --vault-password-file $(VAULT)

# --- 2. TOWER MAINTENANCE (DevOps) ---

dashboard:
	@echo "[OPS] 📊 Pushing Updated Dashboards to Tower..."
	@$(ANSIBLE_ADHOC) core -i $(INVENTORY) -b -m include_role -a "name=tower_core tasks_from=main" --vault-password-file $(VAULT) -t dashboard

logging:
	@echo "[OPS] 🪵 Updating Logging Pipeline (Logstash/OpenSearch)..."
	@$(ANSIBLE_ADHOC) core -i $(INVENTORY) -b -m include_role -a "name=tower_core tasks_from=main" --vault-password-file $(VAULT) -t logging

tower:
	@echo "[OPS] 🗼 Provisioning Tower Core Role..."
	@$(ANSIBLE_ADHOC) core -i $(INVENTORY) -b -m include_role -a "name=tower_core tasks_from=main" --vault-password-file $(VAULT)

# --- 3. DATA PIPELINE ---

fetch:
	@echo "[DATA] 📥 Syncing logs from grid..."
	@$(ANSIBLE) -i $(INVENTORY) infra/ansible/playbooks/fetch.yml --vault-password-file $(VAULT)
	@$(MAKE) consolidate

consolidate:
	@echo "[MAINTENANCE] 🧹 Running Self-Healing on Sensor Logs..."
	@$(PYTHON) scripts/maintenance/consolidate_fragments.py

# --- 4. SCIENCE & FORENSICS ---

ml:
	@echo "[ML] 🧪 Training Ensemble (IsoForest + LOF)..."
	@if [ -d "research_data/raw" ]; then \
		$(PYTHON) scripts/ds_pipeline_master.py; \
	else \
		echo "❌ No data found! Run 'make fetch' first."; \
	fi

ghosts:
	@echo "[VIS] 👻 Generating Forensic Maps..."
	@rm -f docs/showcase/ghost_hunt/D*.png
	$(PYTHON) scripts/visualize_ghosts.py

gnss:
	@echo "[GNSS] 🛰️  Analyzing Sensor Precision (D12)..."
	@$(PYTHON) scripts/gnss_analysis.py --out-dir docs/showcase/gnss_audit

report:
	@echo "[PIPELINE] 🚀 Starting Modular Analysis Pipeline..."
	@echo "[CONFIG] 🕒 Reporting Window: $(WINDOW) Hours"
	@$(eval RUN_ID := run_$(shell date +%Y-%m-%d_%H%M))
	@$(eval OUT_DIR := docs/showcase/$(RUN_ID))
	@mkdir -p $(OUT_DIR)/figures
	@echo "[PIPELINE] 📂 Output Directory: $(OUT_DIR)"
	
	@# 1. Run Infra Health (D5)
	@$(PYTHON) scripts/infra_health.py --out-dir $(OUT_DIR)
	
	@# 2. Run GNSS Precision (D12)
	@$(PYTHON) scripts/gnss_analysis.py --out-dir $(OUT_DIR)/figures
	
	@# 3. Run Science EDA (D1-D4, Report Compiler) with Windowing
	@$(PYTHON) scripts/academic_eda.py --out-dir $(OUT_DIR) --window $(WINDOW)
	
	@# 4. Copy Ghost Maps
	@cp docs/showcase/ghost_hunt/D*.png $(OUT_DIR)/figures/ 2>/dev/null || echo "[PIPELINE] ⚠️  No ghost maps to attach."
	
	@# 5. Update 'latest' link
	@rm -rf docs/showcase/latest
	@cp -r $(OUT_DIR) docs/showcase/latest
	
	@echo "[PIPELINE] ✅ Full Report Compilation Complete."

clean-docs:
	@echo "[MAINTENANCE] 🧹 Archiving old reports..."
	@mkdir -p docs/showcase/archive
	@# FIX: Replaced 'head -n -1' with 'sed $$d' for macOS compatibility
	@cd docs/showcase && ls -d run_*/ 2>/dev/null | sort | sed '$$d' | xargs -I {} mv {} archive/ 2>/dev/null || echo "   ℹ️  Archive up to date."

# --- 5. MASTER SWITCH ---

all: fetch ml ghosts report
	@echo "✅ Full Science Run Complete."
