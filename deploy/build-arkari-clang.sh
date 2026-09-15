#!/usr/bin/env bash
# Build the Arkari obfuscating clang — ONE TIME, pinned.
#
# Arkari (https://github.com/komimoe/Arkari) is an OLLVM-family fork of LLVM: a
# clang whose passes do control-flow flattening, indirect branches/calls with
# encrypted targets, and string/constant encryption. It ships NO prebuilt binary,
# so we build it once into a cached image; every release's Nuitka build then just
# uses that clang (deploy has no per-release cost, see prototype/Dockerfile.nuitka).
#
# WHY ONCE, NOT EVERY RELEASE. The clang is pinned to a tag (llvm-20-obf1.9.1), so
# the image is reproducible. Rebuild it only if you deliberately bump the LLVM or
# Arkari version — otherwise the release pipeline consumes the cached image and the
# heavy compile never runs again.
#
# COST. A full LLVM 20 compile: ~1-2 h on 10 cores, tens of GB of disk. RAM-safe
# settings (single link job, lld) keep it inside ~12 GB. The result image
# `pseudex-arkari-clang:llvm20` is only the clang + its resource headers.
#
#   bash deploy/build-arkari-clang.sh
#   # then: build the release with obfuscation on (see Dockerfile.nuitka header)
#
# Push it to your registry to share the one-time build across machines/CI:
#   docker tag pseudex-arkari-clang:llvm20 <registry>/pseudex-arkari-clang:llvm20
#   docker push <registry>/pseudex-arkari-clang:llvm20
set -euo pipefail

TAG="${ARKARI_TAG:-llvm-20-obf1.9.1}"
IMAGE="${ARKARI_IMAGE:-pseudex-arkari-clang:llvm20}"
CTX="$(mktemp -d)"
trap 'rm -rf "$CTX"' EXIT

cat > "$CTX/Dockerfile" <<EOF
FROM debian:trixie-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends \\
        git cmake ninja-build build-essential python3 lld ca-certificates zlib1g-dev \\
    && rm -rf /var/lib/apt/lists/*
WORKDIR /a
RUN git clone --depth 1 --branch ${TAG} https://github.com/komimoe/Arkari.git src
WORKDIR /a/src
# X86;AArch64 only, no tests/examples, lld linker, single link job: fits ~12 GB RAM.
RUN cmake -S llvm -B build -G Ninja \\
      -DCMAKE_BUILD_TYPE=Release \\
      -DLLVM_ENABLE_PROJECTS=clang \\
      -DLLVM_TARGETS_TO_BUILD="X86;AArch64" \\
      -DLLVM_ENABLE_ASSERTIONS=OFF \\
      -DLLVM_USE_LINKER=lld \\
      -DLLVM_PARALLEL_LINK_JOBS=1 -DLLVM_PARALLEL_COMPILE_JOBS=8 \\
      -DLLVM_INCLUDE_TESTS=OFF -DLLVM_INCLUDE_EXAMPLES=OFF \\
      -DLLVM_INCLUDE_BENCHMARKS=OFF -DCLANG_INCLUDE_TESTS=OFF
RUN ninja -C build clang
FROM debian:trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends \\
        libstdc++6 zlib1g binutils && rm -rf /var/lib/apt/lists/*
COPY --from=build /a/src/build/bin/clang /a/src/build/bin/clang-20 /usr/local/bin/
COPY --from=build /a/src/build/lib/clang /usr/local/lib/clang
RUN clang --version | head -2
EOF

echo "building $IMAGE from Arkari $TAG (this is the ~1-2h one-time compile)…"
docker build -t "$IMAGE" "$CTX"
echo "done: $IMAGE — the release build (Dockerfile.nuitka, PSEUDEX_OBFUSCATE=1) uses it."
