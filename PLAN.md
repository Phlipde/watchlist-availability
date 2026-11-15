# Plan: Fehler beheben, Struktur verbessern, Funktionen ergänzen, dann Docker

Stand: 2026-11-15. Jede Etappe ist ein eigener Commit mit eigenen Tests; die App bleibt nach jedem Schritt lauffähig. Docker für Unraid kommt bewusst zuletzt. Struktur-Umbauten sind mit „(Struktur)“ markiert und stehen jeweils vor den Schritten, die darauf aufbauen.

## Teil A: Fehler und Struktur

### Etappe 0: Vorbereitung
- [x] Arbeitszweig anlegen (Zweig `perf/faster-scan`).
- [x] `.watchlist_latest.json` in `.gitignore` eintragen und aus dem Git-Index nehmen.
- [x] (Struktur) Linter und Formatierer einrichten (`ruff`, Einstellungen in `pyproject.toml`) und automatischen Testlauf bei GitHub anlegen (`.github/workflows/tests.yml`).
- [x] (Struktur) Start-Skripte `run.sh`, `run_web.sh` und `run_web.ps1` nutzen das Python aus `.venv`, sonst das System-Python.
- [x] (Struktur) Doppeltes `clean_year` (in `tmdb.py` und `results.py`) zusammenführen.
- Prüfung: `ruff check`, `ruff format --check` und `pytest` (134 bestanden) laufen sauber.

### Etappe 1: Kleine Anzeige-Fehler
- [x] Share-Icon: `ti-link-45deg` in `templates/partials/result-tools.html` durch `ti-link` ersetzen.
- [x] Trailer-Link: die Variable `links` aus `static/js/app.js` (Zeile 30) in die Karte einfügen.
- [x] „Decades“: `release_date` in `watchlist_app/tmdb.py` und `web/serialization.py` mitliefern.
- [x] „No longer available“: fest gesetztes `data-changes="removed"` in `static/js/rendering.js` entfernen.
- [x] Länderwechsel während eines Scans: laufenden Scan in `web/routes.py` abbrechen statt wiederverbinden; das Frontend fragt nur noch den aktuellen Scan ab.
- Prüfung: im Browser geprüft; neue Tests in `tests/test_web.py` für `release_date` und Länderwechsel (139 bestanden).

### Etappe 2: Frontend-Umbau und Filter-Logik
- [x] (Struktur) `static/js/app.js` aufteilen, ohne Framework: ein Zustand (Filme, Favoriten, Filter), eine Filterfunktion über die Daten, eine Funktion, die daraus die Karten zeichnet. Filter lesen nicht mehr die `data-`-Attribute der Karten aus. (Zustand in `state.js`, Filter in `filtering.js` mit Tests in `tests/js/`, Zeichnen in `rendering.js`.) Noch offen für später: Statistik, Anbieter-Leiste und Ereignisse stecken weiter in `app.js`.
- [x] Angebotsart-Filter und Badges nur aus den ausgewählten Anbietern berechnen. Eine Angebotsart gehört zu ihrem Bereich (Free: free/ads, Paid: flatrate/rent).
- [x] Nicht verfügbare Filme aus „visible films“ herausnehmen und nur bei passendem Filter zeigen. „visible films“ zählt jeden Film nur einmal, auch wenn er in Free und Paid steht.
- [x] Anbieter mit 0 Filmen nur ausblenden, Auswahl behalten (`static/js/filters.js`).
- Reihenfolge: erst aufteilen ohne Verhaltensänderung und im Browser gegenprüfen, dann die drei Fehler beheben.
- Prüfung: „Rent“ lieferte vorher 158 Treffer; danach nur Filme, die bei einem ausgewählten Anbieter leihbar sind. Alle übrigen Filter liefern dieselben Zahlen wie vor dem Umbau.
- Ergebnis: 35 Filter-Fälle vor und nach dem Umbau verglichen; Kartenzahl und Reihenfolge je Bereich sind gleich, abweichend nur die gewollten Änderungen. „Rent“ mit den Standard-Anbietern jetzt 0 (vorher 151), mit „Apple TV Store“ 394 = erwartet.

