---
name: latex-paper
description: Write and edit academic robotics/RL papers in Springer Nature LaTeX format — sections, figures, tables, algorithms, and compilation for sn-jnl class
---

# LaTeX Academic Paper Writing (Springer Nature)

Use this skill when creating, editing, or structuring the LaTeX paper for Springer Nature submission.

## Key Constraint

**Springer Nature requires a single .tex file** — do NOT use `\input{}` or `\include{}` to split sections.
All content goes in `paper_document/sn-article.tex`.

## Document Class and Preamble

```latex
\documentclass[pdflatex,sn-mathphys-num]{sn-jnl}

\usepackage{graphicx}
\usepackage{multirow}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{amsthm}
\usepackage{mathrsfs}
\usepackage[title]{appendix}
\usepackage{xcolor}
\usepackage{booktabs}
\usepackage{algorithm}
\usepackage{algorithmicx}
\usepackage{algpseudocode}
\usepackage{listings}
\usepackage{cleveref}    % add this for \cref
\usepackage{siunitx}     % add this for Hz, ms, degrees units
\usepackage{subcaption}  % add this for subfigures

% Domain macros
\newcommand{\ROS}{ROS\,2}
\newcommand{\PPO}{PPO}
\newcommand{\IsaacLab}{\textsc{IsaacLab}}
\newcommand{\eg}{e.g.,\ }
\newcommand{\ie}{i.e.,\ }
```

## Theorem Environments (Springer style)

```latex
\theoremstyle{thmstyleone}
\newtheorem{theorem}{Theorem}
\newtheorem{proposition}[theorem]{Proposition}

\theoremstyle{thmstyletwo}
\newtheorem{example}{Example}
\newtheorem{remark}{Remark}

\theoremstyle{thmstylethree}
\newtheorem{definition}{Definition}
```

## Document Structure (Springer)

```latex
\title[Short Title]{Full Paper Title}

\author*[1]{\fnm{First} \sur{Last}}\email{email@inst.edu}
\author[1]{\fnm{First} \sur{Last}}\email{email@inst.edu}

\affil*[1]{\orgdiv{Department}, \orgname{University},
  \orgaddress{\street{Street}, \city{City}, \postcode{Code}, \country{Country}}}

\abstract{150--250 words. Context → Problem → Approach → Key results → Significance.}

\keywords{keyword1; keyword2; keyword3}

\maketitle

\section{Introduction}\label{intro}
...

\section{Related Work}\label{sec:related}
...

\section{Methodology}\label{sec:method}
...

\section{Experimental Setup}\label{sec:setup}
...

\section{Results}\label{sec:results}
...

\section{Discussion}\label{sec:discussion}
...

\section{Conclusion}\label{sec:conclusion}
...

\bibliography{sn-bibliography}
```

## Section Writing Guidelines

### Abstract (150–250 words)
Structure: **Context** → **Problem** → **Approach** → **Key results** → **Significance**
- No citations in abstract
- Include key quantitative result (e.g., "87% success rate")

### Introduction
1. Broad context: humanoid robotics challenges (1–2 paragraphs)
2. Specific problem: sim-to-real gap, middleware validation gap
3. Limitations of existing approaches
4. Our approach and key insight
5. **Numbered contributions list**:
   ```latex
   The contributions of this work are threefold:
   \begin{enumerate}
     \item \textbf{A communication-realistic sim-to-sim framework} ...
     \item \textbf{An integrated pipeline} ...
     \item \textbf{Experimental validation} ...
   \end{enumerate}
   ```
6. Paper organization sentence

### Experiments / Results Section
Must include:
- **Setup**: GPU/CPU hardware, Isaac Sim version, training hyperparameters
- **Metrics**: success rate, episode length, cumulative reward, training time
- **Baselines**: if applicable
- **Results with statistics**: mean ± std over multiple seeds or episodes
- **Discussion**: what the numbers mean, limitations, surprising findings

## Figures

### Single figure
```latex
\begin{figure}[t]
  \centering
  \includegraphics[width=\textwidth]{figures/filename.pdf}
  \caption{Descriptive caption. Explain what the reader should take away
  without needing to read the main text.}\label{fig:name}
\end{figure}
```

### Two-column figure
```latex
\begin{figure*}[t]
  \centering
  \includegraphics[width=\textwidth]{figures/filename.pdf}
  \caption{Wide figure caption.}\label{fig:wide}
\end{figure*}
```

### Subfigures
```latex
\begin{figure}[t]
  \centering
  \begin{subfigure}[b]{0.48\linewidth}
    \includegraphics[width=\linewidth]{figures/a.pdf}
    \caption{Subfigure A description.}\label{fig:a}
  \end{subfigure}
  \hfill
  \begin{subfigure}[b]{0.48\linewidth}
    \includegraphics[width=\linewidth]{figures/b.pdf}
    \caption{Subfigure B description.}\label{fig:b}
  \end{subfigure}
  \caption{Overall caption describing both subfigures.}\label{fig:both}
\end{figure}
```

## Tables

```latex
\begin{table}[t]
  \caption{Caption above the table.}\label{tab:results}
  \begin{tabular}{lSSS}
    \toprule
    Method & {Success Rate (\%)} & {Avg. Steps} & {Training Time (h)} \\
    \midrule
    Ours (PPO)   & 87.0 & 342 & 4.2 \\
    Baseline     & 71.3 & 418 & 4.0 \\
    \bottomrule
  \end{tabular}
\end{table}
```

## Algorithms (for RL training loop, reward functions, etc.)

```latex
\begin{algorithm}
  \caption{PPO Training Loop}\label{alg:ppo}
  \begin{algorithmic}[1]
    \Require Environment $\mathcal{E}$, policy $\pi_\theta$, hyperparameters
    \For{iteration $k = 1, 2, \ldots, K$}
      \State Collect rollout $\tau$ by running $\pi_{\theta_k}$ in $\mathcal{E}$
      \State Compute advantages $\hat{A}_t$ using GAE
      \For{epoch $e = 1, \ldots, E$}
        \State Update $\theta$ by maximizing clipped surrogate objective
      \EndFor
    \EndFor
  \end{algorithmic}
\end{algorithm}
```

## Units and Numbers

Use `siunitx` for consistent unit formatting:
```latex
\SI{50}{\hertz}          % 50 Hz
\SI{4.2}{\hour}          % 4.2 h
\SI{87}{\percent}        % 87 %
\SI{29}{}~DOF            % 29 DOF (no built-in unit)
\num{4096}               % 4096 (formatted number, no unit)
```

## Compilation

```bash
cd paper_document/
# Full build (run from docs/ directory)
pdflatex sn-article && bibtex sn-article && pdflatex sn-article && pdflatex sn-article

# Preferred: latexmk handles reruns automatically
latexmk -pdf sn-article.tex

# Clean auxiliary files
latexmk -c
```

## Writing Quality Checklist
- [ ] Each paragraph has a clear topic sentence
- [ ] No paragraph exceeds ~8 lines
- [ ] Active voice: "We propose" not "It is proposed"
- [ ] All variables/notation introduced before use
- [ ] Consistent tense: present for system descriptions, past for experimental findings
- [ ] Every quantitative claim has a supporting result (table or figure reference)
- [ ] All figures/tables cited in text before they appear
- [ ] `\cref{fig:x}` or `Fig.~\ref{fig:x}` — never bare `\ref{}`
