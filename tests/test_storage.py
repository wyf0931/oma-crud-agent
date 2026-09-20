from shared.storage.database import get_database


def test_database_ignores_legacy_files(tmp_path):
    (tmp_path / "sessions.jsonl").write_text('{"id": "legacy-1"}\n', encoding="utf-8")
    (tmp_path / "settings.json").write_text('{"model": "legacy-model"}', encoding="utf-8")

    db = get_database(tmp_path / "app.json")

    assert db.table("sessions").all() == []
    assert db.table("settings").all() == []
