#!/bin/bash
set -e

echo "========================================================"
echo "  Personal Finance Calculator"
echo "  Architecture: Python FastAPI + React (TypeScript)"
echo "========================================================"
echo ""

# ============================================
# Check Python
# ============================================
echo "[1/6] Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 is not installed or not in PATH!"
    echo "Please install Python 3.10+: https://www.python.org/downloads/"
    exit 1
fi
echo "[OK] Python detected"
python3 --version
echo ""

# ============================================
# Create virtual environment if needed
# ============================================
echo "[2/6] Setting up Python Virtual Environment..."
if [ ! -d "venv" ]; then
    echo "Creating venv folder..."
    python3 -m venv venv
fi
echo "Activating venv..."
source venv/bin/activate
echo "[OK] venv activated"
echo ""

# ============================================
# Run bootstrap script to update dependencies
# ============================================
echo "[3/6] Running bootstrap script..."
python scripts/bootstrap.py || echo "[WARN] Bootstrap script failed, continuing anyway..."
echo ""

# ============================================
# Check for updates from Git
# ============================================
echo "[4/6] Checking for updates..."
python scripts/check_update.py || echo "[WARN] Update check failed, continuing anyway..."
echo ""

# ============================================
# Build frontend (only if not already built)
# ============================================
echo "[5/6] Checking frontend build..."
if [ -f "frontend/dist/index.html" ]; then
    echo "[OK] frontend/dist already built - skipping."
    echo "     Delete frontend/dist to force a rebuild after pulling changes."
else
    echo "Frontend not built yet - building now (requires Node.js 20+)..."
    if ! command -v node &> /dev/null; then
        echo "[ERROR] Node.js is not installed or not in PATH!"
        echo "Please install Node.js 20+: https://nodejs.org/"
        exit 1
    fi
    (cd frontend && npm install && npm run build)
    echo "[OK] Frontend built."
fi
echo ""

# ============================================
# Start the application
# ============================================
echo "[6/6] Starting application..."
echo "========================================================"
echo "  main.py picks a free port automatically and opens"
echo "  your browser once the server is ready."
echo "  Press Ctrl+C to stop the server."
echo "========================================================"
echo ""

python3 main.py
