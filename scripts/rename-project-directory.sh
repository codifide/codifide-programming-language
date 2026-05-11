#!/usr/bin/env bash
# Rename the project's parent directory from Noema to Codifide.
#
# This script exists because the Codifide language codebase sits at
# /Users/douglasjones/Projects/Noema — the parent directory still
# carries the old name from before the rename. No file inside the
# repository depends on that path (all imports and paths inside
# the code are relative), so moving the directory is purely a
# disk-layout change.
#
# Run this script from *outside* the project directory. It cannot
# rename the directory it is executing inside. After the move, cd
# into the new location and verify the test suite still passes.
#
# Usage:
#   cd ~/Projects            (or wherever Noema/ lives)
#   bash Noema/scripts/rename-project-directory.sh

set -euo pipefail

OLD="Noema"
NEW="Codifide"

here="$(pwd)"
old_path="${here}/${OLD}"
new_path="${here}/${NEW}"

if [ ! -d "$old_path" ]; then
    echo "error: ${old_path} does not exist."
    echo "Run this script from the directory that contains ${OLD}/"
    exit 1
fi

if [ -e "$new_path" ]; then
    echo "error: ${new_path} already exists. Refusing to clobber."
    exit 1
fi

# Guard against running from inside the directory we're moving.
# `pwd -P` resolves symlinks, matching what macOS gives us.
case "$here" in
    "$old_path"|"$old_path"/*)
        echo "error: you are inside ${old_path}. cd out before running."
        exit 1
        ;;
esac

echo "Moving ${old_path} -> ${new_path}"
mv "$old_path" "$new_path"

echo "Verifying the move..."
if [ -d "$new_path/codifide" ] && [ -f "$new_path/README.md" ]; then
    echo "OK: directory contents look right."
else
    echo "warning: expected contents not found. Inspect ${new_path}."
    exit 1
fi

echo
echo "Done. Next steps:"
echo "  cd ${new_path}"
echo "  python3 -m codifide test    # confirm 122 passing"
echo "  cargo test --release -p codifide-canonical  # confirm 10 passing"
echo
echo "If you use shell history, IDE workspaces, or Git remotes that"
echo "reference the old path, update those separately. Nothing inside"
echo "the repository depends on the parent directory name."
