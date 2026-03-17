---
name: literature-review
description: Systematic literature review for CS algorithm research — guides structured search, paper analysis, and synthesis of related work
context: fork
---

# Systematic Literature Review

Use this skill when investigating prior work on an algorithm, data structure, or CS problem.

## Process

### 1. Define Scope
Before searching, establish:
- **Research question**: What specific question does this review answer?
- **Inclusion criteria**: What types of papers are relevant? (e.g., peer-reviewed, specific venues, date range)
- **Exclusion criteria**: What should be filtered out?

Ask the user to confirm scope before proceeding.

### 2. Search Strategy
Use multiple sources systematically:
- **Primary databases**: Google Scholar, DBLP, ACM Digital Library, IEEE Xplore, arXiv
- **Search terms**: Generate 3-5 query variations combining:
  - Problem name + "algorithm"
  - Technique name + "complexity" / "analysis"
  - Application domain + method
- **Snowball**: From key papers, check both references (backward) and citations (forward)

Present search terms to user for approval before executing.

### 3. Paper Analysis Template
For each relevant paper, extract and document:

```markdown
## [Author et al., Year] — Title

**Venue**: Conference/Journal name
**Key contribution**: One-sentence summary
**Problem addressed**: What problem they solve
**Approach**: Brief description of method/algorithm
**Complexity**: Time and space bounds claimed
**Strengths**: What they do well
**Limitations**: Gaps, assumptions, scalability issues
**Relevance to our work**: How it connects to our research
**BibTeX key**: authorYEARkeyword
```

Save analysis to `notes/literature/` with filename `author-year-keyword.md`.

### 4. Synthesis
After analyzing individual papers, produce:
- **Taxonomy**: Categorize approaches (e.g., exact vs. approximate, deterministic vs. randomized)
- **Comparison table**: Key dimensions across papers (complexity, assumptions, guarantees)
- **Gap analysis**: What hasn't been addressed? Where can we contribute?
- **Timeline**: How has the field evolved?

### 5. Output: Related Work Section
Draft a LaTeX `\section{Related Work}` that:
- Groups papers thematically (not chronologically unless evolution matters)
- Clearly positions our work relative to existing approaches
- Uses `\cite{}` with proper BibTeX keys
- Ends with a paragraph distinguishing our contribution

## File Management
- Save BibTeX entries to `paper/references.bib`
- Save reading notes to `notes/literature/`
- Save synthesis document to `notes/literature-synthesis.md`

## Important
- Never fabricate citations or paper details — if unsure, flag it clearly
- Always verify paper existence via web search when possible
- Distinguish between peer-reviewed and preprint sources
- Note if a paper has been superseded by a newer version
