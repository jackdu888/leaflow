FROM python:3.9-slim

# Install system dependencies
# Switched to chromium/chromium-driver to avoid runtime download issues
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    ca-certificates \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV RUNNING_IN_DOCKER=true
ENV PORT=8080

# Configure Chrome/Chromedriver paths for the python script
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Expose port
EXPOSE 8080

# Run the FastAPI app with python to use PORT env var
CMD ["python", "web/app.py"]
