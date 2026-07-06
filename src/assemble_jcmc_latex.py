#!/usr/bin/env python3
"""Assemble a local JCMC/OUP LaTeX draft from manuscript section files."""

from __future__ import annotations

import re
import shutil
from pathlib import Path


TITLE = "From Correction Capacity to Correction Activation: Network Heterogeneity and Public Misinformation Correction on Reddit"
SHORT_TITLE = "Correction Capacity and Activation"
KEYWORDS = [
    "misinformation correction",
    "public correction",
    "network heterogeneity",
    "Reddit",
    "agent-based modeling",
]

SECTION_FILES = [
    ("Introduction", "03_introduction_draft.md"),
    ("Theory", "07_theory_draft.md"),
    ("Data and Methods", "04_methods_draft.md"),
    ("Results", "05_results_draft.md"),
    ("Discussion", "08_discussion_draft.md"),
]

MAIN_FIGURES = {
    "fig1_detector_validation_and_coverage": {
        "source": "outputs/manuscript_validation_mechanism_figures_20260701T093000Z/figures/fig1_detector_validation_and_coverage.pdf",
        "latex_name": "fig1-detector-validation",
        "caption": (
            "Detector evaluation and full-corpus coverage. Panel A presents average precision, ROC-AUC, "
            "and threshold F1 for the relation-aware public correction detector. Panel B presents the full "
            "comment corpus, candidate claim-response pairs, predicted public correction comments, and "
            "earlier comment-level correction labels."
        ),
        "label": "fig:detector-validation",
        "anchor": "Full-corpus coverage indicates why relation-aware measurement matters for downstream analysis.",
    },
    "fig2_observational_mechanism_results": {
        "source": "outputs/manuscript_validation_mechanism_figures_20260701T093000Z/figures/fig2_observational_mechanism_results.pdf",
        "latex_name": "fig2-observational-mechanism",
        "caption": (
            "Observational evidence for correction capacity and layered heterogeneity. Panel A presents "
            "focal odds ratios from the main heterogeneity logit model. Values above 1 indicate a higher "
            "probability of later public correction. Horizontal lines show 95% confidence intervals. "
            "Blue markers indicate p < 0.05. Panel B presents model-predicted correction probabilities by "
            "cross-group position and early audience structural heterogeneity. Panel C presents the same "
            "scenario comparison using the score-based correction outcome."
        ),
        "label": "fig:observational-mechanism",
        "anchor": "Cross-group users have a higher estimated probability of later public correction.",
    },
    "fig3_abm_correction_activation_condition_map": {
        "source": "outputs/manuscript_abm_figures_20260701T083000Z/figures/fig3_abm_correction_activation_condition_map.pdf",
        "latex_name": "fig3-abm-condition-map",
        "caption": (
            "Correction activation under early correction norm and hostile thread climate. The heatmap "
            "shows simulated correction rates across four local thread contexts. Each cell reports "
            "the simulated correction rate, activated-thread count, and activated-thread change from the "
            "observed baseline."
        ),
        "label": "fig:abm-condition-map",
        "anchor": "Early correction norm and hostile thread climate jointly shape correction activation in the condition map.",
    },
    "fig4_abm_counterfactual_activation_shift": {
        "source": "outputs/manuscript_abm_figures_20260701T083000Z/figures/fig4_abm_counterfactual_activation_shift.pdf",
        "latex_name": "fig4-abm-counterfactual-shift",
        "caption": (
            "Scenario shifts in correction supply relative to the observed baseline. Panel A presents "
            "simulated correction-rate changes in percentage points. Panel B presents changes in activated "
            "threads. Blue bars indicate increases relative to the observed baseline, and red bars indicate "
            "decreases."
        ),
        "label": "fig:abm-counterfactual-shift",
        "anchor": "The broader scenario comparison separates correction-rate change from activated-thread change.",
    },
}

CITATION_REPLACEMENTS = {
    "(e.g., Lewandowsky et al., 2012; Chan et al., 2017; Walter and Murphy, 2018; Ecker et al., 2022)": (
        r"\citep[e.g.,][]{lewandowsky2012misinformation,chan2017debunking,walter2018unring,ecker2022psychological}"
    ),
    "(Lewandowsky et al., 2012; Chan et al., 2017; Walter and Murphy, 2018; Ecker et al., 2022)": (
        r"\citep{lewandowsky2012misinformation,chan2017debunking,walter2018unring,ecker2022psychological}"
    ),
    "(Bode and Vraga, 2015; Vraga and Bode, 2017)": r"\citep{bode2015related,vraga2017expert}",
    "(Mutz, 2002, 2006)": r"\citep{mutz2002crosscutting,mutz2006hearing}",
    "(Noelle-Neumann, 1974; Marwick and boyd, 2011; Hampton et al., 2014)": (
        r"\citep{noelleneumann1974spiral,marwick2011tweet,hampton2014spiral}"
    ),
    "(Epstein, 1999, 2006)": r"\citep{epstein1999agentbased,epstein2006generative}",
}

TEXTTT_REPLACEMENTS = [
    "user_cross_group_observed",
    "high_early_audience_structural_heterogeneity",
    "early_correction_norm_presence",
    "high_thread_hostility_climate",
]


