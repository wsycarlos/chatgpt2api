from pathlib import Path

import pytest

from services.storage.database_storage import DatabaseStorageBackend
from services.storage.json_storage import JSONStorageBackend


def test_json_load_personal_accounts_empty(tmp_path: Path) -> None:
    backend = JSONStorageBackend(tmp_path / "accounts.json")
    assert backend.load_personal_accounts() == []


def test_json_save_and_load_personal_accounts(tmp_path: Path) -> None:
    backend = JSONStorageBackend(tmp_path / "accounts.json")
    accounts = [{"id": "u1", "name": "Alice"}, {"id": "u2", "name": "Bob"}]
    backend.save_personal_accounts(accounts)
    assert backend.load_personal_accounts() == accounts


def test_json_load_personal_accounts_invalid_json(tmp_path: Path) -> None:
    backend = JSONStorageBackend(tmp_path / "accounts.json")
    backend.personal_accounts_path.write_text("not json", encoding="utf-8")
    assert backend.load_personal_accounts() == []


def test_json_load_personal_accounts_not_list(tmp_path: Path) -> None:
    backend = JSONStorageBackend(tmp_path / "accounts.json")
    backend.personal_accounts_path.write_text('{"foo": "bar"}', encoding="utf-8")
    assert backend.load_personal_accounts() == []


def test_database_load_personal_accounts_empty(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'test.db'}"
    backend = DatabaseStorageBackend(url)
    assert backend.load_personal_accounts() == []


def test_database_save_and_load_personal_accounts(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'test.db'}"
    backend = DatabaseStorageBackend(url)
    accounts = [{"id": "u1", "name": "Alice"}, {"id": "u2", "name": "Bob"}]
    backend.save_personal_accounts(accounts)
    assert backend.load_personal_accounts() == accounts


def test_database_load_personal_accounts_invalid_json(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'test.db'}"
    backend = DatabaseStorageBackend(url)
    from services.storage.database_storage import PersonalAccountModel

    session = backend.Session()
    session.add(PersonalAccountModel(data="not json"))
    session.commit()
    session.close()
    assert backend.load_personal_accounts() == []


def test_database_load_personal_accounts_not_list(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'test.db'}"
    backend = DatabaseStorageBackend(url)
    from services.storage.database_storage import PersonalAccountModel

    session = backend.Session()
    session.add(PersonalAccountModel(data='{"foo": "bar"}'))
    session.commit()
    session.close()
    assert backend.load_personal_accounts() == []
