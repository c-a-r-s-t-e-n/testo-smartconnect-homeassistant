# Testo Smart Connect for Home Assistant

[![Validate](https://github.com/c-a-r-s-t-e-n/testo-smartconnect-homeassistant/actions/workflows/validate.yml/badge.svg)](https://github.com/c-a-r-s-t-e-n/testo-smartconnect-homeassistant/actions/workflows/validate.yml)
[![Version](https://img.shields.io/github/v/release/c-a-r-s-t-e-n/testo-smartconnect-homeassistant?include_prereleases)](https://github.com/c-a-r-s-t-e-n/testo-smartconnect-homeassistant/releases)
[![MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![HACS](https://img.shields.io/badge/HACS-custom%20integration-41BDF5)](https://hacs.xyz/)

**Community-Integration für eine bestehende Home-Assistant-Installation.** Testo-Logger über die offizielle **Smart Connect API** überwachen: Messwerte, Datenalter, Batterie, Funkqualität, Stromversorgung, Grenzwerte und Alarmereignisse. Kein VPN und kein lokaler Zugriff auf die Logger erforderlich.

**Version 0.1.0 – erste Community-Vorabversion.** Die API-Felder wurden anhand eines echten, separat gehaltenen Diagnoseexports geprüft. Automatisierte Tests verwenden ausschließlich synthetische Daten. Ein erfolgreicher CI-Lauf ersetzt keinen Funktionstest in der eigenen Home-Assistant-Installation. Dies ist keine offizielle Testo-Integration und kein Ersatz für Testos Alarmierung oder HACCP-Dokumentation.

## Installation über HACS

[![HACS-Repository öffnen](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=c-a-r-s-t-e-n&repository=testo-smartconnect-homeassistant&category=integration)

1. **HACS → Benutzerdefinierte Repositories** öffnen.
2. `https://github.com/c-a-r-s-t-e-n/testo-smartconnect-homeassistant` hinzufügen, Kategorie **Integration**.
3. **Testo Smart Connect** herunterladen. Gegebenenfalls Vorabversionen anzeigen lassen.
4. **Home Assistant vollständig neu starten.**
5. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Testo Smart Connect**.
6. API-Key eingeben und Region auswählen: `eu`, `am` oder `ap`. Für `www.eu.smartconnect.testo.com` ist es `eu`.
7. Die initiale Abfrage abwarten; sie kann mehrere Minuten dauern.

Dies ist eine **HACS Custom Integration**, kein Supervisor-App/Add-on und keine neue Home-Assistant-Installation. Sie ist über ein benutzerdefiniertes Repository installierbar; eine Aufnahme in den standardmäßigen HACS-Katalog ist nicht behauptet.

**Voraussetzungen:** Home Assistant **2025.3+**, HACS (bei HACS-Installation), aktives Testo Smart Connect API-Add-on, gültiger Key und ausgehendes HTTPS zu Testo sowie dessen S3-Ergebnisspeicher. EU ist anhand des Diagnoseexports verifiziert; AM/AP verwenden die dokumentierten Hosts, wurden aber nicht mit realen Konten getestet.

**Manuell:** Nur `custom_components/testo_smartconnect` nach `/config/custom_components/testo_smartconnect` kopieren, neu starten und über die Oberfläche einrichten. Kein YAML und kein zusätzliches Python-Paket erforderlich.

## Unterstützte Systeme

Für stationäre Logger, die in **Testo Smart Connect** registriert sind. Im geprüften Export waren die Modellcodes `0572 2031`, `0572 2032`, `0572 2033` und `0572 2035` enthalten. Der Code entdeckt Geräte und Kanäle dynamisch statt Modell- oder Seriennummern fest einzubauen.

Nicht unterstützt: die alte Saveris-2-API, separate Saveris Food/Data/Device-Management-APIs und Smart Probes/mobile Instrumente, deren Daten Smart Connect nicht bereitstellt. Polarfoxx ist nicht Bestandteil dieses Projekts.

## Welche Informationen werden genutzt?

Alle **sechs dokumentierten Smart-Connect-Datenbereiche** werden vollständig angefragt (kein `$select`, das optionale Felder abschneidet):

| Bereich | API-Endpunkt | Nutzung |
|---|---|---|
| Geräte/Kanäle | `/v3/devices/properties` | Geräte, Modelle, Firmware, Kanäle, Einheiten, Mess-/Sendeintervalle, Fähigkeiten |
| Gerätestatus | `/v4/devices/status` | Batterie, Funk, Stromversorgung, Kommunikations- und Statuszeit |
| Messwerte | `/v2/measurements` | Neuester Messwert pro Sensor **und Kanal**, Zeit, Einheit, Messart |
| Messstellen | `/v1/measuring-objects` | Kanalzuordnung, Alarmgrenzen, Verzögerung und Hysterese als Regelattribute |
| Standorte | `/v1/locations` | Messstellennamen über `back_reference` und `location_uuid` |
| Alarme | `/v3/alarms` | Ereignisse mit Status, Typ, Schwere, Bedingung, Wert und Zeiten |

Eine vollständige Feldliste und die Zuordnungsregeln stehen in [docs/API.md](docs/API.md). Für Gerätestatus wird **v4** verwendet: Dieser Endpunkt wurde mit realen Daten erfolgreich abgefragt. Einzelne ältere Beispiele in der Testo-Dokumentation nennen noch v3.

### Entitäten pro Messkanal

| Entität | Verhalten |
|---|---|
| Messwert | Temperatur, relative Feuchte oder andere von der API bereitgestellte Messart; richtige Einheit |
| Messzeit | Zeitpunkt der tatsächlichen Messung, nicht der letzten HA-Abfrage |
| Messwertalter | Minuten seit Messung |
| Daten veraltet | Problem-Sensor; auch bei noch nie empfangenen Messwerten aktiv |
| Ungültiger Messwert | Neuester Datensatz enthält keinen endlichen numerischen Wert; ohne Datensatz unbekannt |
| Unter-/Obergrenze | Eindeutig zugeordnete Testo-Grenzen; standardmäßig deaktivierte Diagnoseentitäten |
| Außerhalb konfigurierter Grenzen | Unmittelbarer Vergleich mit eindeutigen Grenzen, **ohne** Testo-Verzögerung/Hysterese |

Temperatur und Feuchte erhalten HA-Geräteklassen. Weitere Einheiten bleiben als generische numerische Sensoren erhalten. Der Export enthielt auch Feuchte (`%rF`) und Dichte (`g/m³`) als Kanaldefinitionen, aber nur aktuelle Temperaturmesswerte. Vorhandene Kanaldefinition bedeutet deshalb nicht, dass aktuelle Messwerte vorliegen.

**Keine doppelte Skalierung:** `measurement` ist bereits der physikalische Messwert. `channel_physical_unit_exponent` wird nicht nochmals angewendet. Leere Felder, NaN, Unendlich und ungültige Zahlen werden niemals zu Null umgedeutet.

### Entitäten pro Logger

Batteriestand, Funkqualität in Prozent (kein RSSI/dBm), Batterietemperatur falls geliefert, externe Stromversorgung (dreiwertig: an/aus/unbekannt), letzte und nächste Kommunikation, Statuszeit, Verbindungsart, Firmware, Messintervall, Kommunikationsintervall, beobachtete aktive Alarme im 24-Stunden-Fenster und letztes beobachtetes Alarmereignis.

Batterietemperatur, nächste Kommunikation und Statuszeit sind standardmäßig deaktiviert; bei Bedarf unter den Geräteentitäten aktivieren. Metadaten und Alarmdetails erscheinen zusätzlich als Attribute. Nicht gelieferte Batterie-/Stromfelder bleiben unbekannt.

**Entitäts-IDs vergibt Home Assistant.** Namen/IDs können durch Sprache, Umbenennung und vorhandene Geräte variieren. Beispiele sind keine festen IDs. Intern werden Konto, Gerät, Sensor-ID und Kanalnummer verwendet. Neue Geräte/Kanäle werden nach dem täglichen Metadatenabruf dynamisch ergänzt. Ein Entfernen/Wiederanlegen der Integration ist dafür nicht nötig.

## Aktualisierung, Kontingent und Aktualität

| Daten | Standardintervall |
|---|---:|
| Messwerte | 10 Minuten, ein Sammelauftrag für alle Logger |
| Gerätestatus | 30 Minuten |
| Alarmereignisse | 30 Minuten, jeweils letzte 24 Stunden |
| Geräte, Messstellen und Standorte | Jeweils 24 Stunden |

Das ergibt in einem 31-Tage-Monat etwa **7.533 POST-Abfragen**, zuzüglich Einrichtung, Wiederanläufen und Fehlerwiederholungen. Nur POST zählt laut Testo; die GET-Ergebnisabfragen nicht. Das Kontingent beträgt derzeit **10.000 POSTs pro Monat und Konto**, gemeinsam mit anderen Clients.

- Persistenter **lokaler** Zähler mit UTC-Monatswechsel und Schutzgrenze 9.500; er kennt fremde Clients und die einmalige Einrichtungsprüfung nicht.
- Zähler wird vor dem POST gespeichert, auch fehlgeschlagene Versuche zählen vorsichtshalber lokal mit.
- Bei erkannter Testo-Kontingentsperre keine weiteren neuen Aufträge bis zum Monatswechsel.
- Bereits laufende Aufträge werden bei Polling-Zeitüberschreitung im laufenden Prozess fortgesetzt, statt sofort neue zu starten. Nach HA-Neustart können neue Aufträge entstehen.
- Ein API-Key ist kein Live-Stream. Logger-Sendeintervall und Cloud-Verarbeitung verursachen zusätzliche Verzögerung.
- Messwertabfragen überlappen um eine Stunde für verspätete Daten; nach längeren Ausfällen werden maximal die letzten 24 Stunden nachgeladen. Kein rückwirkender Import alter Messungen in den HA-Recorder.
- Ergebnisdateien werden vollständig gelesen; Grenzen: 100 Dateien, 20 MiB je Datei, 100.000 Zeilen je Auftrag. Ein Überschreiten erzeugt einen Fehler statt stiller Teilergebnisse.

Unter **Konfigurieren** sind Messwertintervall (10–60 Minuten) und Altersgrenze (15–1.440 Minuten, Standard 60) anpassbar. Längere Intervalle reduzieren die Abfragen. Veraltete numerische Messsensoren werden **nicht verfügbar**; Messzeit und Altersdiagnose bleiben sichtbar. Zeitdiagnosen werden im Aktualisierungstakt neu berechnet.

## Alarme richtig verstehen

Die Alarm-API liefert zeitbezogene Ereignisse. Die Integration gruppiert nach `source_alarm_event_uuid` (ersatzweise `uuid`) und nimmt den jüngsten Statuswechsel. Eine spätere `Ok`-Meldung löst das zugehörige beobachtete Ereignis auf.

**Der Zähler ist ausdrücklich kein vollständiger globaler Alarmstatus:** Ältere, weiterhin aktive Alarme außerhalb des 24-Stunden-Fensters können fehlen. Ein Zählerstand 0 bedeutet nur „keine aktiven Ereignisse in diesem abgefragten Fenster“. Der Zeitpunkt des letzten Abrufs wird angezeigt. Testos eigene Alarmierung bleibt maßgeblich.

Der separate Grenzwert-Problemsensor vergleicht aktuelle Messwerte unmittelbar. Verzögerungen und Hysterese sind als Attribute einsehbar, werden aber nicht als Testo-Zustandsautomat nachgebildet. Mehrdeutige Zuordnungen oder mehrere gleichartige Grenzregeln erzeugen keine erfundene skalare Grenze. Eine historische Konfiguration wird nicht rückwirkend angewendet.

## Beispiel: Benachrichtigung bei veralteten Messdaten

IDs unter **Entwicklerwerkzeuge → Zustände** kopieren und beide Platzhalter ersetzen. Der Push-Dienst setzt die Home-Assistant-Companion-App voraus.

```yaml
alias: "Testo: Messdaten veraltet"
triggers:
  - trigger: state
    entity_id: binary_sensor.REPLACE_WITH_DATA_STALE
    to: "on"
    for: "00:10:00"
actions:
  - action: notify.mobile_app_REPLACE_WITH_PHONE
    data:
      title: "Testo: keine aktuellen Messdaten"
      message: "Die Messstelle liefert keine ausreichend aktuellen Werte."
mode: single
```

Beachte: Ein bereits beim HA-Start aktiver Problemsensor und ein nicht verfügbarer Sensor erfordern gegebenenfalls zusätzliche Start-/Verfügbarkeitsautomationen. Ein HA-Neustart setzt laufende `for`-Zeiten zurück.

## Beispiel: Dashboard

```yaml
type: vertical-stack
cards:
  - type: entities
    title: Kühlung
    entities:
      - sensor.REPLACE_WITH_TEMPERATURE
      - sensor.REPLACE_WITH_SAMPLE_TIME
      - binary_sensor.REPLACE_WITH_DATA_STALE
      - sensor.REPLACE_WITH_BATTERY
  - type: history-graph
    hours_to_show: 24
    entities:
      - sensor.REPLACE_WITH_TEMPERATURE
```

## API-Key erneuern, aktualisieren und entfernen

**Key:** In Smart Connect einen neuen Key erstellen. Bei Authentifizierungsfehlern bietet Home Assistant die erneute Anmeldung an; denselben Account und dieselbe Region verwenden. Keys haben eine begrenzte Laufzeit. Der Austausch verändert keine Geräte-Unique-IDs.

**Update:** Über HACS aktualisieren, Home Assistant neu starten, Versionshinweise lesen. Nur ein Neuladen reicht nach Python-Codeänderungen nicht.

**Entfernen:** Zuerst die Integration unter Geräte & Dienste entfernen, dann in HACS deinstallieren und HA neu starten. Der integrationsinterne Cache wird beim Entfernen des Konfigurationseintrags gelöscht. Recorder-Historie, Dashboards und Backups separat verwalten. Den API-Key bei Testo widerrufen, wenn er nicht mehr gebraucht wird.

## Fehlerdiagnose

- **401:** Key abgelaufen/ungültig; erneut authentifizieren.
- **403:** Rechte oder Monatskontingent prüfen. Eine Berechtigungssperre ist nicht automatisch ein falscher Key.
- **429:** Fünf Minuten Abkühlzeit; keine engen Wiederholungsschleifen.
- **Result still pending:** Auftrag wird beim nächsten Abruf im laufenden Prozess fortgesetzt.
- **Unsupported result storage host:** Testo nutzt einen anderen Host als die dokumentierten `tds-…s3…amazonaws.com`-Hosts; nicht blind freischalten. Nur den Hostnamen ohne signierte URL melden.
- **Messwert nicht verfügbar:** Messzeit, Altersgrenze, Kanalanschluss und API-Fehler prüfen. Unbenutzte Eingänge können dauerhaft ohne Werte bleiben.
- **Messstellenname fehlt:** Zuordnung ist nicht eindeutig oder `back_reference` verweist auf Equipment statt eine direkt auflösbare Location. Geräte-/Sensorname und Kanalnummer bleiben als Fallback.
- **Standorthierarchie:** Im geprüften Location-Schema fehlt eine Parent-UUID. Die Integration erfindet deshalb keine Raumhierarchie und legt keine HA-Bereiche automatisch an.
- **Teilweise API-Störung:** Betroffene Mess-/Statusentitäten werden nicht verfügbar; erfolgreiche Datenbereiche bleiben nutzbar. Diagnose herunterladen über den Integrationseintrag.

[Strukturelle Diagnosen](custom_components/testo_smartconnect/diagnostics.py) enthalten nur Feldnamen, Zeilenzahlen, Zeiten, sichere Fehlertexte und lokale Kontingentzähler. Keine Rohdaten, Seriennummern, Kunden-IDs, Gerätenamen, Schlüssel oder signierten URLs.

## Datenschutz, Sicherheit und Grenzen

Der API-Key liegt ausschließlich in Home Assistants privatem Konfigurationseintrag. Lokal gespeicherte Mess-/Gerätecaches enthalten private Daten und können Bestandteil von HA-Backups sein. HTTPS, feste Testo-Regionen, getrennte Authentifizierung für API und Downloads, keine Weiterleitungen mit Credentials, begrenzte Downloads. Keine Gerätebefehle, Alarmquittierungen oder Änderungen von Testo-Einstellungen.

POST erzeugt ausschließlich lesende Exportaufträge. Die Integration lädt keine Daten an andere Dienste hoch. Niemals echte Diagnose-ZIPs, API-Keys oder signierte Download-URLs in öffentliche Issues/PRs stellen. Das Repository enthält keine privaten Exporte und keine einmaligen Diagnoseskripte.

## Entwicklung und Qualität

Python 3.13, Home Assistant 2025.3.4 als Testbasis:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
ruff check .
ruff format --check .
pytest -q
```

GitHub Actions führt **Ruff, Formatprüfung, Tests, hassfest und HACS-Validierung** aus. Tests prüfen unter anderem Byte-Decodierung, mehrteilige Downloads, Secret-Trennung, asynchrone Abfragen, Quoten, Kanalzuordnung, ungültige Werte, Alarmauflösung und HA-Entitäten. Der tatsächliche Laufstatus steht im Actions-Tab; das Vorhandensein einer Workflow-Datei allein bedeutet keinen erfolgreichen Check.

[Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [API-Details](docs/API.md) · [Issues](https://github.com/c-a-r-s-t-e-n/testo-smartconnect-homeassistant/issues)

Offizielle Grundlagen: [Testo FAQ](https://developers.testo.dev/smart-connect-api/faq/), [API-Referenz](https://developers.testo.dev/smart-connect-api/api_reference/), [Home-Assistant-Entwicklung](https://developers.home-assistant.io/).

## Lizenz und Marken

[MIT](LICENSE). Copyright (c) 2026 c-a-r-s-t-e-n und Mitwirkende. Unabhängiges Community-Projekt, nicht von Testo oder Home Assistant herausgegeben, unterstützt oder zertifiziert. Marken gehören ihren jeweiligen Inhabern. Keine Garantie für Verfügbarkeit, Messgenauigkeit oder Alarmzustellung.
