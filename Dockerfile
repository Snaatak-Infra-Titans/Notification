FROM python:3.11-slim-bookworm

LABEL authors="Opstree Solution" \
      application="Notification API" \
      version="v0.1.0"

WORKDIR /app

# Install runtime packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        netcat-openbsd && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

EXPOSE 8085

ENTRYPOINT ["/app/entrypoint.sh"]