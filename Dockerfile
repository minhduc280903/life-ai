FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for RDKit
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxrender1 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Copy all application files
COPY . .

# Install dependencies (non-editable for production)
RUN pip install --no-cache-dir .

# Expose port
EXPOSE 8000

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
