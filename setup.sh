#!/usr/bin/env bash
# ==============================================================================
# 🩸 Phyrexian Forge - One-Click Setup Script (Linux & macOS)
# ==============================================================================

set -e

# Terminal colors
BOLD='\033[1m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_DIR"

echo -e "${BOLD}${CYAN}=====================================================${NC}"
echo -e "${BOLD}${CYAN}🩸 Phyrexian Forge - Environment & Project Setup${NC}"
echo -e "${BOLD}${CYAN}=====================================================${NC}"

# 1. Check Python
echo -e "\n${BOLD}[1/6] Checking Python installation...${NC}"
PYTHON_BIN=""
if command -v python3 &> /dev/null; then
    PYTHON_BIN="python3"
elif command -v python &> /dev/null; then
    PYTHON_BIN="python"
else
    echo -e "${RED}❌ Error: Python 3 is not installed or not in PATH.${NC}"
    echo "Please install Python 3.11 - 3.13 from https://www.python.org/"
    exit 1
fi

PY_VERSION=$($PYTHON_BIN -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "${GREEN}✓ Found Python $PY_VERSION ($($PYTHON_BIN --version))${NC}"

# 2. Check Poetry
echo -e "\n${BOLD}[2/6] Checking Poetry package manager...${NC}"
if ! command -v poetry &> /dev/null; then
    echo -e "${YELLOW}⚠️ Poetry is not installed in PATH.${NC}"
    echo "Attempting to install Poetry via official installer..."
    curl -sSL https://install.python-poetry.org | $PYTHON_BIN -
    export PATH="$HOME/.local/bin:$PATH"
    if ! command -v poetry &> /dev/null; then
        echo -e "${RED}❌ Could not automatically install Poetry. Please install it manually:${NC}"
        echo "   curl -sSL https://install.python-poetry.org | python3 -"
        echo "   or visit https://python-poetry.org/docs/#installation"
        exit 1
    fi
fi
echo -e "${GREEN}✓ Found Poetry ($(poetry --version))${NC}"

# 3. Check Node.js and npm
echo -e "\n${BOLD}[3/6] Checking Node.js and npm...${NC}"
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Error: Node.js is not installed.${NC}"
    echo "Please install Node.js 18+ from https://nodejs.org/"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo -e "${RED}❌ Error: npm is not installed.${NC}"
    echo "Please install npm from https://nodejs.org/"
    exit 1
fi

NODE_VERSION=$(node -v)
NPM_VERSION=$(npm -v)
echo -e "${GREEN}✓ Found Node.js $NODE_VERSION and npm $NPM_VERSION${NC}"

# 4. Environment (.env) Setup
echo -e "\n${BOLD}[4/6] Setting up environment configuration (.env)...${NC}"
if [ ! -f .env ]; then
    if [ -f .env_example ]; then
        cp .env_example .env
        echo -e "${GREEN}✓ Created .env from .env_example${NC}"
    else
        touch .env
        echo "GEMINI_API_KEY=" >> .env
        echo -e "${GREEN}✓ Created new .env file${NC}"
    fi

    # Generate a random secret key for JWT if not present
    RANDOM_KEY=$($PYTHON_BIN -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32 2>/dev/null || echo "dev_jwt_secret_phyrexian_forge_$(date +%s)")
    if ! grep -q "JWT_SECRET_KEY" .env; then
        echo "JWT_SECRET_KEY=$RANDOM_KEY" >> .env
    fi
    echo -e "${CYAN}ℹ️  Generated secure JWT_SECRET_KEY in .env${NC}"
else
    echo -e "${GREEN}✓ Existing .env file found (skipping overwrite)${NC}"
fi

# Ensure required runtime asset directories exist
mkdir -p data/portraits data/audio data/modules

# 5. Backend Dependencies (Poetry)
echo -e "\n${BOLD}[5/6] Installing Backend Dependencies (Poetry)...${NC}"
poetry install --no-interaction

# Set up git pre-commit hooks if git is present
if [ -d .git ]; then
    echo "Configuring git pre-commit hooks..."
    poetry run pre-commit install 2>/dev/null || true
fi
echo -e "${GREEN}✓ Backend dependencies installed successfully!${NC}"

# 6. Frontend Dependencies (Angular client)
echo -e "\n${BOLD}[6/6] Installing Frontend Dependencies (npm)...${NC}"
cd "$PROJECT_DIR/client"
if [ -f package-lock.json ]; then
    npm ci --prefer-offline --no-audit || npm install --no-audit
else
    npm install --no-audit
fi
cd "$PROJECT_DIR"
echo -e "${GREEN}✓ Frontend dependencies installed successfully!${NC}"

# Check MongoDB status
echo -e "\n${BOLD}=====================================================${NC}"
echo -e "${BOLD}🔍 Checking MongoDB service status...${NC}"
if command -v nc &> /dev/null && nc -z localhost 27017 2>/dev/null; then
    echo -e "${GREEN}✓ Local MongoDB is reachable on port 27017.${NC}"
elif command -v mongosh &> /dev/null && mongosh --eval "db.adminCommand('ping')" --quiet &>/dev/null; then
    echo -e "${GREEN}✓ Local MongoDB is active.${NC}"
else
    echo -e "${YELLOW}⚠️  Warning: Local MongoDB on port 27017 was not detected.${NC}"
    echo -e "   Make sure MongoDB is running before starting the server:"
    echo -e "   - Linux (systemd):  ${CYAN}sudo systemctl start mongod${NC}"
    echo -e "   - macOS (brew):     ${CYAN}brew services start mongodb-community${NC}"
    echo -e "   - Docker:           ${CYAN}docker run -d -p 27017:27017 --name mongo mongo:latest${NC}"
    echo -e "   - Or configure remote ${CYAN}MONGO_URI${NC} in your ${BOLD}.env${NC} file."
fi

echo -e "\n${BOLD}${GREEN}🎉 Setup completed successfully!${NC}"
echo -e "\nTo start both Backend and Frontend in one go, run:"
echo -e "   ${BOLD}${CYAN}./start.sh${NC}"
echo -e "\nOr run them individually:"
echo -e "   Backend:  ${CYAN}poetry run uvicorn server.main:app --reload --port 8000${NC}"
echo -e "   Frontend: ${CYAN}cd client && npm start${NC}  (http://localhost:4200)"
echo -e "${BOLD}${CYAN}=====================================================${NC}"
