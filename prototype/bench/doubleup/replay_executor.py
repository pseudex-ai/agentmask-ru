"""RAM-only, Docker-isolated Python execution for future causal replay.

Public API: run_python(code: str, files: dict[str, bytes], timeout_seconds: int)
returns {status, exit_code, stdout, stderr, artifacts, limits_hit, network, error}.
Artifacts are a COMPLETE basename-only workspace snapshot, including unchanged
inputs; replace the caller's per-arm snapshot rather than merging it. No globals,
imports or /tmp state persist between calls. stdout/stderr are UTF-8 strings with
surrogateescape (encode with the same error handler to recover arbitrary bytes).
Files must be STRICTLY smaller than 1 MiB (reaching the hard cap is conservatively
exhaustion), at most 128 files / 8 MiB total. Source <=256 KiB, wall time 1..60s,
stdout/stderr <1 MiB each, artifacts <=8 MiB total; /work 32 MiB, /tmp 64 MiB,
512 MiB cgroup memory/no swap, 1 CPU, 64 PIDs, default Docker seccomp retained.
Invalid inputs return invalid_input without launching Docker; no silent clipping.

Only IMAGE is permitted. Build it using test_replay_executor.py --build, whose
in-memory build context contains exactly this module and the dedicated Dockerfile.
Never use a backend image, host mounts, a socket mount, source/customer data in a
build context, or real data in the synthetic tests. No model/tool schema is implied.

This is defense-in-depth local isolation, NOT a production hostile-code sandbox:
Docker shares its kernel, and the Docker daemon/host/operator remain trusted.
Linux prctl and resource limits are required INSIDE the dedicated Linux image;
the host controller is stdlib-only and works with Docker Desktop on macOS.
"""
from __future__ import annotations

import base64
import json
import os
import selectors
import signal
import stat
import subprocess
import sys
import time
import uuid

IMAGE = "obscura-doubleup-replay-executor:local"
OWNER_LABEL = "io.obscura.doubleup.replay-executor"
TOKEN_LABEL = "io.obscura.doubleup.replay-executor.token"
NAME_PREFIX = "obscura-doubleup-replay-"
MAX_CODE_BYTES = 256 * 1024
MAX_FILES = 128
MAX_FILENAME_BYTES = 128
MAX_FILE_BYTES = 1024 * 1024
MAX_INPUT_BYTES = 8 * 1024 * 1024
MAX_ARTIFACT_BYTES = 8 * 1024 * 1024
MAX_STREAM_BYTES = MAX_FILE_BYTES
MAX_REQUEST_BYTES = 14 * 1024 * 1024
MAX_RESULT_BYTES = 15 * 1024 * 1024
MAX_TIMEOUT_SECONDS = 60
CONTROL_TIMEOUT_SECONDS = 5
CHILD_ENV = {
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "HOME": "/tmp",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "TMPDIR": "/tmp",
    "MPLBACKEND": "Agg",
    "MPLCONFIGDIR": "/tmp/matplotlib",
    "OPENBLAS_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
}


def _result(status, *, exit_code=None, stdout="", stderr="", artifacts=None,
            limits_hit=None, error=None):
    return dict(status=status, exit_code=exit_code, stdout=stdout, stderr=stderr,
                artifacts=[] if artifacts is None else artifacts,
                limits_hit=[] if limits_hit is None else limits_hit,
                network="none", error=error)


def _filename_ok(name):
    if not isinstance(name, str) or name in ("", ".", ".."):
        return False
    try:
        if len(name.encode("utf-8")) > MAX_FILENAME_BYTES:
            return False
    except UnicodeError:
        return False
    return all(c.isalnum() or c in "._- ()" for c in name)


def _validate(code, files, timeout_seconds):
    if not isinstance(code, str):
        return "code_type"
    try:
        if len(code.encode("utf-8")) > MAX_CODE_BYTES:
            return "code_bytes"
    except UnicodeError:
        return "code_encoding"
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS:
        return "timeout_seconds"
    if type(files) is not dict:
        return "files_type"
    if len(files) > MAX_FILES:
        return "file_count"
    total = 0
    for name, content in files.items():
        if not _filename_ok(name):
            return "file_path"
        if type(content) is not bytes:
            return "file_content_type"
        if len(content) >= MAX_FILE_BYTES:
            return "file_bytes"
        total += len(content)
        if total > MAX_INPUT_BYTES:
            return "input_bytes"
    return None


