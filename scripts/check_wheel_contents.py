"""Fail if the built wheel is missing runtime data that the app needs.

The app serves HTML templates and static assets straight out of the package,
and renders generated projects from Jinja templates inside it. If packaging
config regresses, the wheel still builds but the app breaks at runtime, so
this check runs in CI.
"""

import glob
import sys
import zipfile

REQUIRED_IN_WHEEL = [
    "oma_info_system/web/templates/index.html",
    "oma_info_system/web/templates/session.html",
    "oma_info_system/web/templates/magic.html",
    "oma_info_system/web/static/magic-experience.css",
    "oma_info_system/generation/templates/app.py",
    "oma_info_system/generation/templates/views.py",
]


def main() -> int:
    wheels = glob.glob("dist/*.whl")
    if not wheels:
        print("no wheel found in dist/", file=sys.stderr)
        return 1

    wheel = wheels[0]
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())

    missing = [name for name in REQUIRED_IN_WHEEL if name not in names]
    if missing:
        print(f"{wheel} is missing packaged data:", file=sys.stderr)
        for name in missing:
            print(f"  - {name}", file=sys.stderr)
        return 1

    print(f"{wheel}: all {len(REQUIRED_IN_WHEEL)} required data files present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
