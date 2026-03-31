FROM python:3.10-slim

# Install system dependencies (ffmpeg is required for Discord audio streaming)
RUN apt-get update && \
    apt-get install -y ffmpeg curl && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Prevent python from buffering stdout and stderr
ENV PYTHONUNBUFFERED=1

# Run the bot
CMD ["python", "main.py"]
