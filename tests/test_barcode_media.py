import json
from pathlib import Path
import threading
from types import SimpleNamespace
import zipfile

from fastapi.testclient import TestClient
import pytest

from display_app.barcode import ScanBuffer, handle_scan, load_mapping, select_port, run_barcode
from display_app.config import ROOT, load_settings
from display_app.server import create_app
from display_app.state import DisplayState
from scripts.media import check, install_archive, pack, read_manifest, safe_path, sync


def test_barcode_and_camera_share_channel_but_not_nfc():
    state = DisplayState(load_settings())
    state.trigger("nfc", "Prince")
    nfc = state.snapshot("nfc")["event_id"]
    state.trigger("figuras", "J")
    camera = state.snapshot("figuras")["event_id"]
    assert handle_scan(state, "\x00787926301397\r\n")
    barcode = state.snapshot("figuras")
    assert barcode["key"] == "Joker"
    assert barcode["content"]["src"] == "/media/figuras/jokerFigura.mp4"
    assert not state.complete("figuras", camera)
    assert state.snapshot("nfc")["event_id"] == nfc
    assert handle_scan(state, "787926301397")
    assert state.snapshot("figuras")["event_id"] != barcode["event_id"]
    assert not handle_scan(state, "unknown")
    state.trigger("figuras", "F")
    assert state.snapshot("figuras")["content"]["src"] == "/media/figuras/flash.mp4"


def test_all_original_codes_have_events():
    settings = load_settings()
    mapping = load_mapping(ROOT / settings.barcode.mapping_file)
    assert len(mapping) == 14
    assert set(mapping.values()) <= settings.channels["figuras"].events.keys()


def test_serial_frame_boundaries_and_bad_data():
    buffer = ScanBuffer()
    assert buffer.feed(b"84327") == []
    assert buffer.feed(b"52047484\r\nX002A6G2NJ\x00\rnext\n") == ["8432752047484", "X002A6G2NJ", "next"]
    assert buffer.flush() == ""
    assert buffer.feed(b"a" * 600 + b"\nOK\n\xff\n") == ["OK"]
    buffer.feed(b"timeout")
    assert buffer.flush() == "timeout"


def test_port_selection():
    config = load_settings().barcode
    device = SimpleNamespace(device="COM7", vid=config.vid, pid=config.pid)
    assert select_port(config, [device]) == "COM7"
    assert select_port(config, []) is None
    with pytest.raises(ValueError):
        select_port(config, [device, device])
    config.port = "COM8"
    assert select_port(config, []) == "COM8"


def test_barcode_api_demo_and_production():
    with TestClient(create_app(demo=True)) as client:
        assert client.get("/api/status").json()["hardware"]["barcode"]["status"] == "demo"
        assert client.post("/api/demo/barcode", json={"key": "8432752047484"}).status_code == 200
        assert client.get("/api/state/figuras").json()["key"] == "Aquaman"
        assert client.post("/api/demo/barcode", json={"key": "bad"}).status_code == 404
        assert len(client.get("/api/barcodes").json()) == 14
    settings = load_settings()
    for name in ("figures", "nfc", "weather", "barcode"):
        getattr(settings, name).enabled = False
    with TestClient(create_app(settings=settings)) as client:
        assert client.post("/api/demo/barcode", json={"key": "8432752047484"}).status_code == 403


@pytest.fixture
def bundle(tmp_path):
    source = tmp_path / "source"
    (source / "media" / "NFC").mkdir(parents=True)
    (source / "media" / "NFC" / "Prince.mp4").write_bytes(b"video" * 100)
    (source / "media" / "second.mp4").write_bytes(b"second video")
    (source / "media" / "README.md").write_text("keep local")
    archive = pack(source)
    clone = tmp_path / "clone"
    clone.mkdir()
    (clone / "media-manifest.json").write_bytes((source / "media-manifest.json").read_bytes())
    return source, clone, archive


def test_media_install_and_no_download_if_current(bundle, monkeypatch):
    source, clone, archive = bundle
    assert len(check(clone)) == 2
    sync(clone, archive=archive)
    assert not check(clone)
    monkeypatch.setattr("scripts.media.urlopen", lambda *a, **kw: pytest.fail("No debe descargar"))
    sync(clone, url="https://example.invalid/media.zip")
    with zipfile.ZipFile(archive) as package:
        assert "README.md" not in package.namelist()


def test_media_corruption_does_not_replace_existing_files(bundle, tmp_path):
    _, clone, archive = bundle
    sync(clone, archive=archive)
    original = clone / "media" / "NFC" / "Prince.mp4"
    original.write_bytes(b"local content")
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive) as source, zipfile.ZipFile(bad, "w") as output:
        for name in source.namelist():
            data = source.read(name)
            output.writestr(name, b"x" * len(data) if name == "second.mp4" else data)
    with pytest.raises(ValueError, match="Checksum"):
        install_archive(clone, bad, read_manifest(clone))
    assert original.read_bytes() == b"local content"


@pytest.mark.parametrize("name", ["../escape.mp4", "/absolute", "C:/escape", "a\\b", "a/../b", "a./x"])
def test_reject_media_path_traversal(tmp_path, name):
    with pytest.raises(ValueError):
        safe_path(tmp_path, name)


def test_media_missing_url_explains_setup(bundle, monkeypatch):
    monkeypatch.delenv("BIGBANG_MEDIA_URL", raising=False)
    _, clone, _ = bundle
    with pytest.raises(ValueError, match="media-source.json"):
        sync(clone)


def test_media_download_path(bundle, monkeypatch):
    _, clone, archive = bundle
    monkeypatch.setattr("scripts.media.urlopen", lambda *args, **kwargs: archive.open("rb"))
    sync(clone, url="https://example.invalid/media.zip")
    assert not check(clone)


def test_barcode_worker_reads_and_closes(monkeypatch):
    serial = pytest.importorskip("serial")
    state = DisplayState(load_settings())
    state.settings.barcode.port = "COM7"
    stop = threading.Event()
    class Device:
        in_waiting = 100
        closed = False
        def __enter__(self): return self
        def __exit__(self, *args): self.closed = True
        def read(self, count):
            stop.set()
            return b"8432752047484\r\n"
    device = Device()
    monkeypatch.setattr(serial, "Serial", lambda **kwargs: device)
    run_barcode(state, stop)
    assert device.closed
    assert state.snapshot("figuras")["key"] == "Aquaman"
