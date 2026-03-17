# Academic Paper — Claude Configuration

## Project Context

This is the documentation workspace for the master's thesis paper at Universidad de los Andes (MISIS program).
**Paper**: "A Communication-Realistic Sim-to-Sim Validation Framework for Reinforcement Learning Humanoid Locomotion Using Digital Twins"
**Target venue**: Springer Nature journal — `sn-jnl` document class with `sn-mathphys-num` reference style
**Authors**: Juan Andres Mendez, Carlos Lozano-Garzon

## Document Structure

The paper is a **single `.tex` file** (Springer Nature requirement — no `\input{}` of section files):
```
paper_document/
├── sn-article.tex          # Main and only .tex source
├── sn-bibliography.bib     # Bibliography
├── sn-jnl.cls              # Springer Nature class (do not modify)
├── bst/                    # Bibliography style files
└── figures/                # Generated figures (PDF/EPS preferred)
```

## LaTeX Conventions

- **Document class**: `\documentclass[pdflatex,sn-mathphys-num]{sn-jnl}`
- **Do NOT** split into separate section files (Springer requires single-file submission)
- **Bibliography**: BibTeX with `sn-mathphys-num` style — numbered citations `[1]`, `[2,3]`
- **Figures**: prefer PDF or EPS for vector graphics; PNG acceptable for screenshots
- **One sentence per line** in .tex source (cleaner git diffs)
- Use `\cref` (cleveref) for cross-references when possible; `\ref` otherwise
- Tables: use `booktabs` (`\toprule`, `\midrule`, `\bottomrule`) — never `\hline`

## Standard Packages (already in template)

```latex
\usepackage{graphicx}
\usepackage{multirow}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{amsthm}
\usepackage{booktabs}
\usepackage{algorithm}
\usepackage{algorithmicx}
\usepackage{algpseudocode}
\usepackage{listings}
```

Additional useful packages to add as needed:
- `\usepackage{cleveref}` — smart cross-references
- `\usepackage{siunitx}` — SI units (Hz, ms, etc.)
- `\usepackage{subcaption}` — subfigures
- `\usepackage{pgfplots}` — plots generated in LaTeX

## Domain-Specific Macros

Add these to the preamble when needed:
```latex
\newcommand{\ROS}{ROS\,2}                        % consistent ROS 2 spelling
\newcommand{\IsaacLab}{\textsc{IsaacLab}}        % software names
\newcommand{\PPO}{PPO}
\newcommand{\etal}{et al.\@\xspace}
\newcommand{\eg}{e.g.,\@\xspace}
\newcommand{\ie}{i.e.,\@\xspace}
```

## Writing Style

- All academic writing in **English** — formal tone, no contractions
- **Active voice**: "We propose" not "It is proposed"
- **Specific over vague**: "87% success rate" not "high performance"
- Present tense for descriptions of the system/method; past tense for experiments
- Never use: "it is worth noting", "it is important to note", "in the realm of", "leverage", "utilize", "delve into"

## Citation Discipline

- **NEVER hallucinate citations** — verify every reference via web search
- Use `\cite{PLACEHOLDER_author2024_verify}` with TODO comment if uncertain
- Fetch BibTeX from authoritative sources (Springer, IEEE, ACM, arXiv)
- Key format: `firstauthorlastnameYEARkeyword` (e.g., `schulman2017proximal`)
- Include DOIs when available

## Research Lifecycle — Skill Map

| Stage | Skill |
|-------|-------|
| Find/verify references | `citation-search` |
| Review prior work | `literature-review` |
| Write/edit LaTeX sections | `latex-paper` |
| Review for RL experiment quality | `experiment-design` |
| Final prose pass | `writing-polish` |
| Self-review before submission | `paper-review` |
| Respond to reviewers | `rebuttal` |

## Build Commands

```bash
# From paper_document/ directory
cd paper_document/
pdflatex sn-article && bibtex sn-article && pdflatex sn-article && pdflatex sn-article

# Or with latexmk
latexmk -pdf sn-article.tex
```

## Quality Checklist (before submission)

- [ ] Single .tex file with no `\input{}` calls (Springer requirement)
- [ ] All figures referenced in text and have descriptive captions
- [ ] All tables use booktabs formatting
- [ ] Bibliography has no missing fields, all DOIs present where available
- [ ] No orphaned `[?]` references
- [ ] Compiles cleanly with `latexmk -pdf` — zero errors
- [ ] Abstract: 150–250 words covering context/problem/approach/results/significance
- [ ] Contributions explicitly listed as numbered items in introduction
- [ ] Experiment results have quantitative metrics (success rate, mean ± std)
- [ ] All acronyms defined on first use
