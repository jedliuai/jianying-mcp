import json
from pathlib import Path
import sqlite3

import pytest

from jianying_bridge.sound_cache import find_cached_sound_effects


@pytest.fixture
def cache(tmp_path):
    music = tmp_path / "music"
    music.mkdir()
    database = tmp_path / "ressdk_db/fake-account/rp.db"
    database.parent.mkdir(parents=True)
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE http_cache (response_body TEXT, timestamp INTEGER)")
    md5 = "1234567890abcdef1234567890abcdef"
    (music / f"{md5}.mp3").write_bytes(b"synthetic-fixture")
    payload = {"data": {"category_resources": [{"common_attr": {
        "id": 6896679799100656904, "title": "转场音效", "md5": md5,
        "item_urls": ["https://example.invalid/?token=DO_NOT_LEAK"],
    }}, {"common_attr": {"id": "missing", "title": "未下载", "md5": "a" * 32}}]}}
    connection.execute("INSERT INTO http_cache VALUES (?, ?)", (json.dumps(payload), 1))
    connection.execute("INSERT INTO http_cache VALUES (?, ?)", ("invalid JSON", 2))
    connection.commit()
    connection.close()
    return tmp_path, database


def test_catalog_finds_only_downloaded_audio_and_preserves_64_bit_id(cache):
    root, database = cache
    before = database.read_bytes()
    result = find_cached_sound_effects(root)
    assert result["matched"] == 1
    effect = result["effects"][0]
    assert effect["resource_id"] == "6896679799100656904"
    assert effect["title"] == "转场音效"
    assert Path(effect["path"]).is_file()
    assert "DO_NOT_LEAK" not in json.dumps(result)
    assert "item_urls" not in effect
    assert database.read_bytes() == before


def test_catalog_queries_titles(cache):
    root, _ = cache
    assert find_cached_sound_effects(root, "转场")["matched"] == 1
    assert find_cached_sound_effects(root, "点击")["matched"] == 0


def test_duplicate_catalog_entries_do_not_duplicate_files(cache):
    root, database = cache
    connection = sqlite3.connect(database)
    raw = connection.execute("SELECT response_body FROM http_cache WHERE timestamp = 1").fetchone()[0]
    connection.execute("INSERT INTO http_cache VALUES (?, ?)", (raw, 3))
    connection.commit()
    connection.close()
    assert find_cached_sound_effects(root)["matched"] == 1


def test_missing_cache_returns_actionable_result(tmp_path):
    result = find_cached_sound_effects(tmp_path)
    assert result["matched"] == 0
    assert result["issues"]


@pytest.mark.parametrize("limit", [0, 301])
def test_invalid_catalog_limits(cache, limit):
    with pytest.raises(ValueError):
        find_cached_sound_effects(cache[0], limit=limit)


def test_missing_catalog_table_is_reported(cache):
    root, database = cache
    connection = sqlite3.connect(database)
    connection.execute("DROP TABLE http_cache")
    connection.commit()
    connection.close()
    assert find_cached_sound_effects(root)["issues"]