### Etappe 3: Fehlerbehandlung bei TMDB
- [x] Netzwerkfehler und Rate-Limit als eigene Ausnahme melden statt als „nicht gefunden“ (erledigt für den Web-Scan; der CLI-Weg nutzt noch die alten Funktionen).
- [x] Bis zu drei Versuche mit wachsender Pause, `Retry-After` beachten (Web-Scan).
- [x] Beendete Scan-Jobs nach einer Stunde aus dem Speicher entfernen (beim nächsten Scan-Start).
- Prüfung: Tests mit simulierten 429- und Timeout-Antworten; „Failed lookups“ füllt sich (`tests/test_web.py`, 143 bestanden).
- [x] Der CLI-Weg nutzt seit Etappe 4 dieselbe Abfrage wie der Web-Scan und listet fehlgeschlagene Filme am Ende auf.

### Etappe 4: Struktur-Umbau im Backend
- [x] (Struktur) Fassade `watchlist_availability.py` auflösen: Tests direkt gegen die Module in `watchlist_app/` schreiben, das Austauschen von Modul-Variablen zur Laufzeit entfernen, die Datei auf den CLI-Start kürzen. Die alten Einzel-Funktionen für TMDB (`get_tmdb_id`, `get_streaming_platforms`, `get_tmdb_details`) und das ungenutzte `test_unknown_providers` sind entfallen.
- [x] (Struktur) `tests/test_watchlist.py` in eine Testdatei pro Modul aufteilen; Tests für `web/` ergänzen (`test_models`, `test_tmdb`, `test_letterboxd`, `test_providers`, `test_lookup`, `test_results`, `test_store`, `test_rendering`, `test_cli`, `test_web`).
- [x] (Struktur) Ein Datenspeicher `.watchlist.sqlite3` (`watchlist_app/store.py`) mit Tabellen `film_ids`, `films`, `offers` (je Film und Land), `scans`, `favorites`, `settings`. Alte Favoriten, letzter Stand und Film-Cache werden beim ersten Start einmalig übernommen (`legacy_import.py`); die alten Dateien bleiben unangetastet. Der 24-Stunden-Ergebnis-Cache ist jetzt eine Abfrage auf die Tabelle `scans`.
- [x] (Struktur) Festes Film-Objekt (`watchlist_app/models.py`) mit der TMDB-ID als Schlüssel statt `Titel|Jahr`; gleiche Feldnamen in Backend und Web. Favoriten mit altem Schlüssel werden nach jedem Scan auf die TMDB-ID umgestellt.
- [x] (Struktur) `pandas` durch das Standardmodul `csv` ersetzen (kleineres Docker-Image).
- Prüfung (2026-11-15): 157 Python- und 9 JS-Tests bestehen ohne Fassade. Mit kopierten echten Daten: Übernahme der alten Dateien klappt; neuer Scan liefert dieselben 430 Filme mit identischen Angeboten und Details und dieselben 26 nicht verfügbaren; zwei Test-Favoriten wurden mit Status und Notiz auf die TMDB-ID umgestellt. Datenbank 5,7 MB.

### Etappe 5: Scan-Geschwindigkeit
- [x] Cache pro Film: TMDB-ID dauerhaft, Details und Anbieter aller Länder mit Ablaufzeit (24 h). Seit Etappe 4 im gemeinsamen Datenspeicher.
- [x] Sechs Filme parallel abfragen (einstellbar über `WATCHLIST_SCAN_WORKERS`), Verbindungen wiederverwenden, Details und Anbieter in einer TMDB-Abfrage.
- [ ] Kein Scan bei jedem Seitenaufruf; nur per Knopf oder wenn der Stand zu alt ist.
- Gemessen am 2026-11-14 mit 456 Filmen: erster Scan 83 s statt rund 14 Minuten; Auffrischen aller Anbieter-Daten 5 s; Länderwechsel 6 s; alles aus dem Cache unter 1 s (jeweils zuzüglich rund 6 s für den Abruf der Watchlist).

