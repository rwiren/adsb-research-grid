# 📝 Project Changelog

## [0.2.3] - 2026-01-06
### Added
- **License:** Officially added MIT License file.
- **Dependencies:** Froze exact versions in `requirements.txt` (numpy, pyModeS, etc.).
- **Documentation:** Finalized README with "Research Workflow" and citation data.

### Security
- **Git:** Added strict ignore rules for `.vault_pass` and raw data binaries.


## [0.2.2] - 2026-01-06
### Fixed
- **Sensor Node Networking:** Resolved critical issue where `readsb` container ports were closed.
- **Configuration:** Forced `--net` flags using `READSB_EXTRA_ARGS` to bypass container variable parsing issues.
- **Data Recording:** Verified recording of binary data (non-zero byte files confirmed).

### Added
- **Repository Structure:** Added `requirements.txt`, `Makefile`, and `CITATION.cff`.
- **Analysis Tools:** Added `scripts/eda_check.py` for parsing Beast Binary files and generating health-check plots.
- **License:** Added MIT License.

## [v0.2.0] - 2026-01-05 (Infrastructure Baseline)
### 🚀 Added
* **Ansible Roles:**
    * `common`: OS hardening, UFW firewall, Fail2Ban, essential tools.
    * `zerotier`: Automated VPN mesh joining and ID reporting.
    * `sensor_node`: Docker Engine, Compose Plugin, and user permission management.
* **Network Topology:** Established "Century Schema" (VPN IPs .100-.130) for grid independence.
* **Security:** Implemented Vault encryption for secrets and SSH key-based authentication.

## [v0.1.0] - 2026-01-05 (Research Definition)
### 📄 Added
* Initial README with 12-Model Architecture.
* Project directory structure.
* Research goals and licensing.
