# Reproducibility Notes

This public repository preserves the computational pipeline. Full reproduction requires local data and intermediate artifacts that cannot be redistributed through GitHub.

## Reproduction Levels

### 1. Raw Data Preparation

Requires local access to a compatible Reddit dataset or archive.

```bash
python src/prepare_covidvaccine_dataset.py --help
python src/pushshift_filter.py --help
```

Raw comments and submissions are not redistributed through this repository.

### 2. Human Annotation and Relation Modeling

Requires local annotation files, candidate pairs, and model resources.

The relation-model inputs use `manual_pair_label`, `manual_pair_relation_type`,
and `manual_pair_target_specificity` for the adjudicated human coding fields.

```bash
python src/combine_pair_annotations.py --help
python src/train_pair_relation_classifier.py --help
python src/evaluate_pair_relation_classifier.py --help
python src/predict_pair_relation_candidates.py --help
python src/predict_pair_relation_type_candidates.py --help
```

Transformer-based scripts require PyTorch and Hugging Face Transformers. Model checkpoints are not committed.

### 3. Statistical Analysis

Requires local prepared comments and prediction files.

```bash
python src/fit_revised_corrective_response_models.py --help
python src/fit_focused_access_discourse_model.py --help
python src/run_focused_supplementary_sensitivity.py --help
```

Expected outputs are written under `outputs/`, which is ignored by Git.

### 4. Validation, Simulation, and Figures

Requires derived local output tables under `outputs/`.

```bash
python src/validate_corrective_response_classifier.py --help
python src/simulate_network_application.py --help
python src/build_revised_manuscript_artifacts.py --help
python src/build_unified_response_figures.py --help
```

Generated tables and figures are local-only. Unpublished manuscript files and internal run notes are intentionally excluded from Git.
