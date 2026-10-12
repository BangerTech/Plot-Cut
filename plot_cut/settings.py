"""Einstellungen laden/speichern (JSON, keine Datenbank).

Ablageort: ``%APPDATA%\\PlotCut\\settings.json`` (Windows) bzw.
``~/.config/PlotCut/settings.json`` sonst. Schema siehe ``plot-cut.md``.

Ab Version 2 gibt es mehrere Plotter-Profile (``profiles``); jedes Profil hat
eigene Plotterdaten, Verbindung, Standardbedingung und Farbbedingungen.
Version-1-Dateien (ein einzelner Plotter, noch unter ``MimakiCut``) werden beim
Laden automatisch uebernommen.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

from .mgl import CutCondition

APP_DIR_NAME = "PlotCut"
LEGACY_APP_DIR_NAME = "MimakiCut"
SETTINGS_FILE = "settings.json"
SETTINGS_VERSION = 3


def _remap_old_mgl_tool(value: int) -> int:
    """Alte Auswahlliste CT1=1, CT2=2, CT3=3 -> FineCut SP-Nummern."""
    if value == 2:
        return 3
    if value == 3:
        return 4
    return value


def _remap_tools_in_profile(prof: dict[str, Any]) -> None:
    if str(prof.get("plotter", {}).get("language", "mgl2")) != "mgl2":
        return
    defaults = prof.setdefault("defaults", {})
    defaults["tool"] = _remap_old_mgl_tool(int(defaults.get("tool", 1)))
    table = prof.get("conditions_by_color", {})
    if isinstance(table, dict):
        for raw in table.values():
            if isinstance(raw, dict) and "tool" in raw:
                raw["tool"] = _remap_old_mgl_tool(int(raw["tool"]))


def _profile(
    model: str, language: str, sheet_width_mm: float, speed: int, pressure: int, offset: float
) -> dict[str, Any]:
    return {
        "plotter": {
            "model": model,
            "language": language,
            "sheet_width_mm": sheet_width_mm,
            "sheet_height_mm": 1000.0,
            "step_mm": 0.025,
            "crv_res": 0.05,
        },
        "transport": {
            "kind": "file",
            "host": "192.168.1.50",
            "loki_port": 7576,
            "device": "",
            "port": 7580,
            "serial_port": "COM3",
            "baud": 9600,
            "file_path": "out.plt",
        },
        "defaults": {
            "speed": speed,
            "pressure": pressure,
            "offset": offset,
            "overcut_mm": 0.0,
            "sort": True,
            "inner_first": True,
            "send_conditions": True,
            "end_action": "stay",
            "feed_mm": 20.0,
            "extra_passes": 0,
            "pause_per_color": False,
        },
        "conditions_by_color": {},
    }


DEFAULT_PROFILES: dict[str, dict[str, Any]] = {
    "Mimaki CG-60SR": _profile("CG-60SR", "mgl2", 610.0, 30, 100, 0.3),
    "Vevor": _profile("Vevor", "hpgl", 720.0, 20, 80, 0.25),
}

DEFAULT_SETTINGS: dict[str, Any] = {
    "version": SETTINGS_VERSION,
    "control": {"host": "127.0.0.1", "port": 7979, "vectorcraft_exe": "", "auto_start": True},
    "active_profile": "Mimaki CG-60SR",
    "profiles": copy.deepcopy(DEFAULT_PROFILES),
    "favorites": {},
    "per_file": {},
    "ui": {"language": "de"},
}


def _config_root() -> Path:
    base = os.environ.get("APPDATA")
    return Path(base) if base else Path.home() / ".config"


def settings_dir() -> Path:
    return _config_root() / APP_DIR_NAME


def settings_path() -> Path:
    return settings_dir() / SETTINGS_FILE


def _legacy_path() -> Path:
    return _config_root() / LEGACY_APP_DIR_NAME / SETTINGS_FILE


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def migrate(data: dict[str, Any]) -> dict[str, Any]:
    """Hebt eine Einstellungsdatei auf das aktuelle Schema."""
    if "profiles" in data:
        merged = _deep_merge(DEFAULT_SETTINGS, {k: v for k, v in data.items() if k != "profiles"})
        # Profile nicht mit den Standardprofilen mischen: geloeschte bleiben geloescht.
        merged["profiles"] = {
            name: _deep_merge(DEFAULT_PROFILES["Mimaki CG-60SR"], prof)
            for name, prof in data["profiles"].items()
            if isinstance(prof, dict)
        } or copy.deepcopy(DEFAULT_PROFILES)
    else:
        # Version 1: ein Plotter auf oberster Ebene -> wird Profil "Mimaki CG-60SR".
        merged = copy.deepcopy(DEFAULT_SETTINGS)
        legacy = {k: data[k] for k in ("plotter", "transport", "defaults", "conditions_by_color")
                  if isinstance(data.get(k), dict)}
        merged["profiles"]["Mimaki CG-60SR"] = _deep_merge(
            DEFAULT_PROFILES["Mimaki CG-60SR"], legacy
        )
        for key in ("control", "favorites", "per_file", "ui"):
            if isinstance(data.get(key), dict):
                merged[key] = _deep_merge(merged[key], data[key])

    if merged.get("active_profile") not in merged["profiles"]:
        merged["active_profile"] = next(iter(merged["profiles"]))
    previous = int(data.get("version", 1) or 1)
    if previous < 3:
        for prof in merged["profiles"].values():
            if isinstance(prof, dict):
                _remap_tools_in_profile(prof)
        favorites = merged.get("favorites", {})
        if isinstance(favorites, dict):
            for fav in favorites.values():
                if isinstance(fav, dict) and "tool" in fav:
                    fav["tool"] = _remap_old_mgl_tool(int(fav["tool"]))
    merged["version"] = SETTINGS_VERSION
    return merged


def load_settings() -> dict[str, Any]:
    path = settings_path()
    if not path.exists() and _legacy_path().exists():
        path = _legacy_path()
    if not path.exists():
        return copy.deepcopy(DEFAULT_SETTINGS)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return copy.deepcopy(DEFAULT_SETTINGS)
    if not isinstance(data, dict):
        return copy.deepcopy(DEFAULT_SETTINGS)
    return migrate(data)


def save_settings(settings: dict[str, Any]) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


# -- Profile ---------------------------------------------------------------

def active_profile(settings: dict[str, Any]) -> dict[str, Any]:
    profiles = settings["profiles"]
    name = settings.get("active_profile")
    if name not in profiles:
        name = next(iter(profiles))
        settings["active_profile"] = name
    return profiles[name]


def new_profile(settings: dict[str, Any], name: str, copy_from: str | None = None) -> None:
    source = settings["profiles"].get(copy_from or "") or DEFAULT_PROFILES["Mimaki CG-60SR"]
    settings["profiles"][name] = copy.deepcopy(source)
    settings["active_profile"] = name


def delete_profile(settings: dict[str, Any], name: str) -> bool:
    if name not in settings["profiles"] or len(settings["profiles"]) <= 1:
        return False
    del settings["profiles"][name]
    if settings.get("active_profile") == name:
        settings["active_profile"] = next(iter(settings["profiles"]))
    return True


def rename_profile(settings: dict[str, Any], old: str, new: str) -> bool:
    profiles = settings["profiles"]
    if old not in profiles or not new or new in profiles:
        return False
    settings["profiles"] = {(new if k == old else k): v for k, v in profiles.items()}
    if settings.get("active_profile") == old:
        settings["active_profile"] = new
    return True


# -- Komfort-Zugriffe ------------------------------------------------------

def default_condition(profile: dict[str, Any]) -> CutCondition:
    d = profile.get("defaults", {})
    return CutCondition(
        tool=int(d.get("tool", 1)),
        speed=int(d.get("speed", 30)),
        pressure=int(d.get("pressure", 100)),
        offset=float(d.get("offset", 0.3)),
        enabled=True,
    )


def conditions_by_color(profile: dict[str, Any]) -> dict[str, CutCondition]:
    out: dict[str, CutCondition] = {}
    for color, raw in profile.get("conditions_by_color", {}).items():
        if not isinstance(raw, dict):
            continue
        out[color.lower()] = CutCondition(
            tool=int(raw.get("tool", 1)),
            speed=int(raw.get("speed", 30)),
            pressure=int(raw.get("pressure", 100)),
            offset=float(raw.get("offset", 0.3)),
            enabled=bool(raw.get("enabled", True)),
        )
    return out


def get_per_file(settings: dict[str, Any], document_path: str | None) -> dict[str, Any]:
    if not document_path:
        return {}
    return dict(settings.get("per_file", {}).get(document_path, {}))


def set_per_file(settings: dict[str, Any], document_path: str | None, values: dict[str, Any]) -> None:
    if not document_path:
        return
    settings.setdefault("per_file", {})[document_path] = values
