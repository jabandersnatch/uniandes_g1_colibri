# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LaTeX thesis document for a Master's thesis at Universidad de los Andes (MISIS program). The thesis focuses on developing a framework for training and deployment of locomotion for humanoid robots using digital twins, reinforcement learning, and cognitive agents based on LLMs.

## Build Commands

```bash
# Full build (compile + bibliography + recompile for references)
pdflatex main.tex && biber main && pdflatex main.tex && pdflatex main.tex

# Quick compile (no bibliography update)
pdflatex main.tex

# Using latexmk (recommended - handles dependencies automatically)
latexmk -pdf main.tex

# Clean auxiliary files
latexmk -c

# Clean all generated files including PDF
latexmk -C
```

## Document Structure

```
thesis_document/
├── main.tex          # Main document (single-file thesis)
├── src/
│   └── ref.bib       # Bibliography (BibLaTeX format, APA style)
├── img/              # Figures (PNG, SVG, JPG supported)
├── docs/             # Thesis writing documentation and session notes
│   ├── CHANGELOG.md  # Change tracker, next steps, writing guidelines
│   └── SESSION_*.md  # Session-specific notes
└── evidences/        # Implementation evidence for thesis content
    ├── README.md     # Index of all evidence documents
    ├── 01_project_overview.md
    ├── 02_custom_rl_task_implementation.md
    ├── 03_ros2_sim2sim_implementation.md
    ├── 04_docker_deployment.md
    ├── 05_social_navigation_task.md
    └── 06_implementation_summary.md
```

## Key Configuration

- **Document class**: article, 12pt, A4 paper
- **Bibliography**: BibLaTeX with Biber backend, APA style (`sorting=nyt`)
- **Language**: American English
- **Margins**: 40mm left, 20mm right, 30mm bottom
- **Line spacing**: 1.5

## Adding Content

**Citations**: Use `\parencite{key}` for parenthetical or `\textcite{key}` for narrative citations.

**Figures**: Place in `img/` directory. SVG files are supported via the `svg` package (requires Inkscape installed for conversion).

**Acronyms**: Define in the acronym block using `\acro{key}[SHORT]{Long Form}`, reference with `\ac{key}`.

## Dependencies

Required LaTeX packages (install via texlive or similar):
- texlive-latex-extra (for various packages)
- texlive-bibtex-extra, biber (for bibliography)
- texlive-fonts-recommended, texlive-fonts-extra (for Times font)
- inkscape (for SVG support)

## Reference Documentation

### Implementation Evidence (`evidences/` directory)

This directory contains detailed documentation of all features implemented in the `digital_twin_colibri_g1` project (located at `/home/jamendez/Documents/uniandes/MISIS/thesis/uniandes_g1_colibri/digital_twin_colibri_g1/`).

**Purpose**: Technical evidence and implementation details to support thesis claims.

**Contents**:
- `01_project_overview.md` - Repository structure, technology stack, registered tasks
- `02_custom_rl_task_implementation.md` - Goal-directed navigation, commands, rewards
- `03_ros2_sim2sim_implementation.md` - ROS2 bridge, topics, sensor integration
- `04_docker_deployment.md` - Multi-stage build, container configuration
- `05_social_navigation_task.md` - LiDAR, obstacles, avoidance rewards
- `06_implementation_summary.md` - Original contributions, key innovations
- `README.md` - Index with quick reference and development status

**When to consult**:
- Writing methodology sections (Phase 4)
- Describing implementation details (Phase 5)
- Documenting results and experiments (Phase 6)
- Verifying technical claims and specifications
- Checking code statistics and features

**Example usage**: Before writing about the ROS2 sim2sim implementation, read `03_ros2_sim2sim_implementation.md` to ensure accuracy of topics, message types, and frequencies.

### Thesis Writing Documentation (`docs/` directory)

This directory tracks thesis writing progress and maintains writing guidelines.

**Purpose**: Meta-documentation for the thesis writing process.

**Contents**:
- `CHANGELOG.md` - Complete change tracker with:
  - All modifications made to the thesis
  - Next steps and priorities (Phase 1, 2, 3)
  - Writing guidelines (technical language, APA standards, thesis tone)
  - Research scope clarification (what was/wasn't accomplished)
  - File modification tracker
- `SESSION_*.md` - Session-specific notes and decisions

**When to consult**:
- **Before making any significant changes** - Check CHANGELOG.md for context and guidelines
- Starting a new writing session - Review next steps and priorities
- Uncertain about scope - Check "Research Scope Clarification" section
- Formatting questions - Review writing guidelines
- Citation questions - Check APA citation standards

**When to update**:
- **ONLY when explicitly instructed by the user**
- Not automatically after every document edit (to minimize cost)
- User will say "update the docs/" when documentation update is needed

**Example workflow**:
1. User requests thesis modification
2. Read relevant sections in `evidences/` for technical accuracy
3. Read `docs/CHANGELOG.md` for context and guidelines
4. Make changes to `main.tex`
5. Wait for user instruction before updating `docs/`

## Working with This Thesis

### Before Making Changes

1. **Read CHANGELOG.md** (`docs/CHANGELOG.md`) to understand:
   - Recent changes and rationale
   - Current priorities (Phase 1, 2, or 3)
   - Scope constraints (what was/wasn't accomplished)
   - Writing guidelines to follow

2. **Check evidences/** for technical accuracy:
   - Verify implementation details against evidence files
   - Use actual statistics from `06_implementation_summary.md`
   - Reference correct task names from `01_project_overview.md`

3. **Follow writing guidelines** (in CHANGELOG.md):
   - Technical language standards
   - APA citation standards
   - Thesis-appropriate tone

### Making Changes

- **Content changes**: Edit `main.tex` directly
- **Bibliography**: Edit `src/ref.bib` (BibLaTeX format)
- **Figures**: Add to `img/` directory
- **Documentation**: Wait for explicit user instruction to update `docs/`

### After Making Changes

- Compile and verify: `latexmk -pdf main.tex`
- Check for LaTeX errors and warnings
- **Only update docs/ when user explicitly requests it**
