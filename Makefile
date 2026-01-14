# ==============================================================================
# 🏛️ PROJECT: ADS-B Research Grid
# 📂 FILE:    Makefile
# 🔢 VERSION: 5.2.0 (Auto-Clean & Full Ops)
# ==============================================================================

.PHONY: help report clean-docs check all setup deploy

VENV_DIR = venv
PYTHON   = $(VENV_DIR)/bin/python3
ANSIBLE  = $(VENV_DIR)/bin/ansible-playbook

# --- 1. CORE OPERATIONS ---

help:
	@echo "📡 ADS-B Research Grid Control Center"
	@echo "--------------------------------------------------------"
	@echo "  --- OPERATIONS (Infra) ---"
	@echo "  make setup      - 📦 Install dependencies (Python/Ansible)"
	@echo "  make deploy     - 🚀 Configure all sensors (Ansible)"
	@echo "  make check      - 🏥 Check Node Reachability (Ping)"
	@echo ""
	@echo "  --- SCIENCE (Data) ---"
	@echo "  make fetch      - 📥 Download, Heal & Merge logs from grid"
	@echo "  make consolidate- 🧹 Manually fix fragmented logs (1-min -> Daily)"
	@echo "  make ml         - 🧪 Run Anomaly Detection (Isolation Forest)"
	@echo "  make ghosts     - 👻 Generate Forensic Maps (Clean & Rebuild)"
	@echo "  make report     - 📊 Generate Academic Audit Report"
	@echo "  make all        - 🔁 Run Full Pipeline (Fetch->Heal->ML->Report)"
	@echo "--------------------------------------------------------"

setup:
	@echo "[INIT] 📦 Setting up Virtual Environment..."
	@python3 -m venv $(VENV_DIR)
	@$(VENV_DIR)/bin/pip install -r requirements.txt
	@echo "[INIT] ✅ Environment Ready."

deploy:
	@echo "[OPS] 🚀 Deploying Configuration to Grid..."
	@$(ANSIBLE) -i infra/ansible/inventory/hosts.prod infra/ansible/playbooks/site.yml --vault-password-file .vault_pass

check:
	@echo "[OPS] 🏥 Checking Grid Connectivity..."
	@$(ANSIBLE) -i infra/ansible/inventory/hosts.prod infra/ansible/playbooks/ping.yml --vault-password-file .vault_pass

# --- 2. DATA PIPELINE ---

fetch:
	@echo "[DATA] 📥 Syncing logs from grid..."
	@$(ANSIBLE) -i infra/ansible/inventory/hosts.prod infra/ansible/playbooks/fetch.yml --vault-password-file .vault_pass
	@$(MAKE) consolidate

consolidate:
	@echo "[MAINTENANCE] 🧹 Running Self-Healing on Sensor Logs..."
	@$(PYTHON) scripts/maintenance/consolidate_fragments.py

# --- 3. SCIENCE & FORENSICS ---

ml:
	@echo "[ML] 🧪 Training Isolation Forest (v3)..."
	@if [ -d "research_data" ]; then \
		$(PYTHON) scripts/ds_pipeline_master.py; \
	else \
		echo "❌ No data found! Run 'make fetch' first."; \
	fi

ghosts:
	@echo "[VIS] 👻 Generating Forensic Maps..."
	@# Clean old maps to prevent duplicates (e.g. old D11 vs new D10)
	@rm -f docs/showcase/ghost_hunt/D*.png
	$(PYTHON) scripts/visualize_ghosts.py

report:
	@echo "[PIPELINE] 🚀 Starting Modular Analysis Pipeline..."
	@$(eval RUN_ID := run_$(shell date +%Y-%m-%d_%H%M))
	@$(eval OUT_DIR := docs/showcase/$(RUN_ID))
	@mkdir -p $(OUT_DIR)/figures
	@echo "[PIPELINE] 📂 Output Directory: $(OUT_DIR)"
	
	@# 1. Run Infra Health (D5 Combined)
	@$(PYTHON) scripts/infra_health.py --out-dir $(OUT_DIR)
	
	@# 2. Run Science EDA (D1-D4, D6, Report)
	@$(PYTHON) scripts/academic_eda.py --out-dir $(OUT_DIR)
	
	@# 3. Copy Ghost Maps (D7-D10)
	@cp docs/showcase/ghost_hunt/D*.png $(OUT_DIR)/figures/ 2>/dev/null || echo "[PIPELINE] ⚠️  No ghost maps to attach."
	
	@echo "[PIPELINE] ✅ Full Report Compilation Complete."

clean-docs:
	@echo "[MAINTENANCE] 🧹 Archiving old reports..."
	@mkdir -p docs/showcase/archive
	@cd docs/showcase && ls -d run_*/ 2>/dev/null | sort | head -n -1 | xargs -I {} mv {} archive/ 2>/dev/null || echo "   ℹ️  Archive up to date."

# --- 4. MASTER SWITCH ---

all: fetch ml ghosts report
	@echo "✅ Full Science Run Complete."
