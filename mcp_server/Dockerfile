# =============================================================
#  MCP Server Dockerfile
# =============================================================
#  Builds the container image for our SOC Tools MCP Server.
#  
#  What it does:
#   1. Starts from a lightweight Python image
#   2. Installs the required Python packages
#   3. Copies our server.py into the container
#   4. Runs the server when the container starts
# =============================================================

# Use Python 3.11 slim - smaller image, faster to download
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Copy requirements first (Docker caches this layer if requirements don't change,
# making rebuilds faster when you only change server.py)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the server code
COPY server.py .

# Tell Docker this container listens on port 8000
EXPOSE 8000

# Command to run when container starts
CMD ["python", "server.py"]
