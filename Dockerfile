# ═══════════════════════════════════════════════════════════════
#  Dockerfile — Python FastAPI Backend + Node.js Frontend Build
#  Multi-stage build for optimal image size
# ═══════════════════════════════════════════════════════════════

# ───────────────────────────────────────────────────────────────
# Stage 1: Build Frontend (TypeScript + Vite)
# ───────────────────────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source code
COPY src ./src
COPY index.html ./
COPY tsconfig.json ./
COPY vite.config.ts ./

# Build production bundle
RUN npm run build

# ───────────────────────────────────────────────────────────────
# Stage 2: Python Backend with Built Frontend
# ───────────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY api.py .
COPY database.py .
COPY models.py .
COPY config.py .
COPY calculator.py .
COPY prod_calendar.py .

# Copy built frontend from stage 1
COPY --from=frontend-builder /app/frontend/dist ./dist

# Copy index.html to serve frontend
COPY --from=frontend-builder /app/frontend/dist/index.html ./index.html

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Run application
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
