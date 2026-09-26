from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from unittest import mock

from scripts import materialize_pinned_upstream as helper
from scripts.materialize_pinned_upstream import MaterializationError, materialize


class PinnedUpstreamMaterializerTests(unittest.TestCase):
    def test_git_invocation_does_not_copy_the_callers_environment(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "materialize_pinned_upstream.py"
        ).read_text()

        self.assertNotIn("os.environ.copy()", source)
        self.assertNotIn("env=", source)
        self.assertNotIn("capture_output=", source)
        self.assertIn('"credential.helper="', source)
        self.assertIn('"credential.interactive=never"', source)
        self.assertIn("stdin=subprocess.DEVNULL", source)

    def test_materializes_and_reuses_a_verified_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, commit = self._source_repository(root)
            cache = root / "cache"

            checkout = materialize(
                name="example",
                repo="example/repository",
                ref=commit,
                remote_url=source.as_uri(),
                cache_root=cache,
            )
            helper._remove_path(source)
            reused = materialize(
                name="example",
                repo="example/repository",
                ref=commit,
                remote_url=source.as_uri(),
                cache_root=cache,
            )

            self.assertEqual(checkout, cache / "example" / commit)
            self.assertEqual(reused, checkout)
            self.assertEqual(self._git(checkout, "rev-parse", "HEAD").stdout.strip(), commit)

    def test_rebuilds_a_cached_checkout_with_local_edits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, commit = self._source_repository(root)
            cache = root / "cache"
            checkout = materialize(
                name="example",
                repo="example/repository",
                ref=commit,
                remote_url=source.as_uri(),
                cache_root=cache,
            )
            (checkout / "workflow.md").write_text("edited without committing\n")
            (checkout / "extra.md").write_text("untracked\n")

            rebuilt = materialize(
                name="example",
                repo="example/repository",
                ref=commit,
                remote_url=source.as_uri(),
                cache_root=cache,
            )

            self.assertEqual(rebuilt, checkout)
            self.assertEqual((rebuilt / "workflow.md").read_text(), "first\n")
            self.assertFalse((rebuilt / "extra.md").exists())
            self.assertEqual(self._git(rebuilt, "status", "--porcelain").stdout, "")

    def test_rebuilds_a_cached_checkout_with_an_edit_hidden_by_index_flags(self) -> None:
        for flag in ("--skip-worktree", "--assume-unchanged"):
            with self.subTest(flag=flag), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source, commit = self._source_repository(root)
                cache = root / "cache"
                kwargs = dict(name="example", repo="example/repository", ref=commit,
                              remote_url=source.as_uri(), cache_root=cache)
                checkout = materialize(**kwargs)
                self._git(checkout, "update-index", flag, "workflow.md")
                (checkout / "workflow.md").write_text("hidden edit\n")
                self.assertEqual(self._git(checkout, "status", "--porcelain").stdout, "")

                rebuilt = materialize(**kwargs)

                self.assertEqual((rebuilt / "workflow.md").read_text(), "first\n")

    def test_a_lock_error_other_than_contention_fails_at_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            broken = OSError(22, "Invalid argument")
            target = "msvcrt.locking" if sys.platform == "win32" else "fcntl.flock"
            with mock.patch(target, side_effect=broken), mock.patch.object(helper.time, "sleep") as sleep:
                with self.assertRaisesRegex(MaterializationError, "cannot lock"):
                    with helper._exclusive_lock(Path(directory) / ".lock", wait=60):
                        pass
            sleep.assert_not_called()

    def test_a_cache_root_that_is_a_file_raises_a_materialization_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "not-a-directory"
            root.write_text("x")
            with self.assertRaisesRegex(MaterializationError, "cannot prepare cache path"):
                helper._real_directory(root, ("example",))

    def test_rebuilds_a_cached_checkout_holding_an_ignored_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, commit = self._source_repository(root)
            cache = root / "cache"
            checkout = materialize(
                name="example",
                repo="example/repository",
                ref=commit,
                remote_url=source.as_uri(),
                cache_root=cache,
            )
            (checkout / ".git" / "info").mkdir(exist_ok=True)
            (checkout / ".git" / "info" / "exclude").write_text("hidden.md\n")
            (checkout / "hidden.md").write_text("ignored\n")

            rebuilt = materialize(
                name="example",
                repo="example/repository",
                ref=commit,
                remote_url=source.as_uri(),
                cache_root=cache,
            )

            self.assertFalse((rebuilt / "hidden.md").exists())

    def test_replaces_a_wrong_checkout_without_leaving_a_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, first = self._source_repository(root)
            (source / "workflow.md").write_text("second\n")
            self._git(source, "add", "workflow.md")
            self._git(source, "commit", "-m", "second")
            second = self._git(source, "rev-parse", "HEAD").stdout.strip()
            destination = root / "cache" / "example" / second
            destination.parent.mkdir(parents=True)
            self._git(root, "clone", "--quiet", source.as_uri(), str(destination))
            self._git(destination, "checkout", "--quiet", "--detach", first)

            checkout = materialize(
                name="example",
                repo="example/repository",
                ref=second,
                remote_url=source.as_uri(),
                cache_root=root / "cache",
            )

            self.assertEqual(self._git(checkout, "rev-parse", "HEAD").stdout.strip(), second)
            self.assertEqual(list(destination.parent.glob(f".{second}.backup-*")), [])

    @unittest.skipIf(os.name == "nt", "symlink creation requires extra Windows privileges")
    def test_replaces_a_destination_symlink_without_touching_its_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, commit = self._source_repository(root)
            victim = root / "victim"
            victim.mkdir()
            sentinel = victim / "sentinel.txt"
            sentinel.write_text("keep\n")
            destination = root / "cache" / "example" / commit
            destination.parent.mkdir(parents=True)
            destination.symlink_to(victim, target_is_directory=True)

            checkout = materialize(
                name="example",
                repo="example/repository",
                ref=commit,
                remote_url=source.as_uri(),
                cache_root=root / "cache",
            )

            self.assertFalse(checkout.is_symlink())
            self.assertEqual(sentinel.read_text(), "keep\n")
            self.assertEqual(self._git(checkout, "rev-parse", "HEAD").stdout.strip(), commit)

    def test_failed_fetch_preserves_an_existing_invalid_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, existing_commit = self._source_repository(root)
            wanted_commit = "a" * 40
            destination = root / "cache" / "example" / wanted_commit
            destination.parent.mkdir(parents=True)
            self._git(root, "clone", "--quiet", source.as_uri(), str(destination))
            missing = root / "missing.git"

            with self.assertRaises(MaterializationError):
                materialize(
                    name="example",
                    repo="example/repository",
                    ref=wanted_commit,
                    remote_url=missing.as_uri(),
                    cache_root=root / "cache",
                    fetch_attempts=1,
                )

            self.assertEqual(
                self._git(destination, "rev-parse", "HEAD").stdout.strip(),
                existing_commit,
            )

    def test_concurrent_materialization_converges(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, commit = self._source_repository(root)
            cache = root / "cache"

            def run() -> Path:
                return materialize(
                    name="example",
                    repo="example/repository",
                    ref=commit,
                    remote_url=source.as_uri(),
                    cache_root=cache,
                )

            with ThreadPoolExecutor(max_workers=6) as executor:
                checkouts = list(executor.map(lambda _: run(), range(12)))

            self.assertEqual(set(checkouts), {cache / "example" / commit})
            self.assertEqual(
                self._git(checkouts[0], "rev-parse", "HEAD").stdout.strip(),
                commit,
            )
            self.assertEqual(list((cache / "example").glob(".*.tmp-*")), [])

    @unittest.skipIf(os.name == "nt", "symlink creation requires extra Windows privileges")
    def test_refuses_a_symlinked_cache_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, commit = self._source_repository(root)
            outside = root / "outside"
            outside.mkdir()
            explicit = root / "explicit"
            explicit.mkdir()
            (explicit / "example").symlink_to(outside, target_is_directory=True)
            xdg = root / "xdg"
            xdg.mkdir()
            (xdg / "powerful-plugins-upstreams").symlink_to(outside, target_is_directory=True)

            for cache_root, environment in ((explicit, {}), (None, {"XDG_CACHE_HOME": str(xdg)})):
                with (
                    self.subTest(cache_root=cache_root),
                    mock.patch.dict(os.environ, environment),
                    self.assertRaisesRegex(MaterializationError, "cache path"),
                ):
                    materialize(
                        name="example",
                        repo="example/repository",
                        ref=commit,
                        remote_url=source.as_uri(),
                        cache_root=cache_root,
                    )

            self.assertEqual(list(outside.iterdir()), [])

    @unittest.skipIf(os.name == "nt", "symlink creation requires extra Windows privileges")
    def test_refuses_to_publish_when_the_cache_directory_is_swapped_for_a_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, commit = self._source_repository(root)
            cache = root / "cache"
            outside = root / "outside"
            outside.mkdir()
            build = helper._build_checkout

            def build_then_swap(**arguments: Any) -> Path:
                staged = build(**arguments)
                (cache / "example").rename(root / "moved")
                (cache / "example").symlink_to(outside, target_is_directory=True)
                return staged

            with (
                mock.patch.object(helper, "_build_checkout", build_then_swap),
                self.assertRaisesRegex(MaterializationError, "cache path"),
            ):
                materialize(
                    name="example",
                    repo="example/repository",
                    ref=commit,
                    remote_url=source.as_uri(),
                    cache_root=cache,
                )

            self.assertEqual(list(outside.iterdir()), [])

    def test_concurrent_callers_build_once_and_all_return_the_verified_checkout(self) -> None:
        workers = 6
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, commit = self._source_repository(root)
            cache = root / "cache"
            # Hold every caller at its first cache check, so all of them find the cache empty
            # and reach the build step together.
            barrier = threading.Barrier(workers)
            seen = threading.local()
            verify = helper._verified_checkout
            build = helper._build_checkout
            builds: list[Path] = []

            def verify_after_everyone_looked(checkout: Path, ref: str, *, timeout: float) -> bool:
                if not getattr(seen, "first", False):
                    seen.first = True
                    barrier.wait(timeout=30)
                return verify(checkout, ref, timeout=timeout)

            def counted_build(**arguments: Any) -> Path:
                staged = build(**arguments)
                builds.append(staged)
                return staged

            def run(_: int) -> Path:
                return materialize(
                    name="example",
                    repo="example/repository",
                    ref=commit,
                    remote_url=source.as_uri(),
                    cache_root=cache,
                )

            with (
                mock.patch.object(helper, "_verified_checkout", verify_after_everyone_looked),
                mock.patch.object(helper, "_build_checkout", counted_build),
                ThreadPoolExecutor(max_workers=workers) as executor,
            ):
                checkouts = list(executor.map(run, range(workers)))

            self.assertEqual(len(builds), 1)
            self.assertEqual(set(checkouts), {cache / "example" / commit})
            self.assertEqual(self._git(checkouts[0], "status", "--porcelain").stdout, "")

    def test_each_fetch_attempt_starts_from_a_fresh_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, commit = self._source_repository(root)
            run_git = helper._run_git
            fetch_directories: list[Path] = []

            def fail_first_fetch(arguments: list[str], *, cwd: Path, timeout: float) -> str:
                if arguments[0] == "fetch":
                    fetch_directories.append(cwd)
                    if len(fetch_directories) == 1:
                        (cwd / ".git" / "shallow").write_text("partial\n")
                        raise MaterializationError("git fetch timed out")
                return run_git(arguments, cwd=cwd, timeout=timeout)

            with (
                mock.patch.object(helper, "_run_git", fail_first_fetch),
                mock.patch.object(helper.time, "sleep"),
            ):
                checkout = materialize(
                    name="example",
                    repo="example/repository",
                    ref=commit,
                    remote_url=source.as_uri(),
                    cache_root=root / "cache",
                )

            self.assertEqual(len(fetch_directories), 2)
            self.assertNotEqual(fetch_directories[0], fetch_directories[1])
            self.assertFalse(fetch_directories[0].exists())
            self.assertEqual(self._git(checkout, "rev-parse", "HEAD").stdout.strip(), commit)

    def test_removes_a_checkout_with_read_only_git_objects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory) / "checkout"
            objects = checkout / ".git" / "objects" / "ab"
            objects.mkdir(parents=True)
            (objects / "cdef").write_text("object\n")
            (objects / "cdef").chmod(stat.S_IREAD)

            helper._remove_path(checkout)

            self.assertFalse(checkout.exists())

    @unittest.skipUnless(os.name == "nt", "the read-only retry only runs on Windows")
    def test_read_only_retry_only_handles_permission_errors_on_removal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "object"
            target.write_text("object\n")
            target.chmod(stat.S_IREAD)

            helper._clear_read_only_and_retry(os.unlink, str(target), PermissionError())
            self.assertFalse(target.exists())

            with self.assertRaises(FileNotFoundError):
                helper._clear_read_only_and_retry(os.unlink, str(target), FileNotFoundError())
            with self.assertRaises(PermissionError):
                helper._clear_read_only_and_retry(os.lstat, str(root), PermissionError())

    def test_read_only_retry_asks_windows_not_to_follow_symlinks_when_it_can(self) -> None:
        # CI's Windows Python predates 3.13, so both branches are pinned here on every platform.
        for supported, expected in (
            (True, mock.call(mock.ANY, stat.S_IWRITE, follow_symlinks=False)),
            (False, mock.call(mock.ANY, stat.S_IWRITE)),
        ):
            with self.subTest(supported=supported), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "object"
                target.write_text("object\n")
                chmod = mock.Mock()
                with (
                    mock.patch.object(helper.os, "name", "nt"),
                    mock.patch.object(helper.os, "chmod", chmod),
                    mock.patch.object(
                        helper.os, "supports_follow_symlinks", {chmod} if supported else set()
                    ),
                ):
                    helper._clear_read_only_and_retry(os.unlink, str(target), PermissionError())

                self.assertEqual(chmod.call_args_list, [expected])
                self.assertFalse(target.exists())

    @unittest.skipIf(os.name == "nt", "POSIX permissions only")
    def test_read_only_retry_never_changes_modes_on_posix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            victim = root / "victim"
            victim.write_text("keep\n")
            victim.chmod(0o444)
            link = root / "link"
            link.symlink_to(victim)

            for target in (victim, link):
                with self.subTest(target=target.name), self.assertRaises(PermissionError):
                    helper._clear_read_only_and_retry(os.unlink, str(target), PermissionError())

            self.assertTrue(link.is_symlink())
            self.assertEqual(victim.stat().st_mode & 0o777, 0o444)

    def test_zero_fetch_attempts_raise_a_materialization_error(self) -> None:
        # An explicit raise, not an assert, so the check survives python -O.
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(MaterializationError, "fetch_attempts must be positive"):
                helper._build_checkout(
                    parent=Path(directory),
                    ref="0" * 40,
                    remote_url="file:///unused",
                    fetch_attempts=0,
                    timeout=5,
                )

    def test_rejects_unsafe_identifiers(self) -> None:
        cases = [
            {"name": "../escape", "repo": "example/repository", "ref": "a" * 40},
            {"name": "example", "repo": "../repository", "ref": "a" * 40},
            {"name": "example", "repo": "example/repository", "ref": "main"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            for values in cases:
                with self.subTest(values=values), self.assertRaises(MaterializationError):
                    materialize(
                        **values,
                        remote_url=Path(directory, "missing").as_uri(),
                        cache_root=Path(directory, "cache"),
                        fetch_attempts=1,
                    )

    def test_cli_reports_validation_errors_without_a_traceback(self) -> None:
        script = Path(__file__).resolve().parents[1] / "scripts" / "materialize_pinned_upstream.py"
        completed = subprocess.run(
            [
                sys.executable,
                str(script),
                "--name",
                "../escape",
                "--repo",
                "example/repository",
                "--ref",
                "a" * 40,
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("error:", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def _source_repository(self, root: Path) -> tuple[Path, str]:
        source = root / "source"
        source.mkdir()
        self._git(source, "init", "--quiet")
        self._git(source, "config", "user.email", "tests@example.com")
        self._git(source, "config", "user.name", "Tests")
        (source / "workflow.md").write_text("first\n")
        self._git(source, "add", "workflow.md")
        self._git(source, "commit", "-m", "first")
        return source, self._git(source, "rev-parse", "HEAD").stdout.strip()

    @staticmethod
    def _git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
