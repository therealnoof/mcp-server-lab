# Instructor Guide — SOC Analyst AI Workshop
## Phase 1: Single Agent with MCP Tools

> **This guide is for the instructor/lab administrator only.**
> Complete all steps BEFORE students arrive.
> Students begin at the [Student Guide](STUDENT_GUIDE.md).

---

## Hardware Requirements

### Minimum Per Lab Node (Single Student)

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU | NVIDIA T4 (16GB VRAM) | NVIDIA T4 or A10G (24GB VRAM) |
| CPU | 4 cores | 8 cores |
| RAM | 16 GB | 32 GB |
| Disk | 40 GB free | 60 GB free |
| Network | Internet access during setup | Internet access during setup |

> **Why 40GB disk?** The llama3.1:8b model download is ~4.7GB, Docker images
> add ~3GB, and OS + swap overhead accounts for the rest. Tight on space = failed
> model downloads mid-class.

### Shared Node Option (Multiple Students, 1 GPU Server)

If you have one powerful GPU node and multiple students:

| Component | Requirement |
|-----------|-------------|
| GPU | 1x A100 (80GB) or 2x T4 (16GB each) |
| CPU | 16+ cores |
| RAM | 64 GB |
| Disk | 100 GB free |
| Network | Gigabit LAN between students and server |

In shared mode, students each run their own agent and mcp-server containers,
but point to a single shared Ollama instance. Update `OLLAMA_URL` in each
student's `docker-compose.yml` to the shared server's IP address.

### GPU VRAM Usage by Model

| Model | VRAM Required | T4 (16GB) | Notes |
|-------|--------------|-----------|-------|
| llama3.1:8b | ~6 GB | ✅ Comfortable | **Recommended for lab** |
| llama3.1:13b | ~10 GB | ✅ Fits | Better reasoning quality |
| mistral:7b | ~5 GB | ✅ Comfortable | Faster inference |
| llama3.1:70b | ~42 GB | ❌ Too large | Needs multi-GPU setup |

---

## Operating System Requirements

This guide targets **Ubuntu 22.04 LTS** (recommended) or **Ubuntu 20.04 LTS**.
Red Hat / CentOS equivalents are noted where commands differ.

Verify your OS version:
```bash
cat /etc/os-release
```

---

## Step 1: System Updates

Always update before installing dependencies to avoid version conflicts.

```bash
sudo apt-get update && sudo apt-get upgrade -y
```

---

## Step 2: Install Core Utilities

These are basic tools required by later installation steps.

```bash
sudo apt-get install -y \
    curl \
    wget \
    git \
    ca-certificates \
    gnupg \
    lsb-release \
    software-properties-common \
    apt-transport-https \
    unzip
```

---

## Step 3: Install NVIDIA Drivers

Check if drivers are already installed:
```bash
nvidia-smi
```

If you see a GPU status table, skip to Step 4. If you get `command not found`, install drivers:

```bash
# Add NVIDIA driver repository and auto-install
sudo apt-get install -y ubuntu-drivers-common
sudo ubuntu-drivers autoinstall

# Reboot to load the driver
sudo reboot
```

After reboot, verify the driver loaded:
```bash
nvidia-smi
```

Expected output (numbers vary by GPU):
```
+-----------------------------------------------------------------------------+
| NVIDIA-SMI 535.x    Driver Version: 535.x    CUDA Version: 12.x            |
|-------------------------------+----------------------+----------------------+
| GPU  Name       Persistence-M | Bus-Id        Disp.A | Volatile Uncorr. ECC |
|   0  Tesla T4           Off   | 00000000:00:1E.0 Off |                    0 |
+-------------------------------+----------------------+----------------------+
```

> **Red Hat / CentOS equivalent:**
> ```bash
> sudo dnf install -y epel-release
> sudo dnf config-manager --add-repo \
>     https://developer.download.nvidia.com/compute/cuda/repos/rhel8/x86_64/cuda-rhel8.repo
> sudo dnf module install -y nvidia-driver:latest-dkms
> sudo reboot
> ```

---

## Step 4: Install Docker Engine

Docker runs each lab component in an isolated container.

```bash
# Remove any old Docker versions
sudo apt-get remove -y docker docker-engine docker.io containerd runc

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine and Docker Compose plugin
sudo apt-get update
sudo apt-get install -y \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin

# Start and enable Docker service
sudo systemctl start docker
sudo systemctl enable docker

# Allow your user to run Docker without sudo
# NOTE: You must log out and log back in (or run newgrp below) for this to take effect
sudo usermod -aG docker $USER
newgrp docker
```

Verify Docker is working:
```bash
docker run hello-world
# Expected: "Hello from Docker!"

docker compose version
# Expected: Docker Compose version v2.x.x
```

> **Red Hat / CentOS equivalent:**
> ```bash
> sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
> sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
> sudo systemctl start docker && sudo systemctl enable docker
> sudo usermod -aG docker $USER
> ```

---

## Step 5: Install NVIDIA Container Toolkit

This allows Docker containers to access the GPU.
Without this, Ollama won't see the T4 and will fall back to CPU — 10-20x slower.

```bash
# Add NVIDIA Container Toolkit repository
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Configure Docker to use the NVIDIA runtime
sudo nvidia-ctk runtime configure --runtime=docker

# Restart Docker for the runtime change to take effect
sudo systemctl restart docker
```

Verify Docker can see the GPU:
```bash
docker run --rm --gpus all nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi
```

You should see the same GPU table as Step 3, but now running inside a container.
If this works, GPU passthrough is confirmed and the lab will work.