class _CommandTimeout(Exception):
    pass


class _CaptureLimit(Exception):
    pass


class _ExecutorFailure(Exception):
    pass


def _capture(argv, *, payload=b"", timeout, stdout_cap=65536, stderr_cap=65536):
    """Never communicate() an unbounded pipe, even if bootstrap is subverted.

    No temporary host files and no inherited extra descriptors. Killing this CLI
    is NOT container cleanup; the caller's finally always verifies/kills/removes
    the pre-named, token-labelled container separately.
    """
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, close_fds=True)
    selector = selectors.DefaultSelector()
    out, err = bytearray(), bytearray()
    offset = 0
    deadline = time.monotonic() + timeout
    try:
        for pipe in (proc.stdin, proc.stdout, proc.stderr):
            os.set_blocking(pipe.fileno(), False)
        selector.register(proc.stdout, selectors.EVENT_READ, (out, stdout_cap))
        selector.register(proc.stderr, selectors.EVENT_READ, (err, stderr_cap))
        if payload:
            selector.register(proc.stdin, selectors.EVENT_WRITE, None)
        else:
            proc.stdin.close()
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise _CommandTimeout()
            for key, _ in selector.select(remaining):
                if key.data is None:
                    try:
                        count = os.write(key.fd, memoryview(payload)[offset:offset + 65536])
                        offset += count
                    except BrokenPipeError:
                        offset = len(payload)
                    except BlockingIOError:
                        continue
                    if offset == len(payload):
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                else:
                    destination, cap = key.data
                    try:
                        chunk = os.read(key.fd, min(65536, cap - len(destination) + 1))
                    except BlockingIOError:
                        continue
                    if not chunk:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                    else:
                        if len(destination) + len(chunk) > cap:
                            raise _CaptureLimit()
                        destination.extend(chunk)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise _CommandTimeout()
        try:
            return proc.wait(timeout=remaining), bytes(out), bytes(err)
        except subprocess.TimeoutExpired:
            raise _CommandTimeout() from None
    finally:
        selector.close()
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        for pipe in (proc.stdin, proc.stdout, proc.stderr):
            if not pipe.closed:
                pipe.close()


def _control(*args):
    return _capture(["docker", *args], timeout=CONTROL_TIMEOUT_SECONDS)


def _create_command(name, token):
    return [
        "docker", "container", "create", "--pull=never", "--interactive",
        "--name", name,
        "--label", OWNER_LABEL + "=true", "--label", TOKEN_LABEL + "=" + token,
        "--network", "none", "--read-only", "--user", "1000:1000",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges=true",
        "--pids-limit", "64", "--cpus", "1.0", "--memory", "512m",
        "--memory-swap", "512m", "--ulimit", "core=0:0",
        "--ulimit", "nofile=128:128", "--log-driver", "none",
        "--tmpfs", "/work:rw,noexec,nosuid,nodev,size=32m,uid=1000,gid=1000,mode=0700",
        "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m,uid=1000,gid=1000,mode=0700",
        "--workdir", "/work", "--hostname", "replay-executor", IMAGE,
    ]


_INSPECT_FORMAT = ('{"id":{{json .Id}},"name":{{json .Name}},'
                   '"labels":{{json .Config.Labels}},"running":{{json .State.Running}},'
                   '"oom_killed":{{json .State.OOMKilled}},'
                   '"exit_code":{{json .State.ExitCode}}}')


def _inspect_owned(name, token, expected_id=None):
    # An exact unpredictable name AND BOTH labels are necessary before mutation.
    rc, out, err = _control("container", "inspect", "--format", _INSPECT_FORMAT, name)
    if rc:
        text = err.decode("utf-8", "replace")
        if ("No such container: " + name in text or "No such object: " + name in text):
            return None
        raise _ExecutorFailure("inspect_failed")
    try:
        info = json.loads(out)
        labels = info["labels"]
        valid = (info["name"] == "/" + name and name == NAME_PREFIX + token
                 and labels.get(OWNER_LABEL) == "true"
                 and labels.get(TOKEN_LABEL) == token
                 and isinstance(info["id"], str) and len(info["id"]) == 64
                 and all(c in "0123456789abcdef" for c in info["id"])
                 and (expected_id is None or info["id"] == expected_id))
        if not valid:
            raise _ExecutorFailure("ownership_mismatch")
        return info
    except (ValueError, KeyError, TypeError, AttributeError):
        raise _ExecutorFailure("inspect_invalid") from None


