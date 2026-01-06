# ==============================================================================
# 🛠️ ADS-B Research Grid - Controller Makefile
# Version: v0.3.1
# Date: 2026-01-06
#
# This file automates environment setup, deployment, and data analysis.
# ==============================================================================

.PHONY: help setup deploy analyze clean

# --- Global Variables ---
VENV_DIR = venv
PYTHON = $(VENV_DIR)/bin/python3
PIP = $(VENV_DIR)/bin/pip
ANSIBLE_PLAYBOOK = $(VENV_DIR)/bin/ansible-playbook
INVENTORY = infra/ansible/inventory/hosts.prod
PLAYBOOK = infra/ansible/playbooks/site.yml

# --- Default Target ---
help:
	@echo "----------------------------------------------------------------"
	@echo "📡 ADS-B Research Grid Automation"
	@echo "----------------------------------------------------------------"
	@echo "make setup    - Create Python venv and install dependencies"
	@echo "make deploy   - Run Ansible to provision/update the grid"
	@echo "make analyze  - Run the EDA script (Data Quality Check)"
	@echo "make clean    - Remove virtual environment and temp files"
	@echo "----------------------------------------------------------------"

# --- 1. Environment Setup ---
setup:
	@echo "🔧 Creating Python virtual environment..."
	python3 -m venv $(VENV_DIR)
	@echo "📦 Installing requirements..."
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "✅ Setup complete. To activate: source $(VENV_DIR)/bin/activate"

# --- 2. Deployment (Ansible) ---
deploy:
	@echo "🚀 Deploying configuration to the grid..."
	$(ANSIBLE_PLAYBOOK) -i $(INVENTORY) $(PLAYBOOK) --vault-password-file .vault_pass

# --- 3. Analysis (Python) ---
analyze:
	@echo "📊 Running Exploratory Data Analysis (EDA)..."
	$(PYTHON) scripts/eda_check.py

# --- 4. Maintenance ---
clean:
	@echo "🧹 Cleaning up..."
	rm -rf $(VENV_DIR)
	find . -type d -name "__pycache__" -exec rm -rf {} +
	@echo "✨ Clean complete."
