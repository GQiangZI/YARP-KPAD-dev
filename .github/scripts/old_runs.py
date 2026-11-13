#!/usr/bin/env python3
"""Pick old GitHub Actions runs to delete, one run id per output line.

usage: old_runs.py <keep> [<protected run id>...]  < runs.jsonl
runs.jsonl: one Actions run object per line (id, workflow_id, status, conclusion, created_at).

Per workflow it keeps the <keep> newest finished runs and the newest successful one (Verify's
fast path and republish read that run's artifact). Protected ids (e.g. STOCK_RUN, whose stock
images every Verify downloads) and unfinished runs are never picked. Releases are not runs, so
deleting runs never touches them.
"""
import json
import sys
from collections import defaultdict


def pick(runs, keep, protected):
    by_wf = defaultdict(list)
    for r in runs:
        by_wf[r['workflow_id']].append(r)
    old = []
    for wf_runs in by_wf.values():
        done = sorted((r for r in wf_runs if r['status'] == 'completed'), key=lambda r: r['created_at'], reverse=True)
        kept = {r['id'] for r in done[:keep]}
        kept |= {r['id'] for r in [r for r in done if r['conclusion'] == 'success'][:1]}
        old += [r['id'] for r in done if r['id'] not in kept and r['id'] not in protected]
    return sorted(old)


def selftest():
    def run(i, wf, day, status='completed', conclusion='failure'):
        return {'id': i, 'workflow_id': wf, 'status': status, 'conclusion': conclusion, 'created_at': f'2026-10-{day:02d}T00:00:00Z'}
    runs = [run(1, 'b', 1, conclusion='success'), run(2, 'b', 2), run(3, 'b', 3), run(4, 'b', 4),
            run(5, 'v', 1), run(6, 'v', 2), run(7, 'v', 3, status='in_progress', conclusion=None),
            run(8, 's', 1, conclusion='success'), run(9, 's', 2, conclusion='success')]
    got = pick(runs, 2, {8})
    # b: 4,3 newest, 1 newest success; v: 6,5 newest (7 unfinished); s: 9 newest, 8 protected
    assert got == [2], got
    assert pick(runs, 0, set()) == [2, 3, 4, 5, 6, 8], pick(runs, 0, set())
    print('old_runs self-test ok')


if __name__ == '__main__':
    if sys.argv[1:] == ['--selftest']:
        selftest()
        sys.exit(0)
    keep, protected = int(sys.argv[1]), {int(x) for x in sys.argv[2:] if x.isdigit()}
    runs = [json.loads(line) for line in sys.stdin if line.strip()]
    print('\n'.join(map(str, pick(runs, keep, protected))))
