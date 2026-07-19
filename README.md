# Misinformation Correction Heterogeneity

This repository contains the computational pipeline for studying corrective responses in online discussions. It includes data-preparation utilities, human annotation integration, relation-aware text classification, statistical analysis, robustness checks, simulation, and scientific-figure generation.

The unpublished manuscript, submission files, internal research notes, and machine-specific workflow files are intentionally excluded from the public repository.

## Data Access Status

Reddit for Researchers API access was not approved. The rejection was received on July 4, 2026. The project does not assume live Reddit API access.

Repository policy:

- raw Reddit content is not committed;
- local raw, interim, processed, and output files are ignored by Git;
- browser-cookie scraping is not used as a default route;
- scripts that require Reddit OAuth are retained only as optional utilities for users with their own valid access;
- derived datasets, predictions, fitted models, and generated figures remain local unless separately reviewed for release.

See [`docs/data_access.md`](docs/data_access.md) and [`docs/datasets.md`](docs/datasets.md) for the current data-access boundary.

## Repository Layout

```text
.
├── config/                 # query and pilot configuration files
├── data/                   # local-only raw/interim/processed data; ignored except .gitkeep
├── docs/                   # public data-access and reproducibility notes
├── outputs/                # local-only experiment outputs; ignored by Git
├── src/                    # preparation, annotation, modeling, validation, and figure scripts
└── templates/              # reusable template assets
```

## Reproducibility Boundary

This repository publishes code without redistributing raw platform data or unpublished research materials. Reproduction therefore depends on access to compatible source data and local intermediate files.

The most important local-only assets are:

- Reddit raw and interim comment/submission files under `data/`;
- annotation samples and model predictions under `outputs/`;
- model checkpoints and large training artifacts, if generated;
- local credentials in `.env`.

The scripts remain available so that researchers with valid data access can reconstruct the computational pipeline. See [`docs/reproducibility.md`](docs/reproducibility.md) for the run map.

## Main Pipeline Components

Data preparation:

```bash
python src/prepare_covidvaccine_dataset.py
```

Human annotation integration and relation-aware pair modeling:

```bash
python src/combine_pair_annotations.py --help
python src/train_pair_relation_classifier.py --help
python src/evaluate_pair_relation_classifier.py --help
python src/predict_pair_relation_candidates.py --help
```

Statistical analysis and validation:

```bash
python src/fit_revised_corrective_response_models.py --help
python src/validate_corrective_response_classifier.py --help
python src/run_focused_supplementary_sensitivity.py --help
```

Simulation and figure generation:

```bash
python src/simulate_network_application.py --help
python src/build_revised_manuscript_artifacts.py --help
python src/build_unified_response_figures.py --help
```

## GitHub Preparation

Before publishing the repository, run the checklist in [`docs/repository_publication_checklist.md`](docs/repository_publication_checklist.md).

At minimum, verify that:

- `data/`, `outputs/`, and `logs/` contain no tracked files except `.gitkeep`;
- `.env` and API credentials are absent from Git;
- raw Reddit text is not included in committed files;
- unpublished manuscript and internal research materials are not tracked;
- committed source files contain no credentials or machine-specific absolute paths.
