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

### K3c Filterleiste
- **[ENTSCHIEDEN]** „My favorites“ bleibt in der Werkzeugzeile (eigene Ansicht, kein Filter; ein Klick mehr wäre ein Rückschritt); neu bewerten mit K4.
- **[ENTSCHIEDEN]** Kein Verschieben von Genre/Laufzeit/Bewertung in „Filters“ bei Tablet-Breite (doppelte Ids); die Leiste bricht zweizeilig um.
- **[ENTSCHIEDEN]** Altersfreigabe-Adresse `ages=` (Menge) statt `age=` (bis N), alte Links werden umgedeutet, damit „nur 12“ und „bis 12“ nicht verwechselt werden.
- **[ENTSCHIEDEN]** Kein Zusatz bei verwechselbaren Dienstnamen (Namen sind schon ausgeschrieben).
- **[ENTSCHIEDEN]** Votes-Chips Any · 1k+ · 10k+ · 100k+ (aus der Vorlage) statt der alten 100+/1,000+/10,000+.
- **[ERLEDIGT]** K3c: Python 304, JS 46, Browser 24, ruff, mypy; Leiste bei 1440 px und Panels im Browser angesehen.

### A1 Abos-Mindestversion
- **[ENTSCHIEDEN]** „€ / film“ = Preis ÷ Filme nur auf diesem Dienst (wie im Abschnitt), nicht mehr ÷ alle Filme; Test angepasst.
- **[ENTSCHIEDEN]** Preis- und Datumsfelder speichern beim Verlassen (kein Save-Knopf); Summen werden im Browser nachgerechnet.
- **[ENTSCHIEDEN]** Eigene Seite `/settings/services` (Plan 9.12) statt eines Blocks auf der Abo-Seite; Untergruppen „Subscriptions“ und „More services“ aus `providers.provider_groups`.
- **[ENTSCHIEDEN]** Channels werden nur bei Empfehlungen („book“) zusammengefasst, nicht bei den eigenen Diensten (die wählt der Nutzer selbst).
- **[ENTSCHIEDEN]** Währung fest €, Zahlen- und Datumsformat nach Browser-Sprache; Einstellung für Währung erst später.
- **[OFFEN]** Datumsfeld: das Format des Kalender-Popups bleibt das des Browsers (nicht steuerbar).
- **[OFFEN]** Filter „Only on one of my services“ kennt Channels nicht als gleichen Katalog (A2 oder später).
- **[ERLEDIGT]** A1: Python 307, JS 46, Browser 25, ruff, mypy; Abo-Seite und My-services-Seite im Browser angesehen.

### K4 Details und Aktionen (Teil 1)
- **[ENTSCHIEDEN]** Schublade mit der vorhandenen Bootstrap-Dialog-Technik (nur CSS und zwei Knöpfe) statt eines neuen Bauteils: Fokusfalle, Escape und Fokus-Rückkehr bleiben erprobt.
- **[ENTSCHIEDEN]** „Watched“ und „Not now“ in eigener Tabelle `flags`, nicht in den Favoriten: ein Film muss nicht Favorit sein, um gesehen zu sein. Der alte Favoriten-Status „watched“ zählt weiter mit.
- **[ENTSCHIEDEN]** Der Server setzt das Ablaufdatum von „Not now“ (30 Tage); ein Backup darf nichts weiter als 30 Tage in die Zukunft verstecken.
- **[ENTSCHIEDEN]** Tab-Reihenfolge Titel, ♥, ⋯ (laut Plan); das ⋯ steht optisch links vom Herz.
- **[ENTSCHIEDEN]** Die Vergleichsleiste und der Neuaufbau des Fensterinhalts bleiben offen (großer Umbau mit wenig Gewinn gegenüber K5 und Abo-Seite).
- **[ENTSCHIEDEN]** Kein Abgleich mit dem Letterboxd-Tagebuch (neue Datenquelle, schon entschieden).
- **[FEHLER]** (nicht im Plan) Ein Klick auf `summary` in einer Karte (neues ⋯) öffnete zusätzlich das Detailfenster, weil die Klickregel der Karte `summary` nicht ausnahm; behoben.
- **[OFFEN]** `test_skip_link_and_three_stops_per_card` schlug in einem von drei vollen Läufen einmal fehl (einzeln und in den beiden anderen Läufen grün); vermutlich Zeitverhalten, nicht untersucht.
- **[ERLEDIGT]** K4 Teil 1: Python 311, JS 46, Browser 28, ruff, mypy; Schublade, Karten-Menü und Detailfenster am Handy im Browser angesehen.

### A2 Empfehlungen und Fristen
- **[ENTSCHIEDEN]** Empfehlungen stehen vor der Tabelle (laut Seitenskizze), damit die Kündigungsfrage ohne Scrollen beantwortet ist.
- **[ENTSCHIEDEN]** „Not interested“, „Dismiss“ und „Remind me tomorrow“ gelten nur im jeweiligen Browser (localStorage), nicht serverseitig; ein Gerätewechsel zeigt sie wieder. Serverseitig lohnt sich erst mit den Push-Nachrichten (K5).
- **[ENTSCHIEDEN]** „Open Y ↗“, „Plan it“, „Rent instead“, „Watch first“ entfallen (keine Daten dafür).
- **[ENTSCHIEDEN]** Fristen nur ab heute (vergangene Daten erscheinen nicht im Banner); die Status-Seite listet sie weiter.
- **[ERLEDIGT]** A2: Python 315, Browser-Test Banner; Seite im Browser angesehen.

### A3 Abdeckung und Zeit
- **[ENTSCHIEDEN]** Der vierte Balkenteil heißt „Not on your services“ (nicht „Not available“): er enthält auch Filme, die nur bei Diensten laufen, die der Nutzer nicht hat.
- **[ENTSCHIEDEN]** Wochenzeit als Einstellung in Settings → General (Standard 5 h) statt eines Feldes auf der Abo-Seite.
- **[ENTSCHIEDEN]** Poster-Reihe zeigt höchstens 24 Filme; „See all →“ öffnet die Watchlist mit `cost=rent`.
- **[ERLEDIGT]** A3: Python 318, im Browser angesehen.
- **[FEHLER]** (nach A3) Zwei Tastatur-Tests (drei Tab-Stopps, Fokus nach Favorit) schlugen im vollen Browser-Lauf zufällig fehl. Wahrscheinliche Ursache: `loadFavorites` holte Favoriten und Flags nacheinander, das spätere Neuzeichnen nahm dem Test den Fokus. Behoben durch gleichzeitiges Laden (`Promise.all`); danach 3 von 3 vollen Läufen grün (Ursache nicht anders bewiesen). Der frühere Eintrag [OFFEN] zu `three_stops` gilt damit als behoben.
