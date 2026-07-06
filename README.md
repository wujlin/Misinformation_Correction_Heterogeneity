# Misinformation Correction and Network Heterogeneity

This repository contains code, documentation, manuscript drafts, and lightweight figure assets for a computational communication project on public misinformation correction in Reddit discussions.

## Research Question

The project asks when public correction becomes visible in online discussion threads. The current manuscript focuses on a supply-side account of misinformation correction:

> Users may occupy positions that provide correction capacity, but local thread conditions determine whether that capacity becomes public correction.

The empirical setting is Reddit discussion about COVID-19 vaccination. The current analysis uses relation-aware correction detection, observational network analysis, and an empirically calibrated agent-based model.

## Current Manuscript Claim

The current manuscript develops three linked components:

- a supply-side account of public misinformation correction;
- a relation-aware measurement strategy that treats correction as a claim-response relation;
- a capacity-activation framework that links user position and local thread conditions to system-level correction supply.

The manuscript drafts and JCMC LaTeX assembly files are in [`manuscript/`](manuscript/).

## Data Access Status

Reddit for Researchers API access was not approved. The rejection was received on July 4, 2026. The project therefore does not assume live Reddit API access.

Current repository policy:

- raw Reddit content is not committed;
- local raw, interim, processed, and output files are ignored by Git;
- browser-cookie scraping is not used as a default route;
- scripts that require Reddit OAuth are retained only as optional utilities for users with their own valid access;
- manuscript-facing results are documented through derived summaries, figures, and source scripts.

See [`docs/data_access.md`](docs/data_access.md) and [`docs/datasets.md`](docs/datasets.md) for the current data-access boundary.

## Repository Layout

```text
.
├── config/                 # query and pilot configuration files
├── data/                   # local-only raw/interim/processed data; ignored except .gitkeep
├── docs/                   # data notes, design notes, progress logs, reproducibility notes
├── manuscript/             # manuscript drafts, references, JCMC LaTeX shell, figure assets
├── outputs/                # local-only experiment outputs; ignored by Git
├── src/                    # data preparation, annotation, modeling, simulation, and figure scripts
└── templates/              # journal template assets
```

Progress notes from the empirical pipeline are archived in [`docs/progress/`](docs/progress/). These notes preserve the project history but are not the main reader entry point.

Early research design materials are archived in [`docs/design/`](docs/design/). Machine-specific run notes are isolated in [`docs/internal/`](docs/internal/).

## Reproducibility Boundary

This repository is organized for manuscript transparency, not raw-data redistribution. Public replication depends on the data source available to the reader.

The most important local-only assets are:

- Reddit raw and interim comment/submission files under `data/`;
- annotation samples and model predictions under `outputs/`;
- model checkpoints and large training artifacts, if generated;
- local credentials in `.env`.

The scripts remain available so that users with valid data access can reproduce the pipeline. See [`docs/reproducibility.md`](docs/reproducibility.md) for the current run map.

## Main Pipeline Components

Data preparation:

```bash
python src/prepare_covidvaccine_dataset.py
```

Correction detection and relation-aware pair modeling:

```bash
python src/train_pair_relation_classifier.py --help
python src/evaluate_pair_relation_classifier.py --help
python src/predict_pair_relation_candidates.py --help
```

Mechanism analysis:

```bash
python src/fit_thread_climate_models.py --help
python src/fit_thread_climate_score_models.py --help
python src/simulate_correction_abm.py --help
```

Manuscript assembly:

```bash
python src/assemble_manuscript_markdown.py
python src/assemble_jcmc_latex.py
```

## GitHub Preparation

Before publishing the repository, run the checklist in [`docs/repository_publication_checklist.md`](docs/repository_publication_checklist.md).

At minimum, verify that:

- `data/`, `outputs/`, and `logs/` contain no tracked files except `.gitkeep`;
- `.env` and API credentials are absent from Git;
- raw Reddit text is not included in committed files;
- README, data-access notes, and manuscript claims use the same data-access status;
- the final manuscript figures are present in `manuscript/jcmc_latex_draft/figures/`.
