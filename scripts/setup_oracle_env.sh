#!/usr/bin/env bash
# Install the domain toolkits the oracles need, on a host whose system pip is broken.
#
# Why this exists. Each task declares its oracle dependencies in verification/requirements.txt,
# and on the benchmark host `pip install -r` against those files does not work: the system
# interpreter's pip fails at import with
#
#     AttributeError: module 'lib' has no attribute 'X509_V_FLAG_NOTIFY_POLICY'
#
# which is a pyOpenSSL/cryptography binding mismatch in the distribution packages. A virtualenv
# created without --system-site-packages does not inherit the broken bindings, so its pip works;
# pointing that pip at the oracle interpreter's site-packages with --target installs where the
# oracle will actually look.
#
# The oracle runs in the trusted parent, not the sandbox, so installing here does not change the
# isolation model. Candidates receive a toolkit only if their task lists it in
# frontier_eval/candidate_packages.txt and the name appears in the audited allowlist in
# sle/secure_eval.py.
#
# Usage:
#     ORACLE_PYTHON=/path/to/python3.8 bash scripts/setup_oracle_env.sh
#     ORACLE_PYTHON=/path/to/python3.8 bash scripts/setup_oracle_env.sh --check
# Full oracle setup is certified only for Python 3.8 and fails before resolution otherwise.
set -euo pipefail

ORACLE_PYTHON="${ORACLE_PYTHON:-/usr/bin/python3}"
BOOTSTRAP_VENV="${BOOTSTRAP_VENV:-$HOME/.cache/sle-bootstrap-venv}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# One canonical map now drives both this install transaction and secure_eval's runtime checks.
# Installing every pin in one resolver transaction prevents a later toolkit's dependency upgrade
# from silently changing NumPy, SciPy or Astropy's numerical dependencies.
PACKAGE_OUTPUT="$(
  PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}" "$ORACLE_PYTHON" -c \
    "from sle.oracle_package_pins import setup_requirements; import sys; print(*setup_requirements(sys.version_info[:2]), sep='\\n')"
)"
mapfile -t PACKAGES <<< "$PACKAGE_OUTPUT"

# import name -> pip name, since several differ
declare -A IMPORT_NAME=(
  ["stim"]="stim"
  ["pymatching"]="pymatching"
  ["rdkit"]="rdkit"
  ["ViennaRNA"]="RNA"
  ["nmrsim"]="nmrsim"
  ["networkx"]="networkx"
  ["sympy"]="sympy"
  ["qutip"]="qutip"
  ["astropy"]="astropy"
  ["numpy"]="numpy"
  ["scipy"]="scipy"
  ["pyerfa"]="erfa"
  ["PyYAML"]="yaml"
  ["Pillow"]="PIL"
  ["mpmath"]="mpmath"
  ["sparse"]="sparse"
  ["numba"]="numba"
  ["llvmlite"]="llvmlite"
  ["numpy-groupies"]="numpy_groupies"
  ["importlib-metadata"]="importlib_metadata"
  ["typing-extensions"]="typing_extensions"
  ["zipp"]="zipp"
  ["packaging"]="packaging"
  ["matplotlib"]="matplotlib"
  ["contourpy"]="contourpy"
  ["cycler"]="cycler"
  ["fonttools"]="fontTools"
  ["importlib-resources"]="importlib_resources"
  ["kiwisolver"]="kiwisolver"
  ["pyparsing"]="pyparsing"
  ["python-dateutil"]="dateutil"
  ["six"]="six"
)

site_dir() {
  # A configured virtualenv must own its packages; its user site is disabled and installing
  # there creates a plausible-looking environment that the interpreter never imports.
  # Preserve the historical user-site target only for a system interpreter.
  "$ORACLE_PYTHON" -c \
    "import site, sys, sysconfig; print(sysconfig.get_path('purelib') if sys.prefix != sys.base_prefix else site.getusersitepackages())"
}

installed_version() {
  local distribution="$1"
  "$ORACLE_PYTHON" -c \
    "import importlib.metadata, sys; print(importlib.metadata.version(sys.argv[1]))" \
    "$distribution" 2>/dev/null
}

package_matches() {
  local spec="$1"
  local distribution="${spec%%==*}"
  local expected="${spec#*==}"
  local mod="${IMPORT_NAME[$distribution]}"
  local actual
  "$ORACLE_PYTHON" -c "import $mod" >/dev/null 2>&1 || return 1
  actual="$(installed_version "$distribution")" || return 1
  [[ "$actual" == "$expected" ]]
}

report() {
  echo "oracle interpreter: $ORACLE_PYTHON ($("$ORACLE_PYTHON" -V 2>&1))"
  echo "target site-packages: $(site_dir)"
  local missing=0
  for spec in "${PACKAGES[@]}"; do
    local distribution="${spec%%==*}"
    local expected="${spec#*==}"
    local mod="${IMPORT_NAME[$distribution]}"
    local version
    version="$(installed_version "$distribution")" 2>/dev/null || true
    if package_matches "$spec"; then
      printf '  %-22s present  %s\n' "$mod" "$version"
    elif [[ -n "$version" ]]; then
      printf '  %-22s MISMATCH %s (expected %s)\n' \
        "$mod" "$version" "$expected"
      missing=$((missing + 1))
    else
      printf '  %-22s MISSING  (%s)\n' "$mod" "$spec"
      missing=$((missing + 1))
    fi
  done
  return "$missing"
}

if [[ "${1:-}" == "--check" ]]; then
  report
  exit $?
fi

if ! "$BOOTSTRAP_VENV/bin/python" -c \
    'import sys; raise SystemExit(sys.version_info[:2] != (3, 8))' >/dev/null 2>&1 \
    || ! "$BOOTSTRAP_VENV/bin/python" -m pip --version >/dev/null 2>&1; then
  echo "creating bootstrap venv at $BOOTSTRAP_VENV"
  # No --system-site-packages: inheriting them is what pulls in the broken OpenSSL bindings.
  rm -rf "$BOOTSTRAP_VENV"
  "$ORACLE_PYTHON" -m venv "$BOOTSTRAP_VENV"
fi

TARGET="$(site_dir)"
echo "installing into $TARGET"
needs_install=0
for spec in "${PACKAGES[@]}"; do
  package_matches "$spec" || needs_install=1
done
if (( needs_install )); then
  "$BOOTSTRAP_VENV/bin/pip" install --quiet --upgrade --target "$TARGET" "${PACKAGES[@]}"
else
  echo "  all pinned packages already present, skipping"
fi

echo
report
