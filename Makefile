.PHONY: setup deploy download clean analyze

# --- Configuration ---
SENSOR_HOST = pi@sensor-north
DATA_DIR = data/raw

# --- Infrastructure ---
setup: ## Install Python dependencies
	pip install -r requirements.txt

deploy: ## Deploy the latest Ansible configuration to sensors
	ansible-playbook infra/ansible/playbooks/site.yml

# --- Data Management ---
download: ## Fetch the latest binary data from Sensor North
	@echo "Fetching latest data from $(SENSOR_HOST)..."
	mkdir -p $(DATA_DIR)
	scp "$(SENSOR_HOST):/home/pi/adsb_data/*.bin" $(DATA_DIR)/

clean-sensor: ## Delete 0-byte empty files on the sensor
	ssh $(SENSOR_HOST) "find ~/adsb_data -type f -size 0 -delete"

# --- Analysis ---
analyze: ## Run the EDA check script
	python3 scripts/eda_check.py
