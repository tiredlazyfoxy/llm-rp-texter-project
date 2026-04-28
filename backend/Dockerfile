FROM python:3.13

WORKDIR /app

# Install dependencies
COPY backend/pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code
COPY backend/ .

# Create data directories
RUN mkdir -p /app/data

EXPOSE 8085

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8085"]
