#!/usr/bin/env python3
"""
Check the dataset in server/data across all four systems.

    cd server && uv run python ../scripts/check_data.py
    cd server && uv run python ../scripts/check_data.py --min-policies 1000   # also checks coverage targets
    cd server && uv run python ../scripts/check_data.py --json

Exit code 0 when every integrity check passes (and every coverage target, if
you asked for them). Warnings never fail the run: they are the drift in Heron's
hand-keyed claim fields that the modern journey is meant to remove.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'server'))

import data_health  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--data-dir', default=os.path.join(ROOT, 'server', 'data'))
    ap.add_argument('--min-policies', type=int, default=0, help='turn on coverage targets and require this many policies')
    ap.add_argument('--coverage', action='store_true', help='report coverage targets without a minimum policy count')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    rep = data_health.run(a.data_dir, min_policies=a.min_policies, coverage=a.coverage)
    print(json.dumps(rep, indent=1) if a.json else data_health.format_report(rep))
    sys.exit(0 if rep['ok'] else 1)


if __name__ == '__main__':
    main()
