# ==============================================================================
# PROJECT: ADS-B Spoofing Data Collection (Academic Research)
# FILE:    Makefile
# VERSION: 3.5.0 (v0.5.0 Release - Split Workflows)
# DATE:    2026-01-12
# ==============================================================================

.PHONY: help setup check fetch report ml clean

# --- 1. ENVIRONMENT ---
VENV_DIR         = venv
PYTHON           = $(VENV_DIR)/bin/python3
ANSIBLE_PLAYBOOK = $(VENV_DIR)/bin/ansible-playbook
INVENTORY        = infra/ansible/inventory/hosts.prod
VAULT_PASS       = .vault_pass

# --- 2. HELP ---
help:
	@echo "📡 ADS-B Research Grid (v0.5.0 Release)"
	@echo "--------------------------------------------------------"
	@echo "make fetch    - 📥 Download latest logs from sensors"
	@echo "make report   - 📊 Generate Forensic Showcase (Docs)"
	@echo "make ml       - 🧪 Run Anomaly Detection Pipeline (AI)"
	@echo "make check    - 🏥 Real-time Sensor Health Dashboard"
	@echo "make clean    - 🧹 Cleanup temp files"

# --- 3. DATA PIPELINES ---
fetch:
	@echo "[DATA] 📥 Syncing logs from grid..."
	$(ANSIBLE_PLAYBOOK) -i $(INVENTORY) infra/ansible/playbooks/fetch.yml --vault-password-file $(VAULT_PASS)
	@$(PYTHON) scripts/merge_storage_logs.py

report:
	@echo "[DOCS] 📊 Generating Academic Showcase (v4)..."
	$(PYTHON) scripts/academic_eda.py

ml:
	@echo "[ML]   🧪 Training Isolation Forest (v3)..."
	$(PYTHON) scripts/ds_pipeline_master.py

check:
	@echo "[OPS]  🏥 Probing Signal Health..."
	@$(PYTHON) scripts/check_signal_health.py

clean:
	rm -rf output/plots/eda_v3 research_data/ml_ready/dataset_validation_report.txt
