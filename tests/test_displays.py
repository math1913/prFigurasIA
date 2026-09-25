from concurrent.futures import ThreadPoolExecutor
import threading

from fastapi.testclient import TestClient
import pytest

from display_app.config import ROOT, load_settings
from display_app.nfc import NFCObserver, load_aliases
from display_app.server import create_app
from display_app.state import DisplayState, FigureGate
from display_app.weather import run_weather, weather_code


class Clock:
    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def settings():
    return load_settings()


@pytest.fixture
def clock():
    return Clock()


def test_independent_channels_and_stale_completion(settings, clock):
    state = DisplayState(settings, clock)
    state.trigger("figuras", "A")
    first = state.snapshot("figuras")
    state.trigger("nfc", "Prince")
    nfc_id = state.snapshot("nfc")["event_id"]
    state.trigger("figuras", "B")
    second = state.snapshot("figuras")
    assert not state.complete("figuras", first["event_id"])
    assert state.snapshot("figuras")["key"] == "B"
    assert state.complete("figuras", second["event_id"])
    assert state.snapshot("figuras")["mode"] == "base"
    assert state.snapshot("nfc")["event_id"] == nfc_id


def test_video_waits_for_end_and_watchdog_recovers(settings, clock):
    settings.channels["figuras"].events["A"].src = "/media/long.mp4"
    state = DisplayState(settings, clock)
    state.trigger("figuras", "A")
    clock.advance(120)
    assert state.snapshot("figuras")["mode"] == "event"
    clock.advance(3600)
    assert state.snapshot("figuras")["mode"] == "base"


def test_unconfigured_video_returns_to_base(settings, clock):
    settings.channels["nfc"].events["Prince"].src = None
    state = DisplayState(settings, clock)
    state.trigger("nfc", "Prince")
    clock.advance(settings.channels["nfc"].placeholder_seconds)
    assert state.is_idle("nfc")
    assert not state.trigger("nfc", "Desconocido")
    assert state.is_idle("nfc")


def test_same_action_can_replay_after_completion(settings):
    state = DisplayState(settings)
    state.trigger("nfc", "Prince")
    first = state.snapshot("nfc")["event_id"]
    state.complete("nfc", first)
    state.trigger("nfc", "Prince")
    assert state.snapshot("nfc")["event_id"] != first


def test_concurrent_publish_and_completion(settings):
    state = DisplayState(settings)
    def cycle(index):
        channel, key = ("figuras", "B") if index % 2 else ("nfc", "Prince")
        state.trigger(channel, key)
        snapshot = state.snapshot(channel)
        if snapshot["event_id"]:
            state.complete(channel, snapshot["event_id"])
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(cycle, range(100)))
    state.trigger("figuras", "A")
    state.trigger("nfc", "Batman")
    assert state.snapshot("figuras")["key"] == "A"
    assert state.snapshot("nfc")["key"] == "Batman"


def test_weather_does_not_interrupt_active_video(settings):
    settings.weather.base_channels = ["figuras"]
    settings.weather.videos["DD"].src = "/media/weather/day.mp4"
    settings.weather.videos["NN"].src = "/media/weather/night.mp4"
    state = DisplayState(settings)
    state.set_weather("DD")
    assert state.snapshot("figuras")["content"]["src"] == "/media/weather/day.mp4"
    state.trigger("figuras", "A")
    before = state.snapshot("figuras")
    state.set_weather("NN")
    after = state.snapshot("figuras")
    assert before["revision"] == after["revision"]
    assert before["event_id"] == after["event_id"]
    assert after["base"]["src"] == "/media/weather/night.mp4"
    assert state.snapshot("nfc")["content"] == settings.channels["nfc"].base.model_dump()
    state.complete("figuras", after["event_id"])
    assert state.snapshot("figuras")["content"]["src"] == "/media/weather/night.mp4"
    state.set_weather(None)
    assert state.snapshot("figuras")["content"] == settings.channels["figuras"].base.model_dump()


@pytest.mark.parametrize("code,now,expected", [
    (500, 150, "DL"), (800, 100, "DD"), (801, 150, "DN"),
    (800, 200, "A"), (500, 210, "DL"), (801, 210, "DN"),
    (500, 50, "NL"), (800, 50, "ND"), (801, 50, "NN"),
    (800, 230, "ND"),
])
def test_weather_codes(code, now, expected):
    data = {"weather": [{"id": code}], "sys": {"sunrise": 100, "sunset": 200}}
    assert weather_code(data, now, sunset_seconds=30) == expected


