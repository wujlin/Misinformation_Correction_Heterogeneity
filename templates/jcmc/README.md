# JCMC / OUP Template Notes

## Source

Journal target:

- Journal of Computer-Mediated Communication
- Official author instructions: https://academic.oup.com/jcmc/pages/General_Instructions

Template source:

- OUP general LaTeX authoring template
- CTAN package: https://ctan.org/pkg/oup-authoring-template
- Downloaded archive: `downloads/oup-authoring-template.ctan.zip`
- Extracted package: `oup-authoring-template/oup-authoring-template/`

The CTAN package page identifies the package as `oup-authoring-template`, version 1.3, dated 2026-05-28, maintained for OUP journals.

## Important JCMC Submission Constraint

JCMC author instructions currently say that the main submission document should be a Word file and that PDF files are not accepted for the main manuscript.

Use LaTeX as a drafting and internal formatting source, but plan to convert the final manuscript to Word before submission unless JCMC changes this instruction.

## Local Files

- `oup-authoring-template/oup-authoring-template/oup-authoring-template.tex`: original OUP sample template.
- `oup-authoring-template/oup-authoring-template/oup-authoring-template.cls`: OUP class file.
- `oup-authoring-template/oup-authoring-template/doc/oup-authoring-template-doc.pdf`: official package manual.
- `starter/jcmc_starter.tex`: local JCMC-oriented starter file.
- `starter/oup-authoring-template.cls`: copied class file for a self-contained starter folder.
- `starter/oup-abbrvnat.bst`: author-year bibliography style.
- `starter/oup-plain.bst`: numbered bibliography style.
- `starter/reference.bib`: sample bibliography file.

## JCMC Key Formatting Points

From the JCMC official author instructions:

- Follow APA 7th edition.
- Manuscripts should be under 10,000 words, including abstract, references, tables, figures, appendices, and endnotes.
- Page 1 should include an abstract of no more than 250 words and 5-7 keywords.
- Page 2 starts with title and main text.
- Use 12-point font, double spacing, Times New Roman, and 1-inch margins.
- References should include DOI links where available.
- Tables, figures, appendices, and endnotes go after references.
- Remove author-identifying information for anonymous review.
- Include a Data Availability Statement.
- Disclose use of generative AI in the cover letter and, where required, in the manuscript methods.

## Practical Workflow

Draft in `starter/jcmc_starter.tex` if LaTeX is convenient for equations, tables, and references.

Before submission:

1. Export or convert the manuscript to Word.
2. Recheck APA 7th style.
3. Place tables and figures after references.
4. Add alt text for figures.
5. Add Data Availability Statement.
6. Remove author-identifying information from the review manuscript.