def _cleanup_owned(name, token, expected_id=None):
    info = _inspect_owned(name, token, expected_id)
    if info is None:
        return
    container_id = info["id"]
    if info["running"]:
        _control("container", "kill", "--signal", "KILL", container_id)
        info = _inspect_owned(name, token, container_id)
        if info is not None and info["running"]:
            raise _ExecutorFailure("container_still_running")
    # Re-verify even when it exited naturally. Never prune, never broad rm -f.
    info = _inspect_owned(name, token, container_id)
    if info is not None:
        rc, _, _ = _control("container", "rm", container_id)
        if rc:
            raise _ExecutorFailure("container_remove_failed")


def _decode_result(raw):
    try:
        wire = json.loads(raw)
        status = wire["status"]
        if status not in ("ok", "error", "limit_error", "timeout", "executor_error"):
            raise ValueError()
        exit_code = wire["exit_code"]
        if exit_code is not None and type(exit_code) is not int:
            raise ValueError()
        limits = wire["limits_hit"]
        if (type(limits) is not list or len(limits) > 16
                or any(x not in {"stdout_bytes", "stderr_bytes", "artifact_bytes",
                                 "artifact_file_bytes", "artifact_count", "cpu_seconds",
                                 "wallclock", "memory", "protocol_bytes"} for x in limits)):
            raise ValueError()
        streams = []
        for key in ("stdout_b64", "stderr_b64"):
            blob = base64.b64decode(wire[key], validate=True)
            if len(blob) > MAX_STREAM_BYTES:
                raise ValueError()
            streams.append(blob.decode("utf-8", "surrogateescape"))
        if type(wire["artifacts"]) is not list or len(wire["artifacts"]) > MAX_FILES:
            raise ValueError()
        artifacts, seen, total = [], set(), 0
        for item in wire["artifacts"]:
            path = item["path"]
            if not _filename_ok(path) or path in seen:
                raise ValueError()
            content = base64.b64decode(item["content_b64"], validate=True)
            total += len(content)
            if len(content) > MAX_FILE_BYTES or total > MAX_ARTIFACT_BYTES:
                raise ValueError()
            seen.add(path)
            artifacts.append(dict(path=path, content=content))
        if status == "ok" and (exit_code != 0 or limits):
            raise ValueError()
        if status == "limit_error" and not limits:
            raise ValueError()
        error = wire.get("error")
        if error not in (None, "artifact_path", "artifact_read", "bootstrap_failed"):
            raise ValueError()
        return _result(status, exit_code=exit_code, stdout=streams[0], stderr=streams[1],
                       artifacts=artifacts, limits_hit=limits, error=error)
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise _ExecutorFailure("invalid_result") from None


