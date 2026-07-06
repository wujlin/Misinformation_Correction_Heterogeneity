#!/usr/bin/env python3
"""Add parent-comment context to an annotation sample."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def norm(value: Any) -> str:
    return str(value or "").strip().lower()


def compact(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit] if len(text) > limit else text


def load_comment_lookup(path: Path, text_limit: int) -> dict[str, dict[str, str]]:
    lookup = {}
    for row in iter_jsonl(path):
        comment_id = norm(row.get("comment_id"))
        if comment_id:
            lookup[comment_id] = {
                "body": compact(row.get("body"), text_limit),
                "author": str(row.get("author") or ""),
                "parent_id": norm(row.get("parent_id")),
            }
    return lookup


def run(args: argparse.Namespace) -> None:
    rows = read_csv(args.input)
    comments = load_comment_lookup(args.comments, args.text_limit)

    for row in rows:
        parent_id = norm(row.get("parent_id"))
        parent = comments.get(parent_id, {})
        row["parent_body"] = parent.get("body", "")
        row["parent_author"] = parent.get("author", "")
        row["has_parent_body"] = int(bool(row["parent_body"]))

    fieldnames = list(rows[0].keys()) if rows else []
    for field in ["parent_body", "parent_author", "has_parent_body"]:
        if field not in fieldnames:
            fieldnames.append(field)
    write_csv(args.output, rows, fieldnames)
    print(
        json.dumps(
            {
                "input": str(args.input),
                "output": str(args.output),
                "rows": len(rows),
                "rows_with_parent_body": sum(1 for row in rows if row.get("parent_body")),
            },
            indent=2,
            sort_keys=True,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Add parent-comment context to an annotation CSV.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--comments", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--text-limit", type=int, default=5000)
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
