import pytest

from agate_map import fetch


def feature(object_id):
    return {"type": "Feature", "properties": {"id": object_id}, "geometry": None}


def test_features_are_fetched_in_batches_by_id(monkeypatch):
    calls = []

    def fake_get(url, params):
        calls.append(params)
        if params.get("returnIdsOnly"):
            return {"objectIds": [5, 3, 9, 1, 7]}
        wanted = [int(i) for i in params["objectIds"].split(",")]
        return {"features": [feature(i) for i in wanted]}

    monkeypatch.setattr(fetch, "_get", fake_get)
    features = fetch.query_features("https://example.test/layer", "1=1", "X", batch=2)
    assert [f["properties"]["id"] for f in features] == [1, 3, 5, 7, 9]
    assert [c["objectIds"] for c in calls[1:]] == ["1,3", "5,7", "9"]
    assert calls[0]["geometry"] == fetch.BBOX


def test_a_short_download_is_an_error(monkeypatch):
    def fake_get(url, params):
        if params.get("returnIdsOnly"):
            return {"objectIds": [1, 2, 3]}
        return {"features": [feature(1)]}

    monkeypatch.setattr(fetch, "_get", fake_get)
    with pytest.raises(RuntimeError, match="expected 3 features, got 1"):
        fetch.query_features("https://example.test/layer", "1=1", "X", batch=10)


def test_nothing_in_the_area_is_an_empty_list(monkeypatch):
    monkeypatch.setattr(fetch, "_get", lambda url, params: {"objectIds": None})
    assert fetch.query_features("https://example.test/layer", "1=1", "X") == []


def test_cached_downloads_are_reused_and_refresh_replaces_them(tmp_path):
    path = tmp_path / "raw" / "thing.json"
    assert fetch._cached(path, False, lambda: [1]) == [1]
    assert fetch._cached(path, False, lambda: [2]) == [1]
    assert fetch._cached(path, True, lambda: [2]) == [2]
