#!/bin/bash

echo "========================================================"
echo "  Personal Finance Calculator"
echo "  Architecture: Python FastAPI + Vanilla JS Frontend"
echo "  Launch Mode: Direct (No Docker, No Node.js)"
echo "========================================================"
echo ""

# ============================================
# Check Python
# ============================================
echo "[1/3] Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 is not installed or not in PATH!"
    echo "Please install Python 3.8+: https://www.python.org/downloads/"
    exit 1
fi

echo "[OK] Python detected"
python3 --version
echo ""

# ============================================
# Install Python dependencies
# ============================================
echo "[2/3] Installing Python dependencies..."
pip3 install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install Python dependencies!"
    exit 1
fi

echo "[OK] Python dependencies installed"
echo ""

# ============================================
# Start the application
# ============================================
echo "[3/3] Starting application..."
echo "========================================================"
echo ""
echo "  Application URL:    http://localhost:8000"
echo "  API Documentation:  http://localhost:8000/docs"
echo "  Health Check:       http://localhost:8000/api/health"
echo ""
echo "  Opening browser in 2 seconds..."
echo "  Press Ctrl+C to stop the server"
echo "========================================================"
echo ""

# Open browser after a short delay (allowing server to start)
sleep 2

# Open browser (works on Linux/Mac)
if command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:8000
elif command -v open &> /dev/null; then
    open http://localhost:8000
fi

# Start FastAPI backend with api.py (includes frontend serving)
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
