# WSA Qwen Annotation

This document records the planned WSA-side LLM-assisted annotation workflow. The output should be treated as model-assisted labels, not human ground truth.

## Input

Local input:

```text
outputs/pilot_covidvaccine_descriptive_20260624T151500Z/annotation/annotation_sample.csv
```

Rows: 360 comments.

## Remote Run Pattern

On WSA, use the `dpl` environment unless a project-specific environment is created.

First locate the Qwen model path on WSA:

```bash
find /home/jinlin /mnt/data_hdd -maxdepth 5 -type d \
  \( -iname '*qwen*' -o -iname '*Qwen*' \) 2>/dev/null | sort
```

Then run a small GPU and package check:

```bash
nvidia-smi -L
/home/jinlin/miniconda3/envs/dpl/bin/python - <<'PY'
import importlib.util
import torch
print(torch.__version__, torch.cuda.is_available(), torch.cuda.device_count())
print("transformers", bool(importlib.util.find_spec("transformers")))
print("accelerate", bool(importlib.util.find_spec("accelerate")))
PY
```

Expected command after syncing the project and locating the Qwen model path:

```bash
/home/jinlin/miniconda3/envs/dpl/bin/python src/llm_annotate_public_correction.py \
  --input outputs/pilot_covidvaccine_descriptive_20260624T151500Z/annotation/annotation_sample.csv \
  --output-dir outputs/llm_qwen_public_correction_annotation_20260624T000000Z \
  --model /path/to/qwen/model \
  --dtype bfloat16 \
  --device-map auto \
  --temperature 0 \
  --max-new-tokens 220
```

For a smoke test, run only the first 10 rows:

```bash
/home/jinlin/miniconda3/envs/dpl/bin/python src/llm_annotate_public_correction.py \
  --input outputs/pilot_covidvaccine_descriptive_20260624T151500Z/annotation/annotation_sample.csv \
  --output-dir outputs/llm_qwen_public_correction_smoke_20260624T000000Z \
  --model /path/to/qwen/model \
  --dtype bfloat16 \
  --device-map auto \
  --temperature 0 \
  --max-new-tokens 220 \
  --limit 10
```

## Output

Expected files:

- `llm_annotations.csv`
- `llm_raw_outputs.jsonl`
- `metrics/run_summary.json`

## Completed Pilot Run

Completed WSA run:

```text
outputs/llm_qwen_public_correction_annotation_gpu0_20260625T003500Z
```

Summary:

- rows: `360`
- model: `Qwen/Qwen3-8B`
- GPU: `GPU0` via `CUDA_VISIBLE_DEVICES=0`
- elapsed time: about `540` seconds
- labels: `91` public correction, `269` not public correction

GPU1 was occupied by another running job. Running with unrestricted `device_map=auto` was slow because the model could be placed on the busy GPU. Use `CUDA_VISIBLE_DEVICES=0` for future Qwen annotation runs unless GPU1 is free.

## Interpretation Boundary

The LLM labels are useful for fast screening and codebook refinement. They should not be described as human annotation. Before a paper-level classifier or final result is reported, a human-validated subset is still needed to estimate precision and disagreement patterns.
