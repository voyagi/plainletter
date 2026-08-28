"""No tracked file may carry an AWS account id.

This repository goes public at submission and is then frozen, so a leak found afterwards cannot be
fixed by editing a file: the only remedy is deleting and recreating the repository, which is how
the personal email address in the history was dealt with.

It nearly happened on 2026-08-28. The AgentCore scaffold tracks `agentcore/.cli/deployed-state.json`
and un-ignores it deliberately, which is correct for a private repository. The first deploy filled
it with four ARNs and every one of them carried the account id. That file is ignored here now, and
this is the check that would have caught it either way.

A twelve-digit run is also what a Dutch reference number looks like, so the check is anchored on the
places an account id actually appears: an ARN, or an IAM or STS identifier beside it.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

# `arn:aws:service:region:123456789012:` and `"Account": "123456789012"` are the two shapes that
# carry one. A bare twelve-digit number is not enough to accuse a file: the sample letters are full
# of long reference numbers that are nobody's account.
ACCOUNT_ID = re.compile(
    r"arn:aws(?:-[a-z]+)*:[a-z0-9-]*:[a-z0-9-]*:(\d{12}):"
    r"|(?:account[_-]?id|Account)\W{0,4}(\d{12})",
    re.IGNORECASE,
)

#: The gate's own fixtures name a placeholder account on purpose, and this file quotes the shape it
#: is looking for. Neither is a leak, and both would fail a check that could not say so.
ALLOWED = frozenset({"123456789012", "000000000000"})

SKIP_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".ico", ".pdf", ".zip", ".woff", ".woff2")


def tracked_files() -> list[str]:
    # Resolved rather than spelled, so the test runs the git on the path and not a `git` that
    # happens to sit in the working directory.
    git = shutil.which("git")
    assert git, "git is not on the path, so this check cannot say anything"
    listed = subprocess.run(  # noqa: S603
        [git, "ls-files"], capture_output=True, text=True, check=True, cwd=Path.cwd()
    )
    return [line for line in listed.stdout.splitlines() if line]


def test_git_actually_answered() -> None:
    # An empty listing would make every assertion below pass over nothing at all.
    files = tracked_files()
    assert len(files) > 100, f"only {len(files)} tracked files, which is not this repository"


@pytest.mark.parametrize("path", tracked_files())
def test_no_tracked_file_carries_an_aws_account_id(path: str) -> None:
    if path.endswith(SKIP_SUFFIXES):
        return
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (UnicodeDecodeError, FileNotFoundError):
        return
    found = {
        digits
        for match in ACCOUNT_ID.finditer(text)
        for digits in match.groups()
        if digits and digits not in ALLOWED
    }
    assert not found, f"{path} carries what looks like an AWS account id: {sorted(found)}"
