# Entscheidungen und Fortschritt der selbstständigen Arbeit (ab 2026-11-18)

Auftrag: Plan von oben nach unten abarbeiten, nach jedem Schritt prüfen, nach jeder Etappe committen, Fragen vermeiden und selbst abwägen. Jede eigene Entscheidung steht hier mit **[ENTSCHIEDEN]**, jede nicht erledigte oder nicht prüfbare Sache mit **[OFFEN]**, jeder gefundene Fehler außerhalb des Plans mit **[FEHLER]**. Der Plan selbst steht in `PLAN.md`.

## Legende
- **[ENTSCHIEDEN]** ich habe abgewogen und entschieden, ohne zu fragen
- **[OFFEN]** nicht fertig oder nicht überprüfbar (Grund dabei)
- **[FEHLER]** Fehler gefunden, der nicht im Plan stand (steht auch im Plan)
- **[ERLEDIGT]** fertig und geprüft (mit welchen Tests)

## Protokoll

### 17a Docker-Grundlage
- **[ENTSCHIEDEN]** `/health` bleibt der Name (er existierte schon, Dockerfile und Compose nutzen ihn) statt `/healthz`; er prüft jetzt Datenbank und Zeitplan-Thread (503 sonst).
- **[ENTSCHIEDEN]** Benutzerwechsel mit `gosu` in einem Start-Skript (`docker-entrypoint.sh`) statt `USER` im Dockerfile, weil Unraid die Rechte per `PUID`/`PGID` zur Laufzeit setzt.
- **[ENTSCHIEDEN]** Tägliche Sicherung läuft im vorhandenen Zeitplan-Thread (`watchlist_app/backups.py`), nicht als eigener Dienst; eine halb geschriebene Datei zählt nie (erst `.tmp`, dann umbenennen).
- **[ENTSCHIEDEN]** `.gitattributes` erzwingt LF für `*.sh` und `Dockerfile` (sonst bricht das Skript unter Linux).
- **[ENTSCHIEDEN]** Kein Veröffentlichen nach ghcr.io (braucht Push und Zugangsdaten von dir); die Unraid-Vorlage verweist auf ein lokal gebautes Image.
- **[ENTSCHIEDEN]** `.env.example` neu (Compose liest `.env`), `.env` bleibt ignoriert.
- **[FEHLER]** (nicht im Plan) gunicorn 27 stürzte mit „Control server error: Permission denied '/home/app'“ ab, sobald der Container nicht als root lief; behoben mit `--no-control-socket` in `CMD`.
- **[ERLEDIGT]** 17a: Python 304 Tests, ruff, mypy; echtes Docker: Image gebaut, healthy, UID 1001, Backup-Ordner, Neustart (Docker Desktop habe ich dafür gestartet).
- **[OFFEN]** 17a: Lauf auf Unraid und die GitHub-Prüfung `docker.yml` sind ungeprüft (kein Push von mir).
