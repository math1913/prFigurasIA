from display_app.state import FigureGate


def test_same_figure_waits_full_minute_despite_reappearance():
    now = [0]
    gate = FigureGate(0, 1, clock=lambda: now[0])
    assert gate.update([("A", .9)]) == "A"
    gate.update([])
    now[0] = 2
    assert gate.update([("A", .9)]) is None
    for instant in (10, 30, 59.999):
        now[0] = instant
        assert gate.update([("A", .9)]) is None
    now[0] = 60
    assert gate.update([("A", .9)]) == "A"
    now[0] = 120
    assert gate.update([("A", .9)]) is None  # Sin retirada no se repite.


def test_new_figure_interrupts_but_does_not_reset_previous_cooldown():
    now = [0]
    gate = FigureGate(0, 1, clock=lambda: now[0])
    assert gate.update([("A", .9)]) == "A"
    now[0] = 2
    assert gate.update([("B", .9)]) == "B"
    now[0] = 4
    assert gate.update([("A", .9)]) is None
    now[0] = 60
    assert gate.update([("A", .9)]) == "A"


def test_camera_reconnection_and_repeat_mode_cannot_bypass_cooldown():
    now = [0]
    gate = FigureGate(0, 1, clock=lambda: now[0], cooldown_seconds=90)
    assert gate.update([("A", .9)]) == "A"
    now[0] = 2
    gate.reset_visibility()
    assert gate.update([("A", .9)]) is None
    now[0] = 60
    gate.fired.clear()  # El modo repeat_while_present rearma la detección.
    assert gate.update([("A", .9)]) is None
    now[0] = 90
    assert gate.update([("A", .9)]) == "A"
