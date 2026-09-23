"""Verify the release tag matches the packaged distribution version.

pyproject.toml owns the version, and the installed distribution metadata is
derived from it. Comparing that against the release tag catches drift, so a
release cannot be published when the two disagree.

Reads the version through importlib.metadata rather than tomllib, which is
only available on Python 3.11+ while this project supports 3.10.
"""

import os
import re
import sys
from importlib.metadata import PackageNotFoundError, version

DISTRIBUTION_NAME = "ohmyagent-info-system-agent"


def expected_tag_version() -> str | None:
    """Return the version encoded in the release tag, or None when untagged."""
    ref = os.environ.get("GITHUB_REF", "")
    if not ref.startswith("refs/tags/"):
        return None
    tag = ref[len("refs/tags/") :]
    match = re.fullmatch(r"v?(\d+\.\d+\.\d+(?:[-.].+)?)", tag)
    return match.group(1) if match else None


def main() -> int:
    try:
        packaged = version(DISTRIBUTION_NAME)
    except PackageNotFoundError:
        print(f"{DISTRIBUTION_NAME} is not installed", file=sys.stderr)
        return 1

    tag_version = expected_tag_version()
    if tag_version is None:
        print(f"no release tag in this build; packaged version is {packaged}")
        return 0

    if tag_version != packaged:
        print(
            f"release tag says {tag_version} but the distribution is {packaged}",
            file=sys.stderr,
        )
        return 1

    print(f"release tag and packaged version agree on {packaged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
