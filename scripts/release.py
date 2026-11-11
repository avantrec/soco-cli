#!/usr/bin/env python3
"""Automate the SoCo-CLI release process (see RELEASING.txt).

Run from the repository root on the 'next_version' branch, once the
CHANGELOG entry for the version in soco_cli/__init__.py is complete:

    python scripts/release.py [--dry-run] [--test-pypi] [--yes]

Checks (all run before anything is changed):
  - On 'next_version', working tree clean, in sync with 'origin'
  - 'master' can be fast-forwarded to 'next_version'
  - CHANGELOG.txt starts with a non-empty entry for the version
  - Tag vX.Y.Z does not exist; version X.Y.Z is not on PyPI
  - 'make format' and 'make toc' leave the tree unchanged
  - The GitHub CI run for the 'next_version' commit succeeded

Release steps:
  1. Fast-forward 'master' to 'next_version' and push
  2. Create annotated tag vX.Y.Z and push it
  3. Build and upload to PyPI ('make pypi_upload')
  4. On 'next_version': bump the patch version, add a CHANGELOG
     placeholder, commit "Prep for vX.Y.Z+1 development", and push
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INIT_FILE = os.path.join(ROOT, "soco_cli", "__init__.py")
CHANGELOG = os.path.join(ROOT, "CHANGELOG.txt")
DEV_BRANCH = "next_version"
RELEASE_BRANCH = "master"
REMOTE = "origin"
CI_WORKFLOW = "tests.yml"
VERSION_RE = re.compile(r'^__version__ = "(\d+)\.(\d+)\.(\d+)"$', re.M)
TOC_FOOTER_RE = re.compile(r"^[-+]<!-- Added by: .* -->$")


class ReleaseError(Exception):
    pass


def run(*cmd, capture=True, check=True):
    """Run a command in the repo root; return stripped stdout."""
    result = subprocess.run(
        cmd,
        cwd=ROOT,
        check=False,
        universal_newlines=True,
        stdout=subprocess.PIPE if capture else None,
    )
    if check and result.returncode != 0:
        raise ReleaseError(
            "Command failed ({}): {}".format(result.returncode, " ".join(cmd))
        )
    return (result.stdout or "").strip()


def info(msg):
    print("==> " + msg, flush=True)


def get_version():
    with open(INIT_FILE) as f:
        match = VERSION_RE.search(f.read())
    if not match:
        raise ReleaseError("Can't find __version__ in {}".format(INIT_FILE))
    return tuple(int(x) for x in match.groups())


def version_str(version):
    return "{}.{}.{}".format(*version)


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_git_state():
    branch = run("git", "rev-parse", "--abbrev-ref", "HEAD")
    if branch != DEV_BRANCH:
        raise ReleaseError("On branch '{}'; switch to '{}'".format(branch, DEV_BRANCH))
    if run("git", "status", "--porcelain"):
        raise ReleaseError("Working tree is not clean; commit or stash changes first")
    info("Fetching from '{}'".format(REMOTE))
    run("git", "fetch", "--tags", REMOTE)
    head = run("git", "rev-parse", "HEAD")
    remote_head = run("git", "rev-parse", "{}/{}".format(REMOTE, DEV_BRANCH))
    if head != remote_head:
        raise ReleaseError(
            "'{0}' differs from '{1}/{0}'; push or pull first".format(
                DEV_BRANCH, REMOTE
            )
        )
    for ref in (RELEASE_BRANCH, "{}/{}".format(REMOTE, RELEASE_BRANCH)):
        if not run("git", "rev-parse", "--verify", "--quiet", ref, check=False):
            continue  # e.g., no local release branch yet; 'git checkout' will create it
        if (
            subprocess.call(
                ["git", "merge-base", "--is-ancestor", ref, "HEAD"], cwd=ROOT
            )
            != 0
        ):
            raise ReleaseError(
                "'{}' can't be fast-forwarded to '{}'".format(ref, DEV_BRANCH)
            )
    return head


def check_changelog(version):
    with open(CHANGELOG) as f:
        first_line = f.readline().rstrip("\n")
    match = re.match(r"^v(\S+)\s+-\s*(.*)$", first_line)
    if not match or match.group(1) != version:
        raise ReleaseError(
            "CHANGELOG.txt doesn't start with an entry for v{}".format(version)
        )
    if not match.group(2):
        raise ReleaseError("CHANGELOG.txt entry for v{} is empty".format(version))


def check_tag_and_pypi(version):
    tag = "v" + version
    if run("git", "tag", "--list", tag):
        raise ReleaseError("Tag {} already exists".format(tag))
    url = "https://pypi.org/pypi/soco-cli/{}/json".format(version)
    try:
        urllib.request.urlopen(url, timeout=15)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return
        raise ReleaseError("Unexpected response from PyPI: {}".format(e))
    except urllib.error.URLError as e:
        raise ReleaseError("Can't reach PyPI: {}".format(e))
    raise ReleaseError("Version {} is already on PyPI".format(version))


def check_format_and_toc():
    info("Running 'make format' and 'make toc'")
    run("make", "format")
    run("make", "toc")
    for path in glob.glob(os.path.join(ROOT, "README.md.orig.*")) + glob.glob(
        os.path.join(ROOT, "README.md.toc.*")
    ):
        os.remove(path)
    # The TOC footer contains a timestamp: ignore changes to that line alone
    readme_diff = run("git", "diff", "-U0", "--", "README.md").splitlines()
    changed = [
        line
        for line in readme_diff
        if line[:1] in "+-"
        and not line.startswith(("+++", "---"))
        and not TOC_FOOTER_RE.match(line)
    ]
    if not changed:
        run("git", "checkout", "--", "README.md")
    dirty = run("git", "status", "--porcelain")
    if dirty:
        raise ReleaseError(
            "'make format'/'make toc' changed files; review, commit, push, and let CI run:\n"
            + dirty
        )


def check_ci(head):
    try:
        output = run(
            "gh",
            "run",
            "list",
            "--commit",
            head,
            "--workflow",
            CI_WORKFLOW,
            "--json",
            "status,conclusion,url",
        )
    except (OSError, ReleaseError) as e:
        raise ReleaseError("Can't query CI status with 'gh': {}".format(e))
    runs = json.loads(output or "[]")
    if not runs:
        raise ReleaseError("No CI run found for {}".format(head[:7]))
    latest = runs[0]
    if latest["status"] != "completed":
        raise ReleaseError(
            "CI run for {} is still {}: {}".format(
                head[:7], latest["status"], latest["url"]
            )
        )
    if latest["conclusion"] != "success":
        raise ReleaseError(
            "CI run for {} concluded '{}': {}".format(
                head[:7], latest["conclusion"], latest["url"]
            )
        )


# ---------------------------------------------------------------------------
# Release steps
# ---------------------------------------------------------------------------


def bump_for_next_version(version):
    next_version = (version[0], version[1], version[2] + 1)
    next_str = version_str(next_version)
    with open(INIT_FILE) as f:
        text = f.read()
    with open(INIT_FILE, "w") as f:
        f.write(VERSION_RE.sub('__version__ = "{}"'.format(next_str), text))
    with open(CHANGELOG) as f:
        text = f.read()
    with open(CHANGELOG, "w") as f:
        f.write("v{:<9}-\n".format(next_str) + text)
    return next_str


def main():
    parser = argparse.ArgumentParser(description="Release SoCo-CLI (see RELEASING.txt)")
    parser.add_argument(
        "--dry-run", action="store_true", help="run the checks only; change nothing"
    )
    parser.add_argument(
        "--test-pypi", action="store_true", help="upload to TestPyPI instead of PyPI"
    )
    parser.add_argument("--yes", action="store_true", help="don't ask for confirmation")
    args = parser.parse_args()

    version = version_str(get_version())
    tag = "v" + version
    info("Preparing release {}".format(tag))

    head = check_git_state()
    check_changelog(version)
    check_tag_and_pypi(version)
    check_format_and_toc()
    check_ci(head)
    info("All checks passed")

    target = "TestPyPI" if args.test_pypi else "PyPI"
    print(
        "\nThis will:\n"
        "  1. Fast-forward '{rel}' to '{dev}' ({head}) and push\n"
        "  2. Create and push tag {tag}\n"
        "  3. Build and upload {version} to {target}\n"
        "  4. Bump '{dev}' to the next patch version and push\n".format(
            rel=RELEASE_BRANCH,
            dev=DEV_BRANCH,
            head=head[:7],
            tag=tag,
            version=version,
            target=target,
        )
    )
    if args.dry_run:
        info("Dry run: stopping here")
        return
    if not args.yes and input("Proceed? [y/N] ").strip().lower() not in ("y", "yes"):
        info("Aborted; nothing changed")
        return

    steps = [
        "git checkout {0} && git merge --ff-only {1} && git push {2} {0}".format(
            RELEASE_BRANCH, DEV_BRANCH, REMOTE
        ),
        "git tag -a {0} -m 'Version {1}' && git push {2} {0}".format(
            tag, version, REMOTE
        ),
        "make {}".format("pypi_test" if args.test_pypi else "pypi_upload"),
        "git checkout {}; bump version, update CHANGELOG, commit, push".format(
            DEV_BRANCH
        ),
    ]
    step = 0
    try:
        info("Step 1: updating '{}'".format(RELEASE_BRANCH))
        run("git", "checkout", RELEASE_BRANCH, capture=False)
        run("git", "merge", "--ff-only", DEV_BRANCH, capture=False)
        run("git", "push", REMOTE, RELEASE_BRANCH, capture=False)

        step = 1
        info("Step 2: tagging {}".format(tag))
        run("git", "tag", "-a", tag, "-m", "Version " + version)
        run("git", "push", REMOTE, tag, capture=False)

        step = 2
        info("Step 3: uploading to {}".format(target))
        run("make", "pypi_test" if args.test_pypi else "pypi_upload", capture=False)

        step = 3
        info("Step 4: preparing '{}' for the next version".format(DEV_BRANCH))
        run("git", "checkout", DEV_BRANCH, capture=False)
        next_str = bump_for_next_version(get_version())
        run("git", "commit", "-a", "-m", "Prep for v{} development".format(next_str))
        run("git", "push", REMOTE, DEV_BRANCH, capture=False)
    except (ReleaseError, KeyboardInterrupt) as e:
        print("\nRelease failed at step {}: {}".format(step + 1, e), file=sys.stderr)
        print("Remaining steps to complete by hand:", file=sys.stderr)
        for i, remaining in enumerate(steps[step:], start=step + 1):
            print("  {}. {}".format(i, remaining), file=sys.stderr)
        sys.exit(1)

    info("Released {}; '{}' is now at v{}".format(tag, DEV_BRANCH, next_str))


if __name__ == "__main__":
    try:
        main()
    except ReleaseError as e:
        print("Error: {}".format(e), file=sys.stderr)
        sys.exit(1)
