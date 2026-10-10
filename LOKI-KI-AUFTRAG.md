# Auftrag fuer die KI im Repo BangerTech/Loki-PrintServer

Diesen ganzen Text der KI geben, die an Loki-PrintServer (aktuell **1.4.16**) arbeitet.

Repo: https://github.com/BangerTech/Loki-PrintServer  
Plot Cut (Auftraggeber): https://github.com/BangerTech/Plot-Cut

---

## Ziel

Ergaenze den **bestehenden** FastAPI-Server (Port **7576**) um eine kleine **Plot-Cut-API**.
Plot Cut (Windows, neben VectorCraft) erzeugt fertige Plotterbefehle und schickt die
**Rohbytes** per HTTP. Loki schreibt sie unveraendert an den Plotter.

Loki erzeugt **keine** MGL/HP-GL-Befehle.

Beide Plotter laufen **heute schon** aus Adobe Illustrator + FineCut ueber Loki.
Das darf nicht kaputtgehen: USB/IP, Raw-USB-Bridge, socat, CUPS, Loki-Client,
`attach-mode`, Auto-Share.

| Plotter | USB | Loki-Weg heute | Plot-Cut-Sprache |
|---|---|---|---|
| Mimaki CG-60SR | VID **`0x0A50`** (Vendor-USB, kein tty) | `usb_bridge.py` (Raw USB, framed TCP) + USB/IP fuer Windows-FineCut; **nicht** `usbserial` | MGL-IIc |
| Vevor | VID:PID **`1a86:7523`** (CH340) | socat Serial-over-TCP Port **7580+**, `forward_info.serial` | HP-GL |

---

## Was in Loki schon da ist (1.4.16) — wiederverwenden, nicht neu erfinden

| Port | Zweck |
|---|---|
| 7575 | USB/IP (`usbipd`) |
| 7576 | FastAPI + Dashboard + WebSocket `/ws` |
| 7580+ | socat Serial-over-TCP, ein Port pro Geraet |
| 631 | CUPS / IPP |

Wichtige Dateien: `server/api/main.py`, `usbip.py` (`KNOWN_DEVICES`), `forwarder.py`,
`usb_bridge.py` (Mimaki Bulk/Control), `web/index.html`.

Bereits vorhandene Endpunkte (nicht umbauen):

- `GET /api/devices`, `GET /api/devices/shared`, `POST /api/devices/share|unshare`
- `POST /api/devices/{bus_id}/attach-mode` (`usbip` Windows / `bridge` macOS FineCut)
- `GET /api/devices/{bus_id}/forward` → u. a. `serial.port`, `serial.device`
- `PUT /api/devices/{bus_id}/name`, Auto-Share, `/health`, `/api/status`

`forward_info.serial` (Beispiel Vevor):

```json
{ "available": true, "port": 7580, "device": "/dev/ttyUSB0" }
```

Wichtige Loki-Regeln, die du **nicht** brechen darfst:

- `usbip-host` und `usbserial` sind **gegenseitig ausschliessend**. Serial-Forwarding
  passiert **vor** `usbip bind`.
- Mimaki darf **nicht** an `usbserial_generic` gebunden werden (ab 1.4.1 bewusst entfernt).
- Windows-FineCut braucht `attach-mode=usbip`. Ein Fake-`tcp://…:7580` als „Attach“
  laesst FineCut kein USB-Geraet sehen.
- Ist ein Geraet per USB/IP an einen Client angehaengt, gehoert es dem Client.
  Nicht wegnehmen.

---

## Neue API (genau so, Plot Cut ist darauf programmiert)

Basis: bestehender FastAPI auf **7576**, Praefix **`/api/plotcut`**.
Keine neue Auth. `LOKI_SECRET` gilt wie bei den anderen Endpunkten; Plot Cut schickt
derzeit kein Passwort — wenn Secret gesetzt ist, 401 mit klarem `detail`, nicht still
schlucken.

### `GET /api/plotcut/devices`

Alle Plotter, an die Plot Cut senden kann (Peripherie, `is_infrastructure == false`,
Klasse Plotter/Serial bzw. bekannte VID).

```json
{
  "devices": [
    {
      "id": "mimaki-cg60sr",
      "name": "Mimaki CG-60SR",
      "kind": "usb-vendor",
      "available": true,
      "attached_to": null
    },
    {
      "id": "vevor",
      "name": "Vevor",
      "kind": "serial",
      "available": true,
      "attached_to": null
    }
  ]
}
```

- `id`: stabil, URL-tauglich. **Nicht** die wechselnde `bus_id`. Ableiten aus VID:PID
  und/oder `custom_names.json`, z. B. `0a50-…` → `mimaki-cg60sr`, `1a86-7523` → `vevor`.
  Nach Neustart und Umstecken gleich.
- `name`: Dashboard-Name / `custom_name`, sonst Produktstring.
- `kind`: `serial` (socat/tty, typisch Vevor), `usb-vendor` (Raw-USB-Bridge, Mimaki).
- `available`: `false`, wenn Loki gerade nicht schreiben kann (siehe „Belegt“).
- `attached_to`: Client-Name/IP bei USB/IP-Attach, sonst `null`.

### `POST /api/plotcut/devices/{id}/job`

- Body: rohe Plotterbytes, `Content-Type: application/octet-stream`.
  Beispiel: `IN;SP1;VS30;FS100;PU0,1200;PD0,0,1200,0,1200,1200,0,1200;PU0,0;`
- Bytes **unveraendert und vollstaendig** schreiben, dann antworten.
- Erfolg: `200` `{"ok": true, "bytes": <N>}`
- Fehler als FastAPI-`HTTPException`, `detail` auf Deutsch (Plot Cut zeigt das 1:1):
  - `404` unbekannte `id`
  - `409` belegt (USB/IP an Client, Bridge/FineCut aktiv, oder Job laeuft schon)
  - `503` nicht angeschlossen / nicht geshared
  - `500` Schreibfehler (Ursache im `detail`)
