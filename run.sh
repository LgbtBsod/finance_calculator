#!/bin/bash

echo "========================================================"
echo "  Personal Finance Calculator"
echo "  Architecture: Python FastAPI + TypeScript OpenUI5"
echo "  Launch Mode: Direct (No Docker)"
echo "========================================================"
echo ""

# ============================================
# Check Python
# ============================================
echo "[1/4] Checking Python..."
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
echo "[2/4] Installing Python dependencies..."
pip3 install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install Python dependencies!"
    exit 1
fi

echo "[OK] Python dependencies installed"
echo ""

# ============================================
# Check Node.js
# ============================================
echo "[3/4] Checking Node.js..."
if ! command -v node &> /dev/null; then
    echo "[ERROR] Node.js is not installed or not in PATH!"
    echo "Please install Node.js: https://nodejs.org/"
    exit 1
fi

echo "[OK] Node.js detected"
node --version
echo ""

# ============================================
# Install Node.js dependencies
# ============================================
echo "Installing Node.js dependencies..."
npm install

if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install Node.js dependencies!"
    exit 1
fi

echo "[OK] Node.js dependencies installed"
echo ""

# ============================================
# Start the application
# ============================================
echo "[4/4] Starting application..."
echo "========================================================"
echo ""
echo "  Backend (FastAPI): http://localhost:8000"
echo "  API Documentation: http://localhost:8000/docs"
echo "  Health Check:      http://localhost:8000/api/health"
echo ""
echo "  Press Ctrl+C to stop the server"
echo "========================================================"
echo ""

# Open browser (works on Linux/Mac)
if command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:8000
elif command -v open &> /dev/null; then
    open http://localhost:8000
fi

# Start FastAPI backend
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