### Etappe 6: Änderungen dauerhaft speichern (Historie)
- [x] Nach jedem Scan mit dem vorherigen Stand derselben Watchlist vergleichen und „neu auf …“ / „nicht mehr auf …“ mit Datum speichern (Tabelle `changes`, `watchlist_app/history.py`). Filme, die neu auf die Watchlist kommen oder sie verlassen, zählen nicht als Änderung.
- [x] Frontend liest die gespeicherten Änderungen; `showChangeSummary` entfällt. Angezeigt werden die Änderungen der letzten 14 Tage für die ausgewählten Anbieter: als Badge auf der Karte, im Filter und als Liste unter „Scan changes“. Der Filter „No longer available“ zeigt auch Filme, die bei keinem ausgewählten Anbieter mehr laufen.
- Prüfung (2026-11-15): Hinweise bleiben nach dem Neuladen erhalten. Im Browser mit zwei herbeigeführten Änderungen geprüft („New on Netflix“, „No longer on Netflix“); 167 Python- und 10 JS-Tests bestehen.

## Teil B: Funktionen

### Etappe 7: Grundlage für den Server-Betrieb
- [x] (Struktur) Scan-Dienst `watchlist_app/scan_service.py`: `perform_scan` nutzen Knopf, Zeitplan und CLI gleich; `ScanService` hält den Fortschritt, jeder Lauf steht in der Tabelle `jobs`. Ein Scan, der bei einem Neustart lief, wird als „interrupted“ markiert und neu gestartet. `web/scans.py` und `web/serialization.py` sind entfallen.
- [x] (Struktur) Konfiguration an einer Stelle: `watchlist_app/settings.py` (gespeicherte Werte vor `.env` und `platforms.toml`), Länder in `config.COUNTRIES`, Anbieter-Gruppen, „meist kostenlos“ und Leih-Shops in `providers.py`. Der TMDB-Schlüssel bleibt in der Umgebung und wird nie gespeichert.
- [x] Einstellungsseite `/settings`: Letterboxd-Benutzername, Land, eigene Abos je Land, Scan-Intervall.
- [x] „Meine Abos“ als eigene Ansicht, getrennt von Leih-Shops: Knöpfe „My subscriptions“ und „Rental shops“ in der Seitenleiste; Leih-Shops als eigene Gruppe.
- [x] Automatischer Scan nach Zeitplan (`scheduler.py`, alle 24/48 h oder wöchentlich; 6 und 12 h sind mit Etappe 8b entfallen; nach einem Fehlschlag frühestens nach einer Stunde erneut). Hintergrund-Scans werden von einem Seitenaufruf für ein anderes Land nicht abgebrochen.
- [x] Status-Seite `/status`: letzter und nächster Scan, letzte Läufe mit Auslöser, Dauer, Fehlern und TMDB-Abfragen, Größe der Daten.
- [x] Sicherung: Download und Wiederherstellung als eine JSON-Datei (Einstellungen, Favoriten, Änderungs-Historie, letzter Scan je Land); doppeltes Einspielen fügt nichts doppelt hinzu.
- Prüfung (2026-11-15): 203 Python- und 10 JS-Tests. Im Browser: Einstellungen speichern und Ablehnen ungültiger Werte, Abos erscheinen auf der Hauptseite, Neustart während eines Scans, echter FR-Scan mit 456 TMDB-Abfragen in 19,5 s auf der Status-Seite, Sicherung herunterladen und Favoriten wiederherstellen.
- Baut auf Etappe 4 bis 6 auf.

