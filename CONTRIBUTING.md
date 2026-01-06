# How to Contribute to the ADS-B Research Grid

Welcome! We follow a strict DevOps workflow to ensure scientific integrity across Apple Silicon, Intel, and Windows architectures.

## 1. The Golden Rule
**Main is protected.** Never push directly to main. Always use a feature branch.

## 2. Workflow
1.  **Sync:** `git checkout main && git pull origin main`
2.  **Branch:** `git checkout -b feature/description`
3.  **Test:** Run `make analyze` before every commit.
    - *Must pass on your local machine (Mac or WSL).*
4.  **Commit:** Use [Conventional Commits](https://www.conventionalcommits.org/) (e.g., `feat:`, `fix:`, `docs:`).
5.  **Merge:** Open a Pull Request (PR).

## 3. Environment Setup
- Run `make setup` to initialize the Python environment.
- Data is not stored in the repo. You must fetch `.bin` files from the sensor or `sensor-north`.