def latex_escape(text: str) -> str:
    placeholders: dict[str, str] = {}

    def stash(pattern: str, value: str) -> str:
        key = f"@@PLACEHOLDER{len(placeholders)}@@"
        placeholders[key] = value
        return key

    for old, new in CITATION_REPLACEMENTS.items():
        text = text.replace(old, stash(old, new))

    for token in TEXTTT_REPLACEMENTS:
        text = text.replace(f"`{token}`", stash(token, rf"\texttt{{{token.replace('_', r'\_')}}}"))

    text = text.replace("<", stash("lt", r"\textless{}"))
    text = text.replace(">", stash("gt", r"\textgreater{}"))

    replacements = [
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)

    for key, value in placeholders.items():
        text = text.replace(key, value)

    return text


def read_abstract(manuscript_dir: Path) -> str:
    text = (manuscript_dir / "02_abstract_draft.md").read_text(encoding="utf-8").strip()
    text = re.sub(r"^# .+?\n+", "", text).strip()
    return latex_escape(text)


def markdown_to_latex(text: str, section_name: str) -> str:
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]

    output: list[str] = []
    in_code = False
    code_lines: list[str] = []

    for line in lines:
        if line.startswith("```"):
            if in_code:
                output.append(r"\begin{verbatim}")
                output.extend(code_lines)
                output.append(r"\end{verbatim}")
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue

        if in_code:
            code_lines.append(line)
            continue

        if line.startswith("## "):
            output.append(rf"\subsection{{{latex_escape(line[3:].strip())}}}")
            output.append("")
            continue

        if line.strip() == "":
            output.append("")
            continue

        paragraph = line
        if section_name == "Results":
            for figure_name, spec in MAIN_FIGURES.items():
                if paragraph.startswith(spec["anchor"]):
                    output.append(make_figure_environment(spec["latex_name"], spec["caption"], spec["label"]))
                    output.append("")
                    break
        output.append(latex_escape(paragraph))

    return "\n".join(output).strip()


def make_figure_environment(figure_name: str, caption: str, label: str) -> str:
    return "\n".join(
        [
            r"\begin{figure}[!t]",
            r"\centering",
            rf"\includegraphics[width=\linewidth]{{figures/{figure_name}.pdf}}",
            rf"\caption{{{latex_escape(caption)}}}",
            rf"\label{{{label}}}",
            r"\end{figure}",
        ]
    )


def copy_support_files(project_root: Path, output_dir: Path) -> None:
    template_dir = project_root / "templates" / "jcmc" / "starter"
    for name in ["oup-authoring-template.cls", "oup-abbrvnat.bst", "oup-plain.bst"]:
        shutil.copy2(template_dir / name, output_dir / name)
    shutil.copy2(project_root / "manuscript" / "references.bib", output_dir / "references.bib")

    figures_dir = output_dir / "figures"
    figures_dir.mkdir(exist_ok=True)
    for old_pdf in figures_dir.glob("*.pdf"):
        old_pdf.unlink()
    for figure_name, spec in MAIN_FIGURES.items():
        shutil.copy2(project_root / spec["source"], figures_dir / f"{spec['latex_name']}.pdf")


def build_latex(project_root: Path) -> str:
    manuscript_dir = project_root / "manuscript"
    abstract = read_abstract(manuscript_dir)
    sections = []
    for section_name, file_name in SECTION_FILES:
        text = (manuscript_dir / file_name).read_text(encoding="utf-8")
        body = markdown_to_latex(text, section_name)
        sections.append(rf"\section{{{section_name}}}" + "\n\n" + body)

    return "\n\n".join(
        [
            r"\documentclass[namedate,unnumsec,webpdf,contemporary,large]{oup-authoring-template}",
            r"\usepackage{graphicx}",
            r"\graphicspath{{figures/}}",
            "",
            r"\begin{document}",
            "",
            r"\journaltitle{Journal of Computer-Mediated Communication}",
            r"\DOI{}",
            r"\copyrightyear{}",
            r"\pubyear{}",
            r"\vol{}",
            r"\issue{}",
            r"\access{}",
            r"\appnotes{Original Article}",
            r"\firstpage{1}",
            "",
            rf"\title[{SHORT_TITLE}]{{{latex_escape(TITLE)}}}",
            "",
            "% Anonymous review version; author-identifying information is omitted.",
            "",
            r"\abstract{" + abstract + "}",
            "",
            r"\keywords{" + ", ".join(latex_escape(item) for item in KEYWORDS) + "}",
            "",
            r"\maketitle",
            "",
            "\n\n".join(sections),
            "",
            r"\section*{Data Availability}",
            (
                "The anonymized review package includes replication code and derived, non-raw analysis "
                "files for the reported tables and figures. Raw Reddit content is subject to platform "
                "data-sharing constraints and is not redistributed."
            ),
            "",
            r"\section*{Acknowledgments}",
            "Acknowledgments are omitted for anonymous review.",
            "",
            r"\section*{Funding}",
            "No funding was received for this work.",
            "",
            r"\section*{Conflict of Interest}",
            "The authors declare no conflict of interest.",
            "",
            r"\bibliographystyle{oup-abbrvnat}",
            r"\bibliography{references}",
            "",
            r"\end{document}",
            "",
        ]
    )


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    output_dir = project_root / "manuscript" / "jcmc_latex_draft"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "main.tex").write_text(build_latex(project_root), encoding="utf-8")
    copy_support_files(project_root, output_dir)


if __name__ == "__main__":
    main()