### Etappe 8: Zuordnung und Anbieter-Liste
- [x] (Struktur) Browser-Tests mit Playwright (`tests/browser/`, `pytest -m browser`): Scan, Filter, Favorit, Neuladen, Einstellungen, Titel-Korrektur. Die App läuft dabei mit leerer Datenbank und festen Antworten statt Letterboxd und TMDB. Laufen bei GitHub mit. Werkzeuge stehen jetzt in `requirements-dev.txt` (damit ist auch der Punkt aus Etappe 17 erledigt).
- [x] (Struktur) Typprüfung mit `mypy` (Einstellungen in `pyproject.toml`) im automatischen Testlauf; 22 Fundstellen behoben.
- [x] Genauere Zuordnung: TMDB-ID direkt von der Letterboxd-Filmseite lesen, Titelsuche nur als Rückfall (454 von 456 Filmen kamen im Test über Letterboxd). Die Titelsuche nimmt jetzt den Treffer mit gleichem Titel und Jahr statt einfach den ersten.
- [x] Titel-Abgleich prüfen: Seite `/matches` (`watchlist_app/matches.py`) mit Treffern aus der Titelsuche, nicht gefundenen Filmen und Filmen, deren Jahr um mehr als ein Jahr abweicht. Korrektur über TMDB-Suche oder TMDB-Link, „Looks right“ zum Bestätigen, Rückgängig möglich. Korrekturen bleiben dauerhaft (Quelle „manual“), stehen in der Sicherung, und der nächste Scan verwendet den alten Stand nicht wieder.
- [x] Anbieter-Liste automatisch pflegen: der Scan lädt einmal pro Woche alle Anbieter des Landes von TMDB (Tabelle `provider_catalog`, eine Abfrage) und behält alle Angebote eines Films. Neue Anbieter erscheinen in Seitenleiste und Einstellungen und können als Abo gespeichert werden. Leerzeichen in TMDB-Namen werden entfernt; „Joyn“ (kostenlos) und „Joyn Plus“ sind jetzt getrennt. Der erste Scan nach der Umstellung meldet dadurch keine falschen „neu auf …“.
- [x] Nebenbei gefunden (durch die Browser-Tests): nach dem Tippen in ein Filterfeld ging der erste Klick auf eine Karte oder einen Stern verloren, weil die Karten beim Verlassen des Feldes neu gezeichnet wurden. Behoben.
- Prüfung (2026-11-15): 236 Python-Tests, 3 Browser-Tests, 10 JS-Tests, `ruff` und `mypy` sauber. Mit einer Kopie der echten Daten: 196 Anbieter für DE geladen, 430 verfügbar / 26 nicht (wie vorher), 0 falsche Änderungen; 3 Zuordnungen zu prüfen, darunter „Chernobyl (2019)“ (eine Serie), das die Titelsuche einem anderen Film zugeordnet hatte. Korrektur gespeichert, neuer Scan zeigt den gewählten Film, danach rückgängig gemacht.
- Baut auf dem Film-Cache aus Etappe 5 und der TMDB-ID als Schlüssel aus Etappe 4 auf. Früh eingeplant, weil alle späteren Auswertungen von richtigen Treffern abhängen.

