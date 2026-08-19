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

export HF_HOME="${HF_HOME:-/workspace/hf}"
export PSEUDEX_MIN_MBPS="$MIN_MBPS"
mkdir -p "$HF_HOME"

# hf_transfer opens many parallel ranges. On a link that is merely far away
# rather than narrow this is the single biggest lever — a sequential download
# leaves most of the pipe idle no matter which data centre won the lottery.
#
# ENABLED ONLY IF IT IMPORTS. huggingface_hub does not fall back when the flag is
# set and the package is missing: it raises, and the download fails outright. A
# speed optimisation that can stop the run is not an optimisation.
if ! python3 -c "import hf_transfer" 2>/dev/null; then
    pip install --quiet hf_transfer 2>/dev/null || true
fi
if python3 -c "import hf_transfer" 2>/dev/null; then
    export HF_HUB_ENABLE_HF_TRANSFER=1
    echo "hf_transfer включён — загрузка идёт параллельными диапазонами"
else
    echo "hf_transfer недоступен — загрузка последовательная, будет медленнее"
fi

echo "════════ проба сети ════════"
# Written in python3 rather than curl+awk: the sglang image is not guaranteed to
# carry either, and a probe that fails because the tool is missing looks exactly
# like a probe that failed because the link is slow.
python3 - <<'PROBE'
import json, os, sys, time, urllib.request

model = os.environ.get("MODEL", "")
threshold = float(os.environ.get("PSEUDEX_MIN_MBPS", "25"))
# THE SHARD NAME IS ASKED FOR, NEVER GUESSED. It was hard-coded as
# «model-00001-of-00009», and this model has four shards — the probe would have
# 404'd and parked the pod reporting a slow network, which is the one failure it
# exists to tell apart from everything else.
try:
    with urllib.request.urlopen(
            f"https://huggingface.co/api/models/{model}", timeout=20) as meta:
        shards = sorted(f["rfilename"] for f in json.load(meta).get("siblings", [])
                        if f["rfilename"].endswith(".safetensors"))
except Exception as error:
    print(f"  карточка модели недоступна: {error!r}")
    sys.exit(2)
if not shards:
    print(f"  у {model} нет файлов .safetensors — проверьте имя модели")
    sys.exit(2)
print(f"  шардов у модели: {len(shards)}, меряю на {shards[0]}")
url = f"https://huggingface.co/{model}/resolve/main/{shards[0]}"

# 200 MB is past TCP slow start and still free.
request = urllib.request.Request(url, headers={"Range": "bytes=0-209715199"})
read = 0
started = time.monotonic()
try:
    with urllib.request.urlopen(request, timeout=30) as response:
        while time.monotonic() - started < 60:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            read += len(chunk)
except Exception as error:
    print(f"  HuggingFace недоступен: {error!r}")
    sys.exit(2)

elapsed = max(0.001, time.monotonic() - started)
mbps = read / 1048576 / elapsed
print(f"  скачано {read/1048576:.0f} МБ за {elapsed:.0f} с")
print(f"  скорость: {mbps:.1f} МБ/с   порог: {threshold:.0f} МБ/с")
print(f"  ожидаемое время загрузки весов (~31 ГБ): ~{31744/mbps/60:.0f} мин")
sys.exit(0 if mbps >= threshold else 1)
PROBE
PROBE_RESULT=$?

if [ "$PROBE_RESULT" -ne 0 ]; then
    echo
    echo "  ПРОБА НЕ ПРОЙДЕНА (код ${PROBE_RESULT}) — веса НЕ качаются."
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
# CUDA GRAPHS ARE OFF BY DEFAULT HERE, and that is a considered choice, not a
# workaround. Capturing them needs headroom AFTER the weights and the KV cache
# are already resident — 29.3 GB + 9.5 GB on a 46 GB card leaves 4.8 GB, and
# fifty-eight prefill graph sizes up to 8192 tokens do not fit in it. The
# process died mid-capture and the platform restarted it, so the pod looped
# every five minutes without ever serving a request.
#
# Graphs mainly buy decode latency, and our decode is ~15 tokens: the run is
# prefill-bound. So the thing that did not fit is also the thing we least need.
#
# --tool-call-parser is `qwen`; `qwen25` is accepted but deprecated, and the
# deprecation notice is the sort of line that gets read as an error at 3am.
exec python3 -m sglang.launch_server \
    --model-path "$MODEL" \
    --host 0.0.0.0 --port "$PORT" \
    --api-key "$API_KEY" \
    --context-length "$CTX" \
    --enable-metrics \
    --mem-fraction-static "${MEM_FRACTION:-0.85}" \
    --chunked-prefill-size "${CHUNKED_PREFILL:-8192}" \
    --max-running-requests "${MAX_RUNNING:-64}" \
    --tool-call-parser qwen \
    --served-model-name "$MODEL" \
    ${SGLANG_EXTRA:---disable-cuda-graph}
