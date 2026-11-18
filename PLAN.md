# Plan: Fehler beheben, Struktur verbessern, Funktionen ergänzen, dann Docker

Stand: 2026-11-16. Jede Etappe ist ein eigener Commit mit eigenen Tests; die App bleibt nach jedem Schritt lauffähig. Docker für Unraid kommt seit 2026-11-18 früh (Etappe 17a, siehe Reihenfolge), der Rest von Etappe 17 zuletzt. Struktur-Umbauten sind mit „(Struktur)“ markiert und stehen jeweils vor den Schritten, die darauf aufbauen.

Reihenfolge ab 2026-11-18: 17a Docker-Grundlage → K3c Filterleiste → A1 Abos-Mindestversion → K4 Details und Aktionen → A2 bis A4 → K5 Benachrichtigungen → A5, A6 → K6 Feinschliff (PWA) → 17b Betrieb. Rest von Etappe 12 und Etappe 13 bis 16 laufen, soweit sie nicht in K4 bis K6 aufgegangen sind, danach. Offene Punkte aus der Design-Runde stehen in Etappe 9k.

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
- [x] Kein Scan bei jedem Seitenaufruf; nur per Knopf oder wenn der Stand zu alt ist. `GET /api/latest` meldet veraltete Daten; das Frontend startet beim Laden nur bei fehlendem/veraltetem Stand.
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
- [x] Abo-Rechner: neue Seite `/costs` (`watchlist_app/costs.py`). Monatspreis je eigenem Abo eintragen; die Seite zeigt Watchlist-Filme je Dienst, Kosten pro Film und die Summe. Gespeichert je Land (Einstellung `subscription_costs:<Land>`), steht damit auch in der Sicherung.
- [x] Rotations-Plan: „Kündigen“ nennt bezahlte Abos, bei denen kein Film verloren geht, sonst das mit den wenigsten eigenen Filmen. Kostenlose Dienste und Abos mit Preis 0 werden nie vorgeschlagen. „Für einen Monat buchen“ nennt den Dienst ohne Abo mit den meisten Watchlist-Filmen, die keines der eigenen Abos hat, dazu vier weitere.
- [x] Liste „nur leihbar“: Filme ohne kostenloses oder Abo-Angebot bei irgendeinem Anbieter, aber mit Leih-Angebot.
- [x] „Was verliere ich, wenn ich X kündige?“: Spalte „Only here“, also Filme, die kein anderes eigenes Abo hat und kein Anbieter kostenlos zeigt.
- [x] Kündigungs-Erinnerung: Datum je Abo auf der Kosten-Seite; die Status-Seite listet alle Länder, das nächste Datum zuerst, mit „in X Tagen“ bzw. „vor X Tagen“. Die Zustellung kommt mit Etappe 16.
- Prüfung (2026-11-15): 266 Python-Tests (9 neue in `tests/test_costs.py`, 4 in `tests/test_web.py`), 5 Browser-Tests, 12 JS-Tests, `ruff` und `mypy` sauber (nebenbei ein alter mypy-Fund in `tests/helpers.py` behoben). Mit der Kopie der echten Daten (DE): 11 Abos, „nur leihbar“ 44 Filme, Vorschlag „buchen“ Disney+ mit 94 Filmen. Preis für Netflix gespeichert (13,99 → 0,19 pro Film bei 74 Filmen), Erinnerung erscheint auf der Status-Seite. Beim ersten Versuch wurden kostenlose Dienste (Arte, ZDF …) zum Kündigen vorgeschlagen; behoben.
- Bewusst einfach: keine Währung (die Zahl steht für die Währung des Landes); Preise nur für eigene Abos, daher steht beim Buchen-Vorschlag kein Preis; der Rotations-Plan schaut nur einen Monat voraus.
- Baut auf „Meine Abos“ aus Etappe 7 auf.

### Etappe 9a: Knöpfe angleichen und „Free services“ (vor Etappe 10)
- [x] Trailer und TMDB gleich aussehen lassen: Auf der Karte (`static/js/rendering.js`) ist TMDB ein Textlink, Trailer ein `btn btn-link`-Knopf mit anderer Schrift und Farbe. Beide bekommen eine gemeinsame Klasse und eine CSS-Regel; Trailer bleibt ein Knopf, weil er den Player öffnet.
- [x] Trailer gleich verhalten lassen: Im Detailfenster (`static/js/app.js`) öffnet Trailer YouTube in einem neuen Tab, auf der Karte den eingebetteten Player. Künftig überall der eingebettete Player; Reihenfolge überall „TMDB · Trailer“.
- [x] Label „Free“ nach Daten statt nach fester Liste: „Free“, wenn im letzten Scan des Landes mindestens die Hälfte seiner Watchlist-Filme als `free` oder `ads` angeboten wird. Ohne Filme im Scan entscheidet weiter die Liste. „Amazon Prime Video with Ads“ bleibt aus dem Daten-Label, wenn der Scan keine ausreichende kostenlose Abdeckung zeigt.
  - Abgleich mit der Kopie der echten Daten (2026-11-15): ohne Label, aber nur kostenlos: BBC iPlayer, Channel 4, ITVX, M6+, JustWatch TV Free. Mit Label, aber meist bezahlt: Molotov (1 von 60). Mit Label, aber kein kostenloses Angebot: Amazon Prime Video with Ads, Alleskino. Gemischt und zu Recht ohne Label: Rakuten TV (3/341), TF1+ (8/70). Neu dazu käme auch Crunchyroll (1 Film, mit Werbung).
- [x] Knopf „Free services“ neben „Rental shops“ in der Seitenleiste: wählt genau die Anbieter mit Label. Label und Knopf nutzen dieselbe Liste.
- [x] Vorher klären: Lädt ein Länderwechsel die Seite neu? Nein, er startet nur einen Scan. Das Label bleibt auf dem Server; jede Scan-Antwort (`/api/latest` und der fertige Scan) bringt die Liste ihres Landes mit (`free_services`), Label und Knopf werden danach im Browser umgestellt.
- Prüfung: JS-Test für die gemeinsame Klasse der Links, Tests für die 50-%-Regel und den Rückfall auf die Liste, Browser-Test für den Knopf; Bildschirmfoto von Karte und Detailfenster.

### Etappe 9b: Popularität und weitere Filter (vor Etappe 10)
Alles kommt aus der TMDB-Antwort, die der Scan für jeden Film ohnehin lädt (`watchlist_app/tmdb.py`, `_details_from_movie`); es gibt keine zusätzliche Abfrage. Neue Felder erscheinen, wenn die gespeicherten Film-Details ablaufen (spätestens nach 24 Stunden).
- [x] Popularität speichern: `popularity` (wie viel gerade über den Film geredet wird, ändert sich täglich) und `vote_count` (Zahl der Bewertungen auf TMDB, fast fest) ins Film-Objekt (`models.py`) und in die Prüfung der Sicherung (`validation.py`).
- [x] Zwei Sortierungen: „Sort: trending“ (`popularity`) und „Sort: most votes“ (`vote_count`), in `static/js/filtering.js` neben title, newest, oldest und rating.
- [x] Filter „Mindestens N Stimmen“ (any, 100+, 1000+, 10000+). Er behebt, dass „Sort: rating“ heute einen Film mit 9,0 aus 3 Stimmen vor einen mit 8,4 aus 7000 stellt.
- [x] Regie und Besetzung: `credits` an dieselbe TMDB-Abfrage anhängen (`append_to_response`), nur Regie und die ersten fünf Namen der Besetzung speichern. Die Suche findet Filme auch über diese Namen, das Detailfenster zeigt sie an.
- [x] Stichworte: `keywords` an dieselbe Abfrage anhängen (z. B. „heist“, „based on novel“) und als Filter anbieten, wie den Genre-Filter.
- [x] Filter „Only on one of my services“: zeigt die Filme, die bei einer Kündigung verloren gingen. Nutzt dieselbe Regel wie die Kosten-Seite (`watchlist_app/costs.py`), damit beide Stellen dasselbe zählen.
- Schon an anderer Stelle geplant und hier bewusst nicht doppelt: Letterboxd-Bewertung, Originalsprache und Herkunftsland (Etappe 12), Altersfreigabe (Etappe 11), gewichtete Sortierung und Filmreihen (Etappe 10), eigene Schlagworte (Etappe 13), „Nicht interessiert“ und gespeicherte Filter (Etappe 14). Die Popularität bei Letterboxd („Watched by … members“) bräuchte eine eigene Abfrage pro Film und gehört, wenn überhaupt, zu Etappe 12.
- Prüfung: Tests für das Übernehmen der neuen Felder aus einer TMDB-Antwort und für die Sicherung, JS-Tests für beide Sortierungen und die Filter, Browser-Test für einen Filter. Größe der Datenbank vor und nach einem Scan vergleichen, wegen Besetzung und Stichworten.

### Etappe 9c: Befunde aus Ponytail-Audit und -Review (vor dem Commit von 9a/9b/10)
Audit des ganzen Projekts und Review der offenen Änderungen (2026-11-15). Doppelte Funde sind zusammengefasst. Schon behoben, beim Nachstellen gefunden:
- [x] „Free“-Label: Die 50-%-Regel zählte gegen die ganze Watchlist statt gegen die Filme des Dienstes, dadurch hatte kein Dienst das Label und „Free services“ wählte nichts aus. Jetzt je Dienst; Dienste ohne Filme im Scan entscheidet die Liste (`providers.mostly_free_from_scan`, Test in `tests/test_providers.py`).
- [x] Gespeicherte Ergebnisse ohne Scan: Der Fortschrittsbereich blieb auf „Preparing… 0 %“ mit „Cancel scan“; „Retry scan“ war versteckt. Jetzt „Showing saved results.“ mit „Retry scan“.

Muss behoben werden (zuerst):
- [x] 9b-Felder kommen nie an: `make_film` (`watchlist_app/results.py`) übernimmt `popularity`, `vote_count`, `director`, `cast`, `keywords` nicht aus den TMDB-Details. Fünf Zeilen, dazu ein Test, der eine TMDB-Antwort durch `make_film` schickt. Die Daten erscheinen, sobald die gespeicherten Film-Details ablaufen (24 h).
- [x] Stand gilt ohne Zeitplan nie als veraltet (`web/routes.py`, `latest_result`): `settings.scan_interval_hours > 0 and` streichen, veraltet ab 24 Stunden. Der Zeitplan steuert nur noch Hintergrund-Scans. Test in `tests/test_web.py` mit Zeitplan aus.
- [x] Trailer im Detailfenster öffnet sich verdeckt dahinter (Ton läuft, Bild nicht): vor `openTrailer` das Detailfenster schließen (`static/js/app.js`). Schritt im Browser-Test ergänzen.
- [x] Testlauf bei GitHub: `ruff format .` und die zwei zu langen Zeilen in `tmdb.py` umbrechen. In `.github/workflows/validate.yml` den Python-Job löschen (ruft `pytest` auf, ohne es zu installieren; doppelt zu `tests.yml`), nur den Docker-Build behalten.
- [x] `.env` in `.dockerignore` (sonst landet der TMDB-Schlüssel im Image; aus Etappe 17 vorgezogen, weil Dockerfile und Docker-Build schon existieren).

Sollte behoben werden:
- [x] Fehler protokollieren: `logging.exception(...)` im letzten `except` von `ScanService.run` (`scan_service.py`) und im Zeitplan (`scheduler.py`, heute `pass`). Die Meldung auf der Seite bleibt.
- [x] Alte Scans pro Land aufräumen statt über alle Länder (`Store.save_scan`, `MAX_SCANS`): sonst löscht ein täglicher DE-Scan nach 30 Tagen den einzigen GB-Scan, und ein aus der Sicherung eingespielter alter Scan verschwindet sofort. Test in `tests/test_store.py`.
- [x] Kosten-Seite nutzt dieselbe „Free“-Regel wie Seitenleiste und Knopf: in `costs.overview` `mostly_free_from_scan(films, [])` statt `MOSTLY_FREE` (Beispiel: BBC iPlayer als Abo in GB wird heute zum Kündigen vorgeschlagen). Test in `tests/test_costs.py`.
- [x] Fortschritts-Abfrage schickt nur neue Filme: `GET /api/scan/<id>?from=<Anzahl>` gibt `results[from:]` und `unavailable[from:]` zurück; heute bis zu 430 KB pro Abfrage, rund 40 MB pro Scan. Test in `tests/test_web.py`.
- [x] „Only on one of my services“ nur einmal: der Server setzt das Feld `only_on_my_services` je Film in `with_changes` (Abos des Landes), `onlyOnMyServices` in `static/js/filtering.js` entfällt. JS-Test anpassen.
- [x] Tests für neue Logik in `app.js`: Auswahl im Abend-Modus als reine Funktion nach `filtering.js` (JS-Test für Laufzeit, Genre, eigene Abos, drei Treffer); Umschalten der „Free“-Labels beim Länderwechsel als Schritt im Browser-Test.

Optional:
- [x] Doppelte Prüfung `and _watchable(film, name)` in `costs.overview` löschen.
- [ ] Einmal-Umstellungen entfernen, wenn keine ältere Installation mehr existiert: `legacy_import.py` mit `config.legacy_paths` und Tests, `MATCHING_CHANGED`/`compare_only` in `scan_service.py` (rund 150 Zeilen).
- [ ] Nebenbei gefunden: Der Stichwort-Filter hat mit echten Daten 3676 Einträge und ist so kaum bedienbar. Besser nur Stichworte mit mindestens zwei oder drei Filmen anbieten oder ein Suchfeld mit Vorschlagsliste (`datalist`) nehmen.
- Abweichungen bei der Umsetzung (2026-11-15): Die Fortschritts-Abfrage kürzt nur `results`; die Liste der nicht verfügbaren Filme ist klein (rund 15 KB) und kommt weiter ganz. Ihr Test steht in `tests/test_scan_service.py`. „Only on one of my services“ setzt der Server nicht in `with_changes` (die kennt die Abos nicht), sondern in `/api/latest` und in der Scan-Abfrage (`costs.mark_only_on_my_services`). Die Auswahl im Abend-Modus ist jetzt `eveningSuggestions` in `static/js/filtering.js`. Die Einmal-Umstellungen bleiben vorerst, weil nicht feststeht, dass es keine ältere Installation mehr gibt.
- Bewusst gelassen: `index()` berechnet die „Free“-Liste selbst, obwohl `/api/latest` sie kurz danach liefert; so springen die Labels beim Laden nicht.
- Prüfung: `ruff check`, `ruff format --check`, `mypy`, alle Python-, JS- und Browser-Tests. Mit der Kopie der echten Daten: ein Scan nach Ablauf der Film-Details zeigt Stimmen, Stichworte und Regie; Sortierung „most votes“ und Stichwort-Filter liefern Treffer; Trailer aus dem Detailfenster ist sichtbar; Seite startet bei einem Stand älter als 24 Stunden selbst einen Scan.
- Ergebnis (2026-11-15): 278 Python-, 16 JS- und 8 Browser-Tests (neu: Trailer aus dem Detailfenster, „Free“-Labels beim Länderwechsel), `ruff check`, `ruff format --check` und `mypy` sauber. Mit einer Kopie der echten Daten, Film-Details als abgelaufen markiert und Scan zwei Tage alt: Die Seite startet den Scan selbst (36 s); 430 von 430 Filmen haben Stimmen und Regie, 428 Stichworte. „Only on one of my services“ zeigt 136 Filme, „10,000+ votes“ 57. Die Fortschritts-Abfragen übertrugen 2 MB in 68 Abfragen statt rund 20 MB. Datenbank 6,3 MB statt 5,4 MB (Besetzung und Stichworte). Docker-Build nicht geprüft (Docker fehlt auf diesem PC).

### Etappe 9d: Verfügbarkeit im Detailfenster nach Angebotsart, mit Logos
Heute listet das Detailfenster unter „Availability“ jeden Anbieter einzeln, mit der Angebotsart als Badge daneben (`offerBadgesForProviders` in `static/js/rendering.js`), in der Reihenfolge der TMDB-Daten. Kostenlose Angebote gehen so zwischen den Leih-Shops unter (Beispiel: Pluto TV „With ads“ zwischen neun „Rent“-Einträgen).
- [x] Nach Angebotsart gruppieren, in fester Reihenfolge: „Free“, „With ads“, „Subscription“, „Rent“ (Reihenfolge wie `OFFER_KINDS` in `models.py`). Je Gruppe eine Überschrift, darunter die Anbieter alphabetisch. Ein Anbieter mit mehreren Arten steht in jeder passenden Gruppe; leere Gruppen fallen weg.
- [x] Logos: Die Pfade liegen schon in der Tabelle `provider_catalog` (`logo_path`, 197 von 197 Anbietern), also ohne zusätzliche TMDB-Abfrage. Der Server gibt sie als `providerLogos` ({Anzeigename: Pfad}, über `providers.display_name`) in `client_config` mit. Das Bild kommt in kleiner Größe von TMDB (`https://image.tmdb.org/t/p/w92`), neben dem Namen, mit leerem `alt`-Text, weil der Name direkt daneben steht (Screenreader lesen ihn sonst doppelt). Ohne Logo steht nur der Name.
- [x] Sicherheit: Logo-Pfade nur im bekannten Format ausgeben (wie `poster_path`, `_IMAGE_PATH_RE` in `validation.py`) und escapen.
- Kleinere Variante: nur gruppieren, ohne Logos; die Logos blieben dann in Etappe 12.
- Kommt aus Etappe 12 („Anbieter-Logos statt Textnamen“) vorgezogen, aber nur für das Detailfenster. Seitenleiste und Karten bleiben dort.
- Prüfung: JS-Test für Gruppen und Reihenfolge (ein Anbieter mit „flatrate“ und „rent“ steht in beiden Gruppen; ohne Logo nur Text), Test, dass `providerLogos` auf der Seite ankommt, Bildschirmfoto des Detailfensters mit echten Daten.
- Ergebnis (2026-11-15): `availabilityByOffer` in `static/js/rendering.js` ersetzt `offerBadgesForProviders`; Logos kommen über `validation.image_path` als `providerLogos` und `logoBaseUrl` in `client_config`, ungültige Pfade fallen weg. 279 Python-, 17 JS- und 8 Browser-Tests, `ruff` und `mypy` sauber. Mit der Kopie der echten Daten: 197 Logos; „Good Time“ zeigt Free (filmfriend), Subscription (MUBI, MUBI Amazon Channel, Superfresh Amazon Channel) und Rent (acht Shops), alle mit Logo. Asset-Version auf `20261115-7` erhöht, damit Browser das neue CSS und JS laden. Danach auf Wunsch die Farben der Angebotsarten von den Gruppen entfernt (Gruppen tragen nur noch `data-offer`, die Badges auf den Karten bleiben farbig; Version `20261115-8`).

### Etappe 9e: Eine Seite „My subscriptions“ statt Abo-Auswahl in den Einstellungen plus Kosten-Seite
Heute ist ein Abo auf zwei Seiten verteilt: Auf `/settings` wählt man die Dienste je Land (Abschnitt „My subscriptions“), auf `/costs` trägt man für dieselben Dienste Preis und Erinnerung ein und sieht die Auswertung. Wer ein Abo hinzufügt, muss danach die Seite wechseln, um den Preis einzutragen. Dazu kommt: Auf `/settings` hängt die Abo-Liste am Land-Feld der App. Wer die GB-Abos bearbeitet und speichert, stellt damit auch das Land der App auf GB um.
- [x] Neue Seite `/subscriptions` („My subscriptions“) mit drei Teilen, in dieser Reihenfolge:
  1. Eigene Abos als Tabelle: Dienst (mit Logo aus Etappe 9d), Preis pro Monat, Erinnerung, Watchlist-Filme, pro Film, „Only here“. Darunter die Summe.
  2. „Add or remove services“: die heutige Auswahl aus den Einstellungen (Gruppen, aufklappbar). Ein neu angehakter Dienst erscheint nach dem Speichern sofort als Zeile in der Tabelle, ein abgewählter verschwindet samt Preis.
  3. Auswertung wie heute auf `/costs`: Rotation („Cancel“, „Book for a month“) und „Only to rent“.
