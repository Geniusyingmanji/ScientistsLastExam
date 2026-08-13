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
#     bash scripts/setup_oracle_env.sh            # install everything
#     bash scripts/setup_oracle_env.sh --check    # report what is present, install nothing
set -euo pipefail

ORACLE_PYTHON="${ORACLE_PYTHON:-/usr/bin/python3}"
BOOTSTRAP_VENV="${BOOTSTRAP_VENV:-$HOME/.cache/sle-bootstrap-venv}"

# Pinned to match the versions every reference record was measured against. Changing one of these
# invalidates that task's recorded anchors, which is why they are pinned rather than floated.
PACKAGES=(
  "stim==1.13.0"          # QuantumErrorDecoder: seeded sampling is not stable across versions
  "pymatching==2.4.0"     # QuantumErrorDecoder anchor
  "rdkit==2024.03.5"      # MolecularLeadOptimization; last line with cp38 wheels
  "ViennaRNA==2.7.2"      # RNAEnsembleDesign
  "nmrsim==0.6.0"         # SpinSystemInference
  "networkx==3.1"         # GraphFromDistances
  "qutip==4.7.6"          # physics discovery tasks; 5.x needs a toolchain this host lacks
)

# import name -> pip name, since several differ
declare -A IMPORT_NAME=(
  ["stim==1.13.0"]="stim"
  ["pymatching==2.4.0"]="pymatching"
  ["rdkit==2024.03.5"]="rdkit"
  ["ViennaRNA==2.7.2"]="RNA"
  ["nmrsim==0.6.0"]="nmrsim"
  ["networkx==3.1"]="networkx"
  ["qutip==4.7.6"]="qutip"
)

site_dir() {
  # The user site-packages, not a system one. A first version preferred any path containing
  # "local" and picked /usr/local/lib/python3.8/dist-packages, which needs root and is not where
  # the existing toolkits live - a fresh host would have installed to a second location and the
  # two would have drifted.
  "$ORACLE_PYTHON" -c "import site; print(site.getusersitepackages())"
}

report() {
  echo "oracle interpreter: $ORACLE_PYTHON ($("$ORACLE_PYTHON" -V 2>&1))"
  echo "target site-packages: $(site_dir)"
  local missing=0
  for spec in "${PACKAGES[@]}"; do
    local mod="${IMPORT_NAME[$spec]}"
    if version=$("$ORACLE_PYTHON" -c "import $mod, sys; print(getattr($mod, '__version__', '?'))" 2>/dev/null); then
      printf '  %-22s present  %s\n' "$mod" "$version"
    else
      printf '  %-22s MISSING  (%s)\n' "$mod" "$spec"
      missing=$((missing + 1))
    fi
  done
  return "$missing"
}

if [[ "${1:-}" == "--check" ]]; then
  report || true
  exit 0
fi

if ! "$BOOTSTRAP_VENV/bin/python" -m pip --version >/dev/null 2>&1; then
  echo "creating bootstrap venv at $BOOTSTRAP_VENV"
  # No --system-site-packages: inheriting them is what pulls in the broken OpenSSL bindings.
  rm -rf "$BOOTSTRAP_VENV"
  "$ORACLE_PYTHON" -m venv "$BOOTSTRAP_VENV"
fi

TARGET="$(site_dir)"
echo "installing into $TARGET"
for spec in "${PACKAGES[@]}"; do
  mod="${IMPORT_NAME[$spec]}"
  if "$ORACLE_PYTHON" -c "import $mod" >/dev/null 2>&1; then
    echo "  $mod already present, skipping"
    continue
  fi
  echo "  installing $spec"
  "$BOOTSTRAP_VENV/bin/pip" install --quiet --target "$TARGET" "$spec"
done

echo
report
