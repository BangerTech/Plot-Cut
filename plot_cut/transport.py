"""Transportwege fuer die Plotterdaten.

- ``LokiTransport``   HTTP an die Plot-Cut-API des Loki-PrintServers; Loki
                      schreibt die Bytes selbst an das Geraet (seriell oder USB).
- ``TcpTransport``    Rohdaten an einen TCP-Port (z. B. socat am Raspberry Pi mit
                      Loki, oder ein Plotter mit LAN auf Port 9100).
- ``SerialTransport`` lokaler COM-Port (z. B. der von Loki bereitgestellte
                      virtuelle Port).
- ``FileTransport``   schreibt die Befehle in eine .plt-Datei (zum Testen).
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

LOKI_API_PREFIX = "/api/plotcut"


class TransportError(Exception):
    """Fehler beim Senden an den Plotter."""


class Transport(Protocol):
    def send(self, data: bytes) -> None: ...

    def test(self) -> tuple[bool, str]: ...

    def describe(self) -> str: ...


@dataclass
class LokiDevice:
    id: str
    name: str
    kind: str = ""
    available: bool = True
    attached_to: str | None = None


@dataclass
class LokiTransport:
    """Spricht die Plot-Cut-API des Loki-Servers (Vertrag in ``plot-cut.md``)."""

    host: str
    port: int = 7576
    device: str = ""
    timeout: float = 30.0

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}{LOKI_API_PREFIX}"

    def list_devices(self) -> list[LokiDevice]:
        payload = self._call("GET", "/devices")
        devices = payload.get("devices", []) if isinstance(payload, dict) else []
        return [
            LokiDevice(
                id=str(d.get("id", "")),
                name=str(d.get("name") or d.get("id", "")),
                kind=str(d.get("kind", "")),
                available=bool(d.get("available", True)),
                attached_to=d.get("attached_to"),
            )
            for d in devices
            if isinstance(d, dict) and d.get("id")
        ]

    def send(self, data: bytes) -> None:
        if not self.device:
            raise TransportError("Kein Loki-Geraet gewaehlt (Setup -> Verbindung -> Geraet).")
        dev = urllib.parse.quote(self.device, safe="")
        self._call("POST", f"/devices/{dev}/job", body=data)

    def test(self) -> tuple[bool, str]:
        try:
            devices = self.list_devices()
        except TransportError as exc:
            return False, str(exc)
        if not self.device:
            names = ", ".join(d.id for d in devices) or "keine"
            return False, f"Loki erreichbar, aber kein Geraet gewaehlt. Verfuegbar: {names}"
        match = next((d for d in devices if d.id == self.device), None)
        if match is None:
            return False, f"Loki kennt das Geraet '{self.device}' nicht."
        if not match.available:
            who = f" (angehaengt an {match.attached_to})" if match.attached_to else ""
            return False, f"'{match.name}' ist gerade belegt{who}."
        return True, f"'{match.name}' ist bereit ({match.kind or 'Geraet'})."

    def describe(self) -> str:
        return f"Loki {self.host}:{self.port} / {self.device or '?'}"

    def _call(self, method: str, path: str, body: bytes | None = None):
        req = urllib.request.Request(self.base_url + path, data=body, method=method)
        if body is not None:
            req.add_header("Content-Type", "application/octet-stream")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            raise TransportError(f"Loki: {_http_detail(exc)}") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise TransportError(
                f"Loki unter {self.host}:{self.port} nicht erreichbar: {exc}"
            ) from exc
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}


def _http_detail(exc: urllib.error.HTTPError) -> str:
    try:
        detail = json.loads(exc.read().decode("utf-8")).get("detail")
    except Exception:
        detail = None
    messages = {
        404: "Geraet oder Plot-Cut-API nicht gefunden (Loki aktualisiert?)",
        409: "Geraet ist belegt (z. B. per USB/IP an einen PC angehaengt)",
        503: "Geraet ist nicht angeschlossen",
    }
    text = str(detail or messages.get(exc.code, f"HTTP {exc.code}"))
    low = text.lower()
    if "0a50" in low or "gerätedatei" in low or "geraetedatei" in low:
        text += (
            "\n\nDer Mimaki haengt bei Loki im USB/IP-Modus fuer FineCut. "
            "Plot Cut schickt den Auftrag an die USB-Bridge von Loki, und die sieht "
            "das Geraet in diesem Modus nicht.\n\n"
            "Es wurde nichts an den Plotter geschrieben.\n\n"
            "Abhilfe: Im Setup unter Verbindung die Art \"Mimaki USB (lokal, wie FineCut)\" "
            "waehlen. Dann schreibt Plot Cut wie FineCut an den per USB/IP angehaengten Cutter."
        )
    return text


@dataclass
class TcpTransport:
    host: str
    port: int
    timeout: float = 10.0

    def send(self, data: bytes) -> None:
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
                sock.sendall(data)
        except OSError as exc:
            raise TransportError(f"TCP-Senden an {self.host}:{self.port} fehlgeschlagen: {exc}") from exc

    def test(self) -> tuple[bool, str]:
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout):
                return True, f"Verbindung zu {self.host}:{self.port} steht."
        except OSError as exc:
            return False, f"Keine Verbindung zu {self.host}:{self.port}: {exc}"

    def describe(self) -> str:
        return f"TCP {self.host}:{self.port}"


@dataclass
class SerialTransport:
    port: str
    baud: int = 9600
    timeout: float = 10.0

    def _resolve_port(self) -> str:
        """``auto`` sucht einen USB-Seriell-Wandler (CH340 wie beim Vevor), auch per USB/IP."""
        if self.port.strip().lower() != "auto":
            return self.port
        _import_serial()
        from serial.tools import list_ports  # type: ignore

        ports = list(list_ports.comports())
        for vid in AUTO_SERIAL_VIDS:
            for info in ports:
                if info.vid == vid:
                    return info.device
        raise TransportError(
            "Kein USB-Seriell-Plotter (CH340) gefunden. Ist der Plotter im Loki-Client "
            "an diesen PC angehaengt?"
        )

    def send(self, data: bytes) -> None:
        serial = _import_serial()
        port = self._resolve_port()
        try:
            with serial.Serial(port, self.baud, timeout=self.timeout) as ser:
                ser.write(data)
                ser.flush()
        except Exception as exc:  # pyserial wirft SerialException
            raise TransportError(f"Serielles Senden an {port} fehlgeschlagen: {exc}") from exc

    def test(self) -> tuple[bool, str]:
        try:
            serial = _import_serial()
            port = self._resolve_port()
        except TransportError as exc:
            return False, str(exc)
        try:
            with serial.Serial(port, self.baud, timeout=self.timeout):
                return True, f"Port {port} geoeffnet."
        except Exception as exc:
            return False, f"Port {port} nicht verfuegbar: {exc}"

    def describe(self) -> str:
        return f"COM {self.port} @ {self.baud}"


AUTO_SERIAL_VIDS = (0x1A86,)  # WCH CH340/CH341

MKUSB_INTERFACE_GUID = "{fe05b407-0142-458b-ab3d-f7180561e884}"


def find_mimaki_usb_paths() -> list[str]:
    """Geraetepfade des Mimaki-Treibers ``mkusb`` (wie FineCut sie oeffnet).

    Findet auch Cutter, die Loki per USB/IP an diesen PC haengt.
    """
    try:
        import winreg
    except ImportError:
        return []
    key_path = rf"SYSTEM\CurrentControlSet\Control\DeviceClasses\{MKUSB_INTERFACE_GUID}"
    paths: list[str] = []
    try:
        root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
    except OSError:
        return []
    with root:
        i = 0
        while True:
            try:
                name = winreg.EnumKey(root, i)
            except OSError:
                break
            i += 1
            if name.startswith("##?#"):
                paths.append("\\\\?\\" + name[4:])
    return paths


@dataclass
class MimakiUsbTransport:
    """Schreibt direkt an den Mimaki-USB-Treiber, wie FineCut.

    Bei Loki im USB/IP-Modus haengt der Cutter als lokales USB-Geraet an diesem PC.
    """

    device_path: str = ""
    chunk: int = 4096

    def _open(self):
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CreateFileW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
        ]
        candidates = [self.device_path] if self.device_path else find_mimaki_usb_paths()
        if not candidates:
            raise TransportError(
                "Kein Mimaki-USB-Geraet gefunden. Ist der Cutter per Loki-Client (USB/IP) "
                "an diesen PC angehaengt und der Mimaki-Treiber installiert?"
            )
        invalid = wintypes.HANDLE(-1).value
        last_err = 0
        for path in candidates:
            handle = kernel.CreateFileW(path, 0x40000000 | 0x80000000, 0x3, None, 3, 0, None)
            if handle and handle != invalid:
                return kernel, handle, path
            last_err = ctypes.get_last_error()
        raise TransportError(
            "Mimaki-USB-Geraet laesst sich nicht oeffnen "
            f"(Windows-Fehler {last_err}). Ist der Cutter eingeschaltet und angehaengt?"
        )

    def send(self, data: bytes) -> None:
        import ctypes
        from ctypes import wintypes

        kernel, handle, path = self._open()
        try:
            written = wintypes.DWORD(0)
            for start in range(0, len(data), self.chunk):
                block = data[start : start + self.chunk]
                ok = kernel.WriteFile(handle, block, len(block), ctypes.byref(written), None)
                if not ok or written.value != len(block):
                    raise TransportError(
                        f"Schreiben an den Mimaki abgebrochen nach {start + written.value} "
                        f"von {len(data)} Bytes (Windows-Fehler {ctypes.get_last_error()})."
                    )
        finally:
            kernel.CloseHandle(handle)

    def test(self) -> tuple[bool, str]:
        try:
            kernel, handle, path = self._open()
        except TransportError as exc:
            return False, str(exc)
        kernel.CloseHandle(handle)
        return True, f"Mimaki-USB-Geraet bereit:\n{path}"

    def describe(self) -> str:
        return "Mimaki USB (lokal)"


@dataclass
class FileTransport:
    path: str

    def send(self, data: bytes) -> None:
        try:
            Path(self.path).write_bytes(data)
        except OSError as exc:
            raise TransportError(f"Datei {self.path} konnte nicht geschrieben werden: {exc}") from exc

    def test(self) -> tuple[bool, str]:
        parent = Path(self.path).expanduser().resolve().parent
        if parent.exists():
            return True, f"Schreibe nach {self.path}."
        return False, f"Ordner existiert nicht: {parent}"

    def describe(self) -> str:
        return f"Datei {self.path}"


def _import_serial():
    try:
        import serial  # type: ignore
    except ImportError as exc:
        raise TransportError(
            "pyserial ist nicht installiert. Bitte 'pip install pyserial' ausfuehren."
        ) from exc
    return serial


def build_transport(cfg: dict) -> Transport:
    """Erzeugt den passenden Transport aus dem ``transport``-Dict eines Profils."""
    kind = cfg.get("kind", "tcp")
    if kind == "loki":
        return LokiTransport(
            host=cfg.get("host", "127.0.0.1"),
            port=int(cfg.get("loki_port", 7576)),
            device=cfg.get("device", ""),
        )
    if kind == "tcp":
        return TcpTransport(host=cfg.get("host", "127.0.0.1"), port=int(cfg.get("port", 7580)))
    if kind == "serial":
        return SerialTransport(
            port=cfg.get("serial_port", "COM3"), baud=int(cfg.get("baud", 9600))
        )
    if kind == "mimaki_usb":
        return MimakiUsbTransport(device_path=cfg.get("usb_path", ""))
    if kind == "file":
        return FileTransport(path=cfg.get("file_path", "out.plt"))
    raise TransportError(f"Unbekannter Transport: {kind}")
