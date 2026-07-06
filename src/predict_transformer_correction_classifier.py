#!/usr/bin/env python3
"""Apply a fine-tuned transformer correction classifier to the full comment set."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from train_transformer_correction_classifier import (
    TransformerPredictionWrapper,
    load_full_comments_with_context,
    write_prediction_outputs,
)
from train_correction_classifier import write_json


def run(args: argparse.Namespace) -> None:
    start = time.time()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for directory in ["metrics", "tables", "predictions"]:
        (args.output_dir / directory).mkdir(exist_ok=True)

    device = torch.device(args.device if args.device else ("cuda" if torch.cuda.is_available() else "cpu"))
    use_amp = bool(args.fp16 and device.type == "cuda")
    tokenizer = AutoTokenizer.from_pretrained(args.checkpoint_dir)
    model = AutoModelForSequenceClassification.from_pretrained(args.checkpoint_dir)
    model.to(device)

    full_comments = load_full_comments_with_context(args.full_comments, args.feature_mode)
    wrapper = TransformerPredictionWrapper(
        model=model,
        tokenizer=tokenizer,
        device=device,
        max_length=args.max_length,
        batch_size=args.predict_batch_size,
        num_workers=args.num_workers,
        use_amp=use_amp,
    )
    prediction_summary = write_prediction_outputs(args.output_dir, full_comments, wrapper, args.threshold)

    summary = {
        "run_status": "transformer_correction_classifier_prediction_only",
        "checkpoint_dir": str(args.checkpoint_dir),
        "full_comments": str(args.full_comments),
        "output_dir": str(args.output_dir),
        "feature_mode": args.feature_mode,
        "threshold": args.threshold,
        "max_length": args.max_length,
        "predict_batch_size": args.predict_batch_size,
        "device": str(device),
        "fp16": use_amp,
        **prediction_summary,
        "started_utc": datetime.fromtimestamp(start, timezone.utc).isoformat(),
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": time.time() - start,
    }
    write_json(args.output_dir / "metrics" / "run_summary.json", summary)
    (args.output_dir / "run.log").write_text(
        "\n".join(
            [
                "transformer correction classifier prediction-only run",
                f"generated_utc={summary['finished_utc']}",
                f"command={' '.join(sys.argv)}",
                f"checkpoint_dir={args.checkpoint_dir}",
                f"threshold={args.threshold}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply a trained transformer correction classifier.")
    parser.add_argument("--checkpoint-dir", type=Path, required=True)
    parser.add_argument("--full-comments", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--feature-mode",
        choices=["text_only", "text_candidate", "metadata_full", "text_parent", "text_parent_candidate"],
        default="text_only",
    )
    parser.add_argument("--threshold", type=float, required=True)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--predict-batch-size", type=int, default=96)
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--device", default="")
    parser.add_argument("--fp16", action="store_true")
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