def run_python(code: str, files: dict[str, bytes], timeout_seconds: int) -> dict:
    """Execute real Python in one fresh, named, isolated container, no mounts.

    Limits are explicit constants, not configurable Docker flags. Wall time covers
    Docker creation/start and code; verified cleanup has its own bounded control
    calls. Per-file hard RLIMIT_FSIZE also bounds each output stream; reaching the
    stream cap is conservatively a limit_error, even when the code catches EFBIG.
    Artifacts are withheld on limits/errors; within-limit stdout/stderr survive.
    Docker/runtime failures are executor_error, never synthetic successful output.
    The inner watchdog returns bounded streams on ordinary execution timeouts;
    outer hard-kill/OOM/bootstrap failures may have no recoverable streams.
    """
    problem = _validate(code, files, timeout_seconds)
    if problem:
        return _result("invalid_input", error=problem)
    request = json.dumps(dict(code=code, timeout_seconds=timeout_seconds,
                              files={k: base64.b64encode(v).decode("ascii")
                                     for k, v in files.items()}),
                         ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(request) > MAX_REQUEST_BYTES:
        return _result("invalid_input", error="request_bytes")
    token = uuid.uuid4().hex
    name = NAME_PREFIX + token
    expected_id = None
    deadline = time.monotonic() + timeout_seconds
    result = _result("executor_error", error="container_create_failed")
    try:
        rc, out, _ = _capture(_create_command(name, token),
                              timeout=min(CONTROL_TIMEOUT_SECONDS, timeout_seconds))
        if rc:
            raise _ExecutorFailure("container_create_failed")
        expected_id = out.decode("ascii").strip()
        info = _inspect_owned(name, token, expected_id)
        if info is None:
            raise _ExecutorFailure("container_missing")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise _CommandTimeout()
        # The inner watchdog gets LESS than the remaining public wall budget,
        # leaving bounded time to return its captured streams before the outer
        # watchdog kills the actual container. This never extends the deadline.
        # If the bootstrap is stuck/subverted, outer verified kill remains final.
        inner_budget = remaining - min(0.5, remaining / 4)
        envelope = json.loads(request)
        envelope["execution_budget_seconds"] = inner_budget
        request = json.dumps(envelope, ensure_ascii=False,
                             separators=(",", ":")).encode("utf-8")
        if len(request) > MAX_REQUEST_BYTES:
            raise _ExecutorFailure("request_bytes")
        rc, out, _ = _capture(["docker", "container", "start", "--attach", "--interactive", name],
                              payload=request, timeout=max(0.001, deadline - time.monotonic()),
                              stdout_cap=MAX_RESULT_BYTES, stderr_cap=65536)
        info = _inspect_owned(name, token, expected_id)
        if info is None:
            raise _ExecutorFailure("container_missing")
        if info["oom_killed"]:
            result = _result("limit_error", exit_code=info["exit_code"], limits_hit=["memory"])
        elif rc:
            raise _ExecutorFailure("bootstrap_exit")
        else:
            result = _decode_result(out)
    except _CommandTimeout:
        result = _result("timeout", limits_hit=["wallclock"])
    except _CaptureLimit:
        result = _result("limit_error", limits_hit=["protocol_bytes"])
    except (OSError, UnicodeError):
        result = _result("executor_error", error="docker_unavailable")
    except _ExecutorFailure as exc:
        result = _result("executor_error", error=str(exc))
    finally:
        try:
            _cleanup_owned(name, token, expected_id)
        except (OSError, ValueError, _CommandTimeout, _CaptureLimit, _ExecutorFailure):
            # Do not hide a potentially still-running container behind timeout/ok.
            result = _result("executor_error", error="owned_cleanup_failed")
    return result


def _child_limits(timeout_seconds):
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_FILE_BYTES, MAX_FILE_BYTES))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_CPU, (timeout_seconds, timeout_seconds))
    os.umask(0o077)


