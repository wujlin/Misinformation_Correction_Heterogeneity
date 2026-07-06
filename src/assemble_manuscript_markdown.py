#!/usr/bin/env python3
"""Assemble the current manuscript Markdown draft from section files."""

from __future__ import annotations

import re
from pathlib import Path


TITLE = "From Correction Capacity to Correction Activation: Network Heterogeneity and Public Misinformation Correction on Reddit"

SECTION_FILES = [
    ("Abstract", "02_abstract_draft.md"),
    ("Introduction", "03_introduction_draft.md"),
    ("Theory", "07_theory_draft.md"),
    ("Methods", "04_methods_draft.md"),
    ("Results", "05_results_draft.md"),
    ("Discussion", "08_discussion_draft.md"),
]

FIGURE_PLACEHOLDERS = {
    "Full-corpus coverage indicates why relation-aware measurement matters for downstream analysis.": "[Figure 1 about here]\n\nFull-corpus coverage indicates why relation-aware measurement matters for downstream analysis.",
    "Cross-group users have a higher estimated probability of later public correction.": "[Figure 2 about here]\n\nCross-group users have a higher estimated probability of later public correction.",
    "Early correction norm and hostile thread climate jointly shape correction activation in the condition map.": "[Figure 3 about here]\n\nEarly correction norm and hostile thread climate jointly shape correction activation in the condition map.",
    "The broader scenario comparison separates correction-rate change from activated-thread change.": "[Figure 4 about here]\n\nThe broader scenario comparison separates correction-rate change from activated-thread change.",
}


def read_section(path: Path, section_name: str) -> str:
    text = path.read_text(encoding="utf-8").strip()
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    text = "\n".join(lines).strip()
    if section_name == "Results":
        for source, target in FIGURE_PLACEHOLDERS.items():
            text = text.replace(source, target)
    return text.strip()


def normalize_headings(text: str, section_name: str) -> str:
    if section_name in {"Theory", "Methods", "Results", "Discussion"}:
        return re.sub(r"(?m)^## ", "### ", text)
    return text


def assemble(manuscript_dir: Path) -> str:
    parts = [f"# {TITLE}", ""]
    for section_name, file_name in SECTION_FILES:
        section_text = read_section(manuscript_dir / file_name, section_name)
        section_text = normalize_headings(section_text, section_name)
        parts.extend([f"## {section_name}", "", section_text, ""])
    parts.extend(
        [
            "## References",
            "",
            "References are generated from `references.bib` during LaTeX assembly.",
            "",
        ]
    )
    return "\n".join(parts).rstrip() + "\n"


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    manuscript_dir = project_root / "manuscript"
    output_path = manuscript_dir / "11_full_manuscript_draft.md"
    output_path.write_text(assemble(manuscript_dir), encoding="utf-8")


if __name__ == "__main__":
    main()
