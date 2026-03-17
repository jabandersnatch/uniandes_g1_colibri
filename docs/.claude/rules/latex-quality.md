---
paths: ["paper_document/**/*.tex", "paper_document/**/*.bib"]
---

# LaTeX Quality Rules

## Compilation
- Paper must compile with zero errors before any commit
- Warnings should be addressed (especially overfull hboxes > 5pt)
- Use `latexmk -pdf sn-article.tex` as the canonical build command (run from `paper_document/`)

## Writing Anti-Patterns (avoid AI-sounding prose)
- Never use: "it is worth noting that", "in the realm of", "it is important to note"
- Never use: "delve into", "leverage", "utilize" (use "use"), "facilitate"
- Never use: "a myriad of", "in light of", "plays a crucial role", "robust solution"
- Never use: "significant" without a number (say "87% success rate" not "significant improvement")
- Prefer active voice: "We propose" not "It is proposed"
- Prefer specific over vague: "reduces latency by 40 ms" not "improves performance"

## Springer Nature Specifics
- Single `.tex` file — no `\input{}` or `\include{}` calls
- Table captions go **above** the table (Springer convention)
- Use `\cite{key}` for numbered citations — keys must match `sn-bibliography.bib`
- Use Springer affiliation macros: `\fnm`, `\sur`, `\affil`, `\orgdiv`, `\orgname`

## Structure
- One sentence per line in .tex source (makes git diffs readable)
- Comments explain WHY, not WHAT
- Use `\label{sec:name}`, `\label{fig:name}`, `\label{tab:name}` on all floats and sections
- Cross-reference with `\cref{}` or `Fig.~\ref{}` — never bare numbers
