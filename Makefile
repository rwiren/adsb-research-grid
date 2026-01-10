# ==============================================================================
# PROJECT: ADS-B Spoofing Data Collection (Academic Research)
# FILE:    Makefile
# VERSION: 0.4.6
# DATE:    2026-01-09
#
# DESCRIPTION:
#   Primary automation interface for the sensor grid.
#   - Manages Python Virtual Environment (venv) for isolation.
#   - Orchestrates Ansible playbooks for Sensor-North (RTK) & Sensor-West (USB).
#   - Provides specific targets for rapid code deployment vs full provisioning.
# ==============================================================================

.PHONY: help setup deploy deploy-logger check fetch consolidate analyze clean ping

# --- 1. ENVIRONMENT & PATH VARIABLES ---
# VENV_DIR: Isolated python environment for Ansible/EDA tools
VENV_DIR         = venv
PYTHON           = $(VENV_DIR)/bin/python3
PIP              = $(VENV_DIR)/bin/pip
ANSIBLE_BIN      = $(VENV_DIR)/bin/ansible
ANSIBLE_PLAYBOOK = $(VENV_DIR)/bin/ansible-playbook

# CONFIGURATION PATHS
# INVENTORY: Points to production grid definitions
INVENTORY  = infra/ansible/inventory/hosts.prod
# PLAYBOOK_SITE: The master site configuration (Full OS/Network Provisioning)
PLAYBOOK_SITE = infra/ansible/playbooks/site.yml
# PLAYBOOK_LOGGER: The targeted update for the Python Logger (Rapid Deploy)
PLAYBOOK_LOGGER = infra/ansible/playbooks/deploy_smart_logger.yml
# VAULT: Encrypted secrets file
VAULT_PASS = .vault_pass

# --- 2. DEFAULT TARGET (HELP) ---
help:
	@echo "----------------------------------------------------------------"
	@echo "📡 ADS-B Research Grid Automation (v0.4.6)"
	@echo "----------------------------------------------------------------"
	@echo "make setup         - 🔧 Initialize venv and install dependencies"
	@echo "make ping          - 📶 Check connectivity to sensors"
	@echo "make deploy        - 🏗️  FULL Provisioning (OS, Network, Services)"
	@echo "make deploy-logger - 🚀 FAST Update: Deploys only Smart Logger (v1.4)"
	@echo "make check         - 🏥 Run Health Checks & Log Storage Metrics"
	@echo "make fetch         - 📥 Synchronize remote logs for local analysis"
	@echo "make consolidate   - 🧹 Merge fragmented log files into Master CSVs"
	@echo "make analyze       - 📊 Run Exploratory Data Analysis (EDA) on Masters"
	@echo "make clean         - 🧹 Deep clean (removes venv and temp artifacts)"
	@echo "----------------------------------------------------------------"

# --- 3. INITIALIZATION ---
setup:
	@echo "[INIT] Creating isolated Python virtual environment..."
	python3 -m venv $(VENV_DIR)
	@echo "[INIT] Installing requirements (Ansible, Pandas, Scipy)..."
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "[SUCCESS] Environment ready. Activate via: source $(VENV_DIR)/bin/activate"

# --- 4. DEPLOYMENT OPERATIONS (DevOps) ---

# Target: deploy (The "Big Hammer")
# Use this when provisioning a NEW node or changing OS-level configs (Network, NTP, etc.)
deploy:
	@echo "[DEPLOY] Applying Full Site Configuration (v0.4.6)..."
	@echo "[INFO]   Targeting: $(INVENTORY)"
	$(ANSIBLE_PLAYBOOK) -i $(INVENTORY) $(PLAYBOOK_SITE) --vault-password-file $(VAULT_PASS)

# Target: deploy-logger (The "Scalpel")
# Use this to quickly push updates to smart_adsb_logger.py and restart the service.
deploy-logger:
	@echo "[DEPLOY] Updating Smart Logger Code & Service Only..."
	$(ANSIBLE_PLAYBOOK) -i $(INVENTORY) $(PLAYBOOK_LOGGER) --vault-password-file $(VAULT_PASS)

ping:
	@echo "[NET]    Pinging sensor nodes to verify reachability..."
	$(ANSIBLE_BIN) -i $(INVENTORY) sensors -m ping --vault-password-file $(VAULT_PASS)

# --- 5. DATA OPERATIONS (Data Science) ---
check:
	@echo "[OPS]    Snapshotting System Health & Storage Metrics..."
	$(ANSIBLE_PLAYBOOK) -i $(INVENTORY) infra/ansible/playbooks/health.yml --vault-password-file $(VAULT_PASS)

fetch:
	@echo "[DATA]   Ingesting logs from remote sensors to local repository..."
	$(ANSIBLE_PLAYBOOK) -i $(INVENTORY) infra/ansible/playbooks/fetch.yml --vault-password-file $(VAULT_PASS)
	@echo "[DATA]   Updating storage growth projections..."
	# $(PYTHON) scripts/analyze_storage.py  <-- Uncomment when script is ready

# --- 6. SCIENTIFIC ANALYSIS ---
consolidate:
	@echo "[DATA]   Merging fragmented CSV logs into Daily Master Datasets..."
	$(PYTHON) scripts/consolidate_data.py

# analyze: consolidate
#	@echo "[SCIENCE] Executing Exploratory Data Analysis (Quick-Look)..."
#	@echo "[INFO]    Analyzing Signal Strength (RSSI) and GNSS Hardware Health."
#	$(PYTHON) scripts/eda_quicklook.py

analyze: consolidate
	@echo "[SCIENCE] Generatiing 2-Page Academic PDF Reports..."
	@echo "[INFO]    Plots: RSSI, Traffic Rate, Altitudes, GNSS Drift, Thermals."
	$(PYTHON) scripts/eda_academic_report.py

# --- 7. MAINTENANCE ---
clean:
	@echo "[CLEAN] Removing virtual environment and pycache..."
	rm -rf $(VENV_DIR)
	find . -type d -name "__pycache__" -exec rm -rf {} +
	@echo "[CLEAN] Repository sanitized."