def test_weather_missing_key_keeps_server_available(settings, monkeypatch):
    monkeypatch.delenv(settings.weather.api_key_env, raising=False)
    state = DisplayState(settings)
    run_weather(state, threading.Event())
    assert state.health()["hardware"]["weather"]["status"] == "waiting"
    assert state.snapshot("figuras")["mode"] == "base"


def test_weather_failure_uses_backup_and_recovers(settings, monkeypatch):
    import io
    import json
    from display_app import weather
    state = DisplayState(settings)
    monkeypatch.setenv(settings.weather.api_key_env, "test-key")
    clock = Clock()
    monkeypatch.setattr(weather.time, "monotonic", clock)
    monkeypatch.setattr(weather.time, "time", lambda: 150)
    attempts = iter([True, False, True])
    def fetch(*args, **kwargs):
        if not next(attempts):
            raise OSError("API unavailable")
        return io.BytesIO(json.dumps({"weather": [{"id": 500}], "sys": {"sunrise": 100, "sunset": 200}}).encode())
    monkeypatch.setattr(weather, "urlopen", fetch)
    seen = []
    class Stop:
        def is_set(self):
            return len(seen) == 3
        def wait(self, seconds):
            seen.append(state.snapshot("figuras")["content"]["src"])
            assert state.snapshot("nfc")["content"]["src"] == "/media/pantalla/bigBangIntro.mp4"
            clock.advance(settings.weather.poll_seconds)
    run_weather(state, Stop())
    assert seen == ["/media/ventana/lluvioso.mp4", "/media/ventana/despejado.mp4", "/media/ventana/lluvioso.mp4"]


def test_figure_stability_removal_and_reappearance(clock):
    gate = FigureGate(0.5, 1, clock, cooldown_seconds=0)
    assert gate.update([("A", .9)]) is None
    clock.advance(.6)
    assert gate.update([("A", .9)]) == "A"
    for _ in range(100):
        clock.advance(.1)
        assert gate.update([("A", .9)]) is None
    gate.update([])
    clock.advance(1.1)
    gate.update([])
    gate.update([("A", .9)])
    clock.advance(.6)
    assert gate.update([("A", .9)]) == "A"


def test_figure_new_action_and_confidence_priority(clock):
    gate = FigureGate(0.5, 1, clock)
    gate.update([("A", .8), ("B", .95)])
    clock.advance(.6)
    assert gate.update([("A", .8), ("B", .95)]) == "B"
    gate.update([("A", .95)])
    clock.advance(.6)
    assert gate.update([("A", .95)]) == "A"


def test_slow_inference_does_not_retrigger_a_visible_figure(clock):
    gate = FigureGate(0.5, 1, clock)
    gate.update([("A", .95)])
    clock.advance(3)
    assert gate.update([("A", .95)]) == "A"
    clock.advance(3)
    assert gate.update([("A", .95)]) is None


class Card:
    atr = [1, 2, 3]

    def __init__(self, uid="41552CA3", reader="ACR122 0", fail=False):
        self.uid, self.reader, self.fail = uid, reader, fail
        self.disconnected = False

    def createConnection(self):
        return self

    def connect(self):
        if self.fail:
            raise RuntimeError("No card")

    def transmit(self, command):
        assert command == [0xFF, 0xCA, 0, 0, 0]
        return list(bytes.fromhex(self.uid)), 0x90, 0

    def disconnect(self):
        self.disconnected = True


def test_nfc_remove_and_repeated_same_object(settings):
    state = DisplayState(settings)
    observer = NFCObserver({"41552CA3": "Prince"}, state)
    card = Card()
    for _ in range(2):
        observer.update(None, ([card], []))
        assert state.objects()["Prince"]
        assert state.is_idle("nfc")
        assert card.disconnected
        observer.update(None, ([], [card]))
        assert not state.objects()["Prince"]
        assert state.snapshot("nfc")["key"] == "Prince"
        state.complete("nfc", state.snapshot("nfc")["event_id"])
    observer.update(None, ([], [card]))
    assert state.is_idle("nfc")


