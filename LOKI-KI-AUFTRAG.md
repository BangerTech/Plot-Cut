# Auftrag fuer die KI im Repo BangerTech/Loki-PrintServer

Diesen ganzen Text der KI geben, die am Loki-PrintServer arbeitet.

---

## Ziel

Fuege dem Loki-Server eine kleine **Plot-Cut-API** hinzu. "Plot Cut" ist ein Programm auf
dem Windows-PC, das in VectorCraft gezeichnete Schneidepfade in fertige Plotterbefehle
(MGL-IIc fuer Mimaki, HP-GL fuer andere Plotter) umwandelt. Plot Cut schickt diese
**fertigen Rohbytes** per HTTP an Loki. Loki soll sie nur noch **unveraendert** an den
richtigen Plotter schreiben.

Loki erzeugt also **keine** Plotterbefehle und veraendert die Bytes nicht. Es ist reiner
Ueberbringer.

Angeschlossene Plotter (beide funktionieren heute schon ueber Loki aus Adobe Illustrator):

- **Mimaki CG-60SR** (Sprache MGL-IIc, 610 mm Schnittbreite)
- **Vevor Schneideplotter** (Sprache HP-GL)

Die bestehenden Wege (USB/IP-Passthrough, socat, CUPS, Loki-Client) muessen genau so
weiter funktionieren wie bisher. Illustrator + FineCut darf nicht kaputtgehen.

## API-Vertrag (genau so umsetzen, Plot Cut ist bereits darauf programmiert)

Basis: der bestehende FastAPI-Server, Port **7576**, Praefix **`/api/plotcut`**.

### `GET /api/plotcut/devices`

Liste aller Geraete, an die Plot Cut Auftraege schicken kann.

```json
{
  "devices": [
    {
      "id": "mimaki-cg60sr",
      "name": "Mimaki CG-60SR",
      "kind": "serial",
      "available": true,
      "attached_to": null
    },
    {
      "id": "vevor",
      "name": "Vevor",
      "kind": "usblp",
      "available": false,
      "attached_to": "PC-BUERO"
    }
  ]
}
```

- `id`: stabil, URL-tauglich (Kleinbuchstaben, Ziffern, `-`). Darf sich nach Neustart
  oder Umstecken nicht aendern.
- `name`: Anzeigename.
- `kind`: wie Loki das Geraet anspricht, z. B. `serial`, `usblp`, `usb-vendor`, `socat`.
- `available`: `false`, wenn der Server gerade nicht schreiben kann (siehe "Belegt").
- `attached_to`: Name/IP des Clients, an den das Geraet per USB/IP angehaengt ist, sonst `null`.

### `POST /api/plotcut/devices/{id}/job`

- Request-Body: die rohen Plotterbytes, `Content-Type: application/octet-stream`.
  Beispiel-Body: `IN;SP1;VS30;FS100;PU0,1200;PD0,0,1200,0,1200,1200,0,1200;PU0,0;`
- Die Bytes **unveraendert und vollstaendig** an das Geraet schreiben, dann antworten.
- Erfolg: `200` mit `{"ok": true, "bytes": <Anzahl geschriebener Bytes>}`
- Fehler immer als FastAPI-`HTTPException` mit verstaendlichem deutschem `detail`, denn Plot
  Cut zeigt `detail` dem Benutzer direkt an:
  - `404` unbekannte `id`
  - `409` Geraet belegt (z. B. per USB/IP an einen PC angehaengt oder anderer Auftrag laeuft)
  - `503` Geraet nicht angeschlossen / Geraetedatei fehlt
  - `500` Schreibfehler (mit Ursache im `detail`)
- Maximale Body-Groesse mindestens 50 MB.
- Pro Geraet nur ein Auftrag gleichzeitig (Lock pro Geraet). Ein zweiter gleichzeitiger
  Auftrag bekommt `409`.

## Wie die Bytes zum Geraet kommen

Zuerst pro Plotter auf dem Pi pruefen und im Code/README festhalten, wie er sich meldet:
`lsusb`, `lsusb -v -d <vid>:<pid>` und `ls -l /dev/serial/by-id/ /dev/usb/`.

Dann je nach Art schreiben:

1. **Geraet wird bereits von socat bereitgestellt** (serial-over-TCP): den Auftrag ueber
   denselben Weg liefern, also lokal mit dem socat-TCP-Port verbinden und die Bytes senden.
   Die `tty` **nicht** parallel selbst oeffnen, sonst gibt es Konflikte mit socat.
2. **USB-Seriell** (CH340, FTDI, PL2303, CDC-ACM) ohne socat: ueber den stabilen Pfad
   `/dev/serial/by-id/...` schreiben (nie `ttyUSB0`, das kann bei zwei Geraeten tauschen),
   mit den Parametern aus der Geraetekonfiguration (Baud, 8N1, Flusskontrolle).