### Etappe 8a: Sicherheitslücke aus dem Security-Review schließen (vor Etappe 9)
Befund (2026-11-15, mittel): Eine fremde Webseite kann unbemerkt eine präparierte Sicherung an die App schicken (`POST /api/backup` nimmt Datei-Uploads von jeder Seite an). Darin steht Schadcode im Feld „Jahr“ eines Films. Vier Stellen im Frontend setzen Jahr, Laufzeit und Bewertung ohne Escaping ins HTML, also läuft der Code beim nächsten Öffnen der App und hat vollen Zugriff auf die API. Normale Scans sind nicht betroffen, nur wiederhergestellte Daten.
- [x] Frontend: `year`, `runtime` und `rating` werden an allen vier Stellen nur als Zahl ausgegeben (`numberText` in `static/js/ui.js`). Alle übrigen `innerHTML`-Stellen durchgesehen: Texte laufen durch `escapeHtml`.
- [x] Server: neue `watchlist_app/validation.py`. Beim Einspielen werden Filme, Favoriten, Änderungen und Korrekturen mit festen Typen neu gebaut (Jahr und Laufzeit als Ganzzahl, Bewertung 0–10, Bild-Pfade, TMDB- und YouTube-Links nur im bekannten Format, nur erlaubte Angebotsarten). Unbrauchbare Einträge werden übersprungen und auf der Einstellungsseite gezählt. Zeitpunkte in der Zukunft werden abgelehnt. Einstellungen laufen über `AppSettings.restore` mit denselben Prüfungen wie die Einstellungsseite. Auch `POST /api/favorites` und Notizen werden so geprüft.
- [x] Server: schreibende Anfragen fremder Seiten bekommen 403 (`Sec-Fetch-Site`, sonst `Origin` gegen den eigenen Host). Hinter einem Reverse-Proxy zählen auch `X-Forwarded-Host` und `WATCHLIST_TRUSTED_HOSTS`. Anfragen ohne diese Header (Kommandozeile, `curl`) bleiben erlaubt.
- [x] Tests: präparierte Sicherung wird bereinigt (`test_store`), Einstellungen aus der Sicherung werden geprüft, fremde Seiten bekommen 403, eigene Seite, Proxy und Werkzeuge nicht (`test_web`), `numberText` und Karten mit Schadcode (`tests/js/rendering.test.mjs`). Zwei Browser-Tests spielen den Angriff echt durch: Sicherung mit Schadcode über die Einstellungsseite (kein Skript läuft, die Karte zeigt „Year unknown“) und eine fremde Webseite, die eine Sicherung schickt (wird abgewiesen, nichts gespeichert).
- Prüfung (2026-11-15): 241 Python-Tests, 5 Browser-Tests, 12 JS-Tests, `ruff` und `mypy` sauber. Echte Sicherung der Test-Kopie in eine leere Datenbank eingespielt: 1368 Filme ohne Abweichung, nichts übersprungen. Speichern von Favoriten und Einstellungen auf der eigenen Seite geht weiter. Security-Review erneut gelaufen: Befund vollständig behoben, keine neuen Funde. Hinweis daraus (bewusst offen, App ohne Login): DNS-Rebinding ließe sich nur mit einer festen Liste erlaubter Host-Namen ausschließen.
- Klein und eigenständig; vor dem nächsten Commit bzw. vor Docker (Etappe 17) erledigen, weil die App im Container im ganzen Heimnetz erreichbar ist.

### Etappe 8b: Befunde aus den Ponytail-Reviews (vor Etappe 9)
Review der offenen Änderungen und Audit des ganzen Projekts (2026-11-15), zehn Befunde, alle behoben.
- [x] Fehlgeschlagener Scan: Ein Scan mit fehlgeschlagenen Abfragen wird nicht mehr 24 Stunden wiederverwendet. Konnte kein einziger Film geprüft werden (TMDB nicht erreichbar, falscher Schlüssel), wird nichts gespeichert; die Seite behält den letzten guten Stand und der Lauf endet als Fehler.
- [x] Letterboxd-Filmseite nicht ladbar (Timeout, 429, 5xx): Der Film zählt als fehlgeschlagen und wird beim nächsten Scan erneut versucht, statt dauerhaft einen Treffer aus der Titelsuche zu speichern. Andere Antworten (z. B. 403, 404) fallen weiter auf die Titelsuche zurück.
- [x] Zeitplan: 6 und 12 Stunden entfernt, weil ein Scan und seine Angebote 24 Stunden wiederverwendet werden. Ein gespeicherter Wert unter 24 zählt als 24.
- [x] Falscher Letterboxd-Benutzername: Die Meldung von Letterboxd wird gezeigt statt „keine CSV gefunden“, wenn es keine CSV gibt.
- [x] Fortschritts-Abfrage im Browser: Nach einem Netzwerkfehler wird weiter abgefragt, statt bei „Scanning“ hängen zu bleiben.
- [x] Uploads: höchstens 50 MB (`MAX_CONTENT_LENGTH`), größere Dateien bekommen 413 mit Fehlermeldung.
- [x] Debug-Modus startet keinen zweiten Prozess mehr (`use_reloader=False`).
- [x] Watchlist mit mehr als 2800 Filmen: Fehler statt stillem Abschneiden.
- [x] Kein Fortschrittsbalken mehr im Server-Log bei Web-Scans.
- [x] Entfernt: `static/js/api.js` (reichte nur an `fetch` weiter), doppeltes `escape` in `scans.js`, doppelter `except`-Zweig in `results.py`, ungenutztes `pytest-mock`, `sw.js` samt Route (speicherte nur die leere Seite; ein früher installierter Worker wird abgemeldet).
- Prüfung (2026-11-15): 249 Python-Tests, 5 Browser-Tests, 12 JS-Tests, `ruff` und `mypy` sauber. Acht neue Tests; die Fortschritts-Abfrage hat keinen eigenen Test. Nicht gegen die echten Seiten von TMDB und Letterboxd geprüft.

