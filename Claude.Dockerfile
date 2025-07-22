# Dockerfile for Claude Code with Vertex AI support
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including Node.js
RUN apt-get update && apt-get install -y \
    git \
    curl \
    docker.io \
    sudo \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 18+
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs

# Install Google Cloud SDK
RUN curl https://sdk.cloud.google.com | bash
ENV PATH="/root/google-cloud-sdk/bin:${PATH}"

# Install Python dependencies for Vertex AI
RUN pip install --upgrade pip
RUN pip install "anthropic[vertex]" google-cloud-aiplatform

# Install Claude Code via npm
RUN npm install -g @anthropic-ai/claude-code

# Create a non-root user for security
RUN useradd -m -s /bin/bash claude
RUN usermod -aG docker claude
RUN echo 'claude ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

# Set up authentication helper for git
RUN git config --global credential.helper store

# Create workspace directory and set ownership
RUN mkdir -p /workspace && chown claude:claude /workspace

# Switch to claude user
USER claude
WORKDIR /workspace

# Create a script to fix permissions on startup
USER root
RUN echo '#!/bin/bash\n\
# Fix ownership of workspace files to claude user\n\
chown -R claude:claude /workspace 2>/dev/null || true\n\
# Switch to claude user and execute command\n\
exec sudo -u claude "$@"' > /usr/local/bin/fix-permissions.sh && \
    chmod +x /usr/local/bin/fix-permissions.sh

USER claude

# Set default environment variables
ENV CLAUDE_CODE_USE_VERTEX=1
ENV CLOUD_ML_REGION=us-east5

# Default command
CMD ["claude", "--help"]
