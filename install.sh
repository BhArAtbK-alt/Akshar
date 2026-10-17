#!/bin/bash
# ============================================================
# Akshar — अक्षर — Installer
# Universal Real-Time Linguistic Overlay
# ============================================================
# This script installs Akshar as a system-wide IBus input method.
# Run with: chmod +x install.sh && ./install.sh
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

INSTALL_DIR="/usr/share/akshar"
IBUS_COMPONENT_DIR="/usr/share/ibus/component"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}  ${BOLD}अक्षर — Akshar Installer${NC}                    ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}  Universal Real-Time Linguistic Overlay       ${CYAN}║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ---- Check for root privileges ---- #
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}⚠  This script requires sudo privileges to install system-wide.${NC}"
    echo -e "   Re-running with sudo..."
    exec sudo "$0" "$@"
fi

# ---- Check dependencies ---- #
echo -e "${BOLD}[1/5]${NC} Checking dependencies..."

check_dependency() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "  ${RED}✗${NC} $1 not found"
        return 1
    else
        echo -e "  ${GREEN}✓${NC} $1 found"
        return 0
    fi
}

MISSING=0

check_dependency "ibus" || MISSING=1
check_dependency "python3" || MISSING=1

# Check for Python GObject bindings
if python3 -c "import gi; gi.require_version('IBus', '1.0')" 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} python3-gi + IBus bindings found"
else
    echo -e "  ${RED}✗${NC} python3-gi or IBus bindings not found"
    MISSING=1
fi

if [ "$MISSING" -eq 1 ]; then
    echo ""
    echo -e "${YELLOW}Installing missing dependencies...${NC}"
    
    # Detect package manager
    if command -v apt &> /dev/null; then
        apt update -qq
        apt install -y ibus python3-gi gir1.2-ibus-1.0
    elif command -v dnf &> /dev/null; then
        dnf install -y ibus python3-gobject
    elif command -v pacman &> /dev/null; then
        pacman -Sy --noconfirm ibus python-gobject
    else
        echo -e "${RED}Could not detect package manager. Please install manually:${NC}"
        echo "  - ibus"
        echo "  - python3-gi (PyGObject)"
        echo "  - gir1.2-ibus-1.0 (IBus GObject introspection)"
        exit 1
    fi
    
    echo -e "  ${GREEN}✓${NC} Dependencies installed"
fi

# ---- Remove previous installation ---- #
echo -e "${BOLD}[2/5]${NC} Removing previous installation (if any)..."
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    echo -e "  ${GREEN}✓${NC} Old installation removed"
else
    echo -e "  ${GREEN}✓${NC} No previous installation found"
fi

# ---- Copy files ---- #
echo -e "${BOLD}[3/5]${NC} Installing Akshar to ${INSTALL_DIR}..."

mkdir -p "$INSTALL_DIR"
cp -r "$SCRIPT_DIR/engine" "$INSTALL_DIR/"
cp -r "$SCRIPT_DIR/languages" "$INSTALL_DIR/"   # includes languages/lexicon/
find "$INSTALL_DIR" -name "__pycache__" -type d -prune -exec rm -rf {} +

# Make the main engine executable
chmod +x "$INSTALL_DIR/engine/main.py" "$INSTALL_DIR/engine/cli.py"

# `akshar-cli` command
cat > /usr/local/bin/akshar-cli <<'WRAP'
#!/bin/sh
exec python3 /usr/share/akshar/engine/cli.py "$@"
WRAP
chmod +x /usr/local/bin/akshar-cli

echo -e "  ${GREEN}✓${NC} Engine and language files copied"

# ---- Install IBus component ---- #
echo -e "${BOLD}[4/5]${NC} Registering with IBus..."

mkdir -p "$IBUS_COMPONENT_DIR"
# one engine per language, generated from languages/*.json
python3 "$SCRIPT_DIR/tools/gen_ibus_xml.py" "$IBUS_COMPONENT_DIR/akshar.xml" "$INSTALL_DIR/engine/main.py" >/dev/null

echo -e "  ${GREEN}✓${NC} IBus component registered"

# ---- Create user config directory ---- #
echo -e "${BOLD}[5/5]${NC} Setting up user configuration..."

REAL_USER="${SUDO_USER:-$USER}"
REAL_HOME=$(eval echo "~$REAL_USER")
CONFIG_DIR="$REAL_HOME/.config/akshar"

mkdir -p "$CONFIG_DIR/logs"
chown -R "$REAL_USER:$REAL_USER" "$CONFIG_DIR"

echo -e "  ${GREEN}✓${NC} Config directory created at $CONFIG_DIR"

# ---- Restart IBus ---- #
echo ""
echo -e "${BOLD}Restarting IBus daemon...${NC}"
if [ -n "$SUDO_USER" ]; then
    su - "$SUDO_USER" -c "ibus restart" 2>/dev/null || true
else
    ibus restart 2>/dev/null || true
fi
echo -e "  ${GREEN}✓${NC} IBus restarted"

# ---- Done! ---- #
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║${NC}  ${BOLD}✓ Akshar installed successfully!${NC}             ${GREEN}║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}How to activate:${NC}"
echo -e "  1. Go to ${CYAN}Settings → Region & Language → Input Sources${NC}"
echo -e "  2. Click ${CYAN}+ Add${NC} → search for ${CYAN}'Akshar'${NC}"
echo -e "  3. Add ${CYAN}'Akshar — <your language>'${NC} (one entry per language), or the all-in-one ${CYAN}'Akshar — Transliteration'${NC}"
echo ""
echo -e "  ${BOLD}Keyboard shortcuts:${NC}"
echo -e "  • ${CYAN}Super+Space${NC}  — Switch to Akshar input method"
echo -e "  • ${CYAN}F12${NC}          — Toggle transliteration ON/OFF"
echo -e "  • ${CYAN}F11${NC}          — Cycle through languages"
echo -e "  • ${CYAN}F10${NC}          — Transliterate (sounds) ⇄ Translate (meaning)"
echo -e "  • ${CYAN}Tab / Ctrl+1..9${NC} — Choose among alternate spellings"
echo -e "  • ${CYAN}akshar-cli${NC}    — Test from the terminal"
echo ""
echo -e "  ${BOLD}Supported languages:${NC}"
for f in "$INSTALL_DIR/languages/"*.json; do
    LANG_NAME=$(python3 -c "import json; print(json.load(open('$f'))['name'])" 2>/dev/null || echo "Unknown")
    echo -e "  • ${CYAN}$LANG_NAME${NC}"
done
echo ""