### Etappe 9: Kosten und Abos
- [ ] Abo-Rechner: Monatspreise eintragen, Kosten pro verfügbarem Watchlist-Film je Dienst.
- [ ] Rotations-Plan: welchen Dienst für einen Monat buchen, welchen kündigen.
- [ ] Liste „nur leihbar“ für Filme ohne Abo-Angebot.
- [ ] „Was verliere ich, wenn ich X kündige?“: Filme, die nur bei diesem einen Dienst laufen. Grundlage für den Rotations-Plan.
- [ ] Kündigungs-Erinnerung: Ende des Probemonats oder Kündigungsfrist je Abo eintragen; die Status-Seite zeigt sie an, die Zustellung kommt mit Etappe 16.
- Baut auf „Meine Abos“ aus Etappe 7 auf.

### Etappe 10: Entscheidungshilfe
- [ ] Zufallsknopf („Würfeln“): ein Film aus der aktuellen Filteransicht. Erster, einfacher Schritt zum Abend-Modus.
- [ ] Abend-Modus: Zeit und Genre angeben, drei Vorschläge aus den eigenen Abos.
- [ ] „Läuft bald aus“ / „kürzlich entfernt“ aus der Historie (TMDB liefert kein Ablaufdatum).
- [ ] Gewichtete Sortierung: Bewertung pro Laufzeit, am längsten auf der Watchlist, Anzahl eigener Abos.
- [ ] Filmreihen (TMDB „Collections“) zusammen anzeigen.
- [ ] Ähnliche Filme: zu einem Watchlist-Film zeigen, was Vergleichbares auf den eigenen Abos läuft (TMDB „similar“ / „recommendations“).

### Etappe 11: Startdatum (eigene Etappe)
- [ ] Für noch nicht erschienene Watchlist-Filme Kino- und Heimkino-Start anzeigen (TMDB „release_dates“ je Land).
- [ ] Eigene Ansicht „Demnächst“ mit Sortierung nach Datum.
- [ ] Meldung, sobald ein solcher Film streambar wird (nutzt die Historie; Zustellung kommt mit Etappe 16).
- [ ] Altersfreigabe (FSK je Land) anzeigen und als Filter, etwa für Filmabende mit Kindern. Kommt aus derselben Abfrage „release_dates“.
- Baut auf Zeitplan (Etappe 7) und Historie (Etappe 6) auf.

### Etappe 12: Mehr Daten pro Film
- [ ] Letterboxd-Durchschnittsbewertung: steht auf der Filmseite, die der Scan für die TMDB-ID ohnehin lädt; keine zusätzliche Abfrage. Als Filter und Sortierung.
- [ ] Reihenfolge der Watchlist speichern: die Letterboxd-Seite ist nach „zuletzt hinzugefügt“ sortiert, die Position ersetzt das Aufnahmedatum auch ohne CSV-Export.
- [ ] Letterboxd-Daten: Datum der Aufnahme in die Watchlist (nur im CSV-Export), eigene Bewertung.
- [ ] Originalsprache und Herkunftsland als Filter (steckt schon in der TMDB-Antwort).
- [ ] Verfügbarkeit in anderen Ländern („in DE nicht, aber in GB auf Netflix“); der TMDB-Aufruf liefert alle Länder ohne zusätzliche Abfragen.
- [ ] Anbieter-Logos statt Textnamen (TMDB liefert die Bilder).
- [ ] Qualität und Sprache: nur mit zusätzlicher Datenquelle möglich; aufwendig, zuletzt in dieser Etappe und optional.

### Etappe 13: Übersicht und Auswertung
- [ ] Watchlist-Statistik über Zeit: Zugänge, weggeschaute Filme, Abdeckung je Dienst (braucht gespeicherte Scan-Stände aus Etappe 6).
- [ ] „Staubfänger“: Filme, die lange auf der Liste stehen und seit Monaten verfügbar sind (braucht das Watchlist-Datum oder die Reihenfolge aus Etappe 12).
- [ ] Laufzeit-Summe der verfügbaren Filme je Dienst.
- [ ] Eigene Schlagworte pro Film und Filter danach.

