#!/bin/sh
# The files that make up the customer image, from the ONE place that decides
# it: the `COPY` lines of prototype/Dockerfile.nuitka — plus the two Dockerfiles
# themselves, which change the artifact without being copied into it.
#
# Why derived and not listed: a hand-written list drifts the day someone adds a
# COPY line, and then a change to a shipped file mints no engine version (or a
# change to a test file mints one). Both gates that need this set — the commit
# lint in checks.yml and the «empty engine release» refusal in release.yml —
# read it from here, so the set cannot disagree with the build.
#
# Output: one repo-relative path per line, directories with a trailing slash,
# suitable for `git diff --name-only … -- $(deploy/shipped_paths.sh)`.
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
DOCKERFILE="$ROOT/prototype/Dockerfile.nuitka"

printf '%s\n' prototype/Dockerfile prototype/Dockerfile.nuitka

# `COPY a b c ./` copies several sources; `COPY --from=stage …` copies from a
# build stage, not from the context, and is not a source path. The last word
# of each COPY is the destination.
grep -E '^COPY ' "$DOCKERFILE" | grep -v -- '--from=' | while read -r _ rest; do
    set -- $rest
    while [ $# -gt 1 ]; do
        src="$1"; shift
        case "$src" in
            --*) continue ;;
        esac
        src="${src#./}"
        if [ -d "$ROOT/prototype/$src" ]; then
            printf 'prototype/%s\n' "${src%/}/"
        else
            printf 'prototype/%s\n' "$src"
        fi
    done
done | sort -u
