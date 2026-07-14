from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from git import Repo

from services.storage.factory import create_storage_backend
from services.storage.git_storage import GitStorageBackend


class TestJsonPersonalAccounts(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

        self.env_patcher = mock.patch.dict(
            os.environ,
            {"STORAGE_BACKEND": "json"},
            clear=False,
        )
        self.env_patcher.start()
        self.addCleanup(self.env_patcher.stop)

        self.backend = create_storage_backend(self.tmpdir)

    def test_roundtrip(self):
        accounts = [{"id": "a1", "access_token": "t1", "email": "a@example.com"}]
        self.backend.save_personal_accounts(accounts)
        loaded = self.backend.load_personal_accounts()
        self.assertEqual(loaded, accounts)

    def test_empty_load(self):
        self.assertEqual(self.backend.load_personal_accounts(), [])

    def test_health_check_includes_personal_accounts_file_exists(self):
        health = self.backend.health_check()
        self.assertIn("personal_accounts_file_exists", health)
        self.assertFalse(health["personal_accounts_file_exists"])

        self.backend.save_personal_accounts([{"id": "a1", "access_token": "t1"}])
        health = self.backend.health_check()
        self.assertTrue(health["personal_accounts_file_exists"])


class TestDatabasePersonalAccounts(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

        db_url = f"sqlite:///{self.tmpdir / 'store.db'}"
        self.env_patcher = mock.patch.dict(
            os.environ,
            {"STORAGE_BACKEND": "sqlite", "DATABASE_URL": db_url},
            clear=False,
        )
        self.env_patcher.start()
        self.addCleanup(self.env_patcher.stop)

        self.backend = create_storage_backend(self.tmpdir)

    def test_roundtrip(self):
        accounts = [{"id": "a1", "access_token": "t1", "email": "a@example.com"}]
        self.backend.save_personal_accounts(accounts)
        loaded = self.backend.load_personal_accounts()
        self.assertEqual(loaded, accounts)

    def test_empty_load(self):
        self.assertEqual(self.backend.load_personal_accounts(), [])

    def test_health_check_includes_personal_account_count(self):
        health = self.backend.health_check()
        self.assertIn("personal_account_count", health)
        self.assertEqual(health["personal_account_count"], 0)

        self.backend.save_personal_accounts([{"id": "a1", "access_token": "t1"}])
        health = self.backend.health_check()
        self.assertEqual(health["personal_account_count"], 1)


class TestGitPersonalAccounts(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

        origin = self._create_bare_repo()
        self.backend = GitStorageBackend(
            repo_url=f"file://{origin}",
            token="",
            branch="main",
            file_path="accounts.json",
            auth_keys_file_path="auth_keys.json",
            personal_accounts_file_path="personal_accounts.json",
            local_cache_dir=self.tmpdir / "cache",
        )

    def _create_bare_repo(self) -> Path:
        origin = self.tmpdir / "origin.git"
        work = self.tmpdir / "work"

        subprocess.run(["git", "init", "-b", "main", str(work)], check=True, capture_output=True)
        (work / "README.md").write_text("init\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(work), "add", "README.md"], check=True)
        subprocess.run(
            ["git", "-C", str(work), "commit", "-m", "init"],
            check=True,
            capture_output=True,
        )
        subprocess.run(["git", "init", "--bare", str(origin)], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(work), "push", str(origin), "main"],
            check=True,
            capture_output=True,
        )

        return origin.resolve()

    def test_roundtrip(self):
        accounts = [{"id": "a1", "access_token": "t1", "email": "a@example.com"}]
        self.backend.save_personal_accounts(accounts)
        loaded = self.backend.load_personal_accounts()
        self.assertEqual(loaded, accounts)

    def test_empty_load(self):
        self.assertEqual(self.backend.load_personal_accounts(), [])

    def test_health_check_is_healthy(self):
        health = self.backend.health_check()
        self.assertEqual(health["status"], "healthy")
        self.assertIn("personal_accounts_file_path", health)


if __name__ == "__main__":
    unittest.main()
