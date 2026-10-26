"""Owner-approved $10 aggregate dialogue run; always close local paid egress."""

import argparse
import os
import json
import signal
import sys
import subprocess

import httpx
import dialogue_runner
from stand import live_mode, STATE


def interrupted(_signal, _frame):
    dialogue_runner.CANCELLED.set()
    raise KeyboardInterrupt


def require_upstream_ready():
    access = json.loads((STATE / 'runtime' / 'model-access.json').read_text())
    with httpx.Client(timeout=30, trust_env=False, follow_redirects=False) as client:
        response = client.get('http://127.0.0.1:18850/v1/pilot/upstream-check',
            headers={'Authorization': 'Bearer ' + access['request_key']})
    result = response.json()
    safe = {key: result.get(key) for key in ('transport_ok', 'http_status', 'error_type', 'elapsed_seconds')}
    print(json.dumps({'upstream_preflight': safe, 'model_calls': 0, 'reservation_created': False}), flush=True)
    if result.get('transport_ok') is not True:
        if os.environ.get('PILOT_SKIP_PREFLIGHT') == '1':
            print(json.dumps({'upstream_preflight_advisory_only': True}), flush=True)
            return safe
        raise RuntimeError('upstream_preflight_failed_no_model_request')
    return safe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case-index', type=int)
    parser.add_argument('--mode', action='append', choices=('none', 'builtin', 'pseudex'))
    parser.add_argument('--continue-other-arms', action='store_true')
    parser.add_argument('--revision', default='v1')
    parser.add_argument('--bundle', default='full-dialogue-cases')
    parser.add_argument('--parallel-cases', type=int, default=5)
    parser.add_argument('--preflight-only', action='store_true', help='Read-only upstream check; never construct a model run')
    parser.add_argument('--engine-image', default='sha256:45dc6170bf493ef5bf3a9eb78a2213bb69aad26460554ce6a41514fbd60c5c98')
    parser.add_argument('--resume-known-prefix', action='store_true')
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, interrupted)
    try:
        actual = subprocess.check_output(['docker', 'inspect', 'obscura-doubleup-pilot-sidecar-1', '--format', '{{.Image}}'], text=True).strip()
        if actual != args.engine_image:
            raise RuntimeError('approved_engine_image_not_running')
        live_mode(True)
        require_upstream_ready()
        if args.preflight_only:
            print(json.dumps({'preflight_only': True, 'model_calls': 0, 'reservation_created': False}), flush=True)
            return
        sys.argv = ['dialogue_runner', '--live', '--revision', args.revision, '--bundle', args.bundle,
            '--parallel-cases', str(args.parallel_cases)]
        if args.case_index is not None: sys.argv += ['--case-index', str(args.case_index)]
        for mode in args.mode or []: sys.argv += ['--mode', mode]
        if args.continue_other_arms: sys.argv += ['--continue-other-arms']
        if args.resume_known_prefix: sys.argv += ['--resume-known-prefix']
        dialogue_runner.main()
    finally:
        live_mode(False)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('dialogue_run_interrupted_egress_closed', file=sys.stderr)
        raise SystemExit(130)
    except Exception as error:
        print(json.dumps({'ok': False, 'error_type': type(error).__name__, 'error_code': 'dialogue_live_failed_egress_closed'}), file=sys.stderr)
        raise SystemExit(2)
