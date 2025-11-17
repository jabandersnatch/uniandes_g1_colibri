# Dependency Management Guide

This document explains how dependencies are managed for the Colibri G1 Digital Twin project in both native and Docker environments.

## Overview

The project uses **two dependency management systems**:

1. **Python packages** (via `setup.py` and `extension.toml`)
2. **System packages** (APT for Ubuntu/Debian)

Isaac Lab uses its own dependency management system that integrates with Isaac Sim's Python environment. Dependencies are NOT managed via traditional `requirements.txt` or `uv` directly.

---

## Dependency Files

### 1. `source/digital_twin_colibri_g1/setup.py`

**Purpose**: Defines Python package dependencies installed via `pip`

**Current dependencies**:
```python
INSTALL_REQUIRES = [
    "psutil",      # System utilities
    "rclpy",       # ROS2 Python client library
]
```

**Installation**:
```bash
# Native (with Isaac Lab activated)
pip install -e source/digital_twin_colibri_g1

# Docker (automatic during build)
${ISAACLAB_PATH}/isaaclab.sh -p -m pip install -e source/digital_twin_colibri_g1
```

### 2. `source/digital_twin_colibri_g1/config/extension.toml`

**Purpose**: Isaac Lab extension configuration with pip and apt dependencies

**Current configuration**:
```toml
[python.pipapi]
requirements = [
    "hydra-core",  # Configuration management
]

modules = [
    "hydra",
]

[isaaclab_settings]
apt_deps = [
    # ROS2 packages installed via apt (if needed)
]
```

**Installation** (automatic):
```bash
# Isaac Lab's install script reads extension.toml and installs dependencies
${ISAACLAB_PATH}/isaaclab.sh --install
```

### 3. `pyproject.toml`

**Purpose**: Build system configuration and code quality tools (isort, pyright, etc.)

**NOT used for runtime dependencies** - only for development tools.

---

## ROS2 Dependencies

ROS2 has a **unique dependency model**:

### Python Client Library (rclpy)
- **Package**: `rclpy`
- **Installation**: Via `pip` (added to `setup.py`)
- **Used for**: Creating ROS2 nodes, publishers, subscribers

### ROS2 Message Types
- **Packages**: `geometry_msgs`, `nav_msgs`, `sensor_msgs`, etc.
- **Installation**: Via **APT** (NOT pip)
- **Reason**: ROS2 message packages are compiled C++ libraries with Python bindings

**Example**:
```bash
# ❌ WRONG: Don't install message packages via pip
pip install geometry-msgs  # This doesn't work properly

# ✅ CORRECT: Install via apt
sudo apt install ros-humble-geometry-msgs ros-humble-nav-msgs
```

### Docker Handling

In the Dockerfile, ROS2 dependencies are installed in **Stage 2** via APT:

```dockerfile
# Stage 2: ROS2 Humble Installation
RUN apt-get install -y \
    ros-humble-desktop \
    ros-humble-tf2-ros \
    ros-humble-tf2-geometry-msgs \
    ros-humble-foxglove-bridge \
    ros-humble-cv-bridge \
    python3-colcon-common-extensions
```

Then in **Stage 4**, the Python packages are installed:

```dockerfile
# Stage 4: Install extension
RUN ${ISAACLAB_PATH}/isaaclab.sh -p -m pip install -e source/digital_twin_colibri_g1
```

This installs `rclpy` and `hydra-core` from `setup.py` and `extension.toml`.

---

## Adding New Dependencies

### Adding Python Packages

**Step 1**: Add to `setup.py`

```python
INSTALL_REQUIRES = [
    "psutil",
    "rclpy",
    "your-new-package>=1.0.0",  # Add here
]
```

**Step 2**: Reinstall extension

```bash
# Native
pip install -e source/digital_twin_colibri_g1 --force-reinstall

# Docker: Rebuild image
./docker/launch.sh build
```

### Adding Pip Dependencies (via extension.toml)

**Step 1**: Add to `extension.toml`

```toml
[python.pipapi]
requirements = [
    "hydra-core",
    "your-new-package>=1.0.0",  # Add here
]

modules = [
    "hydra",
    "your_module_name",  # Add import name
]
```

**Step 2**: Run Isaac Lab install

```bash
${ISAACLAB_PATH}/isaaclab.sh --install
```

### Adding System (APT) Dependencies

**For native installation**:

```bash
sudo apt install your-package-name
```

**For Docker**: Update `Dockerfile` Stage 2 or Stage 3

```dockerfile
# Stage 2 (for ROS2 packages)
RUN apt-get install -y \
    ros-humble-your-ros-package

# Stage 3 (for other system packages)
RUN apt-get install -y \
    your-system-package
```

**For Isaac Lab auto-install**: Add to `extension.toml`

```toml
[isaaclab_settings]
apt_deps = [
    "your-package-name"
]
```

Then run:
```bash
${ISAACLAB_PATH}/isaaclab.sh -p ${ISAACLAB_PATH}/tools/install_deps.py apt source/digital_twin_colibri_g1
```