3. **USB-Druckerklasse** (`usblp`, `/dev/usb/lpX`): Bytes direkt in die Geraetedatei schreiben.
4. **Herstellerspezifisches USB** (eigene Vendor-Klasse, kein tty/lp): mit `pyusb` den ersten
   Bulk-OUT-Endpunkt suchen und die Bytes in Bloecken schreiben. Den Kernel-Treiber nur
   voruebergehend loesen und danach wieder anhaengen.

Fuer den **Mimaki CG-60SR an seriellen Wegen** gilt: Hardware-Flusskontrolle **RTS/CTS**
einschalten (socat: `crtscts=1`, pyserial: `rtscts=True`). Sonst werden lange Auftraege
abgeschnitten. Der Vevor laeuft ueblicherweise ohne Handshake.

### Belegt / USB/IP

Ist ein Geraet gerade per USB/IP an einen Windows-PC angehaengt (z. B. weil dort FineCut
laeuft), kann der Server nicht darauf schreiben. Dann:

- In `GET /devices` `available: false` und `attached_to` setzen.
- `POST .../job` antwortet `409` mit z. B.
  `"Mimaki CG-60SR ist per USB/IP an PC-BUERO angehaengt. Bitte im Loki-Client trennen."`
- Das Geraet **nicht** automatisch einem Client wegnehmen.

Ist das Geraet fuer USB/IP exportiert (an `usbip-host` gebunden), aber an **keinen** Client
angehaengt, darf der Server es fuer die Dauer des Auftrags vom `usbip-host` loesen, schreiben
und danach wieder exportieren. Waehrend dieser Zeit muss ein Attach-Versuch eines Clients
sauber abgewiesen werden. Danach muss Illustrator/FineCut ueber Loki weiter funktionieren.

## Konfiguration

Eine Geraetekonfiguration (YAML oder JSON, im bestehenden Konfig-Stil von Loki), zum Beispiel:

```yaml
plotcut_devices:
  - id: mimaki-cg60sr
    name: Mimaki CG-60SR
    match: { vendor: "0x....", product: "0x...." }   # aus lsusb eintragen
    path: /dev/serial/by-id/usb-....                  # oder /dev/usb/lp0, oder leer bei usb-vendor
    socat_port: 7580                                  # falls von socat bedient, sonst weglassen
    baud: 9600
    flow: rtscts
  - id: vevor
    name: Vevor
    match: { vendor: "0x1a86", product: "0x7523" }    # typisch CH340, pruefen!
    path: /dev/serial/by-id/usb-1a86-....
    baud: 9600
    flow: none
```

Geraete ohne Eintrag, die Loki als Plotter erkennt, duerfen mit einer automatisch erzeugten
`id` gelistet werden.

## Dashboard (Port 7576)

Im Web-Dashboard einen Bereich "Plot Cut" mit allen Geraeten aus `GET /devices`: Name, `id`,
Art, Status (bereit / belegt durch X / nicht angeschlossen) und ein Knopf "Testauftrag",
der `IN;PU0,0;PD400,0;PU0,0;` sendet (der Plotter faehrt 10 mm).

## Optional, aber sehr hilfreich: Mitschnitt

Fuer serielle/socat-Wege eine Option, die Bytes mitzuschneiden, die **Illustrator/FineCut**
ueber Loki an den Plotter sendet (Datei pro Auftrag mit Zeitstempel, im Dashboard
herunterladbar). Damit kann Plot Cut seine Ausgabe exakt an FineCut angleichen
(Werkzeug-, Druck- und Offset-Befehle des CG-60SR). Standardmaessig aus.

## Abnahmekriterien

1. `curl http://<pi>:7576/api/plotcut/devices` listet beide Plotter mit stabiler `id`.
2. `curl --data-binary "IN;PU0,0;PD400,0;PU0,0;" -H "Content-Type: application/octet-stream" http://<pi>:7576/api/plotcut/devices/mimaki-cg60sr/job`
   laesst den Mimaki 10 mm fahren und antwortet `{"ok": true, "bytes": 23}`.
3. Dasselbe mit `vevor`: der Vevor faehrt 10 mm.
4. Ein 5-MB-Auftrag an den Mimaki wird vollstaendig geschnitten (RTS/CTS greift).
5. Ist ein Plotter per USB/IP an einen PC angehaengt, kommt `409` mit verstaendlichem
   `detail`, und `available` ist `false`.
6. Zwei gleichzeitige Auftraege an dasselbe Geraet: der zweite bekommt `409`.
7. Nach Pi-Neustart und Umstecken bleiben die `id`s gleich.
8. Illustrator + FineCut funktionieren ueber Loki unveraendert weiter.
9. Tests fuer die neuen Endpunkte (mit gemocktem Geraet) und README-Abschnitt "Plot Cut API".

## Was du NICHT tun sollst

- Keinen HP-GL- oder MGL-Generator bauen und die Bytes nicht veraendern.
- Bestehende Loki-Endpunkte, Ports und das USB/IP-Verhalten nicht umbauen.
- Keine Authentifizierung einfuehren, die Plot Cut nicht kennt. Falls du eine fuer noetig
  haeltst, schlage sie vor und frag erst nach.
