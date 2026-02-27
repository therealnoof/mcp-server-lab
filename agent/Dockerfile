# =============================================================
#  Agent Dockerfile
# =============================================================
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent.py .
COPY test_tools.py .

# The agent runs as a loop waiting for work
# For Phase 1 we just run the agent script once
CMD ["python", "agent.py"]