def _snapshot():
    artifacts, total, count = [], 0, 0
    root = os.open("/work", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        with os.scandir(root) as entries:
            for entry in entries:
                count += 1
                if count > MAX_FILES:
                    return [], ["artifact_count"], None
                if not _filename_ok(entry.name):
                    return [], [], "artifact_path"
                try:
                    fd = os.open(entry.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                                 dir_fd=root)
                    with os.fdopen(fd, "rb") as handle:
                        before = os.fstat(handle.fileno())
                        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                            return [], [], "artifact_path"
                        if before.st_size >= MAX_FILE_BYTES:
                            return [], ["artifact_file_bytes"], None
                        if total + before.st_size > MAX_ARTIFACT_BYTES:
                            return [], ["artifact_bytes"], None
                        content = handle.read(min(MAX_FILE_BYTES, MAX_ARTIFACT_BYTES - total) + 1)
                        after = os.fstat(handle.fileno())
                        if len(content) >= MAX_FILE_BYTES:
                            return [], ["artifact_file_bytes"], None
                        total += len(content)
                        if total > MAX_ARTIFACT_BYTES:
                            return [], ["artifact_bytes"], None
                        if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
                            return [], [], "artifact_read"
                except OSError:
                    return [], [], "artifact_path"
                artifacts.append(dict(path=entry.name,
                                      content_b64=base64.b64encode(content).decode("ascii")))
    finally:
        os.close(root)
    return sorted(artifacts, key=lambda x: x["path"]), [], None


def _wire_result(result):
    # A single bounded response is the ONLY bootstrap stdout. No code, environment
    # or intermediate data is logged. The host still treats this pipe as untrusted.
    encoded = json.dumps(result, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    if len(encoded) > MAX_RESULT_BYTES:
        encoded = json.dumps(dict(status="limit_error", exit_code=None,
                                  stdout_b64="", stderr_b64="", artifacts=[],
                                  limits_hit=["protocol_bytes"], error=None)).encode("ascii")
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def _bootstrap():
    import ctypes
    import tempfile
    # PID 1 is essential: kill(-1) below is confined to THIS private PID namespace.
    # Nondumpable stops the same-uid child opening /proc/1/fd/1 to bypass log files
    # and forge/flood the bootstrap's protocol pipe. Fail closed if unavailable.
    if os.getpid() != 1 or os.getuid() != 1000:
        raise RuntimeError("bootstrap_identity")
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(4, 0, 0, 0, 0) != 0:  # PR_SET_DUMPABLE = 4
        raise RuntimeError("bootstrap_prctl")
    os.umask(0o077)
    started = time.monotonic()
    raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    if len(raw) > MAX_REQUEST_BYTES:
        raise ValueError("request_bytes")
    request = json.loads(raw)
    files = {name: base64.b64decode(value, validate=True)
             for name, value in request["files"].items()}
    code, seconds = request["code"], request["timeout_seconds"]
    budget = request["execution_budget_seconds"]
    if (_validate(code, files, seconds) or type(budget) not in (int, float)
            or not 0 < budget <= seconds):
        raise ValueError("invalid_input")
    for name, content in files.items():
        fd = os.open("/work/" + name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
    # Source is in RAM tmpfs, never an argv string, environment value or host file.
    with tempfile.NamedTemporaryFile(dir="/tmp", suffix=".py", delete=False) as source:
        source.write(code.encode("utf-8"))
        source_path = source.name
    del code, files, raw, request
    limits, timed_out = [], False
    with tempfile.TemporaryFile(dir="/tmp") as stdout, tempfile.TemporaryFile(dir="/tmp") as stderr:
        proc = subprocess.Popen([sys.executable, "-I", "-B", "-u", source_path],
                                stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                cwd="/work", env=CHILD_ENV, close_fds=True,
                                start_new_session=True,
                                preexec_fn=lambda: _child_limits(seconds))
        try:
            try:
                exit_code = proc.wait(timeout=max(0.001, budget - (time.monotonic() - started)))
            except subprocess.TimeoutExpired:
                timed_out = True
                os.kill(-1, signal.SIGKILL)
                exit_code = proc.wait(timeout=1)
        finally:
            # A successful main process can leave setsid/fork descendants writing
            # artifacts or holding file descriptors. Kill them before reading.
            try:
                os.kill(-1, signal.SIGKILL)
            except ProcessLookupError:
                pass
        for stream, label in ((stdout, "stdout_bytes"), (stderr, "stderr_bytes")):
            if os.fstat(stream.fileno()).st_size >= MAX_STREAM_BYTES:
                limits.append(label)
        stdout.seek(0)
        stderr.seek(0)
        out = stdout.read(MAX_STREAM_BYTES)
        err = stderr.read(MAX_STREAM_BYTES)
    if timed_out:
        limits.append("wallclock")
    # SIGKILL alone is not proof of a CPU limit (the program can kill itself).
    # Cgroup OOM is identified separately through the owned container's state.
    if exit_code == -signal.SIGXCPU and not timed_out:
        limits.append("cpu_seconds")
    artifacts, artifact_limits, error = _snapshot()
    limits.extend(artifact_limits)
    status = ("timeout" if timed_out else "limit_error" if limits else
              "error" if exit_code != 0 or error else "ok")
    # No partial workspace is ever a successful state transition. On failures the
    # caller may inspect bounded stdout/stderr, but must keep its previous state.
    if status != "ok":
        artifacts = []
    _wire_result(dict(status=status, exit_code=exit_code,
                      stdout_b64=base64.b64encode(out).decode("ascii"),
                      stderr_b64=base64.b64encode(err).decode("ascii"),
                      artifacts=artifacts, limits_hit=limits, error=error))


if __name__ == "__main__":
    if sys.argv[1:] != ["--bootstrap"]:
        raise SystemExit("Import run_python; use test_replay_executor.py for synthetic tests.")
    try:
        _bootstrap()
    except BaseException:
        # Never print a traceback containing source/data or arbitrary exception text.
        _wire_result(dict(status="executor_error", exit_code=None, stdout_b64="",
                          stderr_b64="", artifacts=[], limits_hit=[], error="bootstrap_failed"))