> **Red Hat / CentOS equivalent:**
> ```bash
> curl -s -L https://nvidia.github.io/libnvidia-container/stable/rpm/nvidia-container-toolkit.repo \
>     | sudo tee /etc/yum.repos.d/nvidia-container-toolkit.repo
> sudo dnf install -y nvidia-container-toolkit
> sudo nvidia-ctk runtime configure --runtime=docker
> sudo systemctl restart docker
> ```

---

## Step 6: Install Python 3.11 (Optional)

The lab runs entirely inside Docker containers, so Python on the host is not
required. However, it's useful if students want to run scripts directly
for debugging or experimentation outside Docker.

```bash
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv python3.11-dev python3-pip

# Verify
python3.11 --version
# Expected: Python 3.11.x
```

---

## Step 7: Pre-pull Docker Images and the LLM Model

**Do this before students arrive.** The llama3.1:8b model is ~4.7GB.
Downloading during class wastes time and risks failure on slow connections.

```bash
# Pull base images used by docker-compose
docker pull ollama/ollama:latest
docker pull python:3.11-slim

# Start Ollama temporarily to pull the model into a named volume
docker run -d --gpus all --name ollama-setup \
    -v ollama_models:/root/.ollama \
    -p 11434:11434 \
    ollama/ollama:latest

# Wait for Ollama to start (~15 seconds), then pull the model
sleep 15
docker exec ollama-setup ollama pull llama3.1:8b

# Confirm the model downloaded successfully
docker exec ollama-setup ollama list
# Expected output includes: llama3.1:8b

# Clean up the temporary container (the model stays in the named volume)
docker stop ollama-setup && docker rm ollama-setup
```

---

## Step 8: Distribute Lab Files to Students

The lab repo has been cloned to each student machine at `/home/ubuntu/mcp-server-lab`.

```bash
# If you need to re-clone on a student machine:
git clone https://github.com/therealnoof/mcp-server-lab.git /home/ubuntu/mcp-server-lab
```

---

## Instructor Pre-Lab Verification Checklist

Run this on each lab node before students begin. All checks must pass.

```bash
echo "=== 1. NVIDIA Driver ===" && nvidia-smi | head -5
echo ""
echo "=== 2. Docker ===" && docker --version
echo ""
echo "=== 3. Docker Compose ===" && docker compose version
echo ""
echo "=== 4. GPU Access in Docker ===" && \
    docker run --rm --gpus all nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi | head -5
echo ""
echo "=== 5. Ollama Model Cache ===" && \
    docker run --rm -v ollama_models:/root/.ollama ollama/ollama:latest ollama list
echo ""
echo "=== 6. Disk Space ===" && df -h / | tail -1
```

Common failure resolutions:

| Failing Check | Likely Cause | Fix |
|---------------|-------------|-----|
| `nvidia-smi` not found | Driver not installed | Redo Step 3 |
| GPU not visible in Docker | Container toolkit not configured | Redo Step 5, restart Docker |
| Ollama model missing | Step 7 was skipped | Redo Step 7 |
| Disk < 10GB free | Insufficient space | `docker system prune` to clear old images |

---

## Known Fixes and Operational Notes

These issues were discovered during initial deployment and are already fixed in the current codebase. They're documented here so instructors can troubleshoot forks or older clones.

### 1. MCP Server Healthcheck Fails

**Problem:** The `docker-compose.yml` healthcheck used `curl`, but the `python:3.11-slim` base image doesn't include curl. The container was always marked unhealthy.

**Fix:** Changed the healthcheck to use Python's built-in `urllib` instead of curl.

### 2. FastMCP `.run()` API Mismatch

**Problem:** `server.py` called `mcp.run(host=..., port=...)`, but the installed MCP SDK version expects `host` and `port` as constructor arguments to `FastMCP()`, not as `run()` kwargs.

**Fix:** Moved `host` and `port` into the `FastMCP()` constructor call.

### 3. Model-Puller Entrypoint Override

**Problem:** The `model-puller` service passed a shell command (`sh -c "..."`) to the Ollama image, but the Ollama image's entrypoint is `ollama`, so Docker ran `ollama sh -c "..."` instead of the intended shell command.

**Fix:** Added `entrypoint: ["sh", "-c"]` to the model-puller service in `docker-compose.yml`.

### 4. Agent Crashes After Server Reboot

**Problem:** After a server reboot, Docker restarts all containers simultaneously without re-evaluating `depends_on` health conditions. The agent would crash because Ollama wasn't ready yet.

**Fix:** Added a startup polling loop in `agent.py` that waits for both the Ollama server and the model to be available before proceeding.

### 5. LLM Describes Tools Instead of Calling Them

**Problem:** `llama3.1:8b` would describe tool calls as text/JSON in its response instead of actually invoking them via the Ollama tool-calling API. The agent saw no `tool_calls` and stopped immediately.

**Fix:** Rewrote the system prompt to explicitly instruct the model to use the tool-calling mechanism rather than writing out JSON.

---

## Post-Lab Teardown

After the lab session is complete, clean up the environment:

```bash
# Stop and remove all lab containers
docker compose down

# Remove the Ollama model volume (frees ~5GB)
docker volume rm ollama_models

# Remove built images
docker compose down --rmi local

# Full cleanup: remove all unused Docker data (images, volumes, networks)
docker system prune -a --volumes -f
```

> **Warning:** `docker system prune -a --volumes` removes ALL unused Docker data,
> not just lab resources. Only run this on dedicated lab nodes.

---

When setup is complete, hand students the [Student Guide](STUDENT_GUIDE.md).
