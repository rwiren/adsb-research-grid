# ==============================================================================
# PROJECT: ADS-B Spoofing Data Collection (Academic Research)
# FILE:    Makefile
# VERSION: 3.7.0 (Added Self-Healing Data Pipeline)
# DATE:    2026-01-12
# ==============================================================================

.PHONY: help setup deploy check fetch consolidate ml ghosts report all clean

# --- 1. ENVIRONMENT ---
VENV_DIR         = venv
PYTHON           = $(VENV_DIR)/bin/python3
ANSIBLE_PLAYBOOK = $(VENV_DIR)/bin/ansible-playbook
INVENTORY        = infra/ansible/inventory/hosts.prod
VAULT_PASS       = .vault_pass

# --- 2. HELP ---
help:
	@echo "📡 ADS-B Research Grid Control Center"
	@echo "--------------------------------------------------------"
	@echo "  --- OPERATIONS (Infra) ---"
	@echo "  make setup      - 📦 Install dependencies"
	@echo "  make deploy     - 🚀 Configure all sensors (Ansible)"
	@echo "  make check      - 🏥 Real-time Sensor Health Dashboard"
	@echo ""
	@echo "  --- SCIENCE (Data) ---"
	@echo "  make fetch      - 📥 Download, Heal & Merge logs from grid"
	@echo "  make consolidate- 🧹 Manually fix fragmented logs (1-min -> Daily)"
	@echo "  make ml         - 🧪 Run Anomaly Detection (Isolation Forest)"
	@echo "  make ghosts     - 👻 Generate Forensic Maps (Ghost Hunt)"
	@echo "  make report     - 📊 Generate Academic Audit Report"
	@echo "  make all        - 🔁 Run Full Pipeline (Fetch->Heal->ML->Report)"

setup:
	@echo "📦 Syncing venv dependencies..."
	$(VENV_DIR)/bin/pip install -r requirements.txt
	$(VENV_DIR)/bin/pip install -r infra/ansible/requirements.txt

# --- 3. OPERATIONS ---
deploy:
	@echo "[OPS] 📡 Deploying Configuration to Grid..."
	$(ANSIBLE_PLAYBOOK) -i $(INVENTORY) infra/ansible/site.yml --vault-password-file $(VAULT_PASS)

check:
	@echo "[OPS] 🏥 Probing Signal Health..."
	@$(PYTHON) scripts/check_signal_health.py

# --- 4. DATA PIPELINE ---
fetch:
	@echo "[DATA] 📥 Syncing logs from grid..."
	$(ANSIBLE_PLAYBOOK) -i $(INVENTORY) infra/ansible/playbooks/fetch.yml --vault-password-file $(VAULT_PASS)
	@$(MAKE) consolidate
	@echo "[ETL] 🔄 Merging Storage Logs..."
	@$(PYTHON) scripts/merge_storage_logs.py

consolidate:
	@echo "[MAINTENANCE] 🧹 Running Self-Healing on Sensor Logs..."
	@$(PYTHON) scripts/maintenance/consolidate_fragments.py

ml:
	@echo "[ML] 🧪 Training Isolation Forest (v3)..."
	@if [ -d "research_data" ]; then \
		$(PYTHON) scripts/ds_pipeline_master.py; \
	else \
		echo "❌ No data found! Run 'make fetch' first."; \
	fi

ghosts:
	@echo "[VIS] 👻 Generating Forensic Maps..."
	$(PYTHON) scripts/visualize_ghosts.py

report:
	@echo "[DOCS] 📊 Generating Academic Showcase..."
	$(PYTHON) scripts/academic_eda.py

all: fetch ml ghosts report
	@echo "✅ Full Science Run Complete."

clean:
	@echo "🧹 Cleaning temporary artifacts..."
	rm -rf output/plots/eda_v3 research_data/ml_ready/dataset_validation_report.txt
	@echo "✨ Clean."
