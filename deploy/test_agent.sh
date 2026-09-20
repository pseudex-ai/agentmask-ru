#!/bin/sh
# Decisions of deploy/agent.sh WITHOUT docker, cosign or a host: a throw-away
# clone with the tags of interest, shims for `docker` and `notify.sh` on PATH,
# and the agent run up to its first external call. What is pinned:
#
#   1. the agent follows `platform/v*` only, and never a bare `v*` tag;
#   2. the last tag of the old scheme in `.deployed` (`v0.3.15`) is compared
#      by NUMBER with `platform/v0.3.16` — `sort -V` on raw strings would put
#      `p` before `v` and refuse every platform release as a downgrade;
#   3. a genuinely older platform tag IS refused as a downgrade;
#   4. an identity regexp that cannot match `refs/tags/platform/v…` is refused
#      in words, before any signature is checked;
#   5. with no platform tag at all the agent waits and touches nothing.
#
# The run stops at `docker manifest inspect` (the shim answers "not published")
# so the assertions read the agent's stdout and the notify shim's log only.
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
AGENT="$HERE/agent.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# ── a repository with history and tags ─────────────────────────────────────
REPO="$WORK/repo"
mkdir -p "$REPO/deploy"
cp "$AGENT" "$REPO/deploy/agent.sh"
cat > "$REPO/deploy/compose.yml" <<'EOF'
services: {}
EOF
git -C "$REPO" init -q -b main
cat > "$REPO/deploy/releases.json" <<'EOF'
{"product":"pseudex","schema":1,"updated_at":"2026-09-20T00:00:00Z",
 "support":{"maintenance_months":6,"eol_notice_days":90},
 "cycles":[{"cycle":"0.3","state":"current","release_date":"2026-09-14","eoas":null,"eol":null,"eol_announced":null,
   "latest":{"version":"0.3.15","date":"2026-09-22","digest":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
   "aliases":["0.3","0","latest"]}],"notices":[]}
EOF
git -C "$REPO" add deploy/releases.json
git -C "$REPO" -c user.name=t -c user.email=t@t commit -q -m "one"
git -C "$REPO" tag v0.3.15
git -C "$REPO" tag platform/v0.3.15
git -C "$REPO" -c user.name=t -c user.email=t@t commit -q --allow-empty -m "two"
git -C "$REPO" tag platform/v0.3.16
git -C "$REPO" tag v0.4.0            # an ENGINE tag newer than any platform one
git -C "$REPO" tag veilgate-final    # the old trap: starts with v, sorts above versions

# ── shims ───────────────────────────────────────────────────────────────────
BIN="$WORK/bin"; mkdir -p "$BIN"
cat > "$BIN/docker" <<'EOF'
#!/bin/sh
# `manifest inspect` → not published; the agent must exit 0 with «жду».
case "$1 $2" in
    "manifest inspect") exit 1 ;;
esac
echo "docker shim: unexpected call: $*" >&2
exit 99
EOF
cat > "$REPO/deploy/notify.sh" <<'EOF'
#!/bin/sh
printf '%s|%s|%s\n' "$1" "$2" "$3" >> "$NOTIFY_LOG"
EOF
# macOS has no util-linux `flock`; the agent runs on Ubuntu. The shim takes
# the lock unconditionally — the test never runs two agents at once.
cat > "$BIN/flock" <<'EOF'
#!/bin/sh
exit 0
EOF
# cosign: verifies when COSIGN_SHIM_OK=1, fails otherwise — the registry sync
# must accept the file only on a verified digest.
cat > "$BIN/cosign" <<'EOF'
#!/bin/sh
[ "${COSIGN_SHIM_OK:-0}" = 1 ] && exit 0
exit 1
EOF
chmod +x "$BIN/docker" "$BIN/flock" "$BIN/cosign" "$REPO/deploy/notify.sh"

# `git fetch --tags` needs an origin; point it at the repo itself.
git -C "$REPO" remote add origin "$REPO"

run_agent() {  # $1 = .deployed content ('' for none), $2 = identity regexp
    NOTIFY_LOG="$WORK/notify.log"; : > "$NOTIFY_LOG"; export NOTIFY_LOG
    STATE="$WORK/deployed"; rm -f "$STATE"
    [ -n "$1" ] && printf '%s' "$1" > "$STATE"
    set +e
    PATH="$BIN:$PATH" PSEUDEX_AGENT_STATE="$STATE" PSEUDEX_AGENT_LOCK="$WORK/lock" \
        COSIGN_ISSUER_REGEXP='^https://token$' COSIGN_IDENTITY_REGEXP="$2" \
        COSIGN_SHIM_OK="${COSIGN_SHIM_OK:-1}" \
        sh "$REPO/deploy/agent.sh" > "$WORK/out" 2>&1
    RC=$?
    set -e
}

expect() {  # $1 = description, $2 = expected rc, $3 = grep pattern in stdout+notify
    if [ "$RC" != "$2" ] || ! cat "$WORK/out" "$NOTIFY_LOG" | grep -q -- "$3"; then
        echo "FAIL $1: rc=$RC (expected $2), looking for '$3'"
        echo "--- stdout ---"; cat "$WORK/out"; echo "--- notify ---"; cat "$NOTIFY_LOG"
        exit 1
    fi
    echo "OK   $1"
}

GOOD='^https://github\.com/x/y/\.github/workflows/release\.yml@refs/tags/(platform/)?v[0-9]+\.[0-9]+\.[0-9]+$'
OLD='^https://github\.com/x/y/\.github/workflows/release\.yml@refs/tags/v[0-9]+\.[0-9]+\.[0-9]+$'

# 1+2. Last old-scheme tag deployed → the platform tag is a forward move; the
#      engine tag v0.4.0 and veilgate-final are invisible.
run_agent "v0.3.15" "$GOOD"
expect "мост: v0.3.15 -> platform/v0.3.16" 0 "agent: v0.3.15 -> platform/v0.3.16"
expect "останавливается на неопубликованном образе" 0 "ещё не опубликован — жду"

# no-op: the same platform tag already deployed
run_agent "platform/v0.3.16" "$GOOD"
[ -s "$WORK/out" ] && { echo "FAIL no-op: agent printed: $(cat "$WORK/out")"; exit 1; }
[ "$RC" = 0 ] || { echo "FAIL no-op: rc=$RC"; exit 1; }
echo "OK   no-op на уже выкаченном platform/v0.3.16"

# equal NUMBER under a different prefix is also a no-op (the anchor tag after the bridge)
run_agent "v0.3.16" "$GOOD"
[ -s "$WORK/out" ] && { echo "FAIL anchor no-op: $(cat "$WORK/out")"; exit 1; }
echo "OK   no-op при равном номере под другим префиксом"

# 3. An older platform tag than the deployed one → refused as a downgrade
run_agent "platform/v0.3.17" "$GOOD"
expect "откат назад отменён" 1 "откат назад"

# 4. Identity anchored on the old scheme only → refused in words, before verify
run_agent "v0.3.15" "$OLD"
expect "identity без platform отвергнута" 1 "не принимает platform/v-теги"

# 6. The registry: accepted only on a verified digest, kept otherwise
rm -rf "$REPO/deploy/.registry"
COSIGN_SHIM_OK=0 run_agent "platform/v0.3.16" "$GOOD"
[ -f "$REPO/deploy/.registry/releases.json" ] && { echo "FAIL registry: accepted an unverified digest"; exit 1; }
grep -q "дайджест новейшей версии не подписан" "$NOTIFY_LOG" || { echo "FAIL registry: no crit on unverified digest"; cat "$NOTIFY_LOG"; exit 1; }
echo "OK   реестр с неподписанным дайджестом не принят, тревога отправлена"
COSIGN_SHIM_OK=1 run_agent "platform/v0.3.16" "$GOOD"
[ -f "$REPO/deploy/.registry/releases.json" ] || { echo "FAIL registry: not synced on a verified digest"; cat "$WORK/out"; exit 1; }
grep -q "реестр версий обновлён" "$WORK/out" || { echo "FAIL registry: no sync line"; cat "$WORK/out"; exit 1; }
echo "OK   реестр принят после cosign verify"
COSIGN_SHIM_OK=1 run_agent "platform/v0.3.16" "$GOOD"
grep -q "реестр версий обновлён" "$WORK/out" && { echo "FAIL registry: re-synced an unchanged file"; exit 1; }
echo "OK   неизменённый реестр не подменяется"
printf '{broken' > "$WORK/broken.json"; cp "$WORK/broken.json" "$REPO/deploy/releases.json"
git -C "$REPO" -c user.name=t -c user.email=t@t commit -q -am "break registry"
COSIGN_SHIM_OK=1 run_agent "platform/v0.3.16" "$GOOD"
grep -q "файл не разбирается" "$NOTIFY_LOG" || { echo "FAIL registry: broken file not reported"; cat "$NOTIFY_LOG"; exit 1; }
python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$REPO/deploy/.registry/releases.json" || { echo "FAIL registry: the live copy was replaced by a broken file"; exit 1; }
echo "OK   битый реестр не подменяет прежнюю копию"

# 5. No platform tag at all → wait, touch nothing
git -C "$REPO" tag -d platform/v0.3.15 platform/v0.3.16 >/dev/null
run_agent "v0.3.15" "$GOOD"
expect "без платформенных тегов агент ждёт" 0 "ещё нет — жду первого"

echo "deploy/test_agent.sh: все решения агента подтверждены"
