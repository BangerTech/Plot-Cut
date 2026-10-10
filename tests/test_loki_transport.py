"""Tests fuer den Loki-Transport gegen einen lokalen Fake der Plot-Cut-API."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from plot_cut.transport import LokiTransport, TransportError, build_transport

DEVICES = [
    {"id": "mimaki-cg60sr", "name": "Mimaki CG-60SR", "kind": "serial", "available": True},
    {"id": "vevor", "name": "Vevor", "kind": "usblp", "available": False,
     "attached_to": "PC-Buero"},
]


class _FakeLoki(BaseHTTPRequestHandler):
    received: dict[str, bytes] = {}

    def log_message(self, *args):  # noqa: D401 - Testserver leise halten
        pass

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/plotcut/devices":
            self._json(200, {"devices": DEVICES})
        else:
            self._json(404, {"detail": "Not Found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length)
        parts = self.path.split("/")
        if len(parts) == 6 and parts[1:4] == ["api", "plotcut", "devices"] and parts[5] == "job":
            dev = parts[4]
            if dev == "vevor":
                self._json(409, {"detail": "Vevor ist per USB/IP an PC-Buero angehaengt"})
                return
            if dev != "mimaki-cg60sr":
                self._json(404, {"detail": f"Unbekanntes Geraet: {dev}"})
                return
            _FakeLoki.received[dev] = data
            self._json(200, {"ok": True, "bytes": len(data)})
        else:
            self._json(404, {"detail": "Not Found"})


@pytest.fixture()
def loki_server():
    server = HTTPServer(("127.0.0.1", 0), _FakeLoki)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()


def test_list_devices(loki_server):
    devices = LokiTransport("127.0.0.1", loki_server).list_devices()
    assert [d.id for d in devices] == ["mimaki-cg60sr", "vevor"]
    assert devices[1].available is False
    assert devices[1].attached_to == "PC-Buero"


def test_send_job_bytes(loki_server):
    t = build_transport(
        {"kind": "loki", "host": "127.0.0.1", "loki_port": loki_server, "device": "mimaki-cg60sr"}
    )
    t.send(b"IN;PU0,0;PD400,0;PU0,0;")
    assert _FakeLoki.received["mimaki-cg60sr"] == b"IN;PU0,0;PD400,0;PU0,0;"


def test_busy_device_reports_detail(loki_server):
    t = LokiTransport("127.0.0.1", loki_server, device="vevor")
    with pytest.raises(TransportError, match="USB/IP"):
        t.send(b"IN;")
    ok, msg = t.test()
    assert not ok
    assert "belegt" in msg


def test_missing_device_and_unreachable_server(loki_server):
    ok, msg = LokiTransport("127.0.0.1", loki_server, device="gibtsnicht").test()
    assert not ok and "nicht" in msg
    with pytest.raises(TransportError):
        LokiTransport("127.0.0.1", loki_server).send(b"IN;")  # kein Geraet gewaehlt
    ok, _ = LokiTransport("127.0.0.1", 1, device="x", timeout=1).test()
    assert not ok
