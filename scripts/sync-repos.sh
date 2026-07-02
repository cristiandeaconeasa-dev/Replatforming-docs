#!/bin/bash
# sync-repos.sh — Clone all doc-source repos into _sources/
# Run from the hub repo root.
set -euo pipefail

SOURCES_DIR="_sources"
REPO_LIST_FILE="repos.txt"
GITHUB_ORG="PricerAB"

# Use GITHUB_TOKEN if available (CI), otherwise use gh CLI auth
if [ -n "${GITHUB_TOKEN:-}" ]; then
    CLONE_PREFIX="https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_ORG}"
else
    CLONE_PREFIX="https://github.com/${GITHUB_ORG}"
fi

echo "=== Syncing doc-source repos ==="

# Clean previous sources but preserve .gitkeep
rm -rf "${SOURCES_DIR:?}"/*
touch "${SOURCES_DIR}/.gitkeep"

if [ ! -f "$REPO_LIST_FILE" ]; then
    echo "ERROR: repos.txt not found. Create it with one repo name per line."
    exit 1
fi

FAILED=0
while IFS= read -r repo; do
    # Skip comments and empty lines
    [[ "$repo" =~ ^#.*$ ]] && continue
    [[ -z "$repo" ]] && continue

    # repo can be "PricerAB/repo-name" or just "repo-name"
    if [[ "$repo" == *"/"* ]]; then
        ORG=$(echo "$repo" | cut -d'/' -f1)
        REPO_NAME=$(echo "$repo" | cut -d'/' -f2)
        CLONE_URL="https://github.com/${ORG}/${REPO_NAME}.git"
        if [ -n "${GITHUB_TOKEN:-}" ]; then
            CLONE_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/${ORG}/${REPO_NAME}.git"
        fi
    else
        REPO_NAME="$repo"
        CLONE_URL="${CLONE_PREFIX}/${repo}.git"
    fi

    echo "  Cloning ${repo}..."
    if git clone --depth 1 --filter=blob:none \
        "${CLONE_URL}" \
        "${SOURCES_DIR}/${REPO_NAME}" 2>&1 | tail -1; then
        echo "    ✅ ${repo}"
    else
        echo "    ❌ ${repo} — clone failed"
        FAILED=1
    fi
done < "$REPO_LIST_FILE"

if [ $FAILED -eq 1 ]; then
    echo "WARNING: Some repos failed to clone. Check repos.txt and access tokens."
    echo "The build will continue with available repos."
fi

echo "=== Generating nav from cloned repos ==="
python3 scripts/generate-nav.py

echo "=== Sync complete ==="
find "${SOURCES_DIR}" -maxdepth 1 -type d | tail -n +2 | while read -r d; do
    echo "  $(basename "$d") ($(find "$d" -name '*.md' | wc -l | tr -d ' ') md files)"
done
