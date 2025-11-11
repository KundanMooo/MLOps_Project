# Use Python 3.12 slim image as base
FROM python:3.12-slim

# Set working directory inside container
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy uv project files first (for better caching)
COPY pyproject.toml .
COPY uv.lock .

# Sync dependencies using uv
RUN uv sync --frozen --no-dev

# Copy your Python files
COPY models.py .
COPY app.py .

# Create directory for temporary file uploads
RUN mkdir -p temp_uploads

# Expose port 8000 for the API
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8000/')" || exit 1

# Run the FastAPI application using uv
# Environment variables should be passed at runtime
CMD ["uv", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]