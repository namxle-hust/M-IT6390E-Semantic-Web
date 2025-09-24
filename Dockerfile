FROM python:3.10-slim

LABEL maintainer="M-IT6390E Semantic Web Project"
LABEL description="Vietnamese DBPedia - Semantic Web Knowledge Base"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Install the package
RUN pip install -e .

# Create necessary directories
RUN mkdir -p data/raw data/rdf data/mappings logs ontology

# Set environment variables
ENV PYTHONPATH=/app
ENV FLASK_APP=src/interfaces/web_interface.py
ENV FLASK_ENV=production

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5000/api/statistics || exit 1

# Expose port
EXPOSE 5000

# Default command
CMD ["python", "src/interfaces/web_interface.py"]