#!/usr/bin/env bash
# Стартовая команда пода: сначала МЕРИМ СЕТЬ, потом качаем веса.
#
# WHY THE PROBE COMES FIRST. The weights are ~31 GB and the corpus is 2.4 MB, so
# the only thing that can turn a one-dollar run into an afternoon is the data
# centre's own link. A slow one is not visible in the console and not knowable
# before renting — but it IS measurable in sixty seconds, and sixty seconds of
# an RTX 6000 Ada costs a cent and a half. Destroying a pod that fails the probe
# and creating another in a different data centre is the cheapest possible fix,
# and it can only be done if the measurement happens BEFORE the download.
#
# A failed probe does NOT start the download. It parks the pod so the log can be
# read and the pod destroyed deliberately — a container that exits gets
# restarted by the platform and quietly starts the download it was told not to.
#
#   PSEUDEX_MIN_MBPS=40 MODEL=Qwen/Qwen3-30B-A3B-Instruct-2507-FP8 ./bootstrap.sh
set -uo pipefail

MODEL="${MODEL:-Qwen/Qwen3-30B-A3B-Instruct-2507-FP8}"
MIN_MBPS="${PSEUDEX_MIN_MBPS:-25}"
API_KEY="${SGLANG_API_KEY:?установите SGLANG_API_KEY — порт 30000 публичен через прокси RunPod}"
PORT="${PORT:-30000}"
EXPORTER_PORT="${EXPORTER_PORT:-9400}"
CTX="${CTX:-8192}"

# hf_transfer opens many parallel ranges. On a link that is merely far away
# rather than narrow this is the single biggest lever — a sequential download
# leaves most of the pipe idle no matter which data centre won the lottery.
export HF_HUB_ENABLE_HF_TRANSFER=1
export HF_HOME="${HF_HOME:-/workspace/hf}"
mkdir -p "$HF_HOME"

echo "════════ проба сети ════════"
# A real weight shard from the model we are about to pull, so the number is the
# path that matters — not a speedtest server chosen for its peering.
PROBE_URL="https://huggingface.co/${MODEL}/resolve/main/config.json"
RESOLVED="$(curl -sIL -o /dev/null -w '%{http_code}' "$PROBE_URL" || echo 000)"
echo "  доступность HuggingFace: HTTP ${RESOLVED}"

# 200 MB is enough to leave TCP slow-start behind and short enough to be free.
BIG_URL="https://huggingface.co/${MODEL}/resolve/main/model-00001-of-00009.safetensors"
SPEED="$(curl -sL --max-time 60 -r 0-209715199 -o /dev/null -w '%{speed_download}' "$BIG_URL" 2>/dev/null || echo 0)"
MBPS="$(awk -v s="$SPEED" 'BEGIN { printf "%.1f", s/1048576 }')"
echo "  скорость: ${MBPS} МБ/с   порог: ${MIN_MBPS} МБ/с"
ETA="$(awk -v m="$MBPS" 'BEGIN { if (m > 0) printf "%.0f", 31744/m/60; else print 999 }')"
echo "  ожидаемое время загрузки весов: ~${ETA} мин"

if awk -v m="$MBPS" -v t="$MIN_MBPS" 'BEGIN { exit !(m < t) }'; then
    echo
    echo "  СЕТЬ МЕДЛЕННАЯ — веса НЕ качаются."
    echo "  Уничтожьте под и создайте в другом датацентре."
    echo "  Под оставлен живым нарочно: контейнер, который завершился,"
    echo "  платформа перезапустит, и он начнёт ту самую загрузку."
    sleep infinity
fi
echo "  проба пройдена"
echo

echo "════════ экспортёр железа ════════"
python3 /workspace/gpu_exporter.py --port "$EXPORTER_PORT" &
echo "  метрики железа на :${EXPORTER_PORT}/metrics"
echo

echo "════════ sglang ════════"
# --enable-metrics is what the panel scrapes. RadixAttention is on by default and
# is the lever that matters here: every dialogue shares a ~1200-token prefix of
# system prompt plus tool schemas, and the run is prefill-bound, so the cache hit
# rate on that prefix decides the wall clock far more than the decode batch does.
exec python3 -m sglang.launch_server \
    --model-path "$MODEL" \
    --host 0.0.0.0 --port "$PORT" \
    --api-key "$API_KEY" \
    --context-length "$CTX" \
    --enable-metrics \
    --mem-fraction-static "${MEM_FRACTION:-0.88}" \
    --chunked-prefill-size "${CHUNKED_PREFILL:-8192}" \
    --max-running-requests "${MAX_RUNNING:-64}" \
    --tool-call-parser qwen25 \
    --served-model-name "$MODEL"
