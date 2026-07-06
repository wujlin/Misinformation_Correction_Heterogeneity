# Reproducibility Notes

This repository preserves the code and manuscript-facing structure for the project. Full computational reproduction requires local data that cannot be redistributed through GitHub.

## Current Reproduction Levels

### Level 1: Manuscript Assembly

Available from the repository:

```bash
python src/assemble_manuscript_markdown.py
python src/assemble_jcmc_latex.py
```

Expected outputs:

- `manuscript/11_full_manuscript_draft.md`
- `manuscript/jcmc_latex_draft/main.tex`
- copied figure PDFs in `manuscript/jcmc_latex_draft/figures/`

This level does not require raw Reddit data.

### Level 2: Figure Regeneration

Figure regeneration requires derived local output tables under `outputs/`.

Main scripts:

```bash
python src/visualize_validation_mechanism_figures.py --help
python src/visualize_abm_manuscript_figures.py --help
```

The manuscript-facing figure PDFs are committed under `manuscript/jcmc_latex_draft/figures/`, but the full output directories are local-only.

### Level 3: Mechanism Model Rerun

Mechanism model reruns require local derived comment and prediction files.

Main scripts:

```bash
python src/fit_thread_climate_models.py --help
python src/fit_thread_climate_score_models.py --help
python src/simulate_correction_abm.py --help
```

Expected outputs are written under `outputs/`, which is ignored by Git.

### Level 4: Detector Training and Prediction

Detector training requires annotation files, candidate pairs, and local model resources.

Main scripts:

```bash
python src/train_pair_relation_classifier.py --help
python src/evaluate_pair_relation_classifier.py --help
python src/predict_pair_relation_candidates.py --help
python src/predict_pair_relation_type_candidates.py --help
```

Transformer-based scripts require PyTorch and Hugging Face Transformers. Large model checkpoints are not committed.

### Level 5: Raw Data Preparation

Raw data preparation requires local access to the underlying Reddit dataset or archive files.

Main scripts:

```bash
python src/prepare_covidvaccine_dataset.py --help
python src/pushshift_filter.py --help
```

Raw comments and submissions are not redistributed through the repository.

## Current Manuscript Runs

The current manuscript figures correspond to the latest figure sets copied into `manuscript/jcmc_latex_draft/figures/`.

The most relevant local run summaries are documented in:

- `docs/progress/36_Audit3_Full_Pair_Ensemble_and_Mechanism_Rerun.md`
- `docs/progress/37_ABM_Empirical_Calibration_and_Simulation.md`
- `docs/progress/38_Visualization_Audit_and_ABM_Manuscript_Figures.md`
- `docs/progress/39_Validation_and_Mechanism_Manuscript_Figures.md`

These notes preserve the run history, but the full output directories remain local-only.
