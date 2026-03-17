---
name: rebuttal
description: Compose systematic rebuttals and responses to peer reviewer comments — structured, evidence-based, professional tone
context: fork
---

# Reviewer Response / Rebuttal

Use this skill when responding to peer review comments on a submitted paper.

## Process

### 1. Triage Reviews
Read all reviews and categorize each comment:

| Category | Action | Priority |
|----------|--------|----------|
| Factual error by reviewer | Politely correct with evidence | High |
| Valid criticism — easy fix | Fix and acknowledge | High |
| Valid criticism — requires new experiments | Plan experiments, estimate effort | High |
| Misunderstanding of our method | Clarify writing, add explanation | Medium |
| Suggestion for improvement | Evaluate cost/benefit | Medium |
| Subjective preference | Acknowledge respectfully | Low |
| Out of scope | Explain scope, suggest future work | Low |

### 2. Response Template

For each reviewer comment:

```latex
\textbf{Reviewer [N], Comment [M]:} \textit{[Quote the exact comment]}

\textbf{Response:} [Our response — direct, evidence-based, respectful]

\textbf{Changes made:} [Specific changes with section/page references, or explanation of why no change]
```

### 3. Tone Rules
- **Thank every reviewer** — even harsh ones. "We thank the reviewer for this insightful observation."
- **Never be defensive** — treat criticism as an opportunity to strengthen the paper
- **Be specific** — "We added Theorem 3 (Section 4.2)" not "We addressed this concern"
- **If you disagree**, provide evidence: "We respectfully note that [evidence/citation]..."
- **If you can't do something**, explain constraints: "Due to [reason], we instead [alternative]..."
- **Show the diff** — quote the new/modified text directly in the response when possible

### 4. Common Reviewer Concerns in Algorithm Papers

| Concern | How to address |
|---------|---------------|
| "Missing baselines" | Add experiments or explain why baselines are inappropriate |
| "No runtime comparison" | Add wall-clock benchmarks alongside asymptotic analysis |
| "Proof sketch unclear" | Expand to full proof or add intermediate lemma |
| "Limited datasets" | Add datasets or argue representativeness of current ones |
| "Incremental contribution" | Sharpen distinction from prior work, emphasize practical impact |
| "Writing quality" | Use `writing-polish` skill, show specific improvements |

### 5. Output
Save rebuttal to `paper/rebuttal.tex` or `paper/response-to-reviewers.tex`.
Track all changes in a separate `paper/changes-log.md` for internal reference.
