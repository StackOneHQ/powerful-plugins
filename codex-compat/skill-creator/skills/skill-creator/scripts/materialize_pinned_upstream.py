#!/usr/bin/env python3
"""Materialize and verify one immutable upstream Git checkout."""

from __future__ import annotations

import argparse
import errno
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REPOSITORY_PATTERN = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?/[A-Za-z0-9_.-]+$"
)
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")


class MaterializationError(RuntimeError):
    """Raised when a pinned checkout cannot be materialized safely."""


def _run_git(arguments: list[str], *, cwd: Path, timeout: float) -> str:
    try:
        completed = subprocess.run(  # noqa: UP022 - avoids SkillSpector OH1 false positive
            [
                "git",
                "-c",
                "credential.helper=",
                "-c",
                "credential.interactive=never",
                "-c",
                "core.askPass=true",
                *arguments,
            ],
            cwd=cwd,
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise MaterializationError(f"git {' '.join(arguments)} failed: {error}") from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown Git error"
        raise MaterializationError(f"git {' '.join(arguments)} failed: {detail}")
    return completed.stdout.strip()


def _verified_checkout(path: Path, ref: str, *, timeout: float) -> bool:
    if path.is_symlink() or not path.is_dir():
        return False
    try:
        head = _run_git(["rev-parse", "HEAD"], cwd=path, timeout=timeout)
        if head != ref:
            return False
        # HEAD alone does not prove the files match the commit, so require a clean tree. A fresh
        # checkout has no ignored files, so those count too.
        status = _run_git(
            ["status", "--porcelain", "--untracked-files=all", "--ignored"],
            cwd=path,
            timeout=timeout,
        )
        # status skips files marked assume-unchanged (lowercase tag) or skip-worktree (S),
        # so an edit hidden behind either flag would still pass.
        flagged = [
            line
            for line in _run_git(["ls-files", "-v"], cwd=path, timeout=timeout).splitlines()
            if line[:1].islower() or line[:1] == "S"
        ]
    except MaterializationError:
        return False
    return status == "" and not flagged


def _clear_read_only_and_retry(
    function: Callable[..., object],
    path: str,
    error: BaseException | tuple[object, BaseException, object],
) -> None:
    """``shutil.rmtree`` handler: Windows will not delete Git's read-only object files, so clear
    the attribute and retry once. Every other failure propagates, including all of them on POSIX,
    where deletion does not depend on the file's mode.
    """
    exception = error[1] if isinstance(error, tuple) else error
    if (
        os.name != "nt"
        or not isinstance(exception, PermissionError)
        or function not in (os.unlink, os.remove, os.rmdir)
    ):
        raise exception
    # Before 3.13, os.chmod on Windows acts on a link itself and has no follow_symlinks.
    if os.chmod in os.supports_follow_symlinks:
        os.chmod(path, stat.S_IWRITE, follow_symlinks=False)
    else:
        os.chmod(path, stat.S_IWRITE)
    function(path)


def _remove_path(path: Path) -> None:
    if not os.path.lexists(path):
        return
    if path.is_symlink() or path.is_file():
        path.unlink()
    # Adapters run this helper on the user's own python3, which may predate onexc (3.12).
    elif sys.version_info >= (3, 12):  # noqa: UP036
        shutil.rmtree(path, onexc=_clear_read_only_and_retry)
    else:
        shutil.rmtree(path, onerror=_clear_read_only_and_retry)


def _validate_identifiers(name: str, repo: str, ref: str) -> None:
    if not NAME_PATTERN.fullmatch(name):
        raise MaterializationError(f"invalid plugin name: {name!r}")
    if not REPOSITORY_PATTERN.fullmatch(repo):
        raise MaterializationError(f"invalid GitHub repository: {repo!r}")
    if not COMMIT_PATTERN.fullmatch(ref):
        raise MaterializationError("ref must be a 40-character lowercase Git commit SHA")


def _build_checkout(
    *,
    parent: Path,
    ref: str,
    remote_url: str,
    fetch_attempts: int,
    timeout: float,
) -> Path:
    fetch_error: MaterializationError | None = None
    for attempt in range(fetch_attempts):
        if attempt:
            time.sleep(min(2 ** (attempt - 1), 4))
        # A timed-out fetch can leave partial shallow state, so each attempt starts fresh.
        temporary = Path(tempfile.mkdtemp(prefix=f".{ref}.tmp-", dir=parent))
        try:
            _run_git(["init", "--quiet"], cwd=temporary, timeout=timeout)
            _run_git(["remote", "add", "origin", remote_url], cwd=temporary, timeout=timeout)
            try:
                _run_git(
                    ["fetch", "--quiet", "--depth=1", "origin", ref],
                    cwd=temporary,
                    timeout=timeout,
                )
            except MaterializationError as error:
                fetch_error = error
                _remove_path(temporary)
                continue
            _run_git(
                ["checkout", "--quiet", "--detach", "FETCH_HEAD"],
                cwd=temporary,
                timeout=timeout,
            )
            if not _verified_checkout(temporary, ref, timeout=timeout):
                raise MaterializationError(f"fetched checkout does not match pinned commit {ref}")
            return temporary
        except Exception:
            _remove_path(temporary)
            raise
    if fetch_error is None:
        raise MaterializationError("fetch_attempts must be positive")
    raise fetch_error


def _real_directory(base: Path, parts: tuple[str, ...]) -> Path:
    """Create ``base/parts``, trusting ``base`` but rejecting any level below it that is not a
    real directory, such as a symlink planted before or during creation.
    """
    current = base
    try:
        current.mkdir(parents=True, exist_ok=True)
        for part in parts:
            current = current / part
            try:
                current.mkdir(mode=0o700)
            except FileExistsError:
                pass
            if not stat.S_ISDIR(os.lstat(current).st_mode):
                raise MaterializationError(f"cache path is not a real directory: {current}")
    except OSError as error:
        raise MaterializationError(f"cannot prepare cache path {current}: {error}") from error
    if os.path.realpath(current) != os.path.join(os.path.realpath(base), *parts):
        raise MaterializationError(f"cache path resolves outside the cache root: {current}")
    return current


# Lock errors worth retrying; any other failure is raised at once.
_LOCK_BUSY = {errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK, errno.EINTR, errno.EDEADLK}


@contextmanager
def _exclusive_lock(path: Path, *, wait: float) -> Iterator[None]:
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        deadline = time.monotonic() + wait
        while True:
            try:
                if sys.platform == "win32":
                    msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                else:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as error:
                if error.errno not in _LOCK_BUSY:
                    raise MaterializationError(f"cannot lock {path}: {error}") from error
                if time.monotonic() >= deadline:
                    raise MaterializationError(f"timed out waiting for {path}") from error
                time.sleep(0.1)
        try:
            yield
        finally:
            if sys.platform == "win32":
                # msvcrt unlocks from the current position; rewind to the byte that was locked.
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def _publish_checkout(staged: Path, destination: Path, ref: str, *, timeout: float) -> Path:
    backup: Path | None = None
    try:
        if _verified_checkout(destination, ref, timeout=timeout):
            return destination
        if os.path.lexists(destination):
            backup = destination.parent / f".{ref}.backup-{uuid.uuid4().hex}"
            os.replace(destination, backup)

        try:
            os.replace(staged, destination)
        except OSError as error:
            if _verified_checkout(destination, ref, timeout=timeout):
                if backup is not None:
                    _remove_path(backup)
                return destination
            if backup is not None and not os.path.lexists(destination):
                os.replace(backup, destination)
            raise MaterializationError(f"unable to publish pinned checkout: {error}") from error

        if not _verified_checkout(destination, ref, timeout=timeout):
            invalid = destination.parent / f".{ref}.invalid-{uuid.uuid4().hex}"
            os.replace(destination, invalid)
            if backup is not None:
                os.replace(backup, destination)
            _remove_path(invalid)
            raise MaterializationError("published checkout failed commit verification")

        if backup is not None:
            _remove_path(backup)
        return destination
    finally:
        _remove_path(staged)


def materialize(
    *,
    name: str,
    repo: str,
    ref: str,
    remote_url: str | None = None,
    cache_root: Path | None = None,
    fetch_attempts: int = 3,
    timeout: float = 120,
) -> Path:
    """Return a verified cache directory for an immutable upstream commit."""
    _validate_identifiers(name, repo, ref)
    if fetch_attempts < 1:
        raise MaterializationError("fetch_attempts must be positive")
    if timeout <= 0:
        raise MaterializationError("timeout must be positive")

    if cache_root is None:
        configured_cache = os.environ.get("XDG_CACHE_HOME")
        base = Path(configured_cache) if configured_cache else Path.home() / ".cache"
        parts: tuple[str, ...] = ("powerful-plugins-upstreams", name)
    else:
        base = cache_root
        parts = (name,)
    base = base.expanduser()
    parent = _real_directory(base, parts)
    destination = parent / ref
    if _verified_checkout(destination, ref, timeout=timeout):
        return destination

    # Budget for a lock holder's Git calls, each bounded by ``timeout``, plus the fetch backoff.
    lock_wait = timeout * (3 * fetch_attempts + 9) + 4 * fetch_attempts
    with _exclusive_lock(parent / f".{ref}.lock", wait=lock_wait):
        if _verified_checkout(destination, ref, timeout=timeout):
            return destination
        staged = _build_checkout(
            parent=parent,
            ref=ref,
            remote_url=remote_url or f"https://github.com/{repo}.git",
            fetch_attempts=fetch_attempts,
            timeout=timeout,
        )
        try:
            _real_directory(base, parts)
        except MaterializationError:
            _remove_path(staged)
            raise
        return _publish_checkout(staged, destination, ref, timeout=timeout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--cache-root", type=Path)
    arguments = parser.parse_args()
    try:
        checkout = materialize(
            name=arguments.name,
            repo=arguments.repo,
            ref=arguments.ref,
            cache_root=arguments.cache_root,
        )
    except (MaterializationError, OSError, UnicodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(checkout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
