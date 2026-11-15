from fastapi.testclient import TestClient

from earthtrends.app import app

client = TestClient(app)


def test_map_files_are_served_with_the_right_type():
    # a module script with a wrong content type does not run
    for path in ("/vendor/maplibre-gl/maplibre-gl.mjs", "/vendor/maplibre-gl/maplibre-gl-worker.mjs"):
        r = client.get(path)
        assert r.status_code == 200 and "javascript" in r.headers["content-type"], path
    for path in ("/map.js", "/map.css"):
        assert client.get(path).status_code == 200, path
