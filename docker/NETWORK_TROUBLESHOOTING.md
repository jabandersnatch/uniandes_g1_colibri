# Docker Network Bridge Error - Troubleshooting Guide

## ⚠️ QUICK FIX

**Your system needs a reboot!** You're running an old kernel (6.17.7) but modules are installed for the new kernel (6.17.8).

```bash
sudo reboot
```

After reboot, Docker will work. See "Solution 1" below for details.

---

## Error Description

```
failed to create endpoint ... on network bridge: failed to add the host (vethXXXXXXX) <=> sandbox (vethYYYYYYY) pair interfaces: operation not supported
```

This error occurs during Docker build when the `veth` (Virtual Ethernet) kernel module is not loaded.

## Root Cause

The Linux kernel module `veth` is required for Docker to create network namespaces between containers and the host.

### Specific Issue on This System

**Kernel/Module Mismatch**: Running kernel `6.17.7-arch1-1` but modules exist only for `6.17.8-arch1-1`.

This happens when:
1. Kernel was updated via `pacman -Syu`
2. System wasn't rebooted after update
3. Old kernel is running but new modules were installed

Running kernel:
```bash
$ uname -r
6.17.7-arch1-1
```

Available modules:
```bash
$ ls /lib/modules/
6.17.8-arch1-1
```

The veth module DOES exist, but for the newer kernel:
```bash
$ find /lib/modules/6.17.8-arch1-1 -name "*veth*"
/lib/modules/6.17.8-arch1-1/kernel/drivers/net/veth.ko.zst
```

## Diagnosis

Check if veth module is loaded:
```bash
lsmod | grep veth
```

If no output, the module is NOT loaded (this is the problem).

## Solution 1: Reboot to Load New Kernel (RECOMMENDED)

**This is the proper fix for the kernel/module mismatch.**

```bash
# Reboot the system
sudo reboot
```

After reboot:
1. System will boot into kernel 6.17.8-arch1-1
2. The veth module will be available
3. Docker networking will work

Verify after reboot:
```bash
# Check kernel version matches modules
uname -r  # Should show 6.17.8-arch1-1

# Verify veth module can be loaded
sudo modprobe veth
lsmod | grep veth

# Build Docker image
cd /path/to/digital_twin_colibri_g1
docker-compose -f docker/docker-compose.yaml build
```

## Solution 2: Auto-load veth Module (Permanent)

Create a modules-load configuration file:
```bash
sudo sh -c 'echo "veth" > /etc/modules-load.d/veth.conf'
```

Load the module immediately:
```bash
sudo modprobe veth
```

Restart Docker:
```bash
sudo systemctl restart docker
```

This will ensure `veth` is loaded on every boot.

## Solution 3: Alternative Build Network Configuration

If you cannot modify kernel modules, you can try using Docker's host network during build (with limitations):

Edit `docker/Dockerfile` and add this BEFORE any RUN commands:
```dockerfile
# Workaround for veth module issues
FROM isaac_base AS ros2_layer
USER root

# Use host network for all RUN commands (if veth unavailable)
# NOTE: This disables network isolation during build
```

Then build with:
```bash
docker build --network=host -t colibri_g1_ros2:latest -f docker/Dockerfile .
```

**WARNING**: Using `--network=host` during build has security implications and may cause DNS/network conflicts.

## Solution 4: Check Docker Version Compatibility

Your system is running Docker 28.5.2, which is very recent. Some kernel/Docker version combinations may have compatibility issues.

Try using Docker's legacy builder:
```bash
DOCKER_BUILDKIT=0 docker build -t colibri_g1_ros2:latest -f docker/Dockerfile .
```

Or check if there's a Docker/kernel compatibility issue on Arch Linux:
```bash
pacman -Qi docker
uname -r
```

Consider downgrading Docker or upgrading kernel if there's a known incompatibility.

## Solution 5: Use Podman Instead of Docker

Podman is an alternative to Docker that doesn't require daemon privileges:

```bash
# Install podman
sudo pacman -S podman podman-compose

# Build with podman
podman build -t colibri_g1_ros2:latest -f docker/Dockerfile .

# Or use podman-compose
podman-compose -f docker/docker-compose.yaml build
```

Podman handles networking differently and may not have the veth module requirement.

## Verification After Fix

After applying any solution, verify Docker networking works:

```bash
# Test simple container networking
docker run --rm alpine ping -c 2 google.com

# If successful, proceed with build
docker-compose -f docker/docker-compose.yaml build
```

## References

- Docker networking: https://docs.docker.com/network/
- Linux veth documentation: https://man7.org/linux/man-pages/man4/veth.4.html
- Arch Linux modules: https://wiki.archlinux.org/title/Kernel_module
- Docker on Arch: https://wiki.archlinux.org/title/Docker

## Current System Info

- **OS**: Linux 6.17.7-arch1-1 (Arch Linux)
- **Docker**: 28.5.2
- **Docker Compose**: 2.40.3
- **Issue**: veth kernel module not loaded
- **Recommended Fix**: Solution 2 (permanent module auto-load)
