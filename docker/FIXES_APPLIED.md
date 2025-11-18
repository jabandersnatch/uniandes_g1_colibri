# Docker Fixes Applied - 2025-11-18

## Issues Identified

### 1. **NumPy Version Incompatibility (Primary Issue)**
**Error**: `ValueError: numpy.dtype size changed, may indicate binary incompatibility. Expected 96 from C header, got 88 from PyObject`

**Root Cause**: Isaac Sim 4.5.0's bundled scipy was compiled against NumPy 1.x, but the conda environment installed NumPy 2.2.6 by default.

**Impact**:
- Prevented Isaac Lab extensions from loading properly
- Caused binary incompatibility with scipy's C extensions
- Led to cascading import failures

### 2. **Extension Not Found (Secondary Issue)**
**Error**: `ModuleNotFoundError: No module named 'digital_twin_colibri_g1'`

**Root Cause**:
- Extension installation was not using conda environment properly
- PYTHONPATH was not configured to include the extension location
- Python couldn't find the installed extension

## Fixes Applied

### Fix 1: Enforce NumPy <2.0 Using pip Constraints File (ENHANCED FIX - 2025-11-18)

**Problem**: Initial pin at installation time wasn't sufficient - Isaac Lab's `--install` process was upgrading NumPy back to 2.2.6.

**Solution**: Use PIP_CONSTRAINT environment variable to enforce NumPy <2.0 across ALL pip installations.

**Location**: `docker/Dockerfile:165-176`

```dockerfile
# Create pip constraints file to enforce NumPy <2.0 across ALL installations
RUN echo "numpy<2.0" > /tmp/constraints.txt

# Set PIP_CONSTRAINT environment variable to apply constraints to all pip operations
ENV PIP_CONSTRAINT=/tmp/constraints.txt

# Install NumPy <2.0 first (with constraint applied)
RUN bash -c "eval \"\$(${DOCKER_USER_HOME}/miniconda3/bin/conda shell.bash hook)\" && \
    conda activate isaaclab && \
    pip install 'numpy<2.0'"
```

**Why**:
- Creates a constraints file that pip respects during ALL installations
- PIP_CONSTRAINT environment variable applies constraints globally
- Prevents ANY package (Isaac Lab, extensions, additional packages) from upgrading NumPy to 2.x
- More robust than simple pinning which can be overridden by dependency resolution

**Verification**: Added automated check at Dockerfile:241-246 that fails build if NumPy 2.x detected

### Fix 2: Use Conda Environment for Extension Installation

**Location**: `docker/Dockerfile:201-207`

```dockerfile
# Install Colibri G1 extension in editable mode
# CRITICAL: Use conda environment activation to ensure proper installation
RUN bash -c "eval \"\$(${DOCKER_USER_HOME}/miniconda3/bin/conda shell.bash hook)\" && \
    conda activate isaaclab && \
    cd /workspace/uniandes_g1_colibri/digital_twin_colibri_g1 && \
    pip install -e source/digital_twin_colibri_g1"
```

**Why**: Ensures the extension is installed in the conda environment, not the system Python.

### Fix 3: Use Conda Environment for Additional Packages

**Location**: `docker/Dockerfile:224-228`

```dockerfile
# Install additional Python packages
RUN bash -c "eval \"\$(${DOCKER_USER_HOME}/miniconda3/bin/conda shell.bash hook)\" && \
    conda activate isaaclab && \
    pip install --no-cache-dir opencv-python matplotlib hydra-core"
```

**Why**: Maintains consistency by installing all packages in the same conda environment.

### Fix 4: Configure PYTHONPATH for Extension Discovery

**Location**: `docker/Dockerfile:246-248`

```dockerfile
# CRITICAL: Add Isaac Lab and extension to PYTHONPATH
ENV PYTHONPATH="${ISAACLAB_PATH}/source/isaaclab:${ISAACLAB_PATH}/source/isaaclab_tasks:${ISAACLAB_PATH}/source/isaaclab_assets:/workspace/uniandes_g1_colibri/digital_twin_colibri_g1/source:${PYTHONPATH}"
```

**Why**: Ensures Python can find the extension module and all Isaac Lab dependencies.

### Fix 5: Update Entrypoint to Use Conda Python Directly

