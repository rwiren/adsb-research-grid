# ADS-B Research Grid - Control Plane
# v0.3.0

.PHONY: help deploy analyze clean sync

# ---------------------------------------------------------
# 🆘 Help
# ---------------------------------------------------------
help:
	@echo "📡 ADS-B Grid Commands:"
	@echo "  make deploy   - Update the sensor nodes (Ansible)"
	@echo "  make sync     - Fetch new data from sensor-north"
	@echo "  make analyze  - Run the Scientific Audit (v5 Master)"
	@echo "  make clean    - Remove old analysis artifacts"

# ---------------------------------------------------------
# 🚀 Deployment (Ansible)
# ---------------------------------------------------------
deploy:
	ansible-playbook infra/ansible/playbooks/site.yml -i infra/ansible/inventory/hosts.prod

# ---------------------------------------------------------
# 📥 Data Sync (Fetch from Pi)
# ---------------------------------------------------------
# Uses scp to grab all bin files. 
# Note: "quotes" around the remote path prevent local wildcard expansion errors.
sync:
	@echo "[INFO] Syncing data from Sensor North..."
	scp -C "pi@sensor-north:~/adsb_data/*.bin" data/raw/

# ---------------------------------------------------------
# 📊 Analysis (Master Edition)
# ---------------------------------------------------------
# Runs the new scripts/eda_check.py with the correct directory argument
analyze:
	@echo "[INFO] Running Scientific Audit..."
	python3 scripts/eda_check.py --dir data/raw --lat 60.319555 --lon 24.830816

# ---------------------------------------------------------
# 🧹 Housekeeping
# ---------------------------------------------------------
clean:
	@echo "[INFO] Cleaning analysis output..."
	rm -rf analysis/latest/*
	@echo "[SUCCESS] Analysis folder clean."
