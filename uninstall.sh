#!/bin/bash
# ============================================================
# Akshar — अक्षर — Uninstaller
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

INSTALL_DIR="/usr/share/akshar"
IBUS_COMPONENT="/usr/share/ibus/component/akshar.xml"

echo ""
echo -e "${YELLOW}${BOLD}Akshar — अक्षर — Uninstaller${NC}"
echo ""

if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}⚠  This script requires sudo privileges.${NC}"
    exec sudo "$0" "$@"
fi

# Remove engine files
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    echo -e "  ${GREEN}✓${NC} Removed $INSTALL_DIR"
else
    echo -e "  ${YELLOW}—${NC} $INSTALL_DIR not found (already removed?)"
fi

rm -f /usr/local/bin/akshar-cli

# Remove IBus component
if [ -f "$IBUS_COMPONENT" ]; then
    rm -f "$IBUS_COMPONENT"
    echo -e "  ${GREEN}✓${NC} Removed IBus component registration"
else
    echo -e "  ${YELLOW}—${NC} IBus component not found (already removed?)"
fi

# Ask about config
REAL_USER="${SUDO_USER:-$USER}"
REAL_HOME=$(eval echo "~$REAL_USER")
CONFIG_DIR="$REAL_HOME/.config/akshar"

if [ -d "$CONFIG_DIR" ]; then
    read -p "  Remove user config at $CONFIG_DIR? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$CONFIG_DIR"
        echo -e "  ${GREEN}✓${NC} User config removed"
    else
        echo -e "  ${YELLOW}—${NC} User config kept"
    fi
fi

# Restart IBus
if [ -n "$SUDO_USER" ]; then
    su - "$SUDO_USER" -c "ibus restart" 2>/dev/null || true
else
    ibus restart 2>/dev/null || true
fi

echo ""
echo -e "${GREEN}✓ Akshar uninstalled successfully.${NC}"
echo ""
