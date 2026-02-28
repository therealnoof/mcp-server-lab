# SOC Analyst AI — Agentic AI Workshop

A hands-on lab that builds a single AI agent acting as a junior SOC analyst. The agent autonomously pulls security alerts, checks IP reputations against threat intelligence, geolocates suspicious IPs, and writes a structured threat assessment — all without you directing each step. It uses **MCP (Model Context Protocol)** for tool discovery, **Ollama** for local LLM inference on a GPU, and a simple Python agent loop that ties everything together.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        Docker Network                          │
│                                                                │
│   ┌─────────────┐   A) "What tools exist?"  ┌─────────────┐  │
│   │             │ ──────────────────────►    │             │  │
│   │    AGENT    │                            │ MCP SERVER  │  │
│   │  (agent.py) │ ◄──────────────────────    │ (server.py) │  │
│   │             │   B) Tool results          │             │  │
│   └──────┬──────┘                            └─────────────┘  │
│          │                                    Exposes tools:   │
│          │ C) "Which tool should I           - get_recent_alerts
│          │    call next?"                    - check_ip_reputation
│          ▼                                   - lookup_ip_geolocation
│   ┌─────────────┐                            - get_alert_details  │
│   │   OLLAMA    │                                                │
│   │ llama3.1:8b │  ← The LLM "brain" — runs on your T4 GPU     │
│   │  (T4 GPU)   │                                                │
│   └─────────────┘                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
mcp-server-lab/
├── docker-compose.yml     ← Wires the three services together
├── mcp_server/
│   └── server.py          ← Tool definitions (MCP server)
└── agent/
    ├── agent.py           ← Agent brain: MCP client + LLM loop
    └── test_tools.py      ← Tests tools independently
```

---

## Prerequisites

- NVIDIA GPU (T4 16GB+ recommended)
- Docker Engine + Docker Compose v2
- NVIDIA Container Toolkit (GPU passthrough)
- ~40GB free disk space

See the [Instructor Guide](INSTRUCTOR_GUIDE.md) for full hardware specs and step-by-step setup.

---

## Quick Start

```bash
git clone https://github.com/therealnoof/mcp-server-lab.git
cd mcp-server-lab
docker compose up -d
docker compose run --rm agent python agent.py
```

---

## Guides

| Guide | Audience | Contents |
|-------|----------|----------|
| [Instructor Guide](INSTRUCTOR_GUIDE.md) | Lab admin / instructor | Hardware requirements, OS setup, driver installation, Docker + NVIDIA toolkit, model pre-pull, verification checklist, known fixes, teardown |
| [Student Guide](STUDENT_GUIDE.md) | Workshop participants | Architecture overview, lab walkthrough, 4 hands-on exercises, troubleshooting |

---

## Phase Roadmap

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1** | Single agent with MCP tools (this repo) | Available |
| **Phase 2** | Multi-agent orchestration with A2A protocol | Coming soon |
| **Phase 3** | Security hardening — AI gateways, guardrails, prompt injection defenses | Planned |
