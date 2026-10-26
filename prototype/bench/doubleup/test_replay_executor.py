"""Synthetic checks; no corpus, credentials, models, APIs or persistent test data.

python -B test_replay_executor.py                 # quick stdlib unit checks
python -B test_replay_executor.py --build         # bounded two-file RAM build
python -B test_replay_executor.py --docker        # real isolated checks, <110s budget

The test reporter deliberately omits tracebacks/values so code/stdout/artifacts
never appear in logs, even on failure. Docker tests inspect ONLY containers they
just created, and the executor owns cleanup. No other container is attached/stopped.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
from pathlib import Path
import signal
import tarfile
import time
import unittest
from unittest import mock

import replay_executor as ex


class QuietResult(unittest.TextTestResult):
    def _exc_info_to_string(self, err, test):
        return "Synthetic check failed; code/data/traceback deliberately withheld.\n"


def build_image():
    root = Path(__file__).resolve().parents[3]
    members = {
        "Dockerfile": root / "deploy/doubleup-pilot/Dockerfile.replay-executor",
        "replay_executor.py": Path(ex.__file__).resolve(),
    }
    # Avoid transmitting the repository (or honoring its unrelated .dockerignore).
    # No staging directory, credentials, customer files, or licensing assets.
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w") as tar:
        for name, path in members.items():
            content = path.read_bytes()
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(content), 0o644, 0
            tar.addfile(info, io.BytesIO(content))
    try:
        rc, _, _ = ex._capture(["docker", "build", "--pull=false", "--file", "Dockerfile",
                                "--tag", ex.IMAGE, "-"], payload=archive.getvalue(),
                               timeout=120, stdout_cap=1024 * 1024,
                               stderr_cap=1024 * 1024)
    except (OSError, ex._CommandTimeout, ex._CaptureLimit):
        print("build: failed (bounded build output withheld)")
        return False
    print("build: passed" if rc == 0 else "build: failed (build output withheld)")
    return rc == 0


class UnitTests(unittest.TestCase):
    def test_bad_paths_and_types_never_launch(self):
        invalid = ["/etc/passwd", "../a", "a/b", "a\\b", ".", "..", "", "x\x00y",
                   "x\ny", "a:b", "n" * (ex.MAX_FILENAME_BYTES + 1), "\ud800"]
        with mock.patch.object(ex, "_capture", side_effect=AssertionError("must_not_launch")):
            for name in invalid:
                self.assertTrue(ex.run_python("pass", {name: b"x"}, 2)["status"] == "invalid_input",
                                "invalid_path_was_accepted")
            for code, files, seconds in [(b"pass", {}, 2), ("pass", [], 2),
                                         ("pass", {"a": "not_bytes"}, 2),
                                         ("pass", {}, True), ("pass", {}, 0),
                                         ("pass", {}, ex.MAX_TIMEOUT_SECONDS + 1),
                                         ("\ud800", {}, 2)]:
                self.assertTrue(ex.run_python(code, files, seconds)["status"] == "invalid_input",
                                "invalid_type_was_accepted")

    def test_oversize_is_rejected_not_truncated(self):
        huge = b"x" * ex.MAX_FILE_BYTES
        with mock.patch.object(ex, "_capture", side_effect=AssertionError("must_not_launch")):
            cases = [("x" * (ex.MAX_CODE_BYTES + 1), {}),
                     ("pass", {"a": huge}),
                     ("pass", {str(i): b"" for i in range(ex.MAX_FILES + 1)}),
                     ("pass", {str(i): huge[:-1] for i in range(9)})]
            for code, files in cases:
                self.assertTrue(ex.run_python(code, files, 2)["status"] == "invalid_input",
                                "oversize_was_not_rejected")

    def test_filename_unicode_and_exact_code_boundary(self):
        self.assertTrue(ex._filename_ok("таблица 1.csv"), "unicode_name_rejected")
        self.assertTrue(ex._validate("x" * ex.MAX_CODE_BYTES, {"x": b""}, 1) is None,
                        "exact_source_boundary_rejected")

    def test_create_command_is_explicit_and_narrow(self):
        argv = ex._create_command(ex.NAME_PREFIX + "a" * 32, "a" * 32)
        pairs = {"--network": "none", "--user": "1000:1000", "--cap-drop": "ALL",
                 "--log-driver": "none", "--pids-limit": "64", "--memory": "512m",
                 "--memory-swap": "512m", "--cpus": "1.0"}
        for flag, expected in pairs.items():
            self.assertTrue(argv[argv.index(flag) + 1] == expected, "unsafe_docker_flag")
        for flag in ("--privileged", "--volume", "-v", "--mount", "--publish", "-p",
                     "--env", "--env-file", "--pid", "--init"):
            self.assertTrue(flag not in argv, "forbidden_docker_flag")
        self.assertTrue("--read-only" in argv and argv[-1] == ex.IMAGE,
                        "wrong_rootfs_or_image")
        self.assertTrue("no-new-privileges=true" in argv and
                        not any("seccomp=unconfined" in x for x in argv), "unsafe_security")

    def test_cleanup_refuses_wrong_label_without_mutation(self):
        token, cid = "b" * 32, "c" * 64
        info = dict(id=cid, name="/" + ex.NAME_PREFIX + token,
                    labels={ex.OWNER_LABEL: "true", ex.TOKEN_LABEL: "wrong"}, running=True)
        with mock.patch.object(ex, "_control", return_value=(0, json.dumps(info).encode(), b"")) as call:
            with self.assertRaises(ex._ExecutorFailure):
                ex._cleanup_owned(ex.NAME_PREFIX + token, token, cid)
            self.assertTrue(call.call_count == 1, "cleanup_mutated_unowned_container")

    def test_cleanup_rechecks_name_labels_id_before_kill_and_remove(self):
        token, cid = "b" * 32, "c" * 64
        name, commands = ex.NAME_PREFIX + token, []
        running = [True]

        def control(*args):
            commands.append(args)
            if args[1] == "inspect":
                info = dict(id=cid, name="/" + name,
                            labels={ex.OWNER_LABEL: "true", ex.TOKEN_LABEL: token},
                            running=running[0])
                return 0, json.dumps(info).encode(), b""
            if args[1] == "kill":
                running[0] = False
            self.assertTrue(args[-1] == cid, "cleanup_target_changed")
            return 0, b"", b""

        with mock.patch.object(ex, "_control", side_effect=control):
            ex._cleanup_owned(name, token, cid)
        self.assertTrue([x[1] for x in commands] == ["inspect", "kill", "inspect", "inspect", "rm"],
                        "cleanup_verification_order")

    def test_protocol_decoder_rejects_untrusted_paths_and_limit_success(self):
        wire = dict(status="ok", exit_code=0, stdout_b64="", stderr_b64="",
                    artifacts=[dict(path="../escape", content_b64="")], limits_hit=[])
        with self.assertRaises(ex._ExecutorFailure):
            ex._decode_result(json.dumps(wire).encode())
        wire["artifacts"] = []
        wire["limits_hit"] = ["stdout_bytes"]
        with self.assertRaises(ex._ExecutorFailure):
            ex._decode_result(json.dumps(wire).encode())

    def test_protocol_preserves_binary_without_printing_it(self):
        content = bytes(range(256))
        wire = dict(status="ok", exit_code=0, stdout_b64=base64.b64encode(content).decode(),
                    stderr_b64="", artifacts=[dict(path="bytes.bin",
                    content_b64=base64.b64encode(content).decode())], limits_hit=[])
        result = ex._decode_result(json.dumps(wire).encode())
        self.assertTrue(result["stdout"].encode("utf-8", "surrogateescape") == content,
                        "binary_stdout_not_preserved")
        self.assertTrue(result["artifacts"][0]["content"] == content, "binary_artifact_not_preserved")


class DockerTests(unittest.TestCase):
    def ok(self, result):
        self.assertTrue(result["status"] == "ok", "execution_not_ok")
        self.assertTrue(result["exit_code"] == 0 and result["network"] == "none"
                        and not result["limits_hit"], "incorrect_success_metadata")

    def test_real_arithmetic_pandas_profile_numpy_excel_plot_unicode(self):
        source = '''import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
frame = pd.read_csv("таблица.csv")
values = np.asarray(frame["value"])
print(int(np.dot(values, values)))
print("Привет, мир 🌍")
frame.describe().to_json("profile.json", force_ascii=False)
frame.to_excel("result.xlsx", index=False)
plt.plot(values)
plt.savefig("plot.png")
'''
        result = ex.run_python(source, {"таблица.csv": b"value\n2\n3\n7\n"}, 20)
        self.ok(result)
        self.assertTrue(result["stdout"] == "62\nПривет, мир 🌍\n", "computed_stdout_wrong")
        artifacts = {x["path"]: x["content"] for x in result["artifacts"]}
        self.assertTrue(set(artifacts) == {"таблица.csv", "profile.json", "result.xlsx", "plot.png"},
                        "complete_snapshot_missing")
        self.assertTrue(json.loads(artifacts["profile.json"])["value"]["count"] == 3,
                        "pandas_profile_wrong")
        self.assertTrue(artifacts["result.xlsx"].startswith(b"PK") and
                        artifacts["plot.png"].startswith(b"\x89PNG"), "real_file_outputs_missing")
        changed = ex.run_python('import pandas as pd; print(int(pd.read_csv("x.csv").v.sum()))',
                                {"x.csv": b"v\n11\n13\n"}, 10)
        self.ok(changed)
        self.assertTrue(changed["stdout"] == "24\n", "input_did_not_change_computation")

    def test_independent_calls_and_explicit_snapshot_clone(self):
        original = {"state.txt": b"3"}
        code = 'from pathlib import Path; p=Path("state.txt"); p.write_text(str(int(p.read_text())+4))'
        first = ex.run_python(code, original, 10)
        second = ex.run_python(code, original, 10)
        self.ok(first)
        self.ok(second)
        self.assertTrue(first["artifacts"] == second["artifacts"] and original["state.txt"] == b"3",
                        "arms_shared_mutable_state")
        clone = {x["path"]: x["content"] for x in first["artifacts"]}
        third = ex.run_python('from pathlib import Path; print(int(Path("state.txt").read_text())*2); '
                              'Path("state.txt").unlink()', clone, 10)
        self.ok(third)
        self.assertTrue(third["stdout"] == "14\n" and third["artifacts"] == [],
                        "explicit_clone_or_deletion_wrong")
        empty = ex.run_python('from pathlib import Path; assert not Path("state.txt").exists()', {}, 10)
        self.ok(empty)

    def test_unicode_and_raw_stdout_stderr_are_not_replaced(self):
        result = ex.run_python('import os; os.write(1, "данные 🌍".encode()+bytes([255])); '
                               'os.write(2, "ошибка".encode())', {}, 10)
        self.ok(result)
        self.assertTrue(result["stdout"].encode("utf-8", "surrogateescape") ==
                        "данные 🌍".encode() + b"\xff", "raw_stdout_not_preserved")
        self.assertTrue(result["stderr"] == "ошибка", "stderr_not_preserved")

    def test_nonzero_is_not_a_canned_success(self):
        result = ex.run_python('import sys; print(6*7); sys.stderr.write("synthetic-error"); '
                               'raise SystemExit(7)', {}, 10)
        self.assertTrue(result["status"] == "error" and result["exit_code"] == 7,
                        "real_exit_code_lost")
        self.assertTrue(result["stdout"] == "42\n" and result["stderr"] == "synthetic-error"
                        and not result["artifacts"], "error_streams_lost")

    def test_real_container_config_and_no_host_secret_environment(self):
        capture, inspected = ex._capture, []

        def observed(argv, **kwargs):
            response = capture(argv, **kwargs)
            if argv[1:3] == ["container", "create"] and response[0] == 0:
                name = argv[argv.index("--name") + 1]
                rc, raw, _ = capture(["docker", "container", "inspect", "--format", "{{json .}}", name],
                                     timeout=5)
                self.assertTrue(rc == 0, "own_config_inspect_failed")
                info = json.loads(raw)
                host = info["HostConfig"]
                self.assertTrue(info["Config"]["User"] == "1000:1000", "root_user")
                self.assertTrue(host["ReadonlyRootfs"] and not host["Privileged"], "unsafe_rootfs")
                self.assertTrue(host["NetworkMode"] == "none" and host["LogConfig"]["Type"] == "none",
                                "network_or_logging_enabled")
                self.assertTrue(not host["Binds"] and not host.get("Mounts") and not info["Mounts"],
                                "unexpected_host_mount")
                self.assertTrue(host["CapDrop"] == ["ALL"] and not host["CapAdd"], "capabilities_present")
                self.assertTrue("no-new-privileges=true" in host["SecurityOpt"] and
                                not any("unconfined" in x for x in host["SecurityOpt"]), "unsafe_seccomp")
                self.assertTrue(host["PidsLimit"] == 64 and host["Memory"] == 512 * 1024**2 and
                                host["MemorySwap"] == host["Memory"] and host["NanoCpus"] == 10**9,
                                "missing_cgroup_limits")
                self.assertTrue(not host["PidMode"] and not host["PortBindings"] and
                                not host["PublishAllPorts"] and not host["Devices"], "host_namespace_or_ports")
                self.assertTrue(set(host["Tmpfs"]) == {"/tmp", "/work"} and
                                all("uid=1000" in v and "noexec" in v and "size=" in v
                                    for v in host["Tmpfs"].values()), "tmpfs_config_wrong")
                self.assertTrue(not any(x.startswith("SYNTHETIC_SECRET_SENTINEL=")
                                        for x in info["Config"]["Env"]), "host_environment_inherited")
                inspected.append(name)
            return response

        source = '''import os, resource, socket, time
from pathlib import Path
assert os.getuid() == 1000
assert os.getenv("SYNTHETIC_SECRET_SENTINEL") is None
assert set(os.environ) <= {"PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", "MPLBACKEND", "MPLCONFIGDIR", "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"}
assert not Path("/var/run/docker.sock").exists()
assert not Path("/app").exists()
for path in ("/etc/replay-forbidden", "/proc/1/fd/1", "/proc/1/fd/0"):
    try:
        fd = os.open(path, os.O_WRONLY | (os.O_CREAT if path.startswith("/etc/") else 0), 0o600)
    except OSError:
        pass
    else:
        os.close(fd)
        raise AssertionError("isolation_bypass")
soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
assert soft == hard == 1048576
try:
    resource.setrlimit(resource.RLIMIT_FSIZE, (hard+1, hard+1))
except (ValueError, OSError):
    pass
else:
    raise AssertionError("hard_limit_raised")
start = time.monotonic()
sock = socket.socket()
sock.settimeout(0.25)
try:
    sock.connect(("203.0.113.1", 443))
except OSError:
    pass
else:
    raise AssertionError("outbound_network")
finally:
    sock.close()
assert time.monotonic()-start < 1
print(12+1)
'''
        with mock.patch.dict(os.environ, {"SYNTHETIC_SECRET_SENTINEL": "synthetic-only"}), \
             mock.patch.object(ex, "_capture", side_effect=observed):
            result = ex.run_python(source, {}, 12)
        self.ok(result)
        self.assertTrue(len(inspected) == 1 and result["stdout"] == "13\n", "isolation_check_failed")

    def test_os_write_cannot_flood_host_and_limit_is_explicit(self):
        result = ex.run_python('import os; os.write(2,b"kept"); '
                               'exec("while True:\\n os.write(1,b\\\"x\\\"*65536)")', {}, 10)
        self.assertTrue(result["status"] == "limit_error" and "stdout_bytes" in result["limits_hit"],
                        "stdout_flood_not_a_limit_error")
        self.assertTrue(len(result["stdout"].encode()) <= ex.MAX_STREAM_BYTES and
                        result["stderr"].startswith("kept") and not result["artifacts"],
                        "stdout_flood_not_bounded_or_stderr_lost")

    def test_stderr_and_artifact_file_count_caps_are_explicit(self):
        sources = [
            ('import os; exec("while True:\\n os.write(2,b\\\"x\\\"*65536)")', "stderr_bytes"),
            ('from pathlib import Path; Path("large.bin").write_bytes(b"x"*1048577)',
             "artifact_file_bytes"),
            ('from pathlib import Path\nfor i in range(129): Path(str(i)).touch()',
             "artifact_count"),
        ]
        for source, limit in sources:
            result = ex.run_python(source, {}, 10)
            self.assertTrue(result["status"] == "limit_error" and limit in result["limits_hit"]
                            and result["artifacts"] == [], "hard_cap_not_explicit")

    def test_artifact_total_cap_never_returns_partial_success(self):
        source = 'from pathlib import Path\nfor i in range(17): Path(str(i)+".bin").write_bytes(b"x"*524288)'
        result = ex.run_python(source, {}, 12)
        self.assertTrue(result["status"] == "limit_error" and "artifact_bytes" in result["limits_hit"]
                        and result["artifacts"] == [], "artifact_total_not_enforced")

    def test_symlink_directory_and_fifo_are_not_extracted(self):
        for source in ('import os; os.symlink("/etc/hostname", "escape")',
                       'import os; os.mkdir("nested")', 'import os; os.mkfifo("pipe")'):
            result = ex.run_python(source, {}, 10)
            self.assertTrue(result["status"] == "error" and result["error"] == "artifact_path"
                            and result["artifacts"] == [], "unsafe_artifact_accepted")

    def test_inner_timeout_preserves_streams_and_discards_partial_workspace(self):
        result = ex.run_python('import os, time; os.write(1,b"before-timeout"); '
                               'os.write(2,b"kept-error"); '
                               'exec("while True:\\n time.sleep(0.05)")', {}, 3)
        self.assertTrue(result["status"] == "timeout" and "wallclock" in result["limits_hit"]
                        and result["exit_code"] == -9, "inner_timeout_not_real_kill")
        self.assertTrue(result["stdout"] == "before-timeout" and result["stderr"] == "kept-error"
                        and result["artifacts"] == [], "timeout_streams_not_preserved")

    def test_wallclock_kills_actual_owned_container_and_removes_it(self):
        capture, control = ex._capture, ex._control
        owned, killed = [], []

        def observed(argv, **kwargs):
            if argv[1:3] == ["container", "start"]:
                # Exercise the OUTER fallback, not just the cooperative inner
                # watchdog: remove its reserve without extending the public limit.
                envelope = json.loads(kwargs["payload"])
                envelope["execution_budget_seconds"] = envelope["timeout_seconds"]
                kwargs["payload"] = json.dumps(envelope).encode()
            response = capture(argv, **kwargs)
            if argv[1:3] == ["container", "create"] and response[0] == 0:
                name = argv[argv.index("--name") + 1]
                owned.append((name, name[len(ex.NAME_PREFIX):], response[1].decode().strip()))
            return response

        def mutations(*args):
            if args[:2] == ("container", "kill"):
                killed.append(args[-1])
            return control(*args)

        start = time.monotonic()
        with mock.patch.object(ex, "_capture", side_effect=observed), \
             mock.patch.object(ex, "_control", side_effect=mutations):
            result = ex.run_python("while True: pass", {}, 3)
        self.assertTrue(result["status"] == "timeout" and "wallclock" in result["limits_hit"],
                        "wallclock_not_enforced")
        self.assertTrue(time.monotonic() - start < 12 and len(owned) == 1, "timeout_cleanup_too_slow")
        self.assertTrue(owned[0][2] in killed, "only_cli_was_killed")
        self.assertTrue(ex._inspect_owned(*owned[0]) is None, "owned_container_remained")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--docker", action="store_true")
    args = parser.parse_args()
    if args.build and not build_image():
        return 1
    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(UnitTests)])
    if args.docker:
        # Independent global bound, not a reason to increase individual timeouts.
        def deadline(_signum, _frame):
            raise TimeoutError("synthetic_suite_wallclock")
        signal.signal(signal.SIGALRM, deadline)
        signal.alarm(110)
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(DockerTests))
    try:
        result = unittest.TextTestRunner(verbosity=1, resultclass=QuietResult).run(suite)
        return 0 if result.wasSuccessful() else 1
    finally:
        if args.docker:
            signal.alarm(0)


if __name__ == "__main__":
    raise SystemExit(main())
