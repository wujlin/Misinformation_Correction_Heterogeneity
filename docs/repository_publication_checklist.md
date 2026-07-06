# Repository Publication Checklist

Use this checklist before pushing the project to GitHub.

## Data and Credentials

- [ ] `git status --short --ignored` shows raw data and outputs as ignored, not tracked.
- [ ] No files under `data/raw/`, `data/interim/`, or `data/processed/` are tracked except `.gitkeep`.
- [ ] No files under `outputs/` are tracked.
- [ ] No files under `logs/` are tracked except `.gitkeep`.
- [ ] `.env` is not tracked.
- [ ] Reddit credentials, browser cookies, access tokens, SSH keys, and API keys are absent.
- [ ] Raw Reddit comment or submission text is absent from committed files.

## Documentation

- [ ] `README.md` states that Reddit for Researchers API access was not approved.
- [ ] `docs/data_access.md` and `docs/datasets.md` match the README data-access status.
- [ ] `docs/reproducibility.md` distinguishes manuscript assembly from raw-data reproduction.
- [ ] Progress logs are under `docs/progress/`, not in the repository root.

## Manuscript Assets

- [ ] `manuscript/jcmc_latex_draft/main.tex` exists.
- [ ] `manuscript/jcmc_latex_draft/references.bib` exists.
- [ ] `manuscript/jcmc_latex_draft/figures/` contains the manuscript figure PDFs.
- [ ] Local TeX build artifacts such as `.aux`, `.log`, `.out`, `.bbl`, `.blg`, and `.synctex.gz` are not tracked.

## Code and Environment

- [ ] `requirements.txt` is present and describes the main Python dependencies.
- [ ] Scripts expose `--help` where practical.
- [ ] No script assumes machine-specific absolute paths by default.
- [ ] WSA-specific notes remain in `docs/internal/wsa_qwen_annotation.md` and do not appear as required public setup.

## Final Scan Commands

Run from the repository root:

```bash
git status --short --ignored
rg -n "cookie|authorization|bearer|client_secret|password|api_key|BEGIN .*PRIVATE|ghp_|sk-[A-Za-z0-9]" . -g '!data/**' -g '!outputs/**' -g '!logs/**' -g '!**/__pycache__/**'
rg -n "/mnt/|/home/jinlin|/home/wujlin|E:\\\\|C:\\\\|D:\\\\" . -g '!data/**' -g '!outputs/**' -g '!logs/**' -g '!**/__pycache__/**'
```