---

## UV and Isaac Lab

**Important**: Isaac Lab does **NOT** use `uv` for dependency management.

Isaac Lab uses:
- **Isaac Sim's Python environment** (3.10 or 3.11)
- **Pip** for Python packages
- **APT** for system packages
- **extension.toml** for declarative dependencies

If you want to use `uv` for local development (outside Docker), you would need to:

1. Create a `pyproject.toml` with `[project.dependencies]`
2. Install Isaac Lab's dependencies separately
3. Manage conflicts manually

**Recommendation**: Stick with Isaac Lab's dependency system for compatibility.

---

## Docker Dependency Installation Flow

```
Stage 1: Isaac Sim 5.1.0 Base
    ↓
Stage 2: ROS2 Humble (APT)
    ├── ros-humble-desktop
    ├── ros-humble-tf2-ros
    ├── ros-humble-geometry-msgs (and other message packages)
    └── python3-colcon-common-extensions
    ↓
Stage 3: Isaac Lab Installation
    ├── Clone Isaac Lab
    ├── Install Isaac Lab dependencies (via isaaclab.sh --install)
    └── Read all extension.toml files for dependencies
    ↓
Stage 4: Colibri Extension Installation
    ├── Copy project source
    ├── Run: pip install -e source/digital_twin_colibri_g1
    │   └── Installs: psutil, rclpy (from setup.py)
    └── Isaac Lab's --install already handled extension.toml
    ↓
Stage 5: Final Configuration
    └── Install additional packages: opencv, matplotlib, hydra-core
```

---

## Native Installation (Without Docker)

### Prerequisites
1. ROS2 Humble installed: `sudo apt install ros-humble-desktop`
2. Isaac Sim installed
3. Isaac Lab installed

### Installation Steps

```bash
# 1. Activate Isaac Lab environment
source ~/IsaacLab/isaaclab/bin/activate  # or conda activate isaaclab

# 2. Install ROS2 message packages (system-wide)
sudo apt install \
    ros-humble-geometry-msgs \
    ros-humble-nav-msgs \
    ros-humble-sensor-msgs \
    ros-humble-visualization-msgs \
    ros-humble-std-msgs \
    ros-humble-tf2-ros

# 3. Install Colibri G1 extension (installs Python dependencies)
cd uniandes_g1_colibri/digital_twin_colibri_g1
pip install -e source/digital_twin_colibri_g1

# 4. Verify installation
python -c "import rclpy; print('ROS2 Python OK')"
python -c "from geometry_msgs.msg import Pose; print('ROS2 messages OK')"
python -c "import digital_twin_colibri_g1; print('Extension OK')"
```

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'rclpy'"

**Cause**: ROS2 not installed or not sourced

**Solution**:
```bash
# Check if ROS2 is installed
which ros2

# Source ROS2 (add to ~/.bashrc)
source /opt/ros/humble/setup.bash

# Verify
python3 -c "import rclpy"
```

### "ModuleNotFoundError: No module named 'geometry_msgs'"

**Cause**: ROS2 message packages not installed

**Solution**:
```bash
sudo apt install ros-humble-geometry-msgs ros-humble-nav-msgs
```

### "pip install ros-humble-* doesn't work"

**Cause**: ROS2 packages are not on PyPI

**Solution**: Use APT, not pip:
```bash
sudo apt install ros-humble-<package-name>
```

### Docker build fails at "pip install rclpy"

**Cause**: ROS2 not sourced in Docker environment

**Solution**: Ensure ROS2 is installed before pip install, or source ROS2:
```dockerfile
RUN bash -c "source /opt/ros/humble/setup.bash && pip install rclpy"
```

---

## Dependency Version Management

### Python Packages
- Specified in `setup.py` with version constraints
- Example: `"rclpy>=0.18.0"`

### ROS2 Packages
- Version tied to ROS2 distribution (Humble)
- No separate versioning needed

### Isaac Lab
- Extension compatibility declared in `setup.py`:
  ```python
  classifiers=[
      "Isaac Sim :: 4.5.0",
      "Isaac Sim :: 5.0.0",
  ]
  ```

---

## Summary

| Dependency Type | File | Installation Method | Example |
|----------------|------|---------------------|---------|
| Python packages | `setup.py` | `pip install -e .` | `rclpy`, `psutil` |
| Pip (extension) | `extension.toml` | `isaaclab.sh --install` | `hydra-core` |
| ROS2 messages | N/A (system) | `apt install` | `geometry_msgs` |
| System packages | `extension.toml` or Dockerfile | `apt install` | `tmux`, `git` |

**Key Principle**:
- Python libraries → pip (setup.py or extension.toml)
- ROS2 message types → apt (Dockerfile or manual)
- System tools → apt (Dockerfile)

**No `uv` usage**: Isaac Lab uses its own dependency system via `extension.toml` and Isaac Sim's Python environment.
