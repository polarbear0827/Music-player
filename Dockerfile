# --- Stage 1: Builder (Compilation) ---
FROM python:3.10-slim-bullseye AS builder

# Set build-time environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    python3-dev \
    libsodium-dev \
    libopus-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies into a wheels directory
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt


# --- Stage 2: Runtime (Final Image) ---
FROM python:3.10-slim-bullseye

# Set runtime environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONOPTIMIZE=1
ENV PATH="/home/botuser/.local/bin:${PATH}"

# Install only runtime-critical system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    libopus0 \
    libsodium23 \
    && rm -rf /var/lib/apt/lists/*

# Create a non-privileged user
RUN useradd -m botuser
USER botuser
WORKDIR /home/botuser/app

# Copy wheels from builder and install them
COPY --chown=botuser:botuser --from=builder /app/wheels /tmp/wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --user /tmp/wheels/* && \
    rm -rf /tmp/wheels

# Copy application code (ensure permissions for botuser)
COPY --chown=botuser:botuser . .

# Ensure data directory exists for persistence
RUN mkdir -p data && chmod 755 data

# Run the bot
CMD ["python", "main.py"]
