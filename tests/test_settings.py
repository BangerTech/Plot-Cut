"""Tests fuer Plotter-Profile und die Migration alter Einstellungen."""

from __future__ import annotations

from plot_cut import settings as s


def test_migrates_single_plotter_v1_to_profile():
    v1 = {
        "version": 1,
        "transport": {"kind": "tcp", "host": "10.0.0.5", "port": 7580},
        "plotter": {"model": "CG-60SR", "language": "mgl2", "sheet_width_mm": 600.0},
        "defaults": {"speed": 25},
        "per_file": {"a.vectorcraft": {"copies": 2}},
    }
    out = s.migrate(v1)
    assert out["version"] == s.SETTINGS_VERSION
    mimaki = out["profiles"]["Mimaki CG-60SR"]
    assert mimaki["transport"]["host"] == "10.0.0.5"
    assert mimaki["plotter"]["sheet_width_mm"] == 600.0
    assert mimaki["defaults"]["speed"] == 25
    assert mimaki["defaults"]["pressure"] == 100  # Default ergaenzt
    assert "Vevor" in out["profiles"]
    assert out["per_file"]["a.vectorcraft"]["copies"] == 2


def test_deleted_profiles_stay_deleted():
    data = s.migrate({"profiles": {"Nur einer": {"plotter": {"language": "hpgl"}}},
                      "active_profile": "weg"})
    assert list(data["profiles"]) == ["Nur einer"]
    assert data["active_profile"] == "Nur einer"
    assert data["profiles"]["Nur einer"]["plotter"]["language"] == "hpgl"
    assert "transport" in data["profiles"]["Nur einer"]


def test_profile_management():
    data = s.migrate({})
    s.new_profile(data, "Graphtec", copy_from="Vevor")
    assert data["active_profile"] == "Graphtec"
    assert data["profiles"]["Graphtec"]["plotter"]["language"] == "hpgl"

    assert s.rename_profile(data, "Graphtec", "Graphtec CE")
    assert data["active_profile"] == "Graphtec CE"
    assert not s.rename_profile(data, "Vevor", "Graphtec CE")

    assert s.delete_profile(data, "Graphtec CE")
    assert data["active_profile"] in data["profiles"]


def test_last_profile_cannot_be_deleted():
    data = s.migrate({"profiles": {"A": {}}})
    assert not s.delete_profile(data, "A")