def test_nfc_same_song_keeps_playing_until_it_ends(settings):
    state = DisplayState(settings)
    observer = NFCObserver({"41552CA3": "Prince", "21652CA3": "Beatles"}, state)
    prince = Card()
    observer.update(None, ([prince], []))
    observer.update(None, ([], [prince]))
    playing = state.snapshot("nfc")["event_id"]
    for _ in range(2):  # Colocado y retirado otra vez mientras suena: no vuelve a empezar.
        observer.update(None, ([prince], []))
        observer.update(None, ([], [prince]))
        assert state.snapshot("nfc")["event_id"] == playing
    state.complete("nfc", playing)
    observer.update(None, ([prince], []))
    observer.update(None, ([], [prince]))
    again = state.snapshot("nfc")
    assert again["key"] == "Prince" and again["event_id"] != playing
    beatles = Card(uid="21652CA3", reader="ACR122 1")
    observer.update(None, ([beatles], []))
    observer.update(None, ([], [beatles]))
    assert state.snapshot("nfc")["key"] == "Beatles"


def test_base_clock_and_screen_settings(settings, clock):
    state = DisplayState(settings, clock)
    clock.advance(7)
    base = state.snapshot("nfc")
    assert base["elapsed_seconds"] == 7 and base["fit"] == "cover"
    assert base["audio_on_pc"] and not state.snapshot("figuras")["audio_on_pc"]
    state.trigger("nfc", "Prince")
    clock.advance(3)
    event = state.snapshot("nfc")
    assert event["elapsed_seconds"] == 3
    state.complete("nfc", event["event_id"])
    clock.advance(2)
    assert state.snapshot("nfc")["elapsed_seconds"] == 2  # La base vuelve a empezar al terminar.


def test_audio_page_and_demo_song_without_restart(settings):
    app = create_app(settings=settings, demo=True)
    displays = app.state.displays
    with TestClient(app) as client:
        assert client.get("/audio/nfc").status_code == 200
        assert client.get("/audio/otro").status_code == 422
        client.get("/api/state/nfc")
        assert displays.audio_page_age("nfc") is None
        client.get("/api/state/nfc?audio=1")
        assert displays.audio_page_age("nfc") < 5
        client.post("/api/demo/nfc", json={"key": "Prince"})
        playing = client.get("/api/state/nfc").json()["event_id"]
        client.post("/api/demo/nfc", json={"key": "Prince"})
        assert client.get("/api/state/nfc").json()["event_id"] == playing


def test_audio_browser_reopens_a_page_that_stops_polling(settings, monkeypatch, tmp_path):
    from display_app import audio
    clock = Clock()
    state = DisplayState(settings, clock)
    opened, closed = [], []

    class Process:
        def poll(self):
            return None

    monkeypatch.setattr(audio.time, "monotonic", clock)
    monkeypatch.setattr(audio, "find_browser", lambda configured: tmp_path / "chrome.exe")
    monkeypatch.setattr(audio, "reachable", lambda url: True)
    monkeypatch.setattr(audio, "launch", lambda browser, url, profile: opened.append(url) or Process())
    monkeypatch.setattr(audio, "close", closed.append)
    steps = iter([
        lambda: clock.advance(40),  # 40 s sin consultar el estado: se reabre.
        lambda: (clock.advance(5), state.saw_audio_page("nfc")),
    ])

    class Stop:
        done = False

        def is_set(self):
            return self.done

        def wait(self, seconds):
            try:
                next(steps)()
            except StopIteration:
                self.done = True

    audio.run_audio(state, Stop(), port=8123)
    assert opened == ["http://127.0.0.1:8123/audio/nfc"] * 2
    assert len(closed) == 2  # El colgado y, al parar, el que quedaba abierto.
    assert state.health()["hardware"]["audio"]["status"] == "ready"


def test_find_browser(tmp_path):
    from display_app.audio import find_browser
    browser = tmp_path / "chrome.exe"
    browser.write_bytes(b"")
    assert find_browser(str(browser)) == browser
    assert find_browser(str(tmp_path / "missing.exe")) is None


def test_nfc_unknown_failed_read_and_reader_isolation(settings):
    state = DisplayState(settings)
    observer = NFCObserver({"41552CA3": "Prince"}, state)
    first, second = Card(), Card(reader="ACR122 1")
    observer.update(None, ([first, second], []))
    observer.update(None, ([], [first]))
    assert state.objects()["Prince"]
    state.complete("nfc", state.snapshot("nfc")["event_id"])
    bad = Card(uid="AAAAAAAA", reader="ACR122 0")
    observer.update(None, ([bad], []))
    observer.update(None, ([], [bad]))
    assert state.is_idle("nfc")
    failed = Card(fail=True)
    observer.update(None, ([failed], []))
    observer.update(None, ([], [failed]))
    assert state.is_idle("nfc")


