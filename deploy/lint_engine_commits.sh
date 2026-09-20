#!/bin/sh
# A commit that would mint an ENGINE version without changing the engine is
# refused here, at the source, not discovered as an empty release later.
#
# release-please attributes a commit to the engine when it touches a file under
# prototype/ (outside the excluded directories), and bumps the version when the
# commit's type is visible: feat, fix, security, perf, build, revert. Flat
# scripts in prototype/ — tests, evals, dataset generators — are under that
# path but never ship, so `fix(test): …` on prototype/test_loop.py would mint
# 0.3.17 for an image identical to 0.3.16. That is the 0.3.12/0.3.13 defect in
# a new coat, and the number lying is worse than the CI minutes.
#
# The rule: a visible-type commit that touches prototype/ (minus licensing/,
# bench/, e2e/) must touch at least one SHIPPED path (deploy/shipped_paths.sh);
# otherwise its type must be one that does not bump — test, bench, chore, docs,
# refactor, ci, research. The message says which.
#
#   deploy/lint_engine_commits.sh <from>..<to>      # a range, e.g. origin/main..HEAD
#   deploy/lint_engine_commits.sh <sha>             # one commit
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
RANGE="${1:?usage: lint_engine_commits.sh <range-or-sha>}"

SHIPPED="$(sh "$HERE/shipped_paths.sh")"
VISIBLE="feat fix security perf build revert"

case "$RANGE" in
    *..*) COMMITS="$(git -C "$ROOT" rev-list --no-merges "$RANGE")" ;;
    *)    COMMITS="$(git -C "$ROOT" rev-parse "$RANGE")" ;;
esac

status=0
for sha in $COMMITS; do
    subject="$(git -C "$ROOT" log -1 --format=%s "$sha")"
    # type = the token before `(`, `!` or `:`; anything else is not conventional
    # and bumps nothing, so it is not this lint's business.
    type="$(printf '%s' "$subject" | sed -n 's/^\([a-z]*\)[(!:].*/\1/p')"
    [ -n "$type" ] || continue
    visible=0
    for v in $VISIBLE; do [ "$type" = "$v" ] && visible=1; done
    [ "$visible" = 1 ] || continue

    files="$(git -C "$ROOT" diff-tree --no-commit-id --name-only -r "$sha")"
    engine_side=0; shipped_hit=0
    for f in $files; do
        case "$f" in
            prototype/licensing/*|prototype/bench/*|prototype/e2e/*) continue ;;
            prototype/*) engine_side=1 ;;
            *) continue ;;
        esac
        for s in $SHIPPED; do
            case "$s" in
                */) case "$f" in "$s"*) shipped_hit=1 ;; esac ;;
                *)  [ "$f" = "$s" ] && shipped_hit=1 ;;
            esac
        done
    done
    if [ "$engine_side" = 1 ] && [ "$shipped_hit" = 0 ]; then
        echo "lint: $(printf '%.10s' "$sha") «${subject}»"
        echo "      тип «${type}» поднимет версию ДВИЖКА, но коммит не трогает ничего из образа:"
        printf '%s\n' "$files" | sed 's/^/        /'
        echo "      типизируйте как test:/bench:/chore:/docs:/refactor: — они версию не двигают,"
        echo "      либо это правда изменение движка, и тогда в нём должен быть файл из deploy/shipped_paths.sh"
        status=1
    fi
done
[ "$status" = 0 ] && echo "lint: коммиты движка типизированы честно"
exit $status
