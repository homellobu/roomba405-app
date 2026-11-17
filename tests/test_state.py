import time

from roomba.state import render_state


def test_render_state_full():
    state = {
        "name": "Salón",
        "sku": "Y011040",
        "softwareVer": "v4.5.1",
        "batPct": 87,
        "cleanMissionStatus": {"phase": "run", "cycle": "clean", "error": 0, "mssnM": 12, "sqft": 340},
        "bin": {"present": True, "full": False},
        "pose": {"point": {"x": 100, "y": 200}, "theta": 90},
        "signal": {"rssi": -52},
        "dock": {"known": True},
    }
    text = render_state(state)
    assert "Salón" in text
    assert "Y011040" in text
    assert "87%" in text
    assert "Limpiando" in text
    assert "Limpieza estándar" in text
    assert "Sin errores" in text
    assert "presente" in text
    assert "-52 dBm" in text
    assert "conocida" in text


def test_render_state_empty():
    assert "no se ha recibido" in render_state({})


def test_render_state_error_and_bin_full():
    state = {
        "cleanMissionStatus": {"phase": "stop", "error": 34},
        "bin": {"present": True, "full": True},
    }
    text = render_state(state)
    assert "Depósito lleno" in text
    assert "LLENO" in text