def test_aliases_integrated_without_losses(settings):
    aliases = load_aliases(ROOT / settings.nfc.aliases_file)
    assert aliases["41552CA3"] == "Prince"
    assert aliases["B1492CA3"] == "Jeep"
    assert aliases["D1472CA3"] == "Batman"
    assert set(aliases.values()) <= settings.channels["nfc"].events.keys()


def test_http_pages_demo_completion_and_cache(settings):
    with TestClient(create_app(settings=settings, demo=True)) as client:
        for path in ["/", "/figuras", "/nfc", "/overlay", "/static/player.js"]:
            assert client.get(path).status_code == 200
        assert client.get("/api/status").json()["demo"]
        assert client.get("/objetos").status_code == 200
        response = client.get("/api/state/figuras")
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["mode"] == "base"
        assert client.post("/api/demo/figuras", json={"key": "B"}).status_code == 200
        state = client.get("/api/state/figuras").json()
        assert state["key"] == "B"
        assert client.get("/api/state/nfc").json()["mode"] == "base"
        assert not client.post("/api/complete/figuras", json={"event_id": "old"}).json()["accepted"]
        assert client.post("/api/complete/figuras", json={"event_id": state["event_id"]}).json()["accepted"]
        assert client.get("/api/state/figuras").json()["mode"] == "base"
        assert client.post("/api/demo/weather", json={"key": "DD"}).status_code == 200
        assert client.get("/api/status").json()["weather_code"] == "DD"
        assert client.post("/api/demo/nfc", json={"key": "unknown"}).status_code == 404
        assert client.get("/api/state/unknown").status_code == 422
        assert client.get("/media/../config.json").status_code == 404


def test_overlay_page_logos_and_presence(settings):
    app = create_app(settings=settings, demo=True)
    with TestClient(app) as client:
        html = client.get("/overlay").text
        for alias in settings.nfc.monitored_objects:
            logo = f"/static/img/{alias.lower()}.png"
            assert f'id="{alias}"' in html and logo in html
            assert client.get(logo).headers["content-type"] == "image/png"
        assert client.get("/static/overlay.js").status_code == 200
        assert client.get("/objetos").json() == dict.fromkeys(settings.nfc.monitored_objects, False)
        app.state.displays.set_present({("ACR122 0", (1, 2, 3)): {"uid": "41552CA3", "alias": "Prince"}})
        present = client.get("/objetos").json()
        assert present.pop("Prince") and not any(present.values())


def test_screen_pages_log_the_player_browser(settings, caplog):
    agent = "Mozilla/5.0 (Linux; Android 7.1.2) Chrome/52.0.2743.98"
    with TestClient(create_app(settings=settings, demo=True)) as client, caplog.at_level("INFO"):
        client.get("/nfc", headers={"User-Agent": agent})
    assert f"Pantalla nfc abierta desde testclient · {agent}" in caplog.text


def test_overlay_only_on_configured_channels(settings):
    state = DisplayState(settings)
    assert state.snapshot("nfc")["overlay"] and not state.snapshot("figuras")["overlay"]
    settings.nfc.overlay_channels = ["figuras"]
    assert state.snapshot("figuras")["overlay"] and not state.snapshot("nfc")["overlay"]
    settings.nfc.overlay_channels = []
    assert not state.snapshot("figuras")["overlay"] and not state.snapshot("nfc")["overlay"]


def test_simulation_disabled_in_real_mode(settings):
    settings.barcode.enabled = settings.audio.enabled = False
    settings.figures.enabled = settings.nfc.enabled = settings.weather.enabled = False
    with TestClient(create_app(settings=settings)) as client:
        assert client.post("/api/demo/nfc", json={"key": "Prince"}).status_code == 403
        assert client.post("/api/demo/weather", json={"key": "DD"}).status_code == 403
        assert client.get("/objetos").status_code == 503


def test_media_supports_range_requests(settings, tmp_path):
    # Un reproductor debe poder solicitar rangos para hacer seek al reconectar.
    from fastapi.staticfiles import StaticFiles
    (tmp_path / "sample.mp4").write_bytes(bytes(range(100)))
    app = create_app(settings=settings, demo=True)
    app.mount("/test-media", StaticFiles(directory=tmp_path))
    with TestClient(app) as client:
        result = client.get("/test-media/sample.mp4", headers={"Range": "bytes=10-19"})
        assert result.status_code == 206
        assert result.content == bytes(range(10, 20))
