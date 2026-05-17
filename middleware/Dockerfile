FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for DSP and SDR tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libfftw3-dev \
    libusb-1.0-0-dev \
    cmake \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY mocks/ ./mocks/
COPY tests/ ./tests/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5555/health')" || exit 1

CMD ["python", "src/main.py"]