- [x] Ein Knopf „Save“ speichert Auswahl, Preise und Erinnerungen zusammen, über das vorhandene `PUT /api/settings` (`subscriptions` und `costs`; `AppSettings.update` prüft schon, dass Preise nur für eigene Abos gelten).
- [x] Land auf der Seite wählbar (`/subscriptions?country=GB`), ohne das Land der App zu ändern. Dafür nimmt `PUT /api/settings` ein Feld `subscriptions_country`, das nur bestimmt, für welches Land Abos und Preise gespeichert werden. Standard ist das Land der App.
- [x] `/costs` leitet dauerhaft auf `/subscriptions` weiter (alte Lesezeichen). `templates/costs.html` und `static/js/costs.js` gehen in der neuen Seite auf, `costs.overview` bleibt unverändert.
- [x] Einstellungen: Der Abschnitt „My subscriptions“ wird durch einen Link auf die neue Seite ersetzt; `static/js/settings.js` speichert keine Abos mehr. Übrig bleiben Watchlist, Land, Zeitplan und Sicherung.
- [x] Links anpassen: Kopfzeile der Hauptseite, Status-Seite („Set on the costs page“) und die Seitenleiste („My subscriptions“ wählt weiter die Dienste aus; ein kleiner Link „edit“ führt zur neuen Seite).
- Nicht geändert: Speicherung (`subscriptions:<Land>`, `subscription_costs:<Land>`), Sicherung und die Regeln der Kosten-Seite.
- Kleinere Variante: beide Seiten behalten und nur Preis und Erinnerung als zwei Felder neben jeden angehakten Dienst in den Einstellungen setzen; die Auswertung bliebe auf `/costs`.
- Aus den Design-Reviews, gleich mit umsetzen (die Seiten werden ohnehin neu gebaut):
  - [x] Ungespeicherte Häkchen gehen beim Länderwechsel nicht mehr verloren (ID #2). Entfällt von selbst, weil das Land über `?country=` gewechselt wird; bei ungespeicherten Änderungen vorher nachfragen.
  - [x] „Saved.“ bleibt nach dem Speichern sichtbar, statt im Reload zu verschwinden (ID #6): nach dem Speichern auf `/subscriptions?saved=1` laden und die Meldung im Template zeigen.
  - [x] Speichern-Knopf während des Sendens sperren, bei Netzwerk- oder Serverfehler „Could not reach the app.“ zeigen (WDG #13). Gilt auch für `static/js/settings.js`.
  - [x] Dienst-Checkboxen je Gruppe mit `role="group"` und `aria-label` (WDG #31).
  - [x] Tabelle passt aufs Handy: jede Zeile als Block untereinander statt 622 px Breite in 375 px; kostenlose Dienste ohne Preis- und Datumsfeld oder in einer eigenen kurzen Liste (DC #23). Das Zeitplan-Select in den Einstellungen bekommt `max-width: 100%` (DC #25).
- Prüfung: Tests für `/subscriptions` (Tabelle, Auswertung, Land über `?country=`), für `subscriptions_country` (GB-Abos speichern lässt das Land der App auf DE) und die Weiterleitung von `/costs`. Browser-Test: Dienst anhaken, Preis eintragen, speichern, Zeile mit „pro Film“ erscheint; vorhandene Browser-Tests für die Einstellungen anpassen. Bildschirmfoto mit echten Daten.
- Ergebnis (2026-11-16): `/subscriptions` ersetzt `/costs` (301-Weiterleitung) und den Abo-Abschnitt der Einstellungen. Tabelle mit Logos, Auswahl und Auswertung auf einer Seite, ein „Save“ für alles. `?country=GB` bearbeitet die GB-Abos, das Land der App bleibt (Feld `subscriptions_country`). Kostenlose Dienste zeigen „Free“ statt Preis- und Datumsfeld. Auf 375 px ist jede Zeile ein Block, keine waagrechte Scrollleiste. Mit echten Daten im Browser geprüft (10 Abos, 10 Logos). Neue Tests: fünf in `tests/test_web.py` (Weiterleitung, anderes Land, unbekanntes Land, kostenlose Dienste, „Saved.“) und ein Browser-Test (Preis eintragen, Dienst anhaken, speichern).
- Abweichung: Die Sicherheitsabfrage beim Länderwechsel ist ein `confirm()`; dazu warnt der Browser beim Verlassen der Seite mit ungespeicherten Änderungen. Nicht im Browser nachgestellt: Meldung „Could not reach the app.“ bei gestopptem Server.

### Etappen 9f bis 9i: Befunde aus den Design-Reviews
Drei Reviews vom 2026-11-15, aus dem Code beurteilt: [reviews/web-design-guidelines.md](reviews/web-design-guidelines.md) (WDG, 31 Befunde), [reviews/design-critique.md](reviews/design-critique.md) (DC, 25; davon 20–25 aus der Nachprüfung im Browser mit echten Daten, die 12 der ersten 19 bestätigt und 5 nicht geprüft hat) und [reviews/interaction-design.md](reviews/interaction-design.md) (ID, 17). Doppelte Funde sind zusammengefasst; die Nummern verweisen auf die Reviews, dort stehen Ort und kleinste Lösung. Die Zeilennummern dort gelten für den Stand vom 2026-11-15 und verschieben sich mit jeder Etappe. Vier Befunde stehen in Etappe 9e (ID #2, ID #6, WDG #13, WDG #31). Reihenfolge: 9f zuerst (Datenverlust, falsche Anzeige), dann 9g; 9h und 9i bauen die Hauptseite um und kommen danach.

### Etappe 9f: Datenverlust, falsche Anzeige und Fehlermeldungen
- [x] Zuerst: Werkzeugleiste und Statistik erscheinen auch bei gespeicherten Ergebnissen (DC #20). Heute blendet sie nur ein laufender Scan ein; mit einem Stand jünger als 24 Stunden fehlen Sortierung, „My favorites“, „Random“, „Evening mode“, „Compare“, „Share“ und alle Exporte. In `loadLatestResult` (`static/js/app.js`) beide Bereiche einblenden und `updateStats()` aufrufen. Browser-Test: Seite mit gespeichertem Stand laden, „Random“ ist sichtbar. Danach prüfen, ob die Statistik „Clear“ folgt (DC #24).
- [x] Notiz und Status: Ein Fehler beim Speichern wird gemeldet, das Feld bleibt markiert, bis ein neuer Versuch klappt (ID #1). Heute sieht die Notiz gespeichert aus und ist nach dem nächsten Neuzeichnen weg.
- [x] Länderwechsel im Kopf: zuerst den gespeicherten Scan des neuen Landes laden, nur ohne Daten scannen, dann mit Platzhaltern statt mit den Filmen des alten Landes (ID #3, DC #15). Das Select als Steuerelement gestalten (Rahmen, Pfeil): offen, siehe Abweichungen.
- [x] Zustand „Server nicht erreichbar“: ab dem dritten fehlgeschlagenen Abruf „Lost connection to the app, retrying…“, bei Erfolg zurücksetzen; ein Netzwerkfehler beim Scan-Start zeigt die normale Fehlerausgabe (ID #4).
- [x] Abgebrochener Scan: Balken bleibt stehen und wird grau statt 100 %; die Rückfrage vor dem Abbrechen entfällt (ID #5).
- [x] Knopf heißt „Scan now“ bzw. „Scan again“, „Retry scan“ nur nach einem Fehler (DC #8).
- [x] Toast unterscheidet Fehler von Erfolg: Fehler mit roter Randfarbe, rund 6 s und `role="alert"`; kein Toast mehr für „Added/Removed from favorites“ und „Favorite updated.“ (ID #12).
- [x] Fehlermeldungen nennen den nächsten Schritt statt „Request failed (500).“; bei 5xx Link auf die Status-Seite (DC #16).
- [x] „Share“ funktioniert auch über `http://` im Heimnetz: Rückfall auf `window.prompt`, Meldung über den Toast, `#share-message` entfällt (WDG #12, ID #14).
- Ergebnis (2026-11-15): 279 Python-, 17 JS- und 10 Browser-Tests, `ruff check`, `ruff format --check` und `mypy` sauber. Drei Browser-Tests sind neu oder erweitert: zweiter Besuch mit gespeichertem Stand zeigt Werkzeugleiste, Statistik und „Scan again“; eine Notiz, die nicht gespeichert werden konnte, wird markiert und mit rotem Toast gemeldet; zurück zu einem Land mit Scan lädt den gespeicherten Stand ohne neuen Scan. Mit der Kopie der echten Daten im Browser: Werkzeugleiste und Statistik sind da, die Statistik folgt jetzt „Clear“ (0), „All“ (430) und „My subscriptions“ (169). Asset-Version `20261115-9`.
- Dabei gefunden und behoben: Die Statistik für „Selected providers“ wurde bei einer Änderung der Dienst-Auswahl nicht neu berechnet (offene Frage aus DC #24).
- Abweichungen: Bei 5xx auf `/matches` nennt die Meldung die Status-Seite, statt sie zu verlinken (der Link steht in der Kopfzeile). Das Länder-Select ist noch nicht als Steuerelement gestaltet (Rahmen, Pfeil); das kommt mit der Kopfzeile in Etappe 9h. Nach einem fehlgeschlagenen Favoriten-Klick ändert sich der Stern nicht mehr vorab.
- Nicht im Browser nachgestellt: App stoppen während eines Scans („Lost connection…“), abgebrochener Scan (grauer Balken) und „Share“ über die IP-Adresse; der eingebaute Browser kann `prompt()` nicht anzeigen. Diese drei Wege haben keinen eigenen Test.
- Prüfung: JS- oder Browser-Test für die Fehlermeldung an der Notiz und für den Länderwechsel (gespeicherter Scan wird geladen, kein neuer Scan). Im Browser: App stoppen während eines Scans, „Share“ über die IP-Adresse.

### Etappe 9j: Filter-Fehler aus der Filter-Prüfung
Alle 13 Filter, die Sortierung und „Any / All selected services“ am 2026-11-16 im Browser mit der Kopie der echten Daten geprüft (DE, 10 Abos ausgewählt, 169 sichtbare und 26 nicht verfügbare Filme): Für jede Einstellung die erwartete Zahl aus den Rohdaten berechnet und mit Trefferzahl, Karten und der Liste „nicht verfügbar“ verglichen. Suche (auch über Besetzung und Stichworte), Verfügbarkeit, Angebotsart, Jahr, Bewertung, Stimmen, Genre, Stichwort, Laufzeit, Medien und alle sechs Sortierungen stimmen. Schon im Plan und hier nicht doppelt: fehlende Chips (DC #1, Etappe 9h), kein leerer Zustand (DC #2), „Free“ mit drei Bedeutungen (DC #3), 3675 Stichworte (Etappe 9c).
- [x] „Minimum providers“ zählt alle Anbieter eines Films, auch Leih-Shops und nicht ausgewählte. Dadurch zeigt „2+ providers“ alle 169 Filme statt 17. Nur ausgewählte Anbieter zählen, wie bei der Angebotsart (`commonMatches` in `static/js/filtering.js`). JS-Test.
- [x] Genre und Stichwort aus einem Link gehen beim Laden verloren (`?genre=Horror` zeigt „All genres“): `setInitial` läuft, bevor `populateGenres` die Auswahl füllt. Den Wert aus der URL in `populateGenres` übernehmen, solange die Auswahl noch auf „all“ steht. Browser-Test mit `?genre=Action`.
- [x] Ein Klick auf den Chip „Rating“ oder „Votes“ lässt das Select leer stehen: der Chip setzt `all`, diese Selects haben aber `0` als ersten Wert. Auf den ersten Wert der Auswahl zurücksetzen (`input.options[0].value`).
- [x] „With poster“ entfernen: alle 430 Filme haben ein Poster, die Option filtert nichts. „With trailer“ bleibt (167 von 169).
- [x] Widersprüchliche Filter ergeben stumm 0 Treffer: „Free“ mit „Subscription“, oder „Year from“ größer als „Year to“. Die Jahre beim Lesen tauschen (`readFilters`); für den Rest zeigt der leere Zustand aus Etappe 9h (DC #2) den Ausweg „Reset filters“.
- [x] „All favorite statuses“ wirkt nur in der Favoriten-Ansicht, steht aber immer in der Werkzeugleiste. Nur in der Favoriten-Ansicht zeigen.
- Nicht prüfbar: „Availability changes“ (die Kopie hat keine gespeicherten Änderungen, beide Optionen zeigen 0); „Any / All selected services“ mit „All“ und zehn Diensten zeigt richtig 0, mit zwei Diensten nicht geprüft.
- Prüfung: JS-Tests für „Minimum providers“ und die getauschten Jahre, Browser-Test für Genre aus dem Link; Gegenprobe mit denselben Zahlen wie oben.
- Ergebnis (2026-11-16): alle sechs Punkte behoben. „2+ providers“ zeigt 17 statt 169 Filme; `?genre=Horror` bleibt nach dem Laden stehen; Jahre 2020 bis 2000 ergeben dieselben 4 Horror-Filme wie 2000 bis 2020; der Chip „Rating“ springt auf „Any TMDB rating“. Genre und Stichwort aus dem Link warten in `data-pending`, bis ein Scan Filme mit diesem Wert bringt. Neue Tests: zwei JS-Tests (Anbieter-Zahl, getauschte Jahre) und ein Browser-Test (Genre aus dem Link, Chip, Favoritenstatus). Nebenbei: `ruff` prüft die ruflo-Ordner (`.claude`, `.agents`, `.claude-flow`) nicht mehr, sonst schlägt `ruff format --check` an deren Code-Beispielen fehl.

### Etappe 9g: Barrierefreiheit
Tastatur und Fokus:
- [x] Seitenleiste: festes `aria-hidden="true"` entfernen; Escape schließt das Panel nur, wenn es offen ist (WDG #1).
- [x] Filmkarte ist kein `role="button"` mehr; der Knopf „Details“ öffnet den Dialog, der Mausklick auf die Karte bleibt (WDG #2). Danach bekommen Stern, „Details“, Status und Notiz den Filmtitel im Namen, der Stern `aria-pressed` (WDG #14).
- [x] Sichtbarer Fokus an Favoriten-Status und Notiz (`outline: none` und `!important` weg, WDG #3) und an „Restore from file“ / „Import favorites“ (WDG #11).
- [x] Fokus bleibt am Ort: nach Favoriten-Klick und auf `/matches` nach „Looks right“, „Use this“, „Undo correction“ (WDG #4); auf `/matches` bleibt auch die Markierung „gespeichert“ an der Zeile, sonst Toast (ID #7).
- [x] Dialoge geben den Fokus an den Auslöser zurück: eine Hilfsfunktion `openModal(id)` für alle vier Dialoge (WDG #5); jeder Dialog bekommt `aria-labelledby` (WDG #6).
- [x] Mobiles Filterpanel: schließt nicht mehr nach jedem Häkchen, Fokus geht beim Öffnen hinein und beim Schließen zurück; oben ein Knopf „Done · n films“ (WDG #10, DC #10).
- [x] „Random“ öffnet gleich das Detailfenster des Films (WDG #26, DC #19).

Ansagen für Screenreader:
- [x] Scan: `aria-valuenow`/`min`/`max` am Balken, `role="status"` an der Meldung, `role="alert"` am Fehler (WDG #7).
- [x] Trefferzahl mit `aria-live="polite"`, `aria-busy` am Raster während des Ladens (WDG #8); Vorschläge im Abend-Modus mit `aria-live` (WDG #27).
- [x] `role="group"` bzw. `role="status"` an den `div`s, die heute nur ein `aria-label` tragen (WDG #9).
- [x] Kleinigkeiten: `aria-hidden="true"` an Icons neben Text (WDG #18), Filter-Chips sagen „Remove filter …“ (WDG #19), versteckter Text „films“ / „services selected“ an den Zahlen der Dienstliste (WDG #20), Filmtitel als `<h3>` (WDG #21), Navigation in `<nav>` (WDG #22, zusammen mit DC #17 in Etappe 9h), `alt=""` am Poster auf `/matches` (WDG #30).

Lesbarkeit und Handy:
- [x] Nicht verfügbare Karten: Deckkraft nur auf das Poster, Text bleibt in `--muted` (WDG #15, Kontrast heute geschätzt 2,5:1).
- [x] `100dvh` statt `100vh` im mobilen Panel (WDG #16).
- [x] Touch-Ziele mindestens 44 px: Vergleichs-Checkbox, Filter-Chips, Favoriten-Status und Notiz (WDG #17).
- [x] Schrift in vier Stufen als Variablen, nichts unter 12 px: `.75rem` für Pillen und Zähler, `.875rem` für Knöpfe, Filter, Tabellen und Angaben auf der Karte, `1rem` für Erklärtexte und Filmtitel (DG #3, ersetzt WDG #28). Heute zwölf Zwischengrößen von 9,9 bis 16,8 px. Die wirkungslose Angabe `font-family: Georgia` entfällt.
- [x] `prefers-reduced-motion` beachten, in CSS und beim sanften Scrollen (WDG #24).
- [x] Sichtbare Beschriftung „from“/„to“ an den Jahresfeldern (WDG #23).
- [x] Suche zeichnet erst nach rund 150 ms Pause neu (WDG #25); Leerzeichen bei „Database:“ auf der Status-Seite (WDG #29).
- Prüfung: Browser-Tests für die Tastatur-Wege (Stern bei Film n, Fokus bleibt; Details öffnen und mit Escape schließen, Fokus zurück; drei Dienste im mobilen Panel wählen). Kontrast im Browser messen, mobiles Panel auf einem echten Handy ansehen. Kein Test mit Screenreader geplant.
- Ergebnis (2026-11-16): alle Punkte umgesetzt bis auf `<nav>` (WDG #22), das wie geplant mit DC #17 in Etappe 9h kommt. Gemessen mit der Datenkopie: kein sichtbarer Text unter 12 px (vorher ab 9,9 px; zuletzt noch die Bootstrap-Badges), Text auf nicht verfügbaren Karten 7,0:1 statt etwa 2,5:1, 196 Filmtitel als `<h3>`, kein `role="button"` mehr. „Random“ öffnet das Detailfenster; das mobile Panel ist 100 % hoch, der Fokus geht beim Öffnen auf „Done · n films“. Nebenbei behoben: Der Knopf „Filters“ war auch auf dem Desktop sichtbar, weil die spätere Regel `.btn` das `display: none` überschrieb. Neue Browser-Tests: Stern und „Details“ per Tastatur (Fokus bleibt bzw. kommt zurück), mobiles Panel bleibt beim Wählen offen.
- Abweichungen: 44-px-Ziele nur bei Touch-Bedienung (`pointer: coarse`), damit die Desktop-Ansicht dicht bleibt; die Vergleichs-Checkbox hat überall eine 44-px-Fläche. Die vierte Schriftstufe ist `--fs-heading` (2rem); Seitentitel und der Stern behalten ihre eigene Größe.
- Nicht geprüft: Screenreader (war nicht geplant), echtes Handy (nur 375 px im Browser), `/matches` mit Fokus nach dem Speichern (kein unsicherer Treffer in der Kopie).

### Etappe 9h: Hauptseite aufräumen (Filter, Begriffe, erster Bildschirm)
In einem Rutsch, damit die Seite nur einmal „umzieht“.
- [x] Chips für alle 13 Filter (es fehlen „Media“, „Availability changes“, „Minimum providers“) und ein Knopf „Reset filters“ (DC #1).
- [x] Leerer Zustand: „No film matches these filters.“ mit „Reset filters“ und, ohne gewählten Dienst, „Select my subscriptions“ (DC #2).
- [x] „Free“ eindeutig machen: Abschnitt heißt „Free & with ads“, das Dienst-Abzeichen „Mostly free“; der Filter „Availability“ behält nur eine Achse, die erste Option heißt „Everything (incl. unavailable)“, „Only on one of my services“ wird ein eigenes Kontrollkästchen (DC #3).
- [x] Überall „service“ statt „provider“; „Rental shops“ bleibt (DC #14).
- [x] Werkzeugleiste kürzen: die fünf Export- und Import-Knöpfe in ein `<details>` „Export / import“ oder auf die Einstellungsseite neben die Sicherung; nur ein Knopf in Akzentfarbe (DC #4).
- [x] „Any / All selected services“ in die Seitenleiste zu den Diensten (DC #5).
- [x] Seltene Filter in `<details>` „More filters (n active)“; sichtbar bleiben Suche, Verfügbarkeit, Genre, Laufzeit, Bewertung (DC #6). Der offene Punkt zum Stichwort-Filter (3676 Einträge) bleibt in Etappe 9c. Vorgezogen und erledigt (2026-11-16): Sichtbar bleiben die fünf genannten; Angebotsart, Jahr von/bis, Stimmen, Stichwort, Medien, Änderungen und Anzahl der Dienste liegen unter „More filters“, die Zusammenfassung zählt gesetzte Filter („More filters (2 active)“). Auf dem Handy ist der Filterbereich 243 px statt 578 px hoch. Browser-Test für den Zähler.
- Regel für neue Filter: Die sichtbare Reihe bleibt bei diesen fünf. Jeder neue Filter kommt unter „More filters“, auch die aus den Etappen 11 bis 14. Ein neuer Filter darf nur in die sichtbare Reihe, wenn er dort einen anderen ersetzt.
- [x] Ruhender Scan als eine Zeile („Saved results from … · Scan now“), Statistik unter die Ergebnisse oder in ein `<details>`, Überschrift höchstens 3rem (DC #7). „Grey out films found unavailable“ nur während eines neuen Scans zeigen (ID #16).
- [x] Favoriten-Ansicht deutlich machen: Zeile „Showing your favorites only · Show all films“ über dem Raster, Knopf heißt fest „My favorites“ mit `aria-pressed` (ID #9).
- [x] „Desktop layout“ über 800 px ausblenden und in „Wide view“ umbenennen (DC #9).
- [x] Eine gemeinsame Navigation `partials/page-nav.html` in `<nav>` mit allen Seiten, die aktuelle mit `aria-current="page"` (DC #17, WDG #22). Nach Etappe 9e, weil dort `/costs` entfällt.
- [x] Einleitungstext kürzen oder streichen (DC #18).
- [x] Kopfzeile auf dem Handy: die sechs Knöpfe überlappen und „Status“ ist abgeschnitten; umbrechen lassen oder nur „Filters“ als Knopf zeigen, die Seitenlinks in die gemeinsame Navigation (DC #21). Dabei das Länder-Select als Steuerelement gestalten (Rahmen, Pfeil; Rest von DC #15 aus Etappe 9f).
- [x] Statistik-Zeile geht auf: „8 free · 162 paid“ ergibt 170 bei 169 Filmen; „(1 in both)“ ergänzen oder kürzen (DC #24; dass die Statistik der Auswahl nicht folgte, ist mit 9f behoben). Der Balken füllt sich bei gespeicherten Ergebnissen nicht mehr von 0 auf 100 % (entfällt mit der einzeiligen Scan-Anzeige).
- Farbe und Bausteine, aus [reviews/design-guide.md](reviews/design-guide.md) (DG, 6 Empfehlungen, im Browser gemessen; dort stehen die genauen Werte):
  - [x] Bernstein nur für Bedienung: der Dienstname auf der Karte wird eine neutrale Pille (`#252d29` / `#d9d3c7`), damit er nicht wie „With ads“ aussieht (DG #1).
  - [x] Eine Klasse `.pill` mit den Tönen ok, warn, danger, neutral für Angebotsart, „Free“ am Dienst, Ergebnis auf der Status-Seite und Hinweis auf `/matches`; heute vier verschiedene Bausteine (DG #2).
  - [x] Zeitpunkte ohne Sekunden über eine Hilfsfunktion in `static/js/ui.js` („15 Nov 2026, 23:10“), an vier Stellen (DG #4).
  - [x] „Details“ auf der Karte als normaler `btn btn-sm`, `.film-details-button` entfällt (DG #6).
  - [-] Optional: fast gleiche Farbwerte durch fünf neue Variablen ersetzen (51 Werte bei 6 Variablen, DG #5). Voraussetzung für „Helles Design“ in Etappe 14.
- Kleinere Variante: nur DC #1 und #2 (wenige Zeilen, beseitigen „Warum fehlt mein Film?“), den Umbau der Seite später.
- Prüfung: JS-Tests für Chips und „Reset filters“, Browser-Test für den leeren Zustand; vorhandene Browser-Tests an die neuen Texte anpassen. Bildschirmfoto vom ersten Bildschirm auf Desktop und Handy, vorher und nachher. Danach eine Woche nutzen und notieren, welche Filter gesetzt werden (URL-Parameter).
- Ergebnis (2026-11-16): alles umgesetzt bis auf das optionale DG #5 (Farbvariablen, bleibt für Etappe 14). Erster Bildschirm mit der Datenkopie: Auf dem Handy (375 px) beginnt die erste Filmkarte bei 965 px statt 1632 px, keine überlappenden Knöpfe mehr; auf dem Desktop steht die Scan-Anzeige in einer Zeile. Statistik: „8 free · 162 paid · (1 in both)“ bei 169 Filmen. Chips für alle 14 Filter (das Kontrollkästchen „Only on one of my services“ zählt mit), „Reset filters“ als letzter Chip und im leeren Zustand. Alte Links mit `availability=exclusive` setzen das neue Kontrollkästchen. „Details“ behält die Klasse `film-details-button` nur noch als Haken für das Skript, ohne eigenen Stil. Nebenbei: Die Kopfzeile stand außerhalb von `<main>` und klebte am Bildschirmrand; „My subscriptions“ in der Seitenleiste ragte nach der größeren Knopfschrift aus 9g heraus. Neue Tests: JS-Test für Chips und „Reset filters“, Browser-Test für den leeren Zustand; zwei Browser-Tests an die neuen Texte angepasst.
- Abweichung: Den Knopf im ruhenden Scan nenne ich „Scan now“, nach einem Fehler „Retry scan“ (9f hatte „Scan again“). Die Bildschirmfotos vorher/nachher liegen nur in der Sitzung, nicht als Dateien.
- Offen: eine Woche nutzen und notieren, welche Filter gesetzt werden.
- Nachtrag (Etappe 9k): Standard ist jetzt „Available only“ mit Sortierung nach Bewertung, „Everything (incl. unavailable)“ ist die zweite Option. Das Menü heißt „More“ und enthält auch „Share link“. Am Handy gibt es „Services“ und „Sort & filter“ statt „Filters“, die Filter sind dort eingeklappt; die Zahlen oben (243 px, 965 px) gelten nicht mehr.

### Etappe 9i: Vom Vorschlag bis „gesehen“
- [x] Abend-Modus: Vorschläge sind Knöpfe, die das Detailfenster öffnen, mit „· on Netflix“ dahinter; Hinweis „Uses the subscriptions saved in Settings.“ (DC #13). Genre und Laufzeit in `localStorage` merken (ID #13).
- [x] „Watched“ wirkt: „Random“ und Abend-Modus überspringen gesehene Filme; kleines Abzeichen „Watched“ im Raster (ID #10).
- [x] Link zum Ansehen: Feld `link` aus der TMDB-Antwort „watch/providers“ (JustWatch-Seite je Land) speichern und im Detailfenster als Hauptknopf „Where to watch“ zeigen (ID #11). Vorher prüfen, ob TMDB das Feld für alle Länder liefert; nur als gültige `https://www.themoviedb.org/`-Adresse ausgeben (`validation.py`).
- [x] Detailfenster zeigt die eigenen Abos: in jeder Gruppe zuerst und markiert (DC #22). Heute sehen fremde Dienste wie MUBI genauso aus wie ein eigener.
- [x] Rückgängig nach dem Entfernen eines Favoriten: Toast mit „Undo“, rund 5 s, stellt Status und Notiz wieder her (DC #11; aus Etappe 14 vorgezogen).
- [x] Vergleich: Knopf „Compare (n)“, aktiv ab 2; Checkbox sichtbar beschriftet; „Clear selection“ im Vergleichsdialog (DC #12, ID #8).
- [x] Status und Notiz lassen die Karte nicht mehr springen: nur in der Favoriten-Ansicht und im Detailfenster zeigen (ID #15).
- Prüfung: JS-Tests für `eveningSuggestions` ohne gesehene Filme und für den Zähler am Vergleich; Test für das Feld `link` aus einer TMDB-Antwort und in der Sicherung; Browser-Test für „Undo“.
- Ergebnis (2026-11-16): alle sieben Punkte umgesetzt und mit der Datenkopie im Browser geprüft: Abend-Vorschläge öffnen das Detailfenster („The Pianist … · on Netflix“), Netflix steht im Detailfenster oben mit „Your service“, „Compare (2)“ wird ab zwei Filmen aktiv, auf den Karten stehen ohne Favoriten-Ansicht keine Status- und Notizfelder mehr.
- Abweichung: „Where to watch“ speichert kein Feld `link`. TMDB baut die Seite aus Film-ID und Land (`https://www.themoviedb.org/movie/949/watch?locale=DE`, geprüft: 200, Quelle JustWatch); die Adresse entsteht im Browser aus der schon geprüften `tmdb_url`. Damit entfallen Änderungen an Datenbank, Sicherung und `validation.py` und die Tests dafür. Der Hinweis im Abend-Modus nennt „My subscriptions“ statt „Settings“ (seit 9e).
- Nachtrag (Etappe 9k): „Compare“ ist jetzt immer aktiv und schaltet den Vergleichsmodus ein, erst dann erscheinen die Kästchen. Die Abend-Vorschläge stehen zusätzlich als Poster-Leiste „Tonight“ oben. Im Detailfenster sind fremde Dienste eingeklappt.
- Tests: JS-Tests für den Abend-Modus ohne gesehene Filme und für „Compare (n)“; Browser-Test für „Undo“ (Notiz kommt mit zurück); der Notiz-Test wechselt jetzt in die Favoriten-Ansicht.

### Etappe 10: Entscheidungshilfe
- [x] Zufallsknopf („Würfeln“): ein Film aus der aktuellen Filteransicht. Erster, einfacher Schritt zum Abend-Modus.
- [x] Abend-Modus: Zeit und Genre angeben, drei Vorschläge aus den eigenen Abos.
- [x] „Läuft bald aus“ / „kürzlich entfernt“ aus der Historie (TMDB liefert kein Ablaufdatum).
- [x] Gewichtete Sortierung: Bewertung pro Laufzeit, am längsten auf der Watchlist, Anzahl eigener Abos.
- [x] Filmreihen (TMDB „Collections“) zusammen anzeigen.
- [x] Ähnliche Filme: zu einem Watchlist-Film zeigen, was Vergleichbares auf den eigenen Abos läuft (TMDB „similar“ / „recommendations“).
- Ergebnis (2026-11-16): Auswahl mit dem Nutzer: drei Punkte gebaut, „Ähnliche Filme“ bleibt offen (braucht eigene TMDB-Abfragen je Vorschlag).
  - Kürzlich entfernt: Kasten „Recently gone from your services (n)“ über den Filmen, je Film eine Zeile mit den Diensten und dem Datum, aus den gespeicherten Änderungen der letzten 14 Tage und nur für die eigenen Abos. „Läuft bald aus“ geht nicht, TMDB liefert kein Ablaufdatum.
  - Sortierungen: „rating per hour“, „longest on watchlist“, „on most of my services“, „film series together“. Die Position auf der Watchlist kommt aus der Reihenfolge der Letterboxd-Seite (zuletzt Hinzugefügtes zuerst, angenommen, nicht nachgeprüft); der CSV-Export wird nach seiner Spalte „Date“ genauso sortiert.
  - Filmreihen: Feld `collection` aus `belongs_to_collection` der ohnehin gemachten TMDB-Abfrage; im Detailfenster „Part of … : also on your watchlist …“ mit Links, dazu die Sortierung „film series together“.
  - Ähnliche Filme (nachgeholt, 2026-11-16): Mit dem Nutzer entschieden, nur Filme von der eigenen Watchlist vorzuschlagen; Vorschläge außerhalb der Watchlist bleiben unter „Nicht im Plan“. Die TMDB-Abfrage des Scans holt „recommendations“ und „similar“ gleich mit (`append_to_response`, keine zusätzliche Abfrage); gespeichert werden nur die IDs im neuen Feld `similar_ids` (höchstens 40, Empfehlungen zuerst). Das Detailfenster zeigt „Similar on your services: …“ mit bis zu 5 Watchlist-Filmen, die auf einem eigenen Abo ohne Zusatzkosten laufen, ohne gesehene; ein Klick öffnet deren Details. Erscheint erst, wenn der Scan die TMDB-Daten neu geholt hat. Tests: Python (IDs aus der Antwort, Prüfung beim Import), JS (`similarOnServices`), Browser (Zeile und Klick).
  - Nicht im Browser geprüft: Reihen, Position und „Kürzlich entfernt“, weil der gespeicherte Scan der Kopie von vorher stammt und keine Änderungen hat. Reihe und Position erscheinen nach dem nächsten Scan (gespeicherte TMDB-Daten werden nach ihrer Gültigkeit neu geholt). Abgedeckt durch Tests: zwei Python-Tests (Reihe, Position), zwei JS-Tests (Sortierungen, „Kürzlich entfernt“).

### Etappe 9k: Design-Runde mit Impeccable (Hauptseite)
Kritik der Hauptseite mit `/impeccable critique` (2026-11-16): 24 von 40 Punkten. Größte Probleme: am Handy kein Film auf dem ersten Bildschirm, Startansicht als Katalog von A bis Z, Abend-Modus versteckt. Bericht in `.impeccable/critique/`, Produktbeschreibung in `PRODUCT.md`.
- [x] Werkzeugleiste kürzen: „Share“ und alle Exporte in ein Menü „More“; die Vergleichs-Kästchen auf den Postern erst nach einem Klick auf „Compare“ (Vergleichsmodus), „Clear selection“ beendet ihn.
- [x] Detailfenster: Aktionen mit „Where to watch“ über der Verfügbarkeit; fremde Dienste eingeklappt unter „Other services (n)“, wenn der Film auf einem eigenen Dienst läuft; höchstens 5 Stichworte.
- [x] Startansicht: Sortierung nach Bewertung und „Available only“ statt Titel und „Everything“. Im geteilten Link fallen nur diese Standardwerte weg, „Everything“ bleibt erhalten.
- [x] Handy: Sortierung, Werkzeugleiste und Filter hinter dem Knopf „Sort & filter“; sichtbar bleiben Suche und Chips. Der bisherige Knopf „Filters“ öffnete die Dienste und heißt jetzt „Services“.
- [x] „Tonight on your services“: drei Poster mit den Abend-Vorschlägen (gespeicherte Laufzeit und Genre) über den Bedienelementen; „Change“ öffnet das bisherige Fenster. In der Favoriten-Ansicht ausgeblendet.
- [x] Layout: Filter, Chips und Raster stehen zusammen; die fünf sichtbaren Filter in einer Reihe; 48 px zwischen „Free“ und „Paid“ statt 1 px; 44 px Tippflächen auf Touch-Geräten; TMDB- und Trailer-Links auf den Karten nur noch auf dem Desktop.
- [x] Dienste-Leiste: Suche und Sortierung in einer Reihe, „My subscriptions“ als erster Knopf über die volle Breite, Hilfetext ans Ende; Zähler als lesbare Pille statt grauem Abzeichen (Kontrast 2,5:1).
- Ergebnis (2026-11-16): Handy (375 px) erstes Poster bei 573 px statt 923 px, „Tonight“ ganz auf dem ersten Bildschirm; Desktop: Liste der Dienste beginnt bei 296 px statt 421 px. Layout-Prüfung des Detektors ohne Befund. Der Notiz-Test wartet jetzt auf das Ende des Scans (er tippte, während der fertige Scan die Karte neu zeichnete).
- [x] „Paid“ heißt jetzt „Subscription & rent“ (Abo und Leihe, wie der Bereich rechnet); dazu weitere Texte geklärt (`/impeccable clarify`, 2026-11-17).
- [x] „Shuffle“ für „Tonight“. Nach `/impeccable critique` (25/40, 2026-11-17) umgesetzt: Laufzeit, Genre und „Shuffle“ direkt in „Tonight“; „Pick for tonight“ (Abend-Fenster mit Textliste) und „Random film“ entfallen; „Tonight“ nimmt die angehakten Dienste statt der gespeicherten Abos und bleibt sichtbar, wenn nichts passt; „Scan now“ ist nur nach einem Fehler hervorgehoben; Statistik und „Scan changes“ stehen unter den Filmen, „Last updated“ doppelt sich nicht mehr; im Detailfenster stehen Dienste und Aktionen direkt unter dem Titel, Inhalt und Links darunter; „New on …“ mit genug Kontrast; Kartentitel ausgeglichen umbrochen.
Offen aus der Kritik vom 2026-11-17 (25/40, Bericht in `.impeccable/critique/`):
- [ ] Detailfenster: „Your service“ und „Similar on your services“ nehmen noch die gespeicherten Abos, „Tonight“ und das Raster die angehakten Dienste. Eine Quelle wählen. → K2
- [ ] Eine Leiste statt Werkzeugleiste plus Filterreihe: Suche, „Filters (n)“ und Sortierung; der Rest dahinter (`/impeccable distill`). → K2
- [ ] Sortierung: 11 Einträge, die gewichteten („rating per hour“, „on most of my services“) sind ohne Erklärung kaum zu verstehen. → K2
- [ ] Letzter Klick „Watch on Netflix“ statt TMDB: direkter Link zum Dienst, wo TMDB/JustWatch ihn liefert (heute vier Schritte vom Vorschlag bis zum Abspielen). → K4 (Hauptknopf; echte Direkt-Links nicht möglich)
- [x] Barrierefreiheit (`/ui-ux-pro-max`, 2026-11-17): Link „Skip to films“ als erster Tab-Stopp; Dienste-Leiste am Handy ist geöffnet ein Dialog (`role="dialog"`, `aria-modal`, Seite dahinter `inert`); je Karte zwei Tab-Stopps („Details“ und Stern), TMDB und Trailer nur per Maus (beide im Detailfenster).
- [x] Favoriten-Stern sitzt neben „Details“ statt auf der Poster-Ecke.
- [ ] Handy: „Wide view“ ausblenden; alle Bedienelemente oben statt im Daumenbereich; „Tonight“ beginnt erst rund 380 px weiter unten. → K1 und K3
- [ ] Eigenes Gesicht: Schrift für Überschriften und Filmtitel, Poster als Fläche (z. B. unscharfer Hintergrund vom ersten Vorschlag), weniger umrandete Knöpfe (`/impeccable bolder` oder `/impeccable typeset`).
- [ ] `graphify update .` lief in Git Bash nicht (`graphify` nicht im PATH); mit dem absoluten Pfad wie in den Hooks aufrufen.
- [ ] Filmkarten sind hoch (Desktop rund 570 px, Handy rund 480 px). → Etappe 9l (der Titel übernimmt die Rolle von „Details“).
- [ ] Notiz geht verloren, wenn ein Scan fertig wird, während man tippt (die Karten werden neu gezeichnet). → K1
- [ ] Ein Film aus „Tonight“ steht im Raster noch einmal; vermutlich in Ordnung, nach einer Woche Nutzung entscheiden. → erledigt sich mit K3 (eigene Startseite)
- [ ] Danach `/impeccable critique` erneut und mit 25/40 vergleichen (Verlauf: 24 → 25).

### Etappe 9l: Filmkarte neu (nächste Etappe, Phase 1 des Gesamtkonzepts)
Vorlagen: `movie-card-plan.md` und das Gesamtkonzept (beide in Downloads). Am 2026-11-17 gegeneinander abgewogen nach UI/UX-Regeln: nichts nur per Hover, Text statt Farbe allein, 44-px-Tippflächen, wenige Tab-Stopps, nichts Bedienbares auf dem Poster. Nur Frontend; Backend, API und Daten bleiben unverändert. Ersetzt den 9k-Punkt „Filmkarten sind hoch“.
Probleme heute: fünf Klickziele je Karte ohne Hauptaktion, Angebots-Pillen gelten für die ganze Karte statt je Dienst, Amber für fünf verschiedene Dinge, „Details“ in einer Reihe auf verschiedenen Höhen, Laufzeit bricht um („161“ / „min“), nur 5 Karten je Reihe.
Ziel:
```
┌──────────────────┐
│ [New]            │  Poster 2:3; höchstens ein Status-Badge mit Text (oben links)
│      POSTER      │
├──────────────────┤
│ The King's Speech│  Titel, max. 2 Zeilen = Link ?film=, über die ganze Karte gezogen
│ 2010 · 1h 58m · ★ 3.9   eine Zeile; Letterboxd, ohne Wert „TMDB 7.7“
│ [N] [P]€ [Y]ᴬᵈ   │  alle angehakten Dienste als Logos, Abzeichen für die Angebotsart
│                ♥ │  Favorit unten rechts
└──────────────────┘
```
- [x] Die ganze Karte ist das Klickziel: Der Titel wird ein echter Link (`<a href="?film=<key>">`, siehe unten) und per `::after { inset: 0 }` über die Karte gezogen; der Knopf „Details“ entfällt. Kein `<a>` um die Karte, kein Klick-Handler nur auf dem `<div>`. Was eigenständig klickbar bleibt (♥, „Compare“-Kästchen im Vergleichsmodus, Status und Notiz in der Favoriten-Ansicht), liegt mit `position: relative; z-index: 1` darüber.
- [x] Alle Dienste statt Angebots-Pillen (entschieden 2026-11-17): jeder angehakte Dienst, auf dem der Film im Bereich der Karte läuft, als Logo (Name, wo kein Logo da ist), nach Namen sortiert, damit derselbe Dienst immer an derselben Stelle steht; die Reihe darf umbrechen. Kleines Abzeichen unten rechts am Logo für die Angebotsart in diesem Bereich: Abo ohne Abzeichen, Free mit Geschenk-Symbol (Ton `pill-ok`), „Ad“ und Rent („€“) neutral grau; Ring in `--panel`, `aria-hidden`. Hat ein Dienst im Bereich mehrere Arten, zählt free vor ads bzw. flatrate vor rent; der Tooltip nennt alle. Jedes Logo hat `alt` und `title` mit Dienst und Art („Netflix, subscription“). Kein eigenes Klickziel (kein Direkt-Link zum Anbieter möglich). Angebotsarten je Dienst sind vorhanden (`film.providers`), „Buy“ speichert die App nie.
- [x] Meta-Zeile `2010 · 1h 58m · ★ 3.9` (Letterboxd /5; ohne Wert `TMDB 7.7`), kein „/10“, `white-space: nowrap` mit Ellipse, `tabular-nums`. Neue reine Hilfsfunktion für „2h 34m“ / „58m“ / „2h“ mit JS-Test, nur auf der Karte (Tonight und Filter behalten „min“).
- [x] Favorit wird ♥ statt ☆, weil ★ jetzt die Bewertung ist. Unten rechts, überall gleich. Zustände: Ring ohne Füllung, Hover mit leichter Füllung, nur der Favorit gefüllt. 36 px sichtbar, mindestens 44 px Trefferfläche. `aria-pressed` bleibt, `aria-label` „Add … to favorites“ / „Remove … from favorites“. Sichtbarkeit: Touch immer; mit Maus bei Hover, bei Fokus in der Karte (`:focus-within`) und als Favorit immer; ausblenden mit `opacity: 0; pointer-events: none` (bleibt in der Tab-Reihenfolge), ohne Überblendung bei `prefers-reduced-motion`. Hover beschleunigt nur: Favorit gibt es auch im Detailfenster.
- [x] Status-Badge auf dem Poster, höchstens eins, deckender Grund und Text: vorerst „New“ (aus den gespeicherten Änderungen, ersetzt die „New on …“-Pillen unter dem Text) und „Watched“; „Gone“ kommt mit Etappe K3. „No longer on …“ steht in den Details.
- [x] TMDB- und Trailer-Link von der Karte entfernen. Geprüft: Das Detailfenster hat beide (`film-modal-links`).
- [x] Titel höchstens 2 Zeilen mit „…“ (`-webkit-line-clamp`), voller Titel im Text und als `title`; `text-wrap: balance` bleibt.
- [x] Karte als Flex-Spalte, Fußzeile mit `margin-top: auto` (Fußzeilen einer Reihe auf einer Höhe); graues Band unter dem Poster weg; Abstände in der Karte nur 4/8/12/16 px; Radius 8 px für Karte und Poster.
- [x] Hover der Karte neutral (Rand `--line-strong`, Fläche etwas heller) statt Amber; Tastaturfokus als Amber-Umriss der ganzen Karte (`:has(:focus-visible)`, sonst `:focus-within`). Amber danach nur für ♥ und Fokus.
- [x] Raster dichter: `minmax(180px, 1fr)`, Abstand 16 px (Handy 12 px, 2 Spalten). Ziel mit Seitenleiste rund 7 Karten bei 1760 px; nach K2 (ohne Seitenleiste) 6 bei 1440 px. Messen, nicht unter 160 px.
Detailfenster mit eigener Adresse:
- Es gibt keine Detailseite, nur das Detailfenster. Statt `/movie/:id` bekommt das Fenster eine eigene Adresse `?film=<key>` (entschieden 2026-11-17), nur im Frontend:
  - `href` = aktuelle Adresse plus `film=<filmKey>` (URL-kodiert; der Schlüssel ist meist die TMDB-ID, sonst „Titel|Jahr“). Land, Filter und Sortierung bleiben in der Adresse, ein neuer Tab zeigt also dieselbe Ansicht.
  - Normaler Klick: `preventDefault`, Fenster öffnen wie heute (`showFilmDetails`) und `history.pushState` mit `film`. Mittelklick, Strg-/Cmd-Klick und Umschalt-Klick lässt der Handler in Ruhe (Browser öffnet einen neuen Tab).
  - Schließen (X, Escape, Klick daneben): `film` aus der Adresse nehmen; war der Eintrag per `pushState` angelegt, mit `history.back()`, sonst `replaceState`. Zurück-Knopf des Browsers bei offenem Fenster schließt es (`popstate`), Vor-Knopf öffnet es wieder.
  - Beim Laden mit `?film=`: Fenster öffnen, sobald der Film in den Daten ist (gespeicherter Scan oder laufender Scan liefert ihn). Ist er nach dem Laden bzw. Scan-Ende nicht da (nicht mehr auf der Liste, anderes Land): kurzer Hinweis „Film not found on this watchlist“, `film` aus der Adresse nehmen. Ein Film, den nur die Filter ausblenden, öffnet trotzdem.
  - Die übrigen Adress-Schreiber (Filter-Link, `scan=`, Länderwechsel) nutzen `replaceState` auf der aktuellen Adresse und lassen `film` stehen; prüfen, dass keiner es löscht oder doppelt einträgt. „Share“ teilt bei offenem Fenster den Film mit.
  - Fokus: Beim Schließen zurück auf den Titel-Link der Karte (`openModal` sucht ihn per `data-key`); beim Öffnen per Adresse gibt es keinen Auslöser, dann Fokus auf `#results`.
  - Auch „Tonight“-Poster und Zeilen in „Coming soon“ bekommen denselben Link, damit jeder Film eine Adresse hat.
  - Tests: Browser (Klick öffnet und schreibt `?film=`, Zurück schließt, Seite mit `?film=` öffnet direkt, unbekannter Film zeigt den Hinweis, Strg-Klick öffnet nicht das Fenster), JS (Link-Adresse aus aktueller Adresse plus Schlüssel, falls als reine Funktion herausgelöst).
- Farben nur als OKLCH-Tokens, keine Hex-Werte aus den Vorlagen.
- Mitziehen: Fokus-Rückgabe in `openModal` (`app.js`, sucht heute `.film-details-button` per `data-key`), Klick-Handler für Details, Browser-Tests (Details öffnen, Tab-Stopps: jetzt Titel und ♥), `offerBadges` entfernen, wenn nichts anderes sie nutzt.
- Karte „Not currently available“ (`unavailableCard`) bekommt dasselbe Muster (Titel öffnet die Details).
Fertig, wenn:
- Klick irgendwo auf die Karte außer ♥ öffnet die Details; ♥ schaltet nur den Favoriten. Je Karte genau zwei Tab-Stopps (Titel, ♥); Enter auf dem Titel öffnet, Enter/Leertaste auf ♥ schaltet.
- Mittelklick oder Strg-Klick auf die Karte öffnet den Film in einem neuen Tab mit offenem Detailfenster; Zurück schließt das Fenster; ein geteilter `?film=`-Link öffnet den Film.
- Keine Angebots-Pille mehr; alle angehakten Dienste stehen als Logo auf der Karte, Abo ohne Abzeichen, Free/Ad/Rent mit, jedes Logo mit Alt-Text; derselbe Dienst steht auf allen Karten an derselben Stelle der Reihenfolge.
- Fußzeilen einer Reihe auf einer Höhe, keine Meta-Zeile bricht um, rund 7 Karten bei 1760 px und 2 am Handy (390 px).
- Mit der Datenkopie (`web-copy`) prüfen: langer Titel mit 3+ Diensten, Dienst mit mehreren Arten, Gratis-Dienst, ein Favorit, ein Film mit nur einem Dienst, einer ohne Letterboxd-Wert.
- Ergebnis (2026-11-17): gebaut wie geplant. Karte mit der Datenkopie: 387 px hoch statt rund 570 px, 7 Spalten bei 1760 px (dafür ist die Hauptseite jetzt bis 1800 px breit, `main:has(.workspace)`), 2 am Handy; Fußzeilen einer Reihe auf einer Höhe, keine Meta-Zeile abgeschnitten, lange Titel enden nach 2 Zeilen. Abweichungen: Logos 28 px statt 24 px, damit das Abzeichen nicht die halbe Marke verdeckt; das Herz bleibt mit der Maus anklickbar, auch wenn es unsichtbar ist (wer klickt, fährt vorher über die Karte; `pointer-events: none` hätte nichts gebracht); `aria-label` bleibt „Favorite: Titel“ mit `aria-pressed` (ein wechselnder Name zusammen mit `aria-pressed` wird doppelt angesagt). „No longer on …“ steht jetzt im Detailfenster unter den Diensten. „Tonight“, „Coming soon“ und „Recently gone“ sind ebenfalls Links mit `?film=`. Tests: JS (Laufzeit, Adresse, Titel-Link, Letterboxd zuerst, alle Dienste mit Abzeichen, Poster-Badge), Browser (Adresse: Klick, Zurück, Strg-Klick, geteilter und unbekannter Link; Tab-Stopps Titel und Herz).
- Prüfung mit dem Barrierefreiheits-Baum (2026-11-17, kein echter Screenreader installiert): Tab-Reihenfolge Skip-Link → Films → Titel → Herz stimmt, Herz meldet „pressed“, Dialog hat Namen und fängt den Fokus. Behoben: Fokus sprang nach dem Schließen auf „Films“, wenn vorher der Skip-Link `#results` in die Adresse geschrieben hatte (Skip-Link setzt jetzt nur den Fokus); Dienste wurden doppelt gelesen (Name der Liste und Alt-Text, Tooltip jetzt am Logo); „1h 47m“ hört sich wie Meter an, Screenreader bekommen „1 hour 47 minutes“; Poster auf der Karte ohne Alt-Text (der Titel-Link direkt darunter nennt den Film); Film-Links werden auch beim Fokus aktualisiert, damit „in neuem Tab öffnen“ per Tastatur die Filter mitnimmt.

## Teil B2: Gesamtkonzept „Das perfekte Gesamterlebnis“ (ab 2026-11-17)
Vorlage: `Film-App Das perfekte Gesamterlebnis.md` (Downloads). Die App beantwortet in unter 10 Sekunden: Was aus meiner Watchlist kann ich heute ohne Zusatzkosten schauen? Reihenfolge nach Wirkung: erst entfernen und umsortieren (9l, K1, K2), dann Veränderung zeigen (K3), dann neue Funktionen (K4 bis K6).
Leitregeln, jede Etappe wird daran geprüft:
1. Inhalt vor Bedienung: erster Film auf jedem Bildschirm ohne Scrollen, am Desktop zwei volle Poster-Reihen.
2. Jede Funktion genau einmal.
3. Einstellen ist nicht Filtern: Abos in den Settings, Genre und Laufzeit in der Filterleiste.
4. Kosten zuerst: Free → Subscription → With ads → Rent, in Umschalter, Karten und Farben (Abschnittsüberschriften im Raster entfallen mit K3b).
5. Veränderung (neu, gerade weg) steht oben, nicht eingeklappt. Gezeigt wird nur, was die Daten belegen; nichts wird geschätzt.
6. Alles ohne Hover erreichbar; Hover beschleunigt nur.
7. Möglichst wenige Schritte zum Film (echte Direkt-Links gibt es nicht, siehe „Nicht im Plan“).
8. Systemzustand ist leise: Scan-Status nur bei Fehlern oder auf Abruf.
Entscheidungen 2026-11-17:
- Oberfläche bleibt Englisch (PRODUCT.md); deutsche Filmtitel nur als Option (K6).
- Aussehen bleibt: heutige OKLCH-Farben, nur dunkel, eigener Schrift-Plan aus 9k. Aus dem Konzept kommen nur Maße (36 px Bedienhöhe, gleiche Grundlinie, Radien 6/8/12 px, 4er-Abstände, `tabular-nums`) und Ereignisfarben als neue Tokens (`--free`, `--soon`, `--gone`, in OKLCH).
- Neue Datenquellen: nur PWA (K6). Nicht: Direkt-Links über JustWatch, IMDb über OMDb, Suche im ganzen TMDB-Katalog.
- Abweichungen vom Konzept (abgewogen):
  - Karte: siehe 9l (kein Bedienelement und keine Bewertung auf dem Poster, ♥ statt Herz-und-Stern-Mix, Schnellaktionen als „⋯“-Menü in K4).
  - Kein Wischen auf Karten: kollidiert mit den waagerechten Reihen auf „Tonight“ und dem Zurück-Wischen des Systems; dafür „⋯“ und langes Drücken.
  - Keine Leihpreise, Qualität (HD/4K), Ton und Untertitel: TMDB liefert sie nicht. Reihe „Rent under 4 €“, Preis-Ereignis und Wunschpreis entfallen.
  - Kein „Leaving soon“ (entschieden 2026-11-17): TMDB liefert kein Ablaufdatum, und geschätzt wird nichts. Reihe, Badge, Sortierung, Push und Home-Assistant-Sensor dafür entfallen; kommt erst, wenn eine Quelle echte Daten liefert.
  - Karte: alle angehakten Dienste als Logos statt nur des günstigsten (siehe 9l).
  - Bewertungen: Letterboxd und TMDB (zwei statt drei).
  - Matches (manuelle Zuordnung) wandert in Settings → Data, nicht in Subscriptions.
  - Kalender-Zeitfenster und „Auf Fernseher öffnen“ entfallen (kein Kalender, keine Direkt-Links).
  - Favoriten-Status Plan/Watching/Watched wird zu Favorit (♥), „Watched“ und „Not now“; die Notiz bleibt (K4).
  - Tastenkürzel nach Konzept (`r` Zufall, `s` gesehen); `s` für Shuffle aus Etappe 14 entfällt.
Seiten (Ziel): Tonight (Start, `/`) · Watchlist (`/watchlist`) · Subscriptions · Stats · Settings (mit „Data & status“ und Matches).
Abgleich mit dem zweiten Auftrag `film-app-prompt.md` (Downloads, 2026-11-17): deckt sich weitgehend mit K1 bis K6. Bestätigt am selben Tag: gebaute Karte bleibt (alle Dienste, Bewertung in der Textzeile), heutiges Aussehen und nur dunkel, Oberfläche nur Englisch (keine Übersetzungsdatei), keine neuen Datenquellen außer der PWA (kein IMDb, keine Direkt-Links, keine TMDB-Gesamtsuche), kein „Leaving soon“ ohne echtes Datum. Abweichung vom Auftrag: fünf statt vier Seiten, weil „Stats“ ausdrücklich gewünscht war (Zahlen zur eigenen Watchlist, keine Fremd-Statistiken wie bei Trakt).
Arbeitsweise (aus dem Auftrag):
- Eine Etappe nach der anderen; danach kurz berichten (was geändert, welche Dateien, was testen) und auf OK warten.
- Sync, Letterboxd-Import und Dienst-Auswahl funktionieren nach jeder Etappe; neue Logik (Ereignisse, Filter, Sortierung) bekommt Unit-Tests.
- Vor dem Löschen von Daten oder Dateien auflisten, was genau wegfällt, und fragen.
- Farben, Abstände, Radien und Schriftgrößen nur als Tokens in `app.css`.
Abnahme am Ende jeder Etappe:
- Desktop 1440 × 900: erster Film ohne Scrollen, mindestens zwei volle Reihen (ab K3); Handy 390 × 844: nichts nur per Hover.
- Keine Funktion doppelt; jeder Filterzustand per Adresse reproduzierbar, Zurück funktioniert.
- Detailfenster: genau ein Hauptknopf, keine umbrechende Knopfreihe (ab K4).
- Kontrast aller Texte mindestens 4,5:1, mit Werkzeug gemessen; Filter auf 456 Filme unter 100 ms.
- Tests grün, keine Konsolenfehler; Screenshots vorher/nachher für Hauptansicht und Detailfenster (Desktop und Handy).

### Etappe K1: Aufräumen (nach 9l)
- [x] Überschrift „Find your next film.“ weg; Kopfzeile 56 px, beim Scrollen klebend und 48 px.
- [x] Navigation mit vier Seiten: aktive Seite weiß mit 2-px-Unterstrich in Amber, inaktive gedämpft grau. Status-Seite wird Settings → „Data & status“ (letzter Sync je Quelle, Filmzahl, Fehler der letzten 7 Tage; nimmt „Letzte Fehlermeldungen“ aus Etappe 17 auf), Matches dort als „Unmatched films“. Alte Adressen leiten weiter (301). Handy: Navigation unten mit 4 Symbolen und Beschriftung.
- [x] Sync-Punkt in der Kopfzeile: aktuell nichts, läuft (Ring + „214/456“), veraltet über 24 h (gelb), Fehler (rot, Klartext und Lösung). Klick zeigt Details und „Scan now“. „All films loaded.“ und „Scan now“ verschwinden aus der Hauptansicht; Kürzel `Shift+R` (K4).
- [x] „My subscriptions“ nur noch einmal.
- [x] Alle Bedienelemente einer Zeile 36 px hoch auf einer Grundlinie (heute steht die Sortierung versetzt); ein Schalter sieht aus wie ein Schalter („Available only“).
- [x] Notiz geht verloren, wenn ein Scan fertig wird, während man tippt (aus 9k).
- [x] Handy: „Wide view“ ausblenden (aus 9k).
- Fertig, wenn: Desktop 1440 × 900 zeigt zwei volle Poster-Reihen, Handy 390 × 844 den ersten Film ohne Scrollen.
- Ergebnis (2026-11-17):
  - Kopfzeile 56 px (beim Scrollen 48 px), klebt am Desktop oben; am Handy scrollt sie mit, die Seiten stehen unten als Leiste mit Symbolen. Die Überschrift ist nur noch für Screenreader da.
  - Drei Seiten statt fünf: Watchlist · Subscriptions · Settings („Tonight“ als vierte kommt mit K3). Settings hat Unterseiten General · Data & status (`/settings/data`) · Unmatched films (`/settings/matches`); `/status` und `/matches` leiten mit 301 weiter. „My subscriptions“ heißt in der Navigation „Subscriptions“, der Hinweis in den Settings ist weg.
  - Sync-Punkt: grau und ohne Text, solange die Daten frisch sind; Ring mit Prozent während eines Scans; gelb „Out of date“ nach 24 Stunden; rot „Scan failed“. Ein Klick öffnet das bisherige Scan-Feld (Meldung, Fortschritt, „Scan now“, „Cancel scan“, Fehlschläge). Abweichung: Prozent statt „214/456“.
  - „Wide view“ entfernt (Knopf, Code und CSS; eine gespeicherte Wahl wird gelöscht).
  - Werkzeugleiste, Filter und „Tonight“-Auswahl einheitlich 36 px hoch.
  - Notiz: Ein Neuzeichnen beim Tippen übernimmt Text und Cursor ins neue Feld (Browser-Test).
  - Offen aus dem zweiten Auftrag: Tokens für Abstände (4/8/12/16/24/32/48), Radien (6/8/12 px) und Schriftgrößen (12/13/14/16/20/24) anlegen und die Komponenten darauf umstellen; Kontrast von `--muted` auf allen Flächen mit Werkzeug prüfen. Eine Variante je Komponente: Knopf 36 px, Chip 28 px rund, Abzeichen 20 px.
  - Nicht erledigt: „Available only“ als Schalter; das Feld wird in K2 durch den Kosten-Umschalter ersetzt, Umbau vorher wäre doppelte Arbeit. Ziel „zwei volle Poster-Reihen bei 1440 × 900“ noch nicht erreicht: „Tonight“, Werkzeugleiste und Filter stehen über dem Raster (erste Karte bei 873 px); das lösen K2 (eine Leiste) und K3 (Tonight als eigene Seite). Am Handy sind die ersten Filme (Tonight) bei 137 px sichtbar.

### Etappe K1b: Nachbesserung und Statistik-Seite (2026-11-17, auf Rückmeldung)
- [x] Sync-Punkt öffnete nicht: `tabler.min.js` bringt ein zweites Bootstrap mit, ein Klick öffnete und schloss das Menü sofort. Jetzt ein `<details>`-Menü wie „More“ (schließt bei Klick daneben und mit Escape). Bei „Animationen aus“ in Windows (`prefers-reduced-motion`) dreht sich der Ring nicht, er pulsiert stattdessen langsam.
- [x] Filterfelder wurden bei mittlerer Breite (um 1000 px) abgeschnitten („Available on…“); die Reihe bricht jetzt um (`auto-fit`, mindestens 150 px je Feld). Geprüft bei 390, 1024 und 1440 px.
- [x] Statistik als eigene Seite `/stats` (Navigation „Stats“), statt des Kastens unten auf der Hauptseite (dort nur noch ein Link). Rechnung in `statistics.js` (getestet), Darstellung in `stats-page.js`: 16 Kennzahlen (Filme, verfügbar, auf eigenen Abos mit Stunden, gratis, im Abo, nur Leihen, nicht verfügbar, demnächst, Stunden gesamt, Ø Laufzeit, Ø Letterboxd, Ø TMDB, Jahre, Favoriten, neu und weg in 30 Tagen); eigene Abos mit „nur in diesem“ (was eine Kündigung kostet); Angebotsarten, Genres, Jahrzehnte, Laufzeit, Bewertungen (Letterboxd und TMDB), Sprache, Herkunftsland, Altersfreigabe, Regie, Schauspieler, Filmreihen, Stichworte; Änderungen je Dienst (30 Tage) und je Woche (8 Wochen); „Waiting longest“ und „Best rated on your subscriptions“; Tabelle aller Dienste mit Filmen, „Only here“, Stunden und Angebotsarten. Balkenlisten einfarbig mit Zahl daneben, Anteil im Tooltip, lange Listen hinter „Show n more“. Deckt die Punkte aus Etappe 13 (Laufzeit-Summe je Dienst, „Staubfänger“) zum Teil ab; Statistik über die Zeit (gespeicherte Scan-Stände) fehlt noch.

### Etappe K2: Eine Filterleiste (Watchlist-Seite)
- [x] Seitenleiste fällt weg. Eine klebende Leiste, eine Zeile: Suche (`/`), Dienste-Chip (bis 4 Logos + „+8“, Popover mit Gruppen My subscriptions · Free · Rent, Häkchen und Filmzahl je Dienst), Kosten als Umschalter All · Free · Subscription · Rent (ersetzt „Available only“), Genre (Mehrfachauswahl, Alt-Klick schließt aus), Laufzeit, Bewertung (Quelle Letterboxd oder TMDB), „Filters (n)“ für den Rest, Sortierung rechts.
- [x] Eine Quelle für „meine Dienste“: Settings → My services legt sie fest, der Chip filtert nur. Details („Your service“, „Similar on your services“) und Tonight nutzen dieselbe Quelle (offener 9k-Punkt).
- [x] Aktive Filter als Chips in einer zweiten Zeile, nur wenn welche aktiv sind, davor „47 of 456 films“, dahinter „Reset all“; eine Live-Region sagt die Anzahl an.
- [x] Trefferzahl je Option unter Berücksichtigung der anderen Filter; Optionen mit 0 Treffern grau, nicht versteckt. Filter wirken sofort, ohne Animation.
- [x] Leerer Zustand: „No film fits. Without the runtime filter there would be 12.“ mit Knopf, der genau diesen Filter entfernt.
- [x] Sortierung auf acht: Priority · Letterboxd · TMDB · Runtime · Year · Recently added · Newly available · Random. „Priority“ = Favoriten zuerst, dann Letterboxd. Ersetzt den 9k-Punkt (11 Einträge ohne Erklärung).
- [x] Ganzer Zustand in der Adresse (Filter und `film=` aus 9l); Vor und Zurück funktionieren.
- [ ] Die Liste aller Dienste nur noch in Settings → My services (Gruppen My subscriptions · Free · Rental shops · Others; Voreinstellungen „Free only“ und „All rental shops“ nur dort).
- [x] Handy: ein Knopf „Filters“ öffnet ein Blatt von unten mit aufklappbaren Abschnitten und festem Knopf „Show 47 films“.
- [ ] Aus dem zweiten Auftrag: Watchlist zieht nach `/watchlist` um (`/` wird in K3 „Tonight“; alte Links mit Filtern leiten weiter). „Filters (n)“ enthält Jahrzehnt, Sprache, Land, Altersfreigabe, nur Favoriten und „auch nicht verfügbare zeigen“ (deutsche Untertitel nicht: keine Daten). Laufzeit mit festen Stufen plus Schieberegler. Popover: Escape schließt, Pfeiltasten wandern, Leertaste hakt an. Eine Live-Region sagt die Trefferzahl. Messen: Filter auf 456 Filme unter 100 ms.
- Beim Bauen messen: Trefferzahlen je Option bei 456 Filmen unter 100 ms.
- Ergebnis (2026-11-17):
  - Eine Leiste unter der Kopfzeile, klebend: Suche · Dienste (Logo-Stapel + „+n“, Menü mit Gruppen My subscriptions · Free · Rental shops, je Gruppe „All“, Filmzahl je Dienst, „any/all“, Clear, Link zu den Abos) · Kosten als Umschalter All · Free · Subscription · Rent mit Zahl · Genre (Mehrfachauswahl, „No“ oder Alt-Klick schließt aus, Zahl je Genre) · Runtime (Stufen und Schieberegler) · Rating (Letterboxd oder TMDB in einer Auswahl) · Filters (n) · Sortierung. Neu: `filterbar.js`; Popovers als `<details>` mit Escape, Klick daneben und Pfeiltasten.
  - Eine Quelle: die angehakten Dienste gelten jetzt auch im Detailfenster („Your service“, „Similar on your services“) und für „Recently gone“ (so wie für Tonight entschieden). Abweichung vom Plan: Die Liste aller Dienste stand schon auf der Abo-Seite; dort bleibt sie, Settings bekommt keine zweite.
  - Chips: „47 of 430 films“ in der Zeile darunter; Chips für Dienste (wenn anders als die Abos), Genres, Ausschlüsse und jedes Feld; „Reset all“ setzt auch die Dienste zurück.
  - Leeres Ergebnis: „Without the runtime filter there would be 12.“ mit Knopf, der genau diesen Filter entfernt.
  - Acht Sortierungen: Priority (Standard; Favoriten, dann Letterboxd) · Letterboxd · TMDB · Shortest first · Newest first · Recently added · Newly available · Random (gleiche Reihenfolge pro Besuch). Entfallen: Titel, älteste, Trending, Stimmen, Bewertung pro Stunde, am längsten auf der Watchlist, auf meisten Abos, Filmreihen zusammen. Alte Links mit diesen Werten fallen auf Priority zurück.
  - Adresse: `cost`, `genre`, `nogenre`, `max`, `rating=lb:3.5|tmdb:7`, `unavailable=1`, `match`; alte Links (`availability`, `kind`, `runtime=short|medium`, `rating=7`, `lb`) werden umgedeutet.
  - Handy: „Filters“ öffnet die Leiste als Blatt von unten (Dialog, Seite dahinter `inert`, Escape, „Show 47 films“).
  - Weggezogen statt gelöscht: CSV-Upload ins Sync-Feld, „any/all“ und der Hinweis „filtert nur“ ins Dienste-Menü; „Mostly free“ steht im Menü. „Offer type“ (free/ads/flatrate/rent) entfällt, der Kosten-Umschalter deckt es ab; „Unavailable only“ wird zu „Also show films not available“.
  - Gemessen mit der Datenkopie (430 Filme): Filtern 4 ms, alle Zählungen 19 ms; mit dem Neuzeichnen der rund 170 Karten 60–140 ms. Die Grenze von 100 ms reißt also das Zeichnen, nicht die Logik (Virtualisierung o. Ä. in K6).
  - Offen: Umzug nach `/watchlist` mit K3 (vorher nur eine Weiterleitung); „zwei volle Reihen bei 1440 × 900“ erst mit K3 (Tonight über dem Raster). `templates/partials/provider-sidebar.html` gelöscht (2026-11-17).

### Etappe K3: Veränderung sichtbar machen (Startseite „Tonight“)
- [x] Ereignisse aus dem gespeicherten Verlauf (Etappe 6), überall gleich: New (grün, „New · since 12 Nov“) und Gone (gedämpftes Rot, „Gone since 10 Nov“), beide mit echtem Datum aus dem Scan. Wechselt ein Film nur zwischen zwei eigenen Diensten, gibt es kein Ereignis.
- [x] „Gone“ zeigt den Ausweg: „Gone from Netflix · now on Prime (subscription)“ oder „Rent only“.
- [x] Startseite „Tonight“ als Feed aus waagerechten Reihen: New on your services → Free (free und ads) → eine Reihe je Abo nach Filmzahl („On Netflix (73)“) → Recently gone (eingeklappt, ganz unten). Leere Reihen fehlen. Je Reihe Titel und Zahl, rechts „See all →“ (Watchlist mit passendem Filter). Einrasten an Kartenkanten, Kanten ausgeblendet (Designregel), Pfeilknöpfe bei Hover und Fokus, am Handy 2,5 Karten sichtbar.
- [x] Kontextzeile: „285 films available on 12 services · synced 2 h ago“, Klick auf die Dienste öffnet die Auswahl; Knopf „Pick for me“ (Zufall aus den Treffern, öffnet die Details; „Again“ ohne Wiederholung in der Sitzung). Ersetzt „Shuffle“.
- [x] Schnellfilter-Chips über den Reihen, Mehrfachauswahl: Under 2 h · Under 100 min · Highly rated · Free only (· With partner, erst mit Etappe 15). Ersetzt Laufzeit und Genre im heutigen „Tonight“-Kasten.
- [x] Badge „Gone“ auf den Karten (Badge aus 9l).
- [x] Aus dem zweiten Auftrag: Ein Film gilt erst als „gone“, wenn ihn zwei Scans nacheinander nicht finden (schützt vor TMDB-Aussetzern). Unit-Tests für New, Gone, Wechsel zwischen zwei eigenen Diensten und die Zwei-Scan-Regel. Reihen sortiert: Favoriten zuerst, dann Letterboxd. „Pick for me“ auch mit `r`. Am Handy 2,5 Karten je Reihe sichtbar.
- [x] Änderungsprotokoll als Tab „Changes“ auf der Watchlist-Seite (Datum · Film · Dienst · Ereignis, neueste zuerst, filterbar); ersetzt „Scan changes“ und den Kasten „Recently gone“. Damit erledigt sich der 9k-Punkt „Film aus Tonight steht doppelt im Raster“.
- Fertig, wenn: 1440 × 900 zeigt Kontextzeile, Chips, die erste Reihe ganz und den Titel der zweiten.
- Ergebnis (2026-11-17):
  - `/` ist jetzt „Tonight“, die Watchlist liegt unter `/watchlist`. Alte Links auf `/` mit Filtern leiten dorthin weiter (301); `/?film=` öffnet den Film auf Tonight. Navigation: Tonight · Watchlist · Subscriptions · Stats · Settings.
  - Tonight: Kontextzeile („168 films available on 10 services · synced 4 h ago“, die Dienste verlinken auf die Abo-Seite statt eines eigenen Menüs), „Pick for me“ (auch Taste `r`, „Again“ ohne Wiederholung im Besuch), Chips Under 2 h · Under 100 min · Highly rated (Letterboxd ≥ 3.7, sonst TMDB ≥ 7.5) · Free only (im Browser gespeichert). Reihen: New on your services (14 Tage) → Free → eine Reihe je angehaktem Abo nach Filmzahl; je „See all →“ zur passend gefilterten Watchlist. Waagerecht scrollend mit Einrasten, Kante ausgeblendet, Pfeile bei Hover/Fokus, am Handy rund 2,5 Karten. Gesehene Filme fehlen, Favoriten zuerst. „Recently gone“ (30 Tage) unten eingeklappt mit „now on Prime Video (subscription)“ / „rent only on …“ / „not streaming anywhere“.
  - Zwei-Scan-Regel im Backend (`history.diff_scans(..., older=)`, `store.recent_scans`): „removed“ erst nach zwei Scans ohne den Dienst, ein Dienst nach einem Aussetzer zurück ist nicht „neu“. Verlauf jetzt 30 statt 14 Tage. Wechsel zwischen zwei angehakten Diensten erzeugt weder „New“ noch „Gone“ (`events.js`).
  - Watchlist: Tabs Films · Changes; Changes ist eine Tabelle (Datum · Film · Dienst · Ereignis), filterbar nach Dienst, Ereignis und „nur angehakte Dienste“. Der alte Tonight-Kasten, „Recently gone“ und „Scan changes“ sind dort weg (damit auch die Doppelung aus 9k). Karten zeigen „Gone“, wenn ein angehakter Dienst den Film verloren hat.
  - Abnahme: 1440 × 900 zeigt Kontextzeile, Chips, die erste Reihe ganz (Unterkante 589 px) und den Titel der zweiten (617 px). Handy: erste Reihe ab 252 px.
  - Tests: Python (Zwei-Scan-Regel, Rückkehr nach Aussetzer, Scan-Ablauf), JS (`events.test.mjs`: New, Wechsel, Gone mit „now on“, Reihen, Chips, Pick), Browser (Tonight, Weiterleitung). Entfernt: Abend-Logik `eveningSuggestions`, `recentlyRemoved`, `changeSummary` und ihre Tests.

### Etappe K3b: Kopfzeile, Filter und Sortierung (2026-11-17, auf Rückmeldung; gebaut 2026-11-18)
Aufgenommen aus: „Kopfzeile überall gleich“, „Filter am Handy verbuggt“, „Free & with ads / Subscription & rent unten entfernen“, „weitere Filter verbuggt“, „Sortierung besser unterteilen“. Abgleich mit dem Plan: Kopfzeile und Sortierung waren in K1/K2 nur als eigene Punkte erledigt, eine einheitliche Kopfzeile auf allen Seiten war nicht geplant. Die Abschnitte standen in Leitregel 4 („Kosten zuerst … in Abschnitten“) und werden hier bewusst gestrichen, weil der Kosten-Umschalter oben dasselbe leistet; die Karten zeigen die Angebotsart weiter an jedem Dienst (Ad, €).
Befund (am 2026-11-17 mit der Datenkopie gemessen):
- Kopfzeile: Nur Tonight und Watchlist haben die Kopfzeile mit Land und Sync-Punkt. Subscriptions, Stats und Settings haben stattdessen eine eigene Zeile nur mit der Navigation, ohne Land und ohne Sync, dafür mit sichtbarer Überschrift. Am Handy ist die Kopfzeile 117 px hoch (Markenzeile, darunter ein Knopf „Filters“ über die volle Breite); der Knopf steht auch dort, wo es keine Filter gibt (Tonight).
- Filter-Blatt am Handy: Es ist 495 px hoch und endet bei 832 px; die untere Navigation beginnt bei 783 px und überdeckt den Knopf „Show n films“ (Höhe 772–816 px). Bewertung und Sortierung sind 36 px hoch, der Rest 44 px. Felder haben keine sichtbaren Beschriftungen (nur die Voreinstellung als Text), das Blatt hat keine Überschrift und kein ×. Nicht geprüft: Bildschirmfoto im Browser-Fenster war verzerrt, die Werte stammen aus den Messungen der Elemente.
- „Filters (n)“: zwölf Felder in einem Raster ohne Gruppen; Auswahlfelder zeigen nur „Any language“, „Any country“ usw., ohne Beschriftung, was sie bedeuten, sobald etwas gewählt ist. Bei 1024 px bricht die Leiste in zwei Zeilen um (101 px hoch).
- Abschnitte im Raster: „Free & with ads“ und „Subscription & rent“ (`SECTION_TITLES` in `rendering.js`).
- Sortierung: acht Einträge in einer flachen Auswahl mit dem Vorsatz „Sort:“, ohne Erklärung („Priority“).
Plan:
- [x] Eine Kopfzeile auf allen Seiten, ein Partial: Marke · Seiten-Navigation · Land · Sync-Punkt (am Handy: Marke, Land, Sync in einer Zeile à 56 px, Seiten unten wie heute). Der Knopf „Filters“ wandert aus der Kopfzeile in die Seite (Watchlist; auf Tonight entfällt er). Sync-Punkt und Land funktionieren dann überall; die Überschrift jeder Seite bleibt sichtbar im Inhalt (Seitentitel, nicht in der Kopfzeile). Seiten: `index.html`, `subscriptions.html`, `stats.html`, `settings.html`, `status.html`, `matches.html`; `app.js` verdrahtet Land und Sync heute nur auf der Hauptseite, das Skript muss auf den anderen Seiten dafür geladen werden (klein, eigene Datei `header.js`).
- [x] Abschnitte „Free & with ads“ / „Subscription & rent“ im Raster entfallen: ein Raster, Reihenfolge nach der Sortierung. `SECTION_TITLES`, die Gruppierung in `renderResults` und die zugehörigen Tests/CSS gehen weg; die Abschnitts-Logik für die Dienst-Zeile auf der Karte (`SECTION_KINDS`) bleibt, sie bestimmt, welche Angebote die Karte zeigt. Das ändert die Reihenfolge: Priority sortiert Favoriten dann Letterboxd, nicht mehr „erst gratis, dann bezahlt“; der Umschalter „Free / Subscription / Rent“ ersetzt das.
- [x] Filter-Blatt am Handy neu: Überschrift „Filters“ mit ×, Blatt bis 90 dvh, untere Navigation und Kopfzeile darunter versteckt, solange es offen ist, fester Fuß mit „Show n films“ und „Reset“ (über der Systemleiste, `env(safe-area-inset-bottom)`), alle Felder 44 px, Seite dahinter gesperrt (`overscroll-behavior`), Beschriftung über jedem Feld, Abschnitte Search · Where (Dienste, Kosten) · Film (Genre, Laufzeit, Bewertung) · More. Prüfung mit 390 × 844 und 360 × 640 (kleines Handy), mit geöffneter Tastatur.
- [x] „Filters (n)“ gruppieren und beschriften: Release (Year from/to, Age rating, Original language, Country) · Quality (Minimum votes, Keyword, Trailer) · Availability (On n+ services, Only on one of my services, Newly available / No longer available, Also show films not available). Sichtbare Beschriftung über jedem Feld, die Voreinstellung bleibt „Any …“. Menü hat `max-height` und scrollt innerhalb des Fensters; am Handy sind die Gruppen die Abschnitte im Blatt.
- [x] Jeden der 16 Filter durchprüfen (Desktop 1440 und 1024, Tablet 768, Handy 390): setzen → Chip erscheint → Zahl stimmt gegen die Rechnung aus `/api/latest` → Adresse enthält ihn → Zurück stellt ihn her → „Reset all“ löscht ihn. Gefundene Fehler einzeln beheben, je Fehler ein Browser-Test. Bei 1024 px soll die Leiste in einer Zeile oder in einer sauberen zweiten Zeile stehen (kein Abschneiden).
- [x] Sortierung als Menü mit Erklärung (entschieden 2026-11-18, `<details>`-Popover wie die anderen Filter, Auswahl per Radio, Pfeiltasten): Gruppen Best rated (Priority: favorites first, then Letterboxd · Letterboxd rating · TMDB rating) · By film (Shortest first · Newest first) · By availability (Recently added: when it joined your Letterboxd list · Newly available: when a service added it) · Random (same order per visit). Je Eintrag eine Zeile Erklärung; der Knopf zeigt „Sort: Priority“. Am Handy ein Abschnitt im Blatt.
- Abnahme: Alle Seiten zeigen dieselbe Kopfzeile (gleiche Höhe, gleiche Elemente); am Handy sind „Show n films“ und alle Felder erreichbar und tippbar; kein Filter schneidet Text ab; Tests grün, keine Konsolenfehler; Bildschirmfotos vorher/nachher.
- Ergebnis (2026-11-18):
  - Korrektur zum Befund: Der Knopf „Show n films“ war nicht von der Navigation überdeckt (die Messung zeigte einen Treffer im Knopf). Der Fehler war ein Außenabstand von 12 px (`margin-bottom` der Leiste), der das Blatt über den Bildschirmrand hob, sodass darunter die Navigation hervorschaute.
  - Kopfzeile: ein Partial (`header.html`) für alle sieben Seiten, direkt unter dem Seitenrand (volle Breite), gleiche Höhe und gleiche Lage von Marke, Navigation, Land und Sync-Punkt (gemessen). Auf Tonight/Watchlist öffnet der Punkt das Scan-Feld, auf den anderen Seiten ist er ein Link zu Settings → Data & status mit „Synced“ oder „Out of date“ (nur frisch oder älter als 24 h; „Scan failed“ gibt es dort nicht). Das Land ändert auf den anderen Seiten die Einstellung und öffnet die Watchlist (`header.js`). Der Knopf „Filters“ steht am Handy über der Leiste in der Seite, nicht mehr in der Kopfzeile; auf Tonight gibt es ihn nicht. Handy-Kopfzeile eine Zeile à 56 px (vorher 117 px).
  - Raster: keine Abschnittsüberschriften mehr; `filterFilms` liefert zusätzlich `films` (jeder Film einmal, in der gewählten Reihenfolge) und `sectionOf` (Film in beiden Abschnitten bekommt die Karte „All“ mit allen angehakten Diensten; der Kosten-Umschalter begrenzt weiter, welche Angebote gelten). Tonight verwendet unverändert „Free“ und „Paid“.
  - Filter-Blatt am Handy: Überschrift mit ×, Beschriftungen (Services, Cost, Rating, Sort by), alle Felder 44 px, abgedunkelte Seite dahinter (Tippen schließt), Seite gesperrt, bis 90 dvh, Fuß mit „Reset“ und „Show n films“.
  - „Filters“: drei Gruppen (Release · Quality · Availability) mit sichtbaren Beschriftungen, am Handy untereinander. Auswahlfelder haben wieder ihren Pfeil.
  - Sortierung: Menü mit Gruppen Best rated · By film · By availability · Other und einer Zeile Erklärung je Eintrag; Knopf „Sort: Priority“. `SORTS` in `web/routes.py` trägt Gruppe und Text; `#sort-order` ist jetzt ein verstecktes Feld.
  - Filter durchgeprüft (Datenkopie, 168 sichtbar): Alter, Sprache, Land, Stimmen, Trailer, Änderungen, Mindestzahl Dienste (0 Treffer stimmt: kein Film läuft auf 3 angehakten Diensten), „Only on one of my services“ (131 = Daten), Jahr von/bis, „Also show films not available“ (26 weitere), Bewertung, Laufzeit, Kosten, Suche; jeder setzt Chip und Adresse und lässt sich zurücksetzen. Keine Fehler gefunden, die das Blatt-Problem überstiegen.
  - Offen: Bei 1024 px steht die Leiste in zwei Zeilen (Bewertung und Sortierung rutschen nach unten); das löst K3c (Filter rutschen in „Filters“). Bewertung ist noch ein Auswahlfeld statt Panel (K3c).

### Etappe 17a: Docker-Grundlage (vorgezogen 2026-11-18, vor K3c)
Warum jetzt: Die App ist Alltagswerkzeug auf dem Unraid-Server. Zeitplan (K5), Benachrichtigungen, PWA (braucht dauerhaft erreichbare Adresse mit HTTPS) und echte Daten über Wochen setzen einen Dauerbetrieb voraus; die Datei-Sicherung und die Härtung aus 8a sind schon da. Der Aufwand ist klein, weil `Dockerfile` und `docker-compose.yml` bestehen. Docker ist auf diesem PC vorhanden (Docker Desktop, muss gestartet sein); das Image wird hier gebaut und zusätzlich bei GitHub getestet.
- [x] Gesundheit: `/health` (gibt es) prüft zusätzlich die Datenbank und ob der Zeitplan läuft; der Docker-Healthcheck und die Unraid-Anzeige nutzen ihn.
- [x] `docker-compose.yml`: `TMDB_API_KEY`, `LETTERBOXD_USERNAME`, `COUNTRY`, `TZ` als Umgebungsvariablen (die Werte kommen aus einer `.env` neben der Datei oder aus Unraid; nie ins Image), Datenordner `./data:/data`, Neustart-Richtlinie.
- [x] Nicht-root: ein Start-Skript legt den Benutzer aus `PUID`/`PGID` an (Unraid-Standard 99/100), setzt die Rechte auf `/data` und startet `gunicorn` mit diesem Benutzer.
- [x] Automatische tägliche Sicherung in `/data/backups/` (die letzten 7 bleiben), mit Test für das Aufräumen alter Dateien.
- [x] GitHub Actions: Image bauen, als Container starten, auf „healthy“ warten, `/health`, `/` und `/api/latest` abfragen (ohne TMDB-Schlüssel muss die Seite trotzdem starten und die Einrichtung zeigen). Veröffentlichen nach `ghcr.io` nur, wenn du es willst (Push und Zugangsdaten sind deine Sache).
- [x] Unraid: Vorlage `unraid-template.xml` (Port 5000, `/data` auf `/mnt/user/appdata/watchlist-availability`, die Variablen oben) und ein Abschnitt in der README: Installation, Update, Sicherung wiederherstellen.
- [x] Hinweis in der README: Die App hat keine Anmeldung. Nur im Heimnetz betreiben oder hinter einem Reverse-Proxy mit Anmeldung (dort auch HTTPS für die PWA); Zugriffsschutz in der App selbst bleibt „nicht im Plan“.
- Abnahme: `docker compose up` startet auf einem frischen Ordner, die Einrichtung erscheint, nach den Variablen läuft der erste Scan; der Container läuft nicht als root; ein Neustart behält die Daten; die GitHub-Prüfung ist grün. 
- Ergebnis (2026-11-18, selbstständig):
  - `/health` prüft Datenbank und Zeitplan-Thread (503 mit Grund); `watchlist_app/backups.py` schreibt täglich `backups/backup-JJJJ-MM-TT.json` (7 bleiben, erst `.tmp`, dann umbenannt) aus dem Zeitplan-Thread; Tests dafür in `tests/test_backups.py`.
  - `docker-entrypoint.sh` (gosu, `PUID`/`PGID`, Standard 99/100), `Dockerfile`, `docker-compose.yml` mit den Variablen, `.env.example`, `.gitattributes` (LF für Skripte), `unraid-template.xml`, README-Abschnitt, `.github/workflows/docker.yml`.
  - Lokal mit echtem Docker geprüft: Image baut, Container wird „healthy“, `/`, `/api/latest` und `/health` antworten, PID 1 läuft als UID 1001, die Dateien in `/data` gehören 1001, `backups/` entsteht, Neustart behält die Daten. Gefundener Fehler: gunicorn 27 wollte einen Steuer-Socket im Heimordner des Benutzers (`/home/app`, nicht vorhanden); behoben mit `--no-control-socket`.
  - Nicht geprüft: Lauf in Unraid selbst und die GitHub-Prüfung (Push ist deine Sache).

### Etappe K3c: Filterleiste nach Abschnitt 5 (2026-11-18, aus `abschnitt-5-filter.md`; gebaut 2026-11-18)
Abgleich: Das meiste steht seit K2 (eine Leiste, Kosten mit Zahlen, Logo-Stapel mit Menü, Genre mit Ausschluss, Chips, Trefferzahl je Option, Leer-Hinweis, Zustand in der Adresse, Sortierung mit Text). K3c baut nur den Unterschied. K3b (Fehler und Aufräumen) kommt zuerst, K3c danach, weil beide dieselben Dateien berühren (`film-filters.html`, `filterbar.js`, `app.css`).
Übernommen:
- [x] Dienste-Menü: Suche im Menü (fehlt), Kopfschalter „Only my services“ (Standard an; aus zeigt die Gruppe „All others“), Zusatz bei Verwechslungsgefahr („Prime Video“ / „Prime Video Channels“, „Apple TV+“ / „Apple TV Store“), Breite 360 px, höchstens 70 % der Höhe. „All“ je Gruppe, „Reset“ und der Link zu den Abos sind schon da.
- [x] Jahr, Laufzeit, Bewertung als Panels mit Schnellwahl-Chips, Regler und „Reset“ nur bei aktivem Filter: Jahr (Chips 2020s · 2010s · 2000s · Before 2000, Zwei-Griff-Regler 1920 bis heute, ersetzt „Year from/to“ in „Filters“), Laufzeit (Chips vorhanden, Regler 5-min-Schritte, bis 3 h+), Bewertung (Quelle Letterboxd | TMDB als Umschalter, Chips 3.5+ · 3.8+ · 4.0+, Regler 0.1-Schritte). Mindest-Stimmen (Any · 1k+ · 10k+ · 100k+) wandern in das Bewertungs-Panel, „Minimum votes“ aus „Filters“ entfällt. Chip und Regler sind gekoppelt. Pfeiltasten verschieben den Regler, Umschalt+Pfeil in 10er-Schritten.
- [x] Altersfreigabe als Chips statt Auswahlfeld, Mehrfachauswahl, immer von jung nach alt. Die Werte kommen aus den Daten des Landes (Deutschland 0 · 6 · 12 · 16 · 18, USA G · PG · PG-13 · R · NC-17 …); Überschrift „Age rating“, in Deutschland „FSK“.
- [ ] (verschoben, siehe Ergebnis) „My favorites“ wandert aus der zweiten Werkzeugzeile als Schalter in „Filters“ (offener Punkt aus K2); die Leiste bleibt die einzige Filterzeile. Der Favoriten-Status-Filter (Plan/Watching/Watched) entfällt mit K4 (Favorit, Watched, Not now).
- [x] Aktive Chips: × löscht genau diesen Filter, Klick auf den Text öffnet das zugehörige Panel (heute löscht jeder Klick). Alle Chips bleiben, es gibt keinen aktiven Filter ohne Chip.
- [x] Kosten-Chips: eine Option mit 0 Treffern ist deaktiviert (40 %, nicht klickbar, Tooltip „No films with current filters“) statt nur grau.
- [ ] (anders gelöst, siehe Ergebnis) Schmale Breiten (Tablet): Genre, Laufzeit und Bewertung wandern nacheinander in „Filters“; Kosten, Dienste und Suche bleiben sichtbar. Höhe Leiste plus Chip-Zeile höchstens ca. 100 px bei 1440 px, 1024 px bricht nicht in zwei Zeilen (bei K3b zuerst gemessen).
- [x] Panels: Pfeil am Auslöser dreht sich nach oben; Fokus kehrt nach dem Schließen zurück (ist schon so).
Nicht übernommen (abgewogen):
- „Leaving soon first“ als Sortierung: entfällt, TMDB liefert kein Ablaufdatum (entschieden 2026-11-17).
- Sortierrichtung mit Pfeil („Letterboxd ↓“): jede Sortierung hat nur eine sinnvolle Richtung; das Sortier-Menü mit Erklärung (K3b) sagt sie in Worten.
- Deutsche Untertitel: keine Daten.
- Hinter dem Panel um 30 % abdunkeln: Filter wirken sofort, und man soll die Poster dahinter sehen; das Menü hebt sich mit hellerer Fläche (`--surface-raised`) ab.
- Zwei-Griff-Regler für Laufzeit und Bewertung: ein Mindestwert (Bewertung) und ein Höchstwert (Laufzeit) decken die Fälle ab; nur das Jahr braucht zwei Griffe.
- Neue Adress-Schlüssel (`svc`, `rt`, `genre=thriller,-horror`): bleiben wie heute (`providers`, `max`, `genre`/`nogenre`, `rating=lb:3.8`); auch Jahr (`from`/`to`) und Stimmen (`votes`) behalten ihre Schlüssel, es kommt kein neuer hinzu. Alte Links bleiben gültig.
- Suche erst ab 2 Zeichen: bleibt ab dem ersten Zeichen (bei 430 Filmen 4 ms).
Verschoben auf K6 (stand dort schon): Ansicht Grid · Compact · Table (Knöpfe in der Leiste ganz rechts) und gespeicherte Ansichten („Save view“ in der Chip-Zeile, Auswahl links in der Leiste, Chips auf Tonight).
- Abnahme: Filter auf 430 Filmen unter 100 ms; jeder Zustand per Adresse reproduzierbar und mit Zurück herstellbar; alle Bedienelemente mit Tastatur; Tests (JS für Regler- und Chip-Kopplung, Jahr-Chips, Altersgruppen je Land; Browser für Dienste-Suche, Chip-Klick öffnet Panel) grün.
- Ergebnis (2026-11-18, selbstständig):
  - Dienste-Menü: Suche im Menü, Schalter „Only my services“ (an: Gruppen My subscriptions · Free · Rental shops; aus oder bei einer Suche kommt „All others“ mit den übrigen 169 Diensten), Breite 360 px, höchstens 70 % der Höhe.
  - Neue Panels „Year“ (Chips 2020s · 2010s · 2000s · Before 2000, Zwei-Griff-Regler, „Reset“) und „Rating“ (Umschalter Letterboxd | TMDB, Chips mit Trefferzahl, Regler mit 0.1-Schritten, Votes-Chips Any · 1k+ · 10k+ · 100k+, „Reset“); die Felder Jahr und Mindest-Stimmen sind aus „Filters“ weg. Die Adresse bleibt (`from`, `to`, `rating=lb:3.8`, `votes`); die Panels lesen immer die versteckten Felder, Links und „Reset all“ stimmen so von selbst.
  - Altersfreigabe als Chips mit Mehrfachauswahl und Trefferzahl (in Deutschland „FSK“), von jung nach alt. Die Adresse heißt jetzt `ages=6,12` (eine gewählte Menge, nicht mehr „bis N“); alte `age=16`-Links werden beim Laden in die Menge „alle bis 16“ umgedeutet.
  - Aktive Chips: Text öffnet das zugehörige Panel (Fokus kommt hin), × entfernt genau diesen Filter; zwei Knöpfe je Chip (Tastatur). Kosten-Optionen ohne Treffer sind deaktiviert (nicht klickbar, Tooltip), die gewählte bleibt klickbar. Pfeil an den Auslösern dreht sich beim Öffnen.
  - Gemessen bei 1440 px: Leiste 57 px + Chip-Zeile 24 px, erster Film bei 314 px.
  - Abweichungen (entschieden): „My favorites“ bleibt in der Werkzeugzeile; es schaltet eine eigene Ansicht (Notizen, Banner), keinen reinen Filter, und der Umzug würde einen Klick mehr kosten; neu bewerten mit K4. Bei schmalen Breiten wandern Genre, Laufzeit und Bewertung nicht in „Filters“ (die Felder würden doppelt vorkommen), die Leiste bricht in zwei saubere Zeilen um. Zusätze bei verwechselbaren Namen entfallen, weil die Dienstnamen schon ausgeschrieben sind („Prime Video Amazon Channel“). Laufzeit behält Chips und Regler ohne eigenen „Reset“-Knopf (die Option „Any length“ und das Chip-× leisten es).
  - Tests: JS (Altersmenge), Browser (Dienste-Suche, Jahr- und Rating-Panel, Chip öffnet Panel, Alters-Chips, Menüs im Fenster).

### Teil C: Abos-Seite (2026-11-18, aus `abschnitt-9-abos.md`; geplant, nichts gebaut)
Die Seite beantwortet eine Frage: Welche Abos lohnen sich für meine Watchlist, welche kann ich kündigen, und was tue ich vorher? Sie ersetzt „My subscriptions“ (Matches liegt seit K1 in Settings). Der Abschnitt deckt sich teilweise mit K5 (Tabelle, Rotation, „Worth a trial month“); diese drei Punkte in K5 werden durch die Etappen A1 bis A5 ersetzt, Benachrichtigungen und Zeitplan bleiben in K5.
Abweichungen vom Abschnitt (abgewogen, weil die Daten fehlen oder der Plan etwas anderes entschieden hat):
- Ablaufdaten von Filmen („Leaving“-Spalte, „8 films leave this month“, „Watch these first“, `leaving_boost`, Rotation nach „bald weg“, „leaves on“ im Kalender, Sensor „films leaving soon“) entfallen: TMDB liefert kein Ablaufdatum, geschätzt wird nichts (entschieden 2026-11-17). Das Fristen-Banner bleibt, nutzt aber nur das vom Nutzer eingetragene Datum („Netflix renews on 21.11.“). Die Wertformel läuft ohne `leaving_boost`.
- „Used“ und „€ pro gesehenem Film“ entfallen: das Letterboxd-Tagebuch wäre eine neue Datenquelle (entschieden: keine außer der PWA). Die Spalte wird nicht gebaut; „€ / film“ bleibt Preis geteilt durch „Only here“.
- Vorgeschlagene Standardpreise („approx.“) entfallen: Preise ändern sich, es zählt nur die Eingabe des Nutzers. Ebenso Leihpreise, „Rent instead“-Karte und Preisalarm (entschieden 2026-11-17) und der Hinweis „Filme nur in höherer Stufe“ (keine Daten über Stufen). Das Feld „Plan“ (With ads · Standard · Premium) bleibt als reine Notiz des Nutzers.
- Darstellung: Zahlen und Daten nach der Sprache des Browsers (`Intl`, € je Land), Datum als Text `21.11.2026` in Deutschland; ein Kalenderfeld öffnet sich erst beim Anklicken (das heutige `dd/mm/yyyy` kommt vom Datumsfeld des Browsers). Oberfläche bleibt Englisch.
- Andere Länder: nur Länder mit gespeichertem Scan (kein neuer Abruf), mit dem Hinweis „needs a VPN or being in that country“.
- Gewichte (Favorit 3 · gut bewertet 2 · sonst 1) und Schwelle Letterboxd 3.8 fest, erklärt im ⓘ-Tooltip; ein einstellbarer Expertenbereich erst, wenn jemand ihn braucht.
- Auswahl der Dienste wandert aus der Abo-Seite nach Settings → My services (Gruppen My subscriptions · Free and ad-supported · Rental shops · Amazon Channels · All others eingeklappt, Suche, Liste statt Raster, speichert sofort mit „Saved · Undo“, kein Save-Knopf, kein Erklärsatz). Das ist die ursprüngliche Planung aus K2; die Abweichung dort (Liste bleibt auf der Abo-Seite) wird zurückgenommen. Die Abo-Seite verlinkt dorthin.
- Gleiche Kataloge: keine Handtabelle, sondern eine Regel: „X Amazon Channel“, „X Apple TV Channel“ usw. werden dem Hauptdienst „X“ zugeordnet, wenn er im Katalog des Landes existiert; Pakete („Netflix in MagentaTV“) als Einstellung des Nutzers (Abo A enthält Abo B, Preis 0 für die Rechnung). Tippfehler in Anzeigenamen („Amzon“) über eine kleine Korrekturliste.
Etappen (Reihenfolge nach Wirkung; A1 ist die Mindestversion):
- [x] A1 Mindestversion (gebaut 2026-11-18, siehe Ergebnis): Titel 24 px, Tabelle nach Wert sortiert (Spaltenköpfe klickbar), Gratis-Dienste als Chip-Block („ARD 1 · ZDF 2 · …“, Dienste ohne Filme nur als „+1 with no films“, keine „Only here“-Spalte für sie), Preisfeld mit €-Platzhalter und Speichern beim Verlassen des Feldes („Saved“), Datum als Text mit Kalender erst beim Klick, „Total € … / month · € … / year“, Erklärungen als ⓘ-Tooltip statt Fußnote, Zeilenhöhe 56 px und mittig, Zahlen rechtsbündig mit `tabular-nums`, doppelte Kataloge zusammengefasst, Dienste-Auswahl nach Settings → My services mit Sofort-Speichern und Undo, Länderauswahl vom Seitenkopf weg (Land steht in der gemeinsamen Kopfzeile).
- [x] A2 Empfehlungen und Fristen (gebaut 2026-11-18, siehe Ergebnis A2): zwei bis drei Karten (Cancel · Subscribe for a month, Rand 3 px in Ereignisfarbe) immer mit Aktion und Begründung inkl. Filmen, Stunden und Geld, wenn der Preis bekannt ist, sonst „Based on film count only“; „Next best“ je Katalog einmal, klickbar; „Not interested“ blendet 30 Tage aus. Fristen-Banner nur bei Frist ≤ 7 Tage (Netflix renews on …, Buttons „Remind me tomorrow“ · „Dismiss“), gleiches Banner oben auf Tonight; Push 3 Tage und 1 Tag vorher mit K5.
- [x] A3 Abdeckung und Zeit (gebaut 2026-11-18, siehe Ergebnis A3): Balken in vier Segmenten (Subscriptions · Free · Rent only · Not available, Klick öffnet die Watchlist mit Filter), Kostenzeile, Spalten Hours und „Your pace“ (Hours ÷ Filmzeit pro Woche, Einstellung, Standard 5 h), „Only to rent“ als Poster-Reihe mit Summe der Filme und Filter-Chips statt Textliste, „See all →“ mit `cost=rent`.
- [x] A4 Wert und Detail (gebaut 2026-11-18, siehe Ergebnis A4): Wert je Dienst (Σ Gewicht der exklusiven Filme), „€ per value“ nur bei bekanntem Preis, Favoriten-Zahl „★ 9“ neben „Only here“, Detail-Schublade je Dienst (nach K4, gleiche Schublade wie die Film-Details): Kopf, Kennzahlen, „Only here“-Poster, „Also elsewhere“ (was beim Kündigen nicht verloren geht), Verwaltung (monatlich/jährlich, Kündigungsfrist in Tagen, Probe-Abo, geteilt mit n Personen, Notiz, Link zur Kündigungsseite, alles vom Nutzer).
- [x] A5 Planung (gebaut 2026-11-18, siehe Ergebnis A5): Budget-Planer (Regler € 0–50, beste Kombination nach Wert, Alternativen, +x % gegenüber heute; Unit-Tests für Grenzen und Kataloge), Rotationsplan aus der heutigen Verfügbarkeit (ein Abo je Monat, Monatsleiste, „Add reminders“), „Worth a month?“ (nicht abonnierte Dienste, bis 5 Zeilen, „Show all“, Preis nur wenn eingetragen), Was-wäre-wenn-Modus mit deutlichem Rahmen („nothing saved“, „Apply to my services“).
- [x] A6 Extras (teilweise gebaut 2026-11-18, siehe Ergebnis A6): Überschneidungs-Heatmap (eingeklappt, Zelle öffnet die gemeinsamen Filme), andere Länder („With your services in Austria you would see +12 films“), Verlauf „Only here“ über Zeit sobald gespeicherte Scans 30 Tage zurückreichen, iCal-Feed `/calendar.ics` aus den eingetragenen Fristen, Home-Assistant-Sensoren `next_subscription_deadline` und `watchlist_coverage`.
Zustände: keine Abos gewählt (Auswahl direkt auf der Seite statt leerer Tabelle), keine Preise (alles läuft mit Filmanzahl, Hinweis „Add prices for costs and better advice“), Sync läuft (Skelett und „Updating availability …“).
Abnahme: Die Kündigungsfrage ist ohne Scrollen und ohne Rechnen beantwortet; jede Empfehlung hat eine Aktion; kein Katalog doppelt; keine Spalte nur mit „–“ (ausblenden oder zum Eintragen auffordern); Zahlen- und Datumsformat passt zum Browser; Änderungen speichern sofort mit Undo; Unit-Tests für Wert, Budget, Katalog-Zusammenfassung und Fristen.
- Ergebnis A1 (2026-11-18, selbstständig):
  - Titel 24 px (alle Seiten). Tabelle der bezahlten Dienste, standardmäßig nach „Only here“ absteigend, Spaltenköpfe sortieren (mit `aria-sort`), Spalten Service · Price / month · Renews / cancel by · Watchlist · Only here · Hours · € / film, ⓘ-Hinweise statt Fußnote, Zeilen 56 px mittig, Zahlen rechtsbündig. „€ / film“ ist jetzt Preis ÷ Filme nur dort (vorher ÷ alle Filme des Dienstes); fehlt der Preis, steht „add price“ (springt ins erste leere Feld) und ein Hinweis unter der Tabelle.
  - Preis (Komma erlaubt) und Datum speichern beim Verlassen des Feldes („Saved“), Summen pro Monat und Jahr ziehen sofort nach. Datum als Text im Format des Browsers (21.11.2026 in Deutschland), das Kalenderfeld öffnet sich per Klick; Fristen ≤ 7 Tage in Rot.
  - Gratis-Dienste als Chip-Block mit Filmzahl und „n films free“, Dienste ohne Film nur als „+1 with no films“; keine Zeile und keine „Only here“-Spalte für sie. Amazon-Channels werden bei „Subscribe for a month“ und „Next best“ dem Hauptdienst zugerechnet (`catalog_name`).
  - Neue Seite Settings → My services (`/settings/services`): Suche, Gruppen (My subscriptions · Free and ad-supported · Subscriptions · Rental shops · Amazon Channels und More services eingeklappt), Filmzahl je Dienst, speichert beim Anhaken mit „Saved · Undo“; die Auswahl ist von der Abo-Seite verschwunden (Länderauswahl, Save-Knopf und Erklärsatz auch). `/subscriptions` zeigt immer das Land der Kopfzeile.
  - Tests: Python (Gratis-Block, Sortierung, Stunden, Jahressumme, Channels, Seiten), Browser (Preis speichert beim Verlassen, Dienste speichern und Undo).
  - Entschieden: „Only here“ pro Dienst rechnet weiter mit der bisherigen Regel (nicht auf einem anderen eigenen Dienst, nirgends gratis); die Filmfeld-Markierung `only_on_my_services` für den Filter „Only on one of my services“ behandelt Channels noch nicht als gleichen Katalog (offen für A2).
- Ergebnis A2 (2026-11-18, selbstständig):
  - Oben auf der Abo-Seite, vor der Tabelle: Fristen-Banner (nur bei einem eingetragenen Datum in höchstens 7 Tagen, mit „Remind me tomorrow“ und „Dismiss“, im Browser gemerkt) und bis zu zwei Karten: „Cancel X“ (Filme nur dort, Stunden, bei bekanntem Preis „€ 12.99 a month = € 0.22 per film you would lose“, sonst „Based on the film count only: add a price …“; Aktionen „Set reminder“ öffnet das Datumsfeld der Zeile, „Show the n films“ öffnet die Watchlist mit passendem Filter) und „Subscribe to Y for a month“ (Filme, die keiner der eigenen Dienste hat, Stunden; „Show the films on Y“); „Not interested“ blendet eine Karte 30 Tage in diesem Browser aus. „Next best“ nennt jeden Katalog einmal, jeder Name ist ein Link auf die Watchlist.
  - Dasselbe Banner steht oben auf Tonight (mit Link „Open subscriptions“). Kein Eintrag „Watch first“ und keine „Rent instead“-Karte (keine Ablauf- und Leihpreisdaten). „Open Y ↗“ und „Plan it“ entfallen (keine Dienst-Adressen in den Daten; die Kündigungsseite trägt der Nutzer in A4 selbst ein). Push 3 und 1 Tag vorher kommt mit K5.
  - Tests: Python (Karten, Fristen), Browser (Banner erscheint, Dismiss, Tonight).
- Ergebnis A3 (2026-11-18, selbstständig):
  - Abdeckungs-Balken in vier Teilen (Subscriptions · Free · Rent only · Not on your services; „andere Dienste“ und nicht verfügbare Filme zählen zum letzten) mit Satz „37 % of your watchlist is watchable without extra cost (168 of 456)“, jedes Stück verlinkt auf die Watchlist mit passendem Filter, Legende mit Prozenten, Kostenzeile (oder „Add prices“).
  - Neue Einstellung „Film time per week (hours)“ unter Settings → General (0,5 bis 80, Standard 5; gespeichert, geprüft, Teil der Sicherung); Spalte „Your pace“ rechnet Stunden nur dort ÷ Wochenzeit (≈ 5 mo, ≈ 2 wk).
  - „Only to rent“ als Poster-Reihe (96 px, beste Letterboxd-Bewertung zuerst, Rand ausgeblendet, Titel darunter, Klick öffnet das Detailfenster) mit Zahl und „See all →“. Die Chips „≤ € 2.99“ und die günstigste Leihe je Film entfallen (TMDB liefert keine Leihpreise); „median / cheapest total“ ebenfalls.
  - Tests: Python (Abdeckung, Reihenfolge der Leihfilme, Wochenzeit), Browser-Lauf der Abo-Seite weiter grün.
- Ergebnis A4 (2026-11-18, selbstständig):
  - Wert je Dienst = Summe der Gewichte der Filme nur dort (Favorit 3, Letterboxd ≥ 3,8 zwei, sonst 1; Schwelle fest `GOOD_RATING`), ohne `leaving_boost`. Die Tabelle beginnt mit dem Dienst mit dem größten Wert (Spalte „Value“, sortierbar, ⓘ erklärt die Formel); „Only here“ zeigt daneben „♥ n“ (Favoriten darunter). „Cancel“ wählt den Dienst mit dem geringsten Wert pro Euro (ohne Preis: geringster Wert); ein Dienst ohne Film nur dort bleibt der erste Kündigungskandidat.
  - Schublade je Dienst (Klick auf den Namen; natives `dialog`, Desktop rechts 480 px, Handy Blatt von unten, Escape und Klick daneben schließen, Fokus kehrt zurück): Kennzahlen (Watchlist, Only here mit ♥, Value, Hours, Your pace, € / film), „Only here“ als Poster-Raster (36, Rest per Link), „Also elsewhere“ (was beim Kündigen nicht verloren geht), Notizen mit „Shared with“ (teilt den Preis, Summen und € / film rechnen mit dem eigenen Anteil), Kündigungsfrist in Tagen, „Trial used on“, Kündigungsseite (nur http/https, wird als Link angeboten) und Notiz. Alles speichert beim Verlassen des Feldes; Server prüft jedes Feld (`clean_costs`).
  - Nicht gebaut: „Watch these first“ und Verlauf über 12 Monate (keine Ablaufdaten, gespeicherte Scans reichen noch nicht), „Add all to Today“ (kein Ziel dafür), Laufzeit monatlich/jährlich (der Preis ist monatlich; ein Jahresabo rechnet der Nutzer um), „Also available as Amazon Channel (€ x)“ mit Preisvergleich (keine Preise der Channels).
  - Tests: Python (Wert und Rang, geteilter Preis, Prüfung der Felder), Browser (Schublade speichert, Summe folgt, Fokus kehrt zurück).
- Ergebnis A5 (2026-11-18, selbstständig):
  - Reine Rechnung in `static/js/planner.js` (mit Tests): Abdeckung einer Dienstemenge (gewichtete Filme, kein Film doppelt, Gratis-Filme immer drin), beste Mengen für ein Budget (alle Teilmengen von höchstens 14 Diensten mit Preis; mehr Gewicht zuerst, bei Gleichstand billiger), Rotation (jeden Monat der Dienst mit dem größten Zuwachs, hört auf, wenn nichts mehr dazukommt). Daten liefert `costs.plan_data` (Gewichte, Gratis-Filme, je Dienst seine Filme; eigene bezahlte Dienste plus die 12 mit dem größten Zuwachs; Channels zählen zum Hauptdienst).
  - Abschnitt „Plan“ (Budget-Regler 0 bis 50 €, die besten drei Mengen mit Prozent und Abstand zu heute, „Next months“ mit drei Monaten, „What if“ mit einem Kästchen je Dienst und deutlichem gestricheltem Rahmen, „nothing saved“) und „Worth a month?“ (fünf Dienste mit Filmen, Favoriten, Stunden, „Show films“ und „Try it“, das den Dienst im Was-wäre-wenn einschaltet).
  - Preise: Eigene Dienste nutzen den gespeicherten Preis; für fremde Dienste trägt der Nutzer „€ pro Monat“ ein, gespeichert nur im Browser (`localStorage`), weil es keine bekannten Preise gibt und nichts geschätzt wird.
  - Nicht gebaut: Knopf „Add reminders“ für den Rotationsplan (die Fristen setzt der Nutzer in der Tabelle selbst), „Hinweis bei fehlenden Ablaufdaten“ (der Plan nennt nur die heutige Verfügbarkeit, steht im Satz „Uses the prices you entered“), „Apply to my services“ im Was-wäre-wenn (die Auswahl ändert man unter Settings → My services), zweit- und drittbeste Kombination ist da, die Heatmap folgt in A6.
  - Tests: JS (4: Abdeckung, Budget, Gleichstand, Rotation), Python (`plan_data`, Favoriten in „book“), Browser (Was-wäre-wenn ändert nichts Gespeichertes).
- Ergebnis A6 (2026-11-18, selbstständig):
  - Überschneidung: im Abschnitt „Plan“ eingeklappt, Tabelle Dienst × Dienst (Zahl gemeinsamer Watchlist-Filme, eine Zelle öffnet genau diese Filme über `match=all`), darüber der Satz „X and Y share n films.“
  - Kalender: `GET /calendar.ics` (neues Modul `watchlist_app/calendar.py`) mit einem Ganztagstermin je eingetragenem Datum und, wenn eine Kündigungsfrist eingetragen ist, einem zweiten „last day to cancel“; Link auf der Abo-Seite, Zeilen nach RFC 5545 gefaltet (nie mitten in einem Zeichen). Home-Assistant-Sensoren kamen mit K5 (`/api/sensors`: nächste Frist, Abdeckung; „films leaving soon“ entfällt).
  - Nicht gebaut: „andere Länder“ (bräuchte gespeicherte Scans anderer Länder, die es nur gibt, wenn man dort gescannt hat; die Karte „Also on your services in …“ im Detailfenster leistet das für einzelne Filme) und der Verlauf „Only here über Zeit“ (gespeicherte Scans reichen noch nicht über 30 Tage).

### Etappe K4: Details und Aktionen (teilweise gebaut 2026-11-18, siehe Ergebnis)
- [x] Detailfenster als Schublade von rechts (Desktop 480 px), am Handy Blatt von unten (60 % hoch, hochziehen = ganzer Bildschirm, nach unten wischen schließt). Raster bleibt dahinter sichtbar; Fokus bleibt drin und kehrt zurück (wie heute `openModal`).
- [x] Aufbau: Backdrop 16:9 mit Titel und Jahr; Hauptknopf über die volle Breite für den günstigsten Weg („Where to watch on Netflix“, führt zur TMDB-Seite); Meta (Laufzeit · Genres · Altersfreigabe · Land · Regie, Regie filtert die Watchlist); Bewertungen Letterboxd · TMDB (Stimmen bei Hover/Tippen); Beschreibung 3 Zeilen mit „more“; „Where to watch“ nach Kosten (gibt es, 9d); Verlauf je Dienst der letzten 12 Monate als Zeitleiste; Trailer als Vorschaubild, startet nur auf Klick; Aktionen; „Similar on your services“ (höchstens 8).
- [x] ← und → blättern zum vorigen und nächsten Film der aktuellen Liste; die Adresse wechselt mit.
- [ ] Feinheiten aus dem zweiten Auftrag:
  - Kopf: kleines Poster (80 px) überlappt den Rand des Backdrops; Originaltitel klein darunter, wenn er abweicht. Raster dahinter zu 40 % abgedunkelt; Öffnen in 220 ms, bei reduzierter Bewegung sofort.
  - Meta in einer Zeile ohne Umbruch: `2009 · 2h 21m · rated 12 · Sci-Fi, Drama`. Bewertungszeile: `Letterboxd ★ 3.7` · `TMDB 7.8`, eine Nachkommastelle, Stimmen beim Überfahren/Tippen.
  - Hauptknopf 44 px in Amber mit Logo: „Watch on Netzkino · Free with ads“, „Your service“ als kleines Abzeichen darin; der bisherige Knopf „Where to watch“ fällt weg (Doppelung).
  - Sekundäre Aktionen als eine Symbolleiste in einer Zeile: Favorite · Compare · Seen · Not now · Letterboxd · Share.
  - Beschreibung 3 Zeilen mit „more“; Trailer als Vorschaubild mit Play, YouTube lädt erst beim Klick.
  - „Where to watch“ als senkrechte Liste nach Free · Subscription · Rent, eigene Dienste grün umrandet, jede Zeile ein Link zur TMDB-Seite; unten klein „Something wrong? Report“ (öffnet eine Notiz).
  - Andere Länder als Chips mit Flagge, darunter der VPN-Satz (bleibt).
  - Regie und die ersten 5 Darsteller als Links, die die Watchlist nach der Person filtern; Kontrast mindestens 4,5:1.
  - Stichworte als kleine Chips; „Similar on your services“ als Reihe aus 4–6 Mini-Postern (96 px) mit Dienst-Logo.
  - Links unten als Chips: TMDB · Letterboxd · JustWatch.
  - Daten beim Überfahren oder Sichtbarwerden der Karte vorladen, Öffnen unter 100 ms.
- [x] Schnellaktionen im Menü „⋯“ an der Karte (am Handy auch langes Drücken): Watched, Not now (30 Tage aus Tonight, unter „Filters“ wieder sichtbar; ersetzt „Nicht interessiert“ aus Etappe 14), Add to compare. Drei Tab-Stopps je Karte (Titel, ♥, ⋯).
- [x] Vergleichen über eine Leiste unten („3 to compare · Compare“, höchstens 4) statt Knopf und Vergleichsmodus; im Vergleich ist der beste Wert je Zeile hervorgehoben.
- [x] Watched: Karte ausgegraut mit ✓, optional Letterboxd zum Eintragen öffnen; Abgleich mit dem Letterboxd-Tagebuch (aus Etappe 14).
- [x] Rückgängig statt Nachfragen: „Marked as watched · Undo“, 5 s. Nachfrage nur bei Unumkehrbarem, mit Liste dessen, was gelöscht wird.
- [x] Tastatur: `/` Suche, `g t` / `g w` / `g s` Seiten, Pfeiltasten im Raster, Enter Details, `f` Favorit, `s` Watched, `n` Not now, `c` Compare, `r` Zufall, `Shift+R` Sync, `?` zeigt alle Kürzel; nur außerhalb von Eingabefeldern. Ersetzt den Tastatur-Punkt aus Etappe 14.
- Ergebnis (2026-11-18, selbstständig; Teil 1):
  - Detailfenster als Schublade (Desktop 480 px von rechts, Handy Blatt von unten mit 88 % Höhe), Raster dahinter zu 40 % abgedunkelt, Öffnen in 220 ms (bei reduzierter Bewegung sofort); die Bootstrap-Dialog-Technik bleibt (Fokus, Escape, Rückkehr des Fokus). Knöpfe im Kopf: vorheriger/nächster Film der sichtbaren Liste (Raster oder Tonight-Reihen), ← und → auch per Tastatur; die Adresse `?film=` wechselt mit (ohne neuen Verlaufseintrag).
  - Neu im Backend: Tabelle `flags` (`watched`, `not_now` mit Ablaufdatum 30 Tage, vom Server gesetzt), `GET /api/flags`, `PUT`/`DELETE /api/flags/<key>`, in Sicherung und Wiederherstellung (geprüft: ein Backup kann nichts länger als 30 Tage verstecken), Tests dazu.
  - Karten-Menü „⋯“ (Mark as watched · Not now (30 days) · Add to comparison), dritter Tab-Stopp nach Titel und ♥ (nur im Aussehen rechts); dieselben Aktionen als Knöpfe im Detailfenster. „Not now“ blendet den Film in Raster und Tonight aus, bis der Filter „Also show films I set aside“ (unter „Filters“, Adresse `hidden=1`) an ist; „Watched“ zeigt das Abzeichen und nimmt den Film aus Tonight. Rückgängig: der Toast „… marked as watched · Undo“ (5 s).
  - Tastatur (nicht in Eingabefeldern): `/` Suche, `g t` / `g w` / `g s` Seiten, `f` Favorit, `s` gesehen, `n` Not now, `c` Vergleich (für den Film im geöffneten Detailfenster, sonst den Film mit Fokus oder unter dem Zeiger), `r` Zufall (K3), `Shift+R` Sync, `?` zeigt alle (natives `dialog`).
  - Tests: Python (Flags, Backup, Ablauf, feindliche Datei), Browser (Menü mit Undo und Filter, Pfeiltasten und Knöpfe, Tastaturkürzel, drei Tab-Stopps).
- Ergebnis K4 Teil 2 (2026-11-18, selbstständig): Das Detailfenster hat genau einen Hauptknopf in Amber über die volle Breite: „Where to watch on <günstigster eigener Dienst> (free / with ads)“ (führt zur TMDB-Seite), alle anderen Aktionen sind schlichte Knöpfe im Raster. Meta in einer Zeile (`2010 · 1h 58m · rated 12`), darunter die Bewertungen („Letterboxd ★ 3.8 · TMDB 7.7 (9,654 votes)“). Fund beim Ansehen: `.btn-accent` setzte nur Bootstrap-Variablen, Tabler liest `--tblr-btn-*`; der Knopf blieb grau. Jetzt setzt die Klasse beide Gruppen. Der Favorit-Knopf ist nicht mehr amber (nur der Hauptknopf).
- Ergebnis K4 Teil 3 (2026-11-18, auf Wunsch aus der Liste der Übersprungenen):
  - Detailfenster: Backdrop 16:9 (TMDB-Bild, `w780`) mit kleinem Poster über der Unterkante, Wiedergabe-Knopf auf dem Bild öffnet den Trailer erst beim Klick (kein YouTube-Vorschaubild, damit beim Öffnen nichts an Google geht); Regie und die ersten fünf Darsteller sind Links, die die Watchlist danach durchsuchen; Herkunftsländer und Stichworte als Chips, die nach Land und Stichwort filtern.
  - Vergleichsleiste: erscheint unten mit dem ersten gewählten Film („2 to compare“, „Compare“, „Clear“, höchstens vier); der Knopf und der Vergleichsmodus in der Werkzeugzeile entfallen. Film wählen über „⋯“ und über das Detailfenster. Im Vergleich ist der beste Wert je Zeile hervorgehoben (Letterboxd und TMDB höchster, Laufzeit kürzeste, „On your services“ meiste; bei Gleichstand keiner).
- Ergebnis Übersprungenes, Teil 2 (2026-11-18): Zustands-Banner bei einem fehlgeschlagenen Scan („Letterboxd is not responding, or the watchlist is not public. Showing the data from … Try again in a few minutes.“, mit „Try again“ und einem Link zu den Einstellungen oder zur Datenseite; `static/js/problems.js`, getestet); „Other countries“ auf der Abo-Seite („With your services in AT you would see +12 films“, nur aus gespeicherten Angeboten, kein neuer Abruf); Verlauf „Only here over time“ als Linie in der Dienst-Schublade (neue Tabelle `service_history`, ein Eintrag je Tag und Dienst, ein Jahr lang, geschrieben nach jedem Scan; erst ab dem zweiten Tag sichtbar).
  - Detailfenster fertiggestellt (2026-11-18, auf Rückmeldung "noch nicht fertig"): Hauptknopf mit Dienst-Logo und Abzeichen ("Watch on YouTube Free · Free with ads", "Your service"); Symbolleiste in einer Zeile (Favorite · Compare · Seen · Not now · Letterboxd · Share, Namen als `title` und für Screenreader); Beschreibung 3 Zeilen mit "more"; Altersangabe "0" heißt jetzt "all ages" statt "rated 0"; Link-Chips unten ohne doppeltes Letterboxd. Fund: `ti-columns-gap` gibt es in der Icon-Schrift nicht (leerer Knopf), jetzt `ti-layout-columns`.
  - Danach gebaut: Originaltitel (neues Feld `original_title` durch TMDB, Film, Prüfung und Client; `FILM_FORMAT` 3, der nächste Scan holt ihn), "Similar on your services" als Reihe aus bis zu 6 Mini-Postern mit Dienst darunter, JustWatch-Chip.
  - Bewusst nicht gebaut: Zeitleiste je Film (es gibt nur den Verlauf je Dienst, siehe Dienst-Schublade), "Something wrong? Report" (kein Ziel für die Meldung), Flaggen-Chips (Windows zeigt Flaggen-Emoji als Buchstaben).
  - (alt) Noch offen in K4: Aufbau des Fensters nach Vorlage (Backdrop 16:9 mit Titel, ein Hauptknopf „Where to watch on …“ voller Breite, Bewertungszeile mit Stimmen, Zeitleiste je Dienst, Trailer als Vorschaubild, Personen als Filter-Links, Chips für Länder und Stichworte), Vergleichsleiste unten statt Knopf und Modus (der Vergleich arbeitet weiter wie bisher; neu ist nur „Add to comparison“ im Menü), Ausgrauen gesehener Filme im Raster, Abgleich mit dem Letterboxd-Tagebuch (neue Datenquelle, entfällt), Vorladen der Daten beim Überfahren, Langdruck am Handy.

### Etappe K5: Abos und Benachrichtigungen (Benachrichtigungen gebaut 2026-11-18)
- [ ] (ersetzt durch Teil C, A1 bis A5) Subscriptions als Tabelle: Dienst · Films now · Exclusive (nur hier) · Trend 30 days · Price/month · € per exclusive film · Recommendation (Keep / Can cancel / Worth it again).
- [ ] (ersetzt durch Teil C, A5) Rotations-Ratgeber: „With only one subscription this month: Disney+ (41 exclusive films)“ und eine Reihenfolge für 3 Monate, nur aus der heutigen Verfügbarkeit.
- [ ] (ersetzt durch Teil C, A5) „Worth a trial month?“: nicht abonnierte Dienste nach exklusiven Watchlist-Filmen.
- [x] Benachrichtigungen über ntfy, Gotify oder Webhook, dazu ein Home-Assistant-Sensor „New on your services“. Standard: Favorit ist nicht mehr verfügbar (an), Wochen-Zusammenfassung freitags 17 Uhr (an), neu verfügbar (aus), Abo-Empfehlung ändert sich (aus). Höchstens eine Nachricht pro Tag, Ruhezeit 22–8 Uhr, jede Nachricht öffnet `?film=`, abschaltbar je Film und je Art. Fasst die Zusammenfassung aus Etappe 16 und die offene Meldung aus Etappe 11 zusammen.
- [ ] (nicht gebaut, siehe Ergebnis) Zeitplan: Watchlist alle 6 Stunden und beim Öffnen, wenn älter als 1 Stunde; Verfügbarkeit nachts komplett. Neue Filme erscheinen sofort mit „checking…“, entfernte erst nach zwei Syncs (Schutz bei Letterboxd-Ausfall).
- Ergebnis (2026-11-18, selbstständig):
  - Neues Modul `watchlist_app/notifications.py` und Abschnitt „Notifications“ unter Settings → General: Ziel ntfy, Gotify oder Webhook, Adresse (nur http/https), Token (bleibt in der Datenbank, nicht in der Sicherung, leeres Feld behält ihn, „-“ löscht ihn), vier Arten (Favorit nicht mehr auf meinen Diensten: an; Fristen 3 und 1 Tag vorher: an; Wochenzusammenfassung freitags ab 17 Uhr: an; neu verfügbar: aus), Knopf „Send a test message“ (speichert zuerst).
  - Regeln: höchstens eine Nachricht pro Tag (Ereignisse werden zu einer gebündelt), keine zwischen 22 und 8 Uhr (sie warten), ein Fehlschlag wird beim nächsten Minutenlauf des Zeitplans wiederholt, nichts geht verloren; jede Frist wird je Stufe nur einmal gemeldet. Läuft im vorhandenen Zeitplan-Thread, kein neuer Dienst.
  - Home-Assistant: `GET /api/sensors` liefert `new_on_my_services`, `gone_from_my_services` (7 Tage), `next_subscription_deadline`, `watchlist_coverage`, `films_available`, `last_scan` für einen REST-Sensor.
  - Nicht gebaut: jede Nachricht öffnet `?film=` (bei einem Film ja nur über „Watchlist mit Änderungen“, mehrere Filme haben keinen gemeinsamen Film), abschaltbar je Film, Nachricht „Abo-Empfehlung ändert sich“, Zeitplan alle 6 Stunden und „checking…“ (TMDB-Angebote werden ohnehin 24 Stunden wiederverwendet, siehe 8b), Ruhezeit einstellbar (fest 22 bis 8). Webhook und Gotify nur gegen die Atrappe geprüft, ntfy ebenso; kein echter Sendeversuch.
  - Tests: Python (drei Ziele, Ruhezeit und Tageslimit, Favorit/neu, Wochenzusammenfassung, Fristen je Stufe, Fehlschlag mit Wiederholung, Prüfung der Einstellungen und Token nicht in der Sicherung, Test-Endpunkt, Sensoren).

### Etappe K6: Feinschliff (PWA, Ansichten, gespeicherte Ansichten, Hinweis beim ersten Start, Leistung gebaut 2026-11-18; Rest offen)
- [x] PWA: Manifest, Icons, Service Worker (`/api/latest` und Poster mit stale-while-revalidate), offline mit Hinweis „Data from yesterday 23:10“. Installieren braucht HTTPS im Heimnetz (oder localhost); mit Etappe 17 klären.
- [x] Ansichten Grid · Compact · Table (Table ersetzt die Listenansicht aus Etappe 14; Compact nur Poster, Badge und Bewertung, Titel beim Fokus/langem Drücken).
- [x] Gespeicherte Ansichten („Movie night with Lea“) als Chips auf Tonight und als Auswahl in der Leiste (ersetzt „Gespeicherte Filter“ aus Etappe 14).
- [x] Einrichtung unter 60 Sekunden: Benutzername mit Vorschau (Anzahl und 6 Poster), Land, die 12 häufigsten Dienste zum Antippen, Gratis-Dienste vorausgewählt, Fortschritt „312 of 456 films checked“ (ersetzt „Erster Start“ aus Etappe 14).
- [ ] Zustände: Skelett, teilweise geladen (gibt es), Fehler mit Klartext und Aktion („Letterboxd is not responding. Showing data from 08:00. [Try again]“).
- [x] Leistung: erste Poster unter 1,5 s, Filter unter 100 ms, flüssiges Scrollen bei 456 Karten. Erst messen, dann `content-visibility: auto` vor einer virtuellen Liste. Poster mit `srcset` (w185/w342), Platzhalter in der Posterfarbe.
- [ ] Deutsche Filmtitel als Option in Settings, Originaltitel im Tooltip und in den Details.
- [-] Optional: TV-Ansicht (große Karten, Pfeiltasten, nur die Tonight-Reihen). (entschieden: nicht bauen, siehe ENTSCHEIDUNGEN.md)
- [x] Aus dem zweiten Auftrag: Overlay mit allen Tastenkürzeln auf `?`; Zoom auf 200 % ohne waagerechtes Scrollen (gemessen bei 640 px Breite auf allen acht Seiten: nur Tabellen scrollen in ihrem Kasten); JavaScript unter 200 KB gzip (gemessen: 121 KB für alle Dateien zusammen, eine Seite lädt weniger). Wischgesten auf Karten bleiben weg (siehe Abweichungen).
- Ergebnis PWA (2026-11-18, selbstständig):
  - Manifest mit Symbolen (192, 512 und „maskable“, gezeichnet mit `scripts/make_icons.py` ohne Bildbibliothek: Filmstreifen mit Wiedergabedreieck in den Farben der App), Seitenkopf mit `theme-color`, Symbol und Apple-Symbol auf allen Seiten.
  - Service Worker `/sw.js` (vom Wurzelpfad, `no-cache`): Skripte und Stile zuerst aus dem Netz, offline die gespeicherte Fassung (sie laden als Satz, sonst passen Module nicht zusammen); Schriften, Symbole und Poster sofort aus dem Speicher und im Hintergrund erneuert (Poster höchstens 300); Seiten und `/api/latest` zuerst aus dem Netz, offline die gespeicherte Kopie mit Kopfzeile `X-From-Cache`, dann zeigt die Seite „Offline: showing the data from …“. Er meldet sich nur über https oder localhost an (Installieren braucht HTTPS, siehe README: Reverse-Proxy).
  - Tests: Python (Manifest, Symbole sind PNG, Worker vom Wurzelpfad, jede Seite verlinkt Manifest und Symbol), Browser (Worker speichert Seite, Daten und Skripte).
  - Nicht geprüft: der Aufruf ohne Netz selbst (Playwright schaltet auch Antworten des Service Workers ab, `ERR_INTERNET_DISCONNECTED`), Installieren auf einem Handy, Verhalten unter https.
- Ergebnis gespeicherte Ansichten und Leistung (2026-11-18, selbstständig):
  - Gespeicherte Ansichten: „Save view“ über dem Raster (Name bis 40 Zeichen, höchstens 12), die Ansicht ist ein Chip mit den Filtern der Adresse (ohne geöffneten Film und Scan-Kennung); dieselben Chips stehen oben auf Tonight; × löscht. Gespeichert nur in diesem Browser (`localStorage`, `static/js/saved-views.js`, JS-Tests und ein Browser-Test). Die Auswahl „links in der Leiste“ entfällt (die Chips über dem Raster leisten dasselbe).
  - Leistung: `content-visibility: auto` auf den Karten des Rasters. Gemessen mit der Datenkopie (168 Karten, Neusortieren inklusive Layout, 6 Läufe): vorher 160 bis 230 ms, nachher 100 bis 130 ms (Ausreißer 200 ms beim ersten Lauf). Gemessen nur im eingebauten Browser, nicht auf einem Handy; „erste Poster unter 1,5 s“ und `srcset` sind nicht angefasst.
  - Noch offen in K6: Ansichten Grid · Compact · Table, Einrichtung unter 60 Sekunden, schönere Zustände (Skelett gibt es), deutsche Filmtitel als Option, TV-Ansicht, 200-%-Zoom und JavaScript-Größe messen.
- Ergebnis K6-Rest (2026-11-18, selbstständig):
  - Ansichten Grid · Compact · Table: Umschalter in der Werkzeugzeile (Radiogruppe, bleibt im Browser). Compact zeigt nur Poster, Abzeichen und Bewertung, der Titel erscheint bei Fokus oder Überfahren (der Titel-Link bleibt für Tastatur und Screenreader da); Table ist eine Tabelle mit Titel-Link, Jahr, Laufzeit, Bewertung und den angehakten Diensten (`filmTable`, getestet). Beides ohne Herz und ohne „⋯“ (dort hilft die Schublade). Die Spalten sind nicht sortierbar; die Sortierung bleibt in der Leiste.
  - Erster Start: Tonight zeigt „Set up in a minute“ (TMDB-Schlüssel setzen, Letterboxd-Namen eintragen, Dienste anhaken), solange weder ein Name noch ein Scan da ist. Einen Assistenten mit Vorschau (Anzahl, 6 Poster) und Fortschritt „312 of 456“ gibt es nicht; der Fortschritt steht im Sync-Feld.
  - Gemessen (JavaScript, gzip): Hauptseite etwa 44 KB eigener Code plus 63 KB Bootstrap und Tabler = rund 107 KB, unter der Grenze von 200 KB. 200-%-Zoom nicht geprüft.
  - Weiter offen: deutsche Filmtitel (bräuchte Titel in der Landessprache in den Scan-Daten), TV-Ansicht, Zustands-Texte („Letterboxd is not responding …“).

### Etappe 11: Startdatum (eigene Etappe)
- [x] Für noch nicht erschienene Watchlist-Filme Kino- und Heimkino-Start anzeigen (TMDB „release_dates“ je Land).
- [x] Eigene Ansicht „Demnächst“ mit Sortierung nach Datum.
- [ ] Meldung, sobald ein solcher Film streambar wird (nutzt die Historie; Zustellung kommt mit Etappe K5).
- [x] Altersfreigabe (FSK je Land) anzeigen und als Filter unter „More filters“, etwa für Filmabende mit Kindern. Kommt aus derselben Abfrage „release_dates“.
- Baut auf Zeitplan (Etappe 7) und Historie (Etappe 6) auf.
- Ergebnis (2026-11-16): Keine zusätzliche TMDB-Abfrage; „release_dates“ kommt mit der Abfrage des Scans (`append_to_response`). Gespeichert wird je Land die Freigabe (die des breiten Kinostarts zuerst) und der jeweils erste Kino- (Typ 2/3) und Heimkino-Start (digital/physisch, Typ 4/5); der Film bekommt die Werte des gescannten Landes (`certification`, `cinema_date`, `home_date`, geprüft beim Import).
  - „Demnächst“ ist ein einklappbarer Kasten „Coming soon (n)“ über „Not currently available“, sortiert nach dem nächsten Termin; jede Zeile öffnet die Details. Das Detailfenster zeigt „rated 16“ und „Coming in cinemas … · at home …“, nur für Termine in der Zukunft.
  - Filter „Age rating“ unter „More filters“: bei Zahlen „Up to 12“ (FSK und die meisten Länder Europas), andere Systeme wie „PG-13“ genau; Filme ohne Freigabe fallen raus, sobald ein Wert gewählt ist. Steht im Link als `age=`.
  - Offen: die Meldung, sobald ein solcher Film streambar wird; sie braucht die Zustellung aus Etappe 16 (heute zeigt „Newly available“ die Änderung schon an).
  - Erscheint erst, wenn der Scan die TMDB-Daten neu holt (nach 24 Stunden). Tests: Python (Daten aus der TMDB-Antwort, Land beim Nachschlagen, Felder am Film, Prüfung beim Import), JS (Freigabe-Filter, Sortierung der Werte, „Coming soon“), Browser (Kasten, Details, Filter).

### Etappe 12: Mehr Daten pro Film
- [x] Letterboxd-Durchschnittsbewertung: steht auf der Filmseite, die der Scan für die TMDB-ID ohnehin lädt; keine zusätzliche Abfrage. Als Sortierung und als Filter unter „More filters“; ersetzt die TMDB-Bewertung in der sichtbaren Reihe, falls sie sich als nützlicher erweist.
- [x] (In Etappe 10 erledigt: `watchlist_position`.) Reihenfolge der Watchlist speichern: die Letterboxd-Seite ist nach „zuletzt hinzugefügt“ sortiert, die Position ersetzt das Aufnahmedatum auch ohne CSV-Export.
- [-] Letterboxd-Daten: Datum der Aufnahme in die Watchlist, eigene Bewertung. (entschieden: nicht bauen; die Position ersetzt das Datum)
- [x] Originalsprache und Herkunftsland als Filter unter „More filters“ (steckt schon in der TMDB-Antwort).
- [x] Verfügbarkeit in anderen Ländern („in DE nicht, aber in GB auf Netflix“); der TMDB-Aufruf liefert alle Länder ohne zusätzliche Abfragen.
- [x] Anbieter-Logos statt Textnamen (TMDB liefert die Bilder).
- [ ] Qualität und Sprache: nur mit zusätzlicher Datenquelle möglich; aufwendig, zuletzt in dieser Etappe und optional.
- Ergebnis (2026-11-16), vier Punkte nacheinander gebaut:
  - Sprache und Land: `original_language` und `origin_country` aus der TMDB-Antwort des Scans; zwei Filter „Original language“ und „Country of origin“ unter „More filters“ mit englischen Namen („Japanese“, „Japan“), im Link als `lang=` und `origin=`.
  - Andere Länder: neuer Endpunkt `/api/films/<id>/countries` liest die gespeicherten Angebote aller Länder (keine TMDB-Abfrage). Das Detailfenster zeigt „Also on your services in Belgium (Prime Video), …“: Länder, in denen der Film auf einem der eigenen Dienste ohne Zusatzkosten läuft, nach Namen sortiert, höchstens sechs. Mit der Datenkopie geprüft.
  - Logos: auf den Karten Logo statt Name (Name als Alternativtext und Tooltip, ohne Logo bleibt der Name); in der Seitenleiste Logo vor dem Namen, „Mostly free“ jetzt unter dem Namen, damit Namen nicht mitten im Wort umbrechen. Mit der Datenkopie: 186 Logos auf den Karten, 197 in der Seitenleiste.
  - Letterboxd-Bewertung: Abweichung vom Plan. Die Filmseite wird nur beim ersten Nachschlagen geladen, danach steht die TMDB-ID im Speicher; damit alle Filme eine Bewertung bekommen, lädt der Scan die Seite höchstens alle 30 Tage je Film neu (`LETTERBOXD_RATING_TTL_SECONDS`). Der erste Scan nach dem Update lädt sie also einmal für alle Filme mit Letterboxd-Link; Fehler dabei überspringen nur die Bewertung. Gespeichert in `film_ids` (`lb_rating`, `lb_checked_at`). Sortierung „Letterboxd rating“, Filter „Letterboxd 3.0+/3.5+/4.0+“ unter „More filters“ (`lb=`), im Detailfenster „Letterboxd 4.33/5“. Die sichtbare Filterreihe bleibt bei TMDB.
  - Tests: Python (Felder aus der TMDB-Antwort, Prüfung beim Import, Endpunkt, Bewertung aus der Seite, Nachladen einmal im Monat, Fehler ohne Folgen), JS (Filter, Sortierung, andere Länder, Karten-Logos). Tests laden nie eine Letterboxd-Seite (`conftest.py`).
  - Nachbesserung nach Rückmeldung: Der Letterboxd-Filter leerte die Liste, weil noch kein Film eine Bewertung hatte; ein Scan derselben Watchlist innerhalb von 24 Stunden wurde ohne neues Nachschlagen wiederverwendet. Jetzt wird ein gespeicherter Scan in einem älteren Film-Format (`FILM_FORMAT` in `scan_service.py`) nicht wiederverwendet, und TMDB-Daten ohne die neuen Felder werden neu geholt; der nächste Scan bringt also alle neuen Felder. Bis dahin sind Filter und Sortierung nach Letterboxd ausgegraut („after the next scan“). Die Zeile zu anderen Ländern sagt jetzt dazu, dass man dort ein VPN braucht oder im Land sein muss.
  - Offen: Datum der Aufnahme und eigene Bewertung (nächster Punkt), Qualität und Sprache (optional).

### Etappe 13: Übersicht und Auswertung
- [ ] Watchlist-Statistik über Zeit: Zugänge, weggeschaute Filme, Abdeckung je Dienst (braucht gespeicherte Scan-Stände aus Etappe 6).
- [x] „Staubfänger“: Filme, die lange auf der Liste stehen und seit Monaten verfügbar sind. (erledigt mit der Statistik-Seite: „Waiting longest“, Abgleich 2026-11-18)
- [x] Laufzeit-Summe der verfügbaren Filme je Dienst. (erledigt mit A1 und Stats-Seite: Spalte „Hours“, Abgleich 2026-11-18)
- [-] Eigene Schlagworte pro Film und Filter danach. (entschieden: nicht bauen, siehe ENTSCHEIDUNGEN.md)

### Etappe 14: Bedienung
- [x] Listenansicht (kompakte, sortierbare Tabelle) neben der Kartenansicht. → K6 (erledigt mit K6: Ansicht „Table“; Spalten nicht sortierbar, die Sortierung bleibt in der Leiste, Abgleich 2026-11-18)
- [x] Gespeicherte Filter als Knöpfe. → K6 (erledigt mit K6: gespeicherte Ansichten als Chips, Abgleich 2026-11-18)
- [x] (In Etappe 9k erledigt: „Sort & filter“.) Filter auf dem Handy einklappbar: mit „More filters“ (Etappe 9h) ist der Bereich nur noch 243 px hoch; erst nach einer Woche Nutzung entscheiden, ob noch nötig.
- [ ] Favoriten-Status mit dem Letterboxd-Tagebuch abgleichen; gesehene Filme ausblenden. → K4
- Helles Design und Farbwahl: entfällt (2026-11-17 entschieden: die App bleibt nur dunkel).
- [x] Tastatur-Bedienung: `/` Suche, `s` Shuffle, Pfeiltasten durch die Karten, `f` Favorit; nur wenn der Fokus nicht in einem Eingabefeld ist, Kürzel im `title` des Knopfs (ID #17). → K4 (mit den Kürzeln aus dem Gesamtkonzept) (erledigt mit K4: Kürzel nach dem Gesamtkonzept, `?` zeigt sie, Abgleich 2026-11-18)
- [x] „Nicht interessiert“: Film in der App ausblenden, ohne die Letterboxd-Watchlist zu ändern; eigener Filter unter „More filters“, um ihn wieder zu zeigen. → K4 („Not now“) (erledigt mit K4: „Not now“ mit Filter „Also show films I set aside“, Abgleich 2026-11-18)
- [x] Erster Start: ohne Benutzernamen und ohne Watchlist-Datei öffnet die App die Einstellungsseite statt eines leeren Rasters. → K6 (Einrichtung) (erledigt mit K6: Hinweiskasten auf Tonight statt Weiterleitung, Abgleich 2026-11-18)
- Rückgängig nach dem Entfernen eines Favoriten steht jetzt in Etappe 9i.

### Etappe 15: Gemeinsam schauen
- [-] Abstimmung: Filme auswählen, Link im Heimnetz teilen, jeder stimmt am Handy ab. (entschieden: nicht bauen, siehe ENTSCHEIDUNGEN.md)
- [-] Gäste-Abos: Abos von Freunden oder Familie als zweites Profil. (entschieden: nicht bauen)
- Baut auf „Meine Abos“ aus Etappe 7 auf. Die Abstimmung ist ohne Anmeldung gedacht, also nur fürs Heimnetz.

### Etappe 16: Ausgabe und Benachrichtigung
- [x] Kalender-Feed (ICS) oder RSS mit „neu verfügbar“. (erledigt mit A6: `/calendar.ics` aus den Fristen; „neu verfügbar“ steht nicht darin, Abgleich 2026-11-18)
- [x] Wöchentliche Zusammenfassung per Mail oder ntfy. → K5 (erledigt mit K5, Abgleich 2026-11-18)
- [x] Kleine API mit Dokumentation für Home Assistant oder Dashboards. (README, 2026-11-18)
- [x] Startseiten-Kachel („heute neu / Tipp des Tages“): `/tile`; dazu RSS `/feed.xml` (2026-11-18).
- Baut auf Zeitplan und Historie auf.

## Teil D: Docker für Unraid

### Etappe 17b: Betrieb (zuletzt, nach K6)
Der Rest von Etappe 17; die Grundlage steht in 17a (vor K3c).
- [x] Knopf „TMDB-Schlüssel testen“ auf der Einstellungsseite (2026-11-18: „Check the TMDB key“ unter Settings → General, fragt TMDB `/configuration`; 401 heißt „does not accept this key“; Tests mit Atrappe).
- [-] Datenbank aufräumen (entschieden: später, erst nach Monaten Betrieb; Löschen nur nach Rückfrage mit Liste): Filmdaten von Filmen, die seit Monaten nicht mehr auf der Watchlist stehen, löschen und die Datei verkleinern (`VACUUM`); erst sinnvoll, wenn der Server Monate gelaufen ist.
- [x] Letzte Fehlermeldungen auf der Status-Seite (K1, Settings → Data & status).
- [x] `.env` in `.dockerignore` (mit Etappe 9c), `pytest` in `requirements-dev.txt` (mit Etappe 8).
- [ ] `platforms.toml` aus `/data` lesen: entfällt, die Einstellungen liegen seit Etappe 7 in der Datenbank.

## Nicht im Plan (frühere Ideen)

Direkt-Link in die App des Anbieters (TMDB liefert nur den Link zur JustWatch-Seite, siehe Etappe 9i), mehrere Letterboxd-Profile, weitere Letterboxd-Listen, Serien, Abgleich mit Plex/Jellyfin, deutsche Oberfläche (offene Frage aus der Design-Kritik: die Oberfläche ist englisch), Push-Nachrichten über Discord/Telegram (ntfy/Gotify/Webhook stehen in K5; installierbare App jetzt in K6), Zugriffsschutz, umgekehrte Suche (Vorschläge außerhalb der Watchlist), Filmsuche ohne Watchlist (auch die TMDB-Gesamtsuche aus dem Gesamtkonzept), IMDb-Bewertung über OMDb, Leihpreise und Qualität (HD/4K, Ton, Untertitel; TMDB liefert sie nicht), Kalender-Zeitfenster, „Auf Fernseher öffnen“, Wischgesten auf Karten.