**Location**: `docker/entrypoint.sh:30-42`

```bash
# Verify conda environment is active
echo "[INFO] Python location: $(which python)"
echo "[INFO] Checking digital_twin_colibri_g1 installation..."
python -c "import digital_twin_colibri_g1; print('[SUCCESS] Extension found')" || echo "[WARNING] Extension not found"

# Use Python directly from conda environment
exec python sim2sim/isaac_colibri_g1_ros2.py
```

**Why**:
- Uses conda Python with all dependencies properly installed
- Provides diagnostic output to verify extension installation
- Avoids complexity of isaaclab.sh wrapper script

### Fix 6: Automated NumPy Version Verification (NEW - 2025-11-18)

**Location**: `docker/Dockerfile:241-246`

```dockerfile
# CRITICAL: Verify NumPy version is <2.0 (fail build if not)
RUN bash -c "eval \"\$(${DOCKER_USER_HOME}/miniconda3/bin/conda shell.bash hook)\" && \
    conda activate isaaclab && \
    python -c 'import numpy; assert numpy.__version__.startswith(\"1.\"), f\"NumPy version {numpy.__version__} is not 1.x! Build failed.\"' && \
    echo \"✓ NumPy version verified: \$(python -c 'import numpy; print(numpy.__version__)')\" "
```

**Why**:
- Catches any accidental NumPy upgrades during the build process
- Fails build early if NumPy 2.x is detected
- Provides clear error message if constraint enforcement failed
- Gives confidence that the final image has correct NumPy version

## Testing Instructions

### 1. Rebuild Docker Image

```bash
cd /home/jamendez/Documents/uniandes/MISIS/thesis/uniandes_g1_colibri/digital_twin_colibri_g1

# Stop existing container
docker-compose -f docker/docker-compose.yaml down

# Rebuild with fixes
docker-compose -f docker/docker-compose.yaml build --no-cache

# Run
docker-compose -f docker/docker-compose.yaml up isaac_sim_ros2
```

### 2. Verify NumPy Version

```bash
docker exec -it colibri_g1_sim2sim bash -c "conda activate isaaclab && python -c 'import numpy; print(numpy.__version__)'"
```

**Expected Output**: `1.26.4` (or any 1.x version, NOT 2.x)

### 3. Verify Extension Installation

```bash
docker exec -it colibri_g1_sim2sim bash -c "conda activate isaaclab && python -c 'import digital_twin_colibri_g1; print(digital_twin_colibri_g1.__file__)'"
```

**Expected Output**: `/workspace/uniandes_g1_colibri/digital_twin_colibri_g1/source/digital_twin_colibri_g1/__init__.py`

### 4. Check for Import Errors

Monitor the container logs for:
- ✅ No "ValueError: numpy.dtype size changed" errors
- ✅ No "ModuleNotFoundError: No module named 'digital_twin_colibri_g1'" errors
- ✅ Extension loads successfully
- ✅ Simulation starts without crashes

## Key Learnings

1. **Isaac Sim Version Compatibility**: Isaac Sim 4.5.0 requires NumPy <2.0 due to bundled scipy compilation
2. **Pip Constraints Essential**: Simple version pinning isn't enough - use PIP_CONSTRAINT environment variable to enforce constraints across ALL pip operations
3. **Dependency Resolution Override**: Isaac Lab's installation can upgrade packages despite initial pins - constraints file prevents this
4. **Conda Isolation**: Using conda environment properly isolates dependencies from Isaac Sim's bundled packages
5. **PYTHONPATH Critical**: Extensions outside Isaac Lab directory MUST be added to PYTHONPATH
6. **Direct Python Execution**: Simpler to use conda Python directly rather than through wrapper scripts
7. **Build-Time Verification**: Adding automated version checks during build catches issues early

## References

- Isaac Sim 4.5.0 NumPy compatibility: https://docs.omniverse.nvidia.com/isaacsim/latest/release_notes.html
- Isaac Lab Docker guide: https://isaac-sim.github.io/IsaacLab/main/source/deployment/docker.html
- isaac-go2-ros2 reference implementation: Working Docker setup with similar architecture
- NumPy 2.0 migration guide: https://numpy.org/doc/stable/numpy_2_0_migration_guide.html
