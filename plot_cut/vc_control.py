"""Client fuer den VectorCraft-Steuerkanal (``vectorcraft --control <port>``).

Das Protokoll: eine JSON-Zeile pro Request ueber TCP auf 127.0.0.1:<port>.
Antwort ebenfalls eine JSON-Zeile. Siehe ``docs/control-protocol.md`` im
VectorCraft-Repo.

Dieser Client kapselt die wenigen Methoden, die Plot-Cut braucht:

- ``ping``              Verbindung / Version pruefen
- ``list_commands``    verfuegbare Engine-Kommandos (zum Feststellen, was die
                       installierte Version kann)
- ``get_document_info``  Dateipfad, Auswahlzaehler, Ebenen
- ``export_selection``   die aktuelle Auswahl als Vektordaten (SVG bevorzugt,
                         DXF als Rueckfall) als Bytes
"""

from __future__ import annotations

import base64
import json
import socket
from dataclasses import dataclass, field
from typing import Any


class VcControlError(Exception):
    """Fehler bei der Kommunikation mit dem VectorCraft-Steuerkanal."""


@dataclass
class Selection:
    """Ergebnis eines Auswahl-Exports."""

    data: bytes
    fmt: str  # "svg" oder "dxf"
    count: int = 0
    document_path: str | None = None


@dataclass
class VcControlClient:
    """Verbindet sich pro Request neu (der Server erlaubt nur Requests, keine
    dauerhafte Sitzung mit mehreren Antworten pro Zeile zuverlaessig fuer uns)."""

    host: str = "127.0.0.1"
    port: int = 7979
    timeout: float = 5.0
    _next_id: int = field(default=1, init=False, repr=False)

    # -- rohe Kommunikation ------------------------------------------------

    def _request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Schickt einen Request und gibt ``result`` zurueck oder wirft."""
        req_id = self._next_id
        self._next_id += 1
        payload = {"id": req_id, "method": method}
        if params:
            payload["params"] = params
        line = json.dumps(payload) + "\n"

        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
                sock.sendall(line.encode("utf-8"))
                raw = self._read_line(sock)
        except OSError as exc:
            raise VcControlError(
                f"Keine Verbindung zu VectorCraft ({self.host}:{self.port}). "
                "Laeuft es mit --control?"
            ) from exc

        if not raw:
            raise VcControlError("Leere Antwort vom Steuerkanal.")
        try:
            resp = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise VcControlError(f"Ungueltige Antwort: {raw!r}") from exc

        if not resp.get("ok", False):
            raise VcControlError(str(resp.get("error", "unbekannter Fehler")))
        return resp.get("result")

    @staticmethod
    def _read_line(sock: socket.socket) -> str:
        """Liest bis zum ersten Zeilenumbruch (eine Antwort pro Zeile)."""
        chunks: list[bytes] = []
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
            if b"\n" in chunk:
                break
        data = b"".join(chunks)
        line, _, _ = data.partition(b"\n")
        return line.decode("utf-8", errors="replace")

    # -- hilfsfunktionen ---------------------------------------------------

    def ping(self) -> bool:
        """True, wenn der Steuerkanal antwortet."""
        try:
            self._request("ui.inspect")
            return True
        except VcControlError:
            return False

    def list_commands(self) -> set[str]:
        """Namen aller Engine-Kommandos (zum Feature-Erkennen)."""
        try:
            result = self._request("engine.commands")
        except VcControlError:
            return set()
        names: set[str] = set()
        # Das Format kann je nach Version abweichen; robust einsammeln.
        candidates: Any = result
        if isinstance(result, dict):
            candidates = result.get("commands", result.values())
        if isinstance(candidates, dict):
            candidates = candidates.values()
        if isinstance(candidates, list):
            for item in candidates:
                if isinstance(item, str):
                    names.add(item)
                elif isinstance(item, dict):
                    name = item.get("name") or item.get("command") or item.get("id")
                    if isinstance(name, str):
                        names.add(name)
        return names

    def get_document_info(self) -> dict[str, Any]:
        """Dateipfad, Auswahlzaehler und Ebenen, so gut die Version es liefert."""
        info: dict[str, Any] = {"path": None, "selection_count": 0, "layers": []}
        try:
            result = self._request("document.inspect", {"depth": 2})
        except VcControlError:
            return info
        if not isinstance(result, dict):
            return info

        info["path"] = result.get("path") or result.get("file") or result.get("title")

        selection = result.get("selection")
        if isinstance(selection, list):
            info["selection_count"] = len(selection)
        elif isinstance(selection, dict):
            ids = selection.get("ids")
            info["selection_count"] = len(ids) if isinstance(ids, list) else int(
                selection.get("count", 0) or 0
            )

        layers = result.get("layers")
        if isinstance(layers, list):
            info["layers"] = layers
        return info

    # -- auswahl exportieren ----------------------------------------------

    def export_selection(self) -> Selection:
        """Exportiert die aktuelle Auswahl als Vektordaten.

        Versucht zuerst SVG (am einfachsten zu parsen), dann DXF. Wenn die
        Version ``selectedOnly`` nicht unterstuetzt, kommt der ganze Artboard
        zurueck -- der Aufrufer sollte dann warnen.
        """
        doc = self.get_document_info()
        last_error: str | None = None

        # 1) SVG ueber app.export ohne path -> dataBase64
        for params in (
            {"format": "svg", "selectedOnly": True},
            {"format": "svg"},
        ):
            try:
                data = self._export_bytes(params)
                if data:
                    return Selection(
                        data=data,
                        fmt="svg",
                        count=doc["selection_count"],
                        document_path=doc["path"],
                    )
            except VcControlError as exc:
                last_error = str(exc)

        # 2) DXF als Rueckfall
        for params in (
            {"format": "dxf", "selectedOnly": True},
            {"format": "dxf"},
        ):
            try:
                data = self._export_bytes(params)
                if data:
                    return Selection(
                        data=data,
                        fmt="dxf",
                        count=doc["selection_count"],
                        document_path=doc["path"],
                    )
            except VcControlError as exc:
                last_error = str(exc)

        raise VcControlError(
            "Auswahl konnte nicht exportiert werden"
            + (f": {last_error}" if last_error else ".")
        )

    def _export_bytes(self, params: dict[str, Any]) -> bytes:
        """Ruft ``app.export`` ohne ``path`` auf und dekodiert ``dataBase64``."""
        result = self._request("app.export", params)
        if not isinstance(result, dict):
            raise VcControlError("Unerwartete Antwort von app.export.")
        b64 = result.get("dataBase64")
        if not b64:
            raise VcControlError("app.export lieferte keine Daten (dataBase64 fehlt).")
        try:
            return base64.b64decode(b64)
        except (ValueError, TypeError) as exc:
            raise VcControlError("dataBase64 konnte nicht dekodiert werden.") from exc
