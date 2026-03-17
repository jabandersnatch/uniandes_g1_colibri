---
name: paper-review
description: Self-review an academic robotics/RL paper before submission — checks structure, experimental rigor, Springer Nature formatting, and common issues in systems/RL papers
context: fork
---

# Academic Paper Self-Review (Robotics / RL Systems)

Use this skill to review the paper draft before submission to Springer Nature.

## Review Dimensions

### 1. Structure and Flow
- [ ] Abstract: context → problem → approach → results → significance (150–250 words, no citations)
- [ ] Introduction clearly states the sim-to-real / middleware validation gap and motivation
- [ ] Contributions are explicitly listed as numbered items
- [ ] Related work covers: RL for humanoid locomotion, digital twins, sim-to-real methods, middleware architectures
- [ ] Methodology section describes system architecture clearly (can a reader reproduce it?)
- [ ] Experimental setup: hardware, software versions, hyperparameters, seeds all specified
- [ ] Results section presents quantitative outcomes with statistics
- [ ] Discussion interprets results and acknowledges limitations
- [ ] Conclusion summarizes without introducing new material
- [ ] Sections flow logically; no unexplained jumps

### 2. Technical Rigor (RL / Systems paper)
- [ ] Training hyperparameters fully specified (lr, batch size, clip ratio, GAE λ, etc.)
- [ ] Number of training environments (`num_envs`) and total timesteps stated
- [ ] Observation space dimensions stated and all components listed
- [ ] Action space described (joint positions/velocities, control frequency)
- [ ] Reward function terms all defined with weights
- [ ] Domain randomization parameters listed if used
- [ ] Policy checkpoint used for evaluation matches stated training config
- [ ] Success metric defined clearly (distance threshold, time limit)
- [ ] ROS 2 integration described: topic names, message types, frequencies

### 3. Experimental Evaluation
- [ ] Training setup fully described (GPU model, Isaac Sim version, num_envs)
- [ ] Results include quantitative metrics: success rate, episode length, reward curves
- [ ] Error measures reported (std deviation, or N episodes evaluated)
- [ ] Figures are readable: axis labels with units, legend, sufficient resolution
- [ ] Training curves show both mean and variance (shaded region or error bars)
- [ ] Tables use booktabs formatting (no `\hline`)
- [ ] Obstacle avoidance / social nav results acknowledge limitations honestly
- [ ] Videos or supplementary material referenced if applicable

### 4. Writing Quality
- [ ] No grammar or spelling errors
- [ ] Consistent terminology: "ROS 2" not "ROS2" or "ROS2.0"; "Isaac Lab" not "IsaacLab"
- [ ] Active voice preferred: "We train" not "The policy is trained"
- [ ] No vague hedging: "somewhat", "fairly", "quite", "significantly" without quantification
- [ ] No unjustified superlatives: "best", "optimal", "state-of-the-art" without citation
- [ ] All acronyms defined on first use: PPO, DOF, RL, ROS, IMU, etc.
- [ ] No AI-sounding phrases: "delve into", "leverage", "utilize", "it is worth noting"

### 5. Springer Nature Formatting
- [ ] Single `.tex` file (no `\input{}` calls)
- [ ] Document class: `\documentclass[pdflatex,sn-mathphys-num]{sn-jnl}`
- [ ] Author/affiliation blocks use Springer macros (`\fnm`, `\sur`, `\affil`, etc.)
- [ ] Keywords provided (semicolon-separated)
- [ ] All figures have captions and `\label`
- [ ] All tables have captions **above** the table (Springer convention) and `\label`
- [ ] Bibliography in `sn-bibliography.bib`, compiled with `bibtex`
- [ ] Paper compiles cleanly: `latexmk -pdf sn-article.tex` — zero errors
- [ ] No overfull/underfull hbox warnings > 5pt
- [ ] Figure files exist and are referenced by correct filename

### 6. Citation Quality
- [ ] No `[?]` or undefined references
- [ ] No hallucinated citations — all verified via web search
- [ ] Primary sources cited, not just surveys
- [ ] Key works cited: Schulman et al. (PPO), Isaac Lab, Unitree G1, relevant humanoid locomotion papers
- [ ] arXiv preprints noted as such; published versions preferred

## Review Output Format

```markdown
# Paper Review: [version/date]

## Summary
One paragraph: what the paper does and its main contribution.

## Strengths
- S1: ...
- S2: ...

## Critical Issues (must fix before submission)
- C1: [Section X] ...
- C2: [Figure Y] ...

## Minor Issues
- Line ~XX: ...
- Table Z: ...

## Suggestions (optional improvements)
- ...

## Verdict
Ready / needs revision / major revisions needed.
Priority order for fixes: ...
```

## Common Issues in RL Systems Papers
1. **Underspecified hyperparameters**: reader cannot reproduce training without full config
2. **Single-seed results**: RL is high variance — report across multiple seeds or episodes
3. **Missing ablations**: unclear which component drives performance
4. **Overclaiming generalization**: tested on one environment/scenario
5. **Misleading training curves**: showing only the best run, not typical behavior
6. **Ignored failure modes**: obstacle avoidance challenges dismissed without analysis
7. **Version mismatch**: Isaac Sim/Isaac Lab version affects reproducibility
8. **Undefined reward terms**: equation given but weights/rationale not discussed
