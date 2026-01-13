# ==============================================================================
# 🏛️ PROJECT: ADS-B Spoofing Data Collection (Academic Research)
# 📂 FILE:    Makefile
# 🔢 VERSION: 3.8.0 (Merged "Command Center" Ops with "Data Science" Pipeline)
# 📅 DATE:    2026-01-13
# ✍️ AUTHOR:  ADSB Research Grid Team
# ==============================================================================

.PHONY: help setup check all clean
.PHONY: deploy sensors tower dashboard database monitoring kick-sensors ping
.PHONY: fetch consolidate ml ghosts report

# --- 1. ENVIRONMENT ---
VENV_DIR         = venv
PYTHON           = $(VENV_DIR)/bin/python3
ANSIBLE_CMD      = $(VENV_DIR)/bin/ansible-playbook
# Corrected path to the master playbook
PLAYBOOK         = infra/ansible/playbooks/site.yml
INVENTORY        = infra/ansible/inventory/hosts.prod
VAULT_PASS       = .vault_pass

# --- 2. HELP ---
help:
	@echo "📡 ADS-B Research Grid Control Center (v3.8.0)"
	@echo "--------------------------------------------------------"
	@echo "  --- 🚀 OPERATIONS (Infrastructure) ---"
	@echo "  make setup        - 📦 Install Python & Ansible dependencies"
	@echo "  make deploy       - 🌐 Full Site Deployment (Slow & Safe)"
	@echo "  make sensors      - 📡 Deploy only Sensor Nodes"
	@echo "  make tower        - 🗼 Deploy only Tower Core"
	@echo "  make check        - 🏥 Real-time Sensor Health Dashboard"
	@echo "  make ping         - 📶 Test Ansible Connectivity"
	@echo ""
	@echo "  --- 🔧 SURGICAL UPDATES (Quick Fixes) ---"
	@echo "  make dashboard    - 📊 Update Grafana Dashboards ONLY"
	@echo "  make database     - 💾 Update InfluxDB Config ONLY"
	@echo "  make monitoring   - 📈 Update Telegraf Configs (Fixes Auth)"
	@echo "  make kick-sensors - 🥾 Force Restart Telegraf (Emergency)"
	@echo ""
	@echo "  --- 🧪 SCIENCE (Data Pipeline) ---"
	@echo "  make fetch        - 📥 Download & Heal logs from grid"
	@echo "  make consolidate  - 🧹 Self-Healing (Fragment Stitching)"
	@echo "  make ml           - 🤖 Run Isolation Forest (Anomaly Detection)"
	@echo "  make ghosts       - 👻 Generate Forensic Maps"
	@echo "  make report       - 📄 Generate Academic Audit Report"
	@echo "  make all          - 🔁 Run Full Data Cycle (Fetch->ML->Report)"

setup:
	@echo "📦 Syncing venv dependencies..."
	$(VENV_DIR)/bin/pip install -r requirements.txt
	$(VENV_DIR)/bin/pip install -r infra/ansible/requirements.txt

# --- 3. OPERATIONS (INFRASTRUCTURE) ---

deploy: ## Full Site Deployment
	@echo "[OPS] 🚀 Deploying Full Configuration to Grid..."
	$(ANSIBLE_CMD) -i $(INVENTORY) $(PLAYBOOK) --vault-password-file $(VAULT_PASS)

sensors: ## Deploy only Sensor Nodes
	@echo "[OPS] 📡 Deploying Sensor Nodes (HW & Recorders)..."
	$(ANSIBLE_CMD) -i $(INVENTORY) $(PLAYBOOK) --tags "sensor_node,common,zerotier,gnss,recorder" --vault-password-file $(VAULT_PASS)

tower: ## Deploy only Tower Core
	@echo "[OPS] 🗼 Deploying Tower Core..."
	$(ANSIBLE_CMD) -i $(INVENTORY) $(PLAYBOOK) --tags "tower_core" --vault-password-file $(VAULT_PASS)

dashboard: ## Update Grafana Only
	@echo "[OPS] 📊 Updating Grafana Dashboards..."
	$(ANSIBLE_CMD) -i $(INVENTORY) $(PLAYBOOK) --tags "grafana" --vault-password-file $(VAULT_PASS)

database: ## Update InfluxDB Only
	@echo "[OPS] 💾 Updating InfluxDB Configuration..."
	$(ANSIBLE_CMD) -i $(INVENTORY) $(PLAYBOOK) --tags "influxdb" --vault-password-file $(VAULT_PASS)

monitoring: ## Update Telegraf Agents
	@echo "[OPS] 📈 Updating Telegraf Agents (Auth/Config)..."
	$(ANSIBLE_CMD) -i $(INVENTORY) $(PLAYBOOK) --tags "telegraf" --vault-password-file $(VAULT_PASS)

kick-sensors: ## Emergency Restart
	@echo "[OPS] 🥾 Kicking Sensor Monitoring Agents..."
	venv/bin/ansible sensors -i $(INVENTORY) -a "docker restart telegraf" --become --vault-password-file $(VAULT_PASS)

ping: ## Connectivity Check
	@echo "[OPS] 👋 Pinging all nodes..."
	venv/bin/ansible all -i $(INVENTORY) -m ping --vault-password-file $(VAULT_PASS)

check:
	@echo "[OPS] 🏥 Probing Signal Health..."
	@$(PYTHON) scripts/check_signal_health.py

# --- 4. DATA PIPELINE (SCIENCE) ---

fetch:
	@echo "[DATA] 📥 Syncing logs from grid..."
	$(ANSIBLE_CMD) -i $(INVENTORY) infra/ansible/playbooks/fetch.yml --vault-password-file $(VAULT_PASS)
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
