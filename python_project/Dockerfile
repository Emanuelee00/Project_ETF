FROM python:3.12-slim

WORKDIR /app

# System deps for pandas/openpyxl
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev && rm -rf /var/lib/apt/lists/*

# Install Python dependencies via uv (pyproject.toml / uv.lock)
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy source
COPY . .

# Create required directories
RUN mkdir -p data output logs

EXPOSE 8000

ENV ETF_PORT=8000

CMD ["uv", "run", "python", "src/server.py"]
