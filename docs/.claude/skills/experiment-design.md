---
name: experiment-design
description: Design and document RL robotics experiments — training setup, evaluation metrics, result visualization, and reproducibility for humanoid locomotion papers
---

# Experiment Design for RL Robotics Evaluation

Use this skill when designing, running, analyzing, or writing up experiments for the humanoid locomotion paper.

## Process

### 1. Hypothesis Formulation
Before any experiment, state:
- **Hypothesis**: What do we expect and why?
- **Independent variables**: What do we vary? (reward weights, num_envs, curriculum, sensors)
- **Dependent variables**: What do we measure? (success rate, episode length, reward, training stability)
- **Controls**: What stays fixed? (random seed, Isaac Sim version, robot model)

### 2. Training Setup Documentation

Save to `experiments/configs/` as YAML:
```yaml
experiment:
  name: "ppo_g1_locomotion_v1"
  date: "2026-03-17"
  git_commit: "<hash>"

hardware:
  gpu: "NVIDIA RTX XXXX"
  cpu: "AMD/Intel model"
  ram: "XX GB"

software:
  isaac_sim: "4.5.0"
  isaac_lab: "2.2.0"
  python: "3.10.x"
  rsl_rl: "x.x.x"

training:
  task: "Isaac-Colibri-G1-v0"
  num_envs: 512
  max_iterations: 5000
  seed: 42
  headless: true

ppo:
  learning_rate: 1.0e-3
  num_steps_per_env: 24
  num_mini_batches: 4
  num_learning_epochs: 5
  clip_param: 0.2
  gamma: 0.99
  lam: 0.95
  entropy_coef: 0.01
  value_loss_coef: 1.0

observation_dim: 125
action_dim: 29
```

### 3. Key Metrics for Locomotion Papers

**Training metrics** (logged every N iterations):
- Mean episode reward (cumulative)
- Mean episode length (steps)
- Policy loss, value loss, entropy
- Goal success rate (% episodes reaching goal within time limit)

**Evaluation metrics** (computed at fixed checkpoints, no gradient):
- **Goal success rate**: % of `num_eval_episodes` where robot reaches goal within threshold
- **Mean navigation distance**: how far the robot traveled when successful
- **Mean steps to goal**: efficiency of navigation
- **Obstacle collision rate**: for SocialNav task
- **Stability metric**: episodes terminated early due to fall vs. timeout

**ROS 2 integration metrics** (for sim2sim validation):
- Topic publish rate (actual vs. target 50 Hz)
- End-to-end latency (action command → joint state update)
- Message drop rate under load

### 4. Result Visualization

**Training curve plot** (save as `figures/training_curves.pdf`):
```python
import matplotlib.pyplot as plt
import matplotlib
import numpy as np

matplotlib.rcParams.update({
    "font.size": 11,
    "font.family": "serif",
    "figure.figsize": (6, 4),
    "figure.dpi": 150,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.05,
})

def plot_training_curves(data_dict, ylabel, title=None):
    """Plot mean ± std training curves for one or more runs/configs."""
    fig, ax = plt.subplots()
    colors = plt.cm.tab10.colors
    for i, (label, data) in enumerate(data_dict.items()):
        # data: dict with "iterations", "mean", "std"
        iters = np.array(data["iterations"])
        mean = np.array(data["mean"])
        std = np.array(data["std"])
        ax.plot(iters, mean, label=label, color=colors[i])
        ax.fill_between(iters, mean - std, mean + std, alpha=0.2, color=colors[i])
    ax.set_xlabel("Training Iterations")
    ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    return fig
```

**Figure requirements for paper**:
- Export as **PDF** (vector) for inclusion in LaTeX
- Font size ≥ 10pt (legible when scaled to column width)
- Axis labels must include units: "Training Iterations", "Mean Episode Reward", "Success Rate (%)"
- Include legend when multiple curves shown
- Use colorblind-safe colors (tab10 or explicitly accessible palette)
- For training curves: show mean + shaded std region

### 5. Ablation Study Design

For the locomotion paper, consider ablating:
- **Reward weights**: vary goal distance weight vs. velocity tracking weight
- **Observation components**: with/without goal position in observation
- **Domain randomization**: with/without terrain randomization
- **SocialNav**: single objective (goal only) vs. multi-objective (goal + obstacle avoidance)

Document each ablation as a separate experiment config with one variable changed.

### 6. Statistical Reporting

Since RL training is stochastic:
- Run training with ≥ 3 different seeds for key results
- Report **mean ± std** across seeds
- For success rate evaluation: use ≥ 100 episodes, report percentage
- State exactly how many evaluation episodes were used

### 7. Results Section Writing Template

```latex
\subsection{Locomotion Training Results}
\label{sec:locomotion-results}

We evaluate the trained policy over \num{200} evaluation episodes.
The policy achieves a goal success rate of $87.0 \pm 3.2\%$,
with a mean of $342 \pm 45$ steps to goal when successful.
\Cref{fig:training-curve} shows the training reward curve over 5000 iterations.

\begin{table}[t]
  \caption{Locomotion evaluation results.}\label{tab:locomotion}
  \begin{tabular}{lSSS}
    \toprule
    Metric & {Mean} & {Std} & {Unit} \\
    \midrule
    Goal success rate     & 87.0 & 3.2  & \% \\
    Steps to goal         & 342  & 45   & steps \\
    Episode length (fail) & 500  & 0    & steps \\
    \bottomrule
  \end{tabular}
\end{table}
```

### 8. Reproducibility Checklist

- [ ] Git commit hash recorded for training run
- [ ] All hyperparameters saved to config file
- [ ] Random seed(s) specified
- [ ] Isaac Sim + Isaac Lab versions specified
- [ ] Hardware described (GPU model, RAM)
- [ ] Checkpoint file archived alongside config
- [ ] Training logs saved to `logs/rsl_rl/<experiment>/<timestamp>/`
- [ ] Evaluation script saved to `scripts/evaluate.py`

## Output Artifacts
- Experiment configs → `experiments/configs/`
- Training logs → `logs/rsl_rl/`
- Generated figures → `paper_document/figures/`
- Evaluation scripts → `scripts/`