### Etappe 14: Bedienung
- [ ] Listenansicht (kompakte, sortierbare Tabelle) neben der Kartenansicht.
- [ ] Gespeicherte Filter als Knöpfe.
- [ ] Filter auf dem Handy einklappbar.
- [ ] Favoriten-Status mit dem Letterboxd-Tagebuch abgleichen; gesehene Filme ausblenden.
- [ ] Helles Design und Farbwahl.
- [ ] Tastatur-Bedienung: `/` Suche, Pfeiltasten durch die Karten, `f` Favorit.
- [ ] „Nicht interessiert“: Film in der App ausblenden, ohne die Letterboxd-Watchlist zu ändern; eigener Filter, um ihn wieder zu zeigen.
- [ ] Erster Start: ohne Benutzernamen und ohne Watchlist-Datei öffnet die App die Einstellungsseite statt eines leeren Rasters.
- [ ] Rückgängig nach dem Entfernen eines Favoriten (kurze Meldung mit Knopf).

### Etappe 15: Gemeinsam schauen
- [ ] Abstimmung: Filme auswählen, Link im Heimnetz teilen, jeder stimmt am Handy ab.
- [ ] Gäste-Abos: Abos von Freunden oder Familie als zweites Profil („bei Lisa läuft der auf Disney+“).
- Baut auf „Meine Abos“ aus Etappe 7 auf. Die Abstimmung ist ohne Anmeldung gedacht, also nur fürs Heimnetz.

### Etappe 16: Ausgabe und Benachrichtigung
- [ ] Kalender-Feed (ICS) oder RSS mit „neu verfügbar“.
- [ ] Wöchentliche Zusammenfassung per Mail oder ntfy.
- [ ] Kleine API mit Dokumentation für Home Assistant oder Dashboards.
- [ ] Startseiten-Kachel („heute neu / Tipp des Tages“) zum Einbetten in Homepage oder Homarr.
- Baut auf Zeitplan und Historie auf.

## Teil C: Docker für Unraid (zuletzt)

### Etappe 17
Betrieb auf dem Server (vor dem Image):
- [ ] Automatische tägliche Sicherung in den Datenordner (`backups/`), die letzten 7 bleiben erhalten.
- [ ] Gesundheits-Endpunkt `/healthz` (Datenbank erreichbar, Zeitplan läuft) für den Docker-Healthcheck und die Unraid-Anzeige.
- [ ] Knopf „TMDB-Schlüssel testen“ auf der Einstellungsseite.
- [ ] Datenbank aufräumen: Filmdaten von Filmen, die seit Monaten nicht mehr auf der Watchlist stehen, löschen und die Datei verkleinern (`VACUUM`).
- [ ] Letzte Fehlermeldungen auf der Status-Seite, ohne in die Logs schauen zu müssen.

Docker:
- [ ] `.env` in `.dockerignore` aufnehmen (API-Key nicht ins Image).
- [ ] `TMDB_API_KEY`, `LETTERBOXD_USERNAME`, `COUNTRY` als Umgebungsvariablen in `docker-compose.yml`.
- [ ] `platforms.toml` aus `/data` lesen (entfällt, falls Etappe 7 die Datei ersetzt hat).
- [ ] Container als Nicht-root-Benutzer mit PUID/PGID.
- [x] `pytest` in `requirements-dev.txt` auslagern (mit Etappe 8 erledigt).
- Prüfung: Image bauen und starten (auf diesem PC nicht möglich, Docker fehlt).

## Nicht im Plan (frühere Ideen)

Direkt-Link zum Anbieter, mehrere Letterboxd-Profile, weitere Letterboxd-Listen, Regie und Besetzung, Serien, Abgleich mit Plex/Jellyfin, deutsche Oberfläche, Push-Nachrichten über Discord/Telegram, installierbare App im LAN (HTTPS, Icons), Zugriffsschutz, umgekehrte Suche (Vorschläge außerhalb der Watchlist), Filmsuche ohne Watchlist.