- Body mindestens 50 MB.
- Ein Job pro Geraet (Lock). Zweiter gleichzeitiger Request → `409`.

---

## Wie die Bytes zum Geraet kommen

Die Geraete sind Loki bereits bekannt. Keine parallele Geraetedatenbank.

### Vevor (`1a86:7523`, `kind=serial`)

1. Geraet muss **shared** sein (`forward_info.serial.available`).
2. Bytes an den **bestehenden** socat-Weg: lokal zu `127.0.0.1:{forward_info.serial.port}`
   verbinden und senden (`reuseaddr,fork` bleibt).
3. Die `tty` **nicht** parallel zu socat oeffnen.
4. Kein RTS/CTS (CH340, `flow=none`).

### Mimaki CG-60SR (`0x0A50`, `kind=usb-vendor`)

FineCut spricht den Plotter per **Raw USB** (Vendor-Klasse, Bulk IN/OUT, Control
`0xC0/0x01` Identifikation `CG-SR-00`) — nicht als COM-Port. Dieselbe Bruecke
(`usb_bridge.py` / pyusb) nutzen:

1. Geraet shared, Kernel-Treiber wie heute entbunden, **kein** `usbserial`.
2. Job-Bytes auf den **Bulk-OUT**-Endpunkt schreiben (dieselbe Pipe wie FineCut-Daten,
   ohne das FineCut-TCP-Frame fuer Control-Requests umzubauen, wenn die Nutzlast
   schon die MGL-Bytes sind). Falls die Bridge nur framed TCP kennt: intern denselben
   Schreibpfad aufrufen, den die Bridge fuer Bulk-OUT schon hat — nicht einen zweiten
   pyusb-Claim daneben.
3. Ist USB/IP an einen Windows-Client gebunden (FineCut): **nicht** schreiben → `409`.
4. Ist das Geraet nur exportiert, aber an **keinen** Client angehaengt: fuer die Dauer
   des Jobs vom `usbip-host` loesen, schreiben, wieder exportieren. Attach-Versuche
   in der Zeit abweisen. Danach FineCut wie bisher.
5. Lange Jobs nicht abschneiden (USB-Bulk in Bloecken, vollstaendig).

Nicht raten, sondern am Code in `usb_bridge.py` und `forwarder.py` entlanggehen.

### Andere Plotter

`KNOWN_DEVICES` (FTDI, CP2102, Graphtec, …): wie Vevor ueber `forward_info.serial`,
falls socat laeuft.

---

## Belegt

`available: false` und `POST …/job` → `409`, wenn:

- USB/IP an einen Client angehaengt (typisch Windows + FineCut), oder
- macOS-Vendor-Bridge den Plotter exklusiv haelt, oder
- bereits ein Plot-Cut-Job laeuft.

Beispiel-`detail`:
`"Mimaki CG-60SR ist per USB/IP an PC-BUERO angehaengt. Bitte im Loki-Client trennen."`

Geraet **nicht** automatisch einem Client wegnehmen.

---

## Dashboard (Port 7576)

Bereich **Plot Cut**: Geraete aus `GET /api/plotcut/devices` (Name, id, kind, Status
bereit / belegt durch X / nicht geshared). Knopf **Testauftrag** sendet
`IN;PU0,0;PD400,0;PU0,0;` (10 mm) ueber `POST …/job`.

---

## Optional: Mitschnitt

Option, Bytes mitzuschneiden, die **Illustrator/FineCut** ueber die Raw-USB-Bridge
oder socat an den Plotter schickt (Datei pro Auftrag, im Dashboard ladbar). Damit
kann Plot Cut `VS`/`FS`/`!PT` an FineCut angleichen. Standard: aus.

---

## Abnahme

1. `curl http://<pi>:7576/api/plotcut/devices` listet Mimaki und Vevor mit **stabiler** `id`.
2. Vevor:  
   `curl --data-binary "IN;PU0,0;PD400,0;PU0,0;" -H "Content-Type: application/octet-stream" http://<pi>:7576/api/plotcut/devices/vevor/job`  
   → Plotter faehrt 10 mm, `{"ok":true,"bytes":23}`.
3. Mimaki analog mit `id=mimaki-cg60sr` (Geraet shared, **kein** USB/IP-Attach).
4. 5-MB-Job kommt vollstaendig an (Vevor socat / Mimaki Bulk).
5. USB/IP-Attach → `409`, `available: false`.
6. Zweiter paralleler Job am selben Geraet → `409`.
7. `id`s nach Pi-Neustart und Umstecken gleich.
8. Illustrator + FineCut (Windows USB/IP, macOS Bridge) unveraendert.
9. Bestehende `/api/devices*` und Ports unveraendert.
10. Tests (gemocktes Geraet) + README-Abschnitt „Plot Cut API“.

---

## Was du NICHT tun sollst

- Keinen HP-GL/MGL-Generator bauen, Bytes nicht veraendern.
- Keine neuen socat-Listener „daneben“, wenn `forward_info.serial` schon existiert.
- Mimaki nicht an `usbserial` binden.
- `attach-mode`, USB/IP, Raw-USB-Bridge und den Loki-Client nicht umbauen.
- Keine Auth erfinden, die Plot Cut nicht kennt. `LOKI_SECRET` nur wie bei den
  bestehenden Routen.
- Kein Release-Tag noetig, solange nur der Server eine API dazubekommt (kein
  Client-Rebuild). Wenn du Client/Build anfasst: laut Loki-Doku commit + push +
  Semver-Tag, sonst baut Actions kein Release.
