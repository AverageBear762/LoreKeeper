#!/usr/bin/env bash
# ===========================================================================
# LoreKeeper — Cross-Platform Build Script
# ===========================================================================
# Usage:
#   ./compile.sh                  # Build for current platform
#   ./compile.sh --clean          # Remove old build artifacts first
#   ./compile.sh --debug          # Build with debug symbols
#   ./compile.sh --onefile        # Build single-file executable (experimental)
#   ./compile.sh --upx            # Compress with UPX (if installed)
#
# Output:
#   dist/LoreKeeper/    — One-directory bundle (run ./LoreKeeper/LoreKeeper)
# ===========================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# --- Detect virtual environment -------------------------------------------
if [ -n "${VIRTUAL_ENV:-}" ]; then
    PYTHON="$VIRTUAL_ENV/bin/python"
elif [ -d ".venv" ]; then
    PYTHON=".venv/bin/python"
elif [ -d "venv" ]; then
    PYTHON="venv/bin/python"
else
    PYTHON="python3"
fi

echo "=== LoreKeeper Build ==="
echo "  Python:    $($PYTHON --version 2>&1)"
echo "  PyInstaller: $($PYTHON -m PyInstaller --version 2>&1)"
echo "  Platform:  $(uname -s) $(uname -m)"
echo "  Directory: $SCRIPT_DIR"
echo ""

# --- Parse arguments ------------------------------------------------------
CLEAN=false
DEBUG=false
ONEFILE=false
UPX=""
SPEC="lorekeeper.spec"

for arg in "$@"; do
    case "$arg" in
        --clean)   CLEAN=true ;;
        --debug)   DEBUG=true ;;
        --onefile) ONEFILE=true ;;
        --upx)     UPX="--upx-dir=/usr/bin" ;;
        *)         echo "Unknown argument: $arg" && exit 1 ;;
    esac
done

# --- Clean previous build artifacts ---------------------------------------
if [ "$CLEAN" = true ]; then
    echo ">>> Cleaning previous build artifacts..."
    rm -rf build/ dist/ __pycache__/
    find . -name "*.pyc" -delete
    echo "    Done."
    echo ""
fi

# --- Verify dependencies --------------------------------------------------
echo ">>> Checking dependencies..."
$PYTHON -c "import sqlite3; print('    sqlite3:', sqlite3.sqlite_version)" 2>/dev/null
$PYTHON -c "import PySide6; print('    PySide6:', PySide6.__version__)" 2>/dev/null || echo "    PySide6: MISSING!"
$PYTHON -c "import PIL; print('    Pillow:', PIL.__version__)" 2>/dev/null || echo "    Pillow: MISSING!"
echo ""

# --- Run database tests ---------------------------------------------------
echo ">>> Running database tests..."
$PYTHON test_database.py || { echo "    TESTS FAILED! Aborting build."; exit 1; }
echo ""

# --- Build executable -----------------------------------------------------
echo ">>> Building LoreKeeper executable..."
echo "    Spec:     $SPEC"
echo "    Onefile:  $ONEFILE"
echo "    Debug:    $DEBUG"
echo ""

PYINSTALLER_ARGS=("$SPEC" "--noconfirm" "--windowed")

if [ "$DEBUG" = true ]; then
    PYINSTALLER_ARGS+=("--debug" "all")
fi

if [ "$ONEFILE" = true ]; then
    echo "    NOTE: --onefile builds for PySide6 can be very large and slow to"
    echo "          start. The one-directory bundle is recommended instead."
    PYINSTALLER_ARGS+=("--onefile")
fi

# Run PyInstaller
$PYTHON -m PyInstaller "${PYINSTALLER_ARGS[@]}"

echo ""
echo "=== Build Complete ==="

# --- Show output ----------------------------------------------------------
if [ "$ONEFILE" = true ]; then
    if [ -f "dist/LoreKeeper" ]; then
        echo "  Executable: dist/LoreKeeper"
        ls -lh "dist/LoreKeeper"
    elif [ -f "dist/LoreKeeper.exe" ]; then
        echo "  Executable: dist/LoreKeeper.exe"
        ls -lh "dist/LoreKeeper.exe"
    fi
else
    if [ -d "dist/LoreKeeper" ]; then
        echo "  Bundle: dist/LoreKeeper/"
        echo "  Size:"
        du -sh "dist/LoreKeeper/" 2>/dev/null || echo "    (check with 'du')"
        echo ""
        echo "  To run:"
        echo "    ./dist/LoreKeeper/LoreKeeper"
    fi
fi

echo ""
echo "=== Platform Notes ==="

case "$(uname -s)" in
    Linux)
        echo "  Linux build. Run standalone or package into AppImage/Flatpak."
        echo "  Test on target distros with the minimum glibc you support."
        ;;
    Darwin)
        echo "  macOS build. Run 'codesign -s <identity> dist/LoreKeeper.app'"
        echo "  before distribution. Use 'create-dmg' for a DMG installer."
        ;;
    MINGW*|MSYS*|CYGWIN*)
        echo "  Windows build. Use Inno Setup or NSIS to create an installer."
        echo "  Or just zip dist/LoreKeeper/ and distribute as a portable app."
        ;;
esac