# Plan: Fehler beheben, Struktur verbessern, Funktionen ergänzen, dann Docker

Stand: 2026-11-15. Jede Etappe ist ein eigener Commit mit eigenen Tests; die App bleibt nach jedem Schritt lauffähig. Docker für Unraid kommt bewusst zuletzt. Struktur-Umbauten sind mit „(Struktur)“ markiert und stehen jeweils vor den Schritten, die darauf aufbauen.

Als Nächstes offen: Etappe 9g (Barrierefreiheit), 9h und 9i (Hauptseite), danach weiter mit Etappe 10.

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
- [ ] Seitenleiste: festes `aria-hidden="true"` entfernen; Escape schließt das Panel nur, wenn es offen ist (WDG #1).
- [ ] Filmkarte ist kein `role="button"` mehr; der Knopf „Details“ öffnet den Dialog, der Mausklick auf die Karte bleibt (WDG #2). Danach bekommen Stern, „Details“, Status und Notiz den Filmtitel im Namen, der Stern `aria-pressed` (WDG #14).
- [ ] Sichtbarer Fokus an Favoriten-Status und Notiz (`outline: none` und `!important` weg, WDG #3) und an „Restore from file“ / „Import favorites“ (WDG #11).
- [ ] Fokus bleibt am Ort: nach Favoriten-Klick und auf `/matches` nach „Looks right“, „Use this“, „Undo correction“ (WDG #4); auf `/matches` bleibt auch die Markierung „gespeichert“ an der Zeile, sonst Toast (ID #7).
- [ ] Dialoge geben den Fokus an den Auslöser zurück: eine Hilfsfunktion `openModal(id)` für alle vier Dialoge (WDG #5); jeder Dialog bekommt `aria-labelledby` (WDG #6).
- [ ] Mobiles Filterpanel: schließt nicht mehr nach jedem Häkchen, Fokus geht beim Öffnen hinein und beim Schließen zurück; oben ein Knopf „Done · n films“ (WDG #10, DC #10).
- [ ] „Random“ öffnet gleich das Detailfenster des Films (WDG #26, DC #19).

Ansagen für Screenreader:
- [ ] Scan: `aria-valuenow`/`min`/`max` am Balken, `role="status"` an der Meldung, `role="alert"` am Fehler (WDG #7).
- [ ] Trefferzahl mit `aria-live="polite"`, `aria-busy` am Raster während des Ladens (WDG #8); Vorschläge im Abend-Modus mit `aria-live` (WDG #27).
- [ ] `role="group"` bzw. `role="status"` an den `div`s, die heute nur ein `aria-label` tragen (WDG #9).
- [ ] Kleinigkeiten: `aria-hidden="true"` an Icons neben Text (WDG #18), Filter-Chips sagen „Remove filter …“ (WDG #19), versteckter Text „films“ / „services selected“ an den Zahlen der Dienstliste (WDG #20), Filmtitel als `<h3>` (WDG #21), Navigation in `<nav>` (WDG #22, zusammen mit DC #17 in Etappe 9h), `alt=""` am Poster auf `/matches` (WDG #30).

Lesbarkeit und Handy:
- [ ] Nicht verfügbare Karten: Deckkraft nur auf das Poster, Text bleibt in `--muted` (WDG #15, Kontrast heute geschätzt 2,5:1).
- [ ] `100dvh` statt `100vh` im mobilen Panel (WDG #16).
- [ ] Touch-Ziele mindestens 44 px: Vergleichs-Checkbox, Filter-Chips, Favoriten-Status und Notiz (WDG #17).
- [ ] Schrift in vier Stufen als Variablen, nichts unter 12 px: `.75rem` für Pillen und Zähler, `.875rem` für Knöpfe, Filter, Tabellen und Angaben auf der Karte, `1rem` für Erklärtexte und Filmtitel (DG #3, ersetzt WDG #28). Heute zwölf Zwischengrößen von 9,9 bis 16,8 px. Die wirkungslose Angabe `font-family: Georgia` entfällt.
- [ ] `prefers-reduced-motion` beachten, in CSS und beim sanften Scrollen (WDG #24).
- [ ] Sichtbare Beschriftung „from“/„to“ an den Jahresfeldern (WDG #23).
- [ ] Suche zeichnet erst nach rund 150 ms Pause neu (WDG #25); Leerzeichen bei „Database:“ auf der Status-Seite (WDG #29).
- Prüfung: Browser-Tests für die Tastatur-Wege (Stern bei Film n, Fokus bleibt; Details öffnen und mit Escape schließen, Fokus zurück; drei Dienste im mobilen Panel wählen). Kontrast im Browser messen, mobiles Panel auf einem echten Handy ansehen. Kein Test mit Screenreader geplant.

### Etappe 9h: Hauptseite aufräumen (Filter, Begriffe, erster Bildschirm)
In einem Rutsch, damit die Seite nur einmal „umzieht“.
- [ ] Chips für alle 13 Filter (es fehlen „Media“, „Availability changes“, „Minimum providers“) und ein Knopf „Reset filters“ (DC #1).
- [ ] Leerer Zustand: „No film matches these filters.“ mit „Reset filters“ und, ohne gewählten Dienst, „Select my subscriptions“ (DC #2).
- [ ] „Free“ eindeutig machen: Abschnitt heißt „Free & with ads“, das Dienst-Abzeichen „Mostly free“; der Filter „Availability“ behält nur eine Achse, die erste Option heißt „Everything (incl. unavailable)“, „Only on one of my services“ wird ein eigenes Kontrollkästchen (DC #3).
- [ ] Überall „service“ statt „provider“; „Rental shops“ bleibt (DC #14).
- [ ] Werkzeugleiste kürzen: die fünf Export- und Import-Knöpfe in ein `<details>` „Export / import“ oder auf die Einstellungsseite neben die Sicherung; nur ein Knopf in Akzentfarbe (DC #4).
- [ ] „Any / All selected services“ in die Seitenleiste zu den Diensten (DC #5).
- [x] Seltene Filter in `<details>` „More filters (n active)“; sichtbar bleiben Suche, Verfügbarkeit, Genre, Laufzeit, Bewertung (DC #6). Der offene Punkt zum Stichwort-Filter (3676 Einträge) bleibt in Etappe 9c. Vorgezogen und erledigt (2026-11-16): Sichtbar bleiben die fünf genannten; Angebotsart, Jahr von/bis, Stimmen, Stichwort, Medien, Änderungen und Anzahl der Dienste liegen unter „More filters“, die Zusammenfassung zählt gesetzte Filter („More filters (2 active)“). Auf dem Handy ist der Filterbereich 243 px statt 578 px hoch. Browser-Test für den Zähler.
- Regel für neue Filter: Die sichtbare Reihe bleibt bei diesen fünf. Jeder neue Filter kommt unter „More filters“, auch die aus den Etappen 11 bis 14. Ein neuer Filter darf nur in die sichtbare Reihe, wenn er dort einen anderen ersetzt.
- [ ] Ruhender Scan als eine Zeile („Saved results from … · Scan now“), Statistik unter die Ergebnisse oder in ein `<details>`, Überschrift höchstens 3rem (DC #7). „Grey out films found unavailable“ nur während eines neuen Scans zeigen (ID #16).
- [ ] Favoriten-Ansicht deutlich machen: Zeile „Showing your favorites only · Show all films“ über dem Raster, Knopf heißt fest „My favorites“ mit `aria-pressed` (ID #9).
- [ ] „Desktop layout“ über 800 px ausblenden und in „Wide view“ umbenennen (DC #9).
- [ ] Eine gemeinsame Navigation `partials/page-nav.html` in `<nav>` mit allen Seiten, die aktuelle mit `aria-current="page"` (DC #17, WDG #22). Nach Etappe 9e, weil dort `/costs` entfällt.
- [ ] Einleitungstext kürzen oder streichen (DC #18).
- [ ] Kopfzeile auf dem Handy: die sechs Knöpfe überlappen und „Status“ ist abgeschnitten; umbrechen lassen oder nur „Filters“ als Knopf zeigen, die Seitenlinks in die gemeinsame Navigation (DC #21). Dabei das Länder-Select als Steuerelement gestalten (Rahmen, Pfeil; Rest von DC #15 aus Etappe 9f).
- [ ] Statistik-Zeile geht auf: „8 free · 162 paid“ ergibt 170 bei 169 Filmen; „(1 in both)“ ergänzen oder kürzen (DC #24; dass die Statistik der Auswahl nicht folgte, ist mit 9f behoben). Der Balken füllt sich bei gespeicherten Ergebnissen nicht mehr von 0 auf 100 % (entfällt mit der einzeiligen Scan-Anzeige).
- Farbe und Bausteine, aus [reviews/design-guide.md](reviews/design-guide.md) (DG, 6 Empfehlungen, im Browser gemessen; dort stehen die genauen Werte):
  - [ ] Bernstein nur für Bedienung: der Dienstname auf der Karte wird eine neutrale Pille (`#252d29` / `#d9d3c7`), damit er nicht wie „With ads“ aussieht (DG #1).
  - [ ] Eine Klasse `.pill` mit den Tönen ok, warn, danger, neutral für Angebotsart, „Free“ am Dienst, Ergebnis auf der Status-Seite und Hinweis auf `/matches`; heute vier verschiedene Bausteine (DG #2).
  - [ ] Zeitpunkte ohne Sekunden über eine Hilfsfunktion in `static/js/ui.js` („15 Nov 2026, 23:10“), an vier Stellen (DG #4).
  - [ ] „Details“ auf der Karte als normaler `btn btn-sm`, `.film-details-button` entfällt (DG #6).
  - [ ] Optional: fast gleiche Farbwerte durch fünf neue Variablen ersetzen (51 Werte bei 6 Variablen, DG #5). Voraussetzung für „Helles Design“ in Etappe 14.
- Kleinere Variante: nur DC #1 und #2 (wenige Zeilen, beseitigen „Warum fehlt mein Film?“), den Umbau der Seite später.
- Prüfung: JS-Tests für Chips und „Reset filters“, Browser-Test für den leeren Zustand; vorhandene Browser-Tests an die neuen Texte anpassen. Bildschirmfoto vom ersten Bildschirm auf Desktop und Handy, vorher und nachher. Danach eine Woche nutzen und notieren, welche Filter gesetzt werden (URL-Parameter).

### Etappe 9i: Vom Vorschlag bis „gesehen“
- [ ] Abend-Modus: Vorschläge sind Knöpfe, die das Detailfenster öffnen, mit „· on Netflix“ dahinter; Hinweis „Uses the subscriptions saved in Settings.“ (DC #13). Genre und Laufzeit in `localStorage` merken (ID #13).
- [ ] „Watched“ wirkt: „Random“ und Abend-Modus überspringen gesehene Filme; kleines Abzeichen „Watched“ im Raster (ID #10).
- [ ] Link zum Ansehen: Feld `link` aus der TMDB-Antwort „watch/providers“ (JustWatch-Seite je Land) speichern und im Detailfenster als Hauptknopf „Where to watch“ zeigen (ID #11). Vorher prüfen, ob TMDB das Feld für alle Länder liefert; nur als gültige `https://www.themoviedb.org/`-Adresse ausgeben (`validation.py`).
- [ ] Detailfenster zeigt die eigenen Abos: in jeder Gruppe zuerst und markiert (DC #22). Heute sehen fremde Dienste wie MUBI genauso aus wie ein eigener.
- [ ] Rückgängig nach dem Entfernen eines Favoriten: Toast mit „Undo“, rund 5 s, stellt Status und Notiz wieder her (DC #11; aus Etappe 14 vorgezogen).
- [ ] Vergleich: Knopf „Compare (n)“, aktiv ab 2; Checkbox sichtbar beschriftet; „Clear selection“ im Vergleichsdialog (DC #12, ID #8).
- [ ] Status und Notiz lassen die Karte nicht mehr springen: nur in der Favoriten-Ansicht und im Detailfenster zeigen (ID #15).
- Prüfung: JS-Tests für `eveningSuggestions` ohne gesehene Filme und für den Zähler am Vergleich; Test für das Feld `link` aus einer TMDB-Antwort und in der Sicherung; Browser-Test für „Undo“.

### Etappe 10: Entscheidungshilfe
- [x] Zufallsknopf („Würfeln“): ein Film aus der aktuellen Filteransicht. Erster, einfacher Schritt zum Abend-Modus.
- [x] Abend-Modus: Zeit und Genre angeben, drei Vorschläge aus den eigenen Abos.
- [ ] „Läuft bald aus“ / „kürzlich entfernt“ aus der Historie (TMDB liefert kein Ablaufdatum).
- [ ] Gewichtete Sortierung: Bewertung pro Laufzeit, am längsten auf der Watchlist, Anzahl eigener Abos.
- [ ] Filmreihen (TMDB „Collections“) zusammen anzeigen.
- [ ] Ähnliche Filme: zu einem Watchlist-Film zeigen, was Vergleichbares auf den eigenen Abos läuft (TMDB „similar“ / „recommendations“).

### Etappe 11: Startdatum (eigene Etappe)
- [ ] Für noch nicht erschienene Watchlist-Filme Kino- und Heimkino-Start anzeigen (TMDB „release_dates“ je Land).
- [ ] Eigene Ansicht „Demnächst“ mit Sortierung nach Datum.
- [ ] Meldung, sobald ein solcher Film streambar wird (nutzt die Historie; Zustellung kommt mit Etappe 16).
- [ ] Altersfreigabe (FSK je Land) anzeigen und als Filter unter „More filters“, etwa für Filmabende mit Kindern. Kommt aus derselben Abfrage „release_dates“.
- Baut auf Zeitplan (Etappe 7) und Historie (Etappe 6) auf.

### Etappe 12: Mehr Daten pro Film
- [ ] Letterboxd-Durchschnittsbewertung: steht auf der Filmseite, die der Scan für die TMDB-ID ohnehin lädt; keine zusätzliche Abfrage. Als Sortierung und als Filter unter „More filters“; ersetzt die TMDB-Bewertung in der sichtbaren Reihe, falls sie sich als nützlicher erweist.
- [ ] Reihenfolge der Watchlist speichern: die Letterboxd-Seite ist nach „zuletzt hinzugefügt“ sortiert, die Position ersetzt das Aufnahmedatum auch ohne CSV-Export.
- [ ] Letterboxd-Daten: Datum der Aufnahme in die Watchlist (nur im CSV-Export), eigene Bewertung.
- [ ] Originalsprache und Herkunftsland als Filter unter „More filters“ (steckt schon in der TMDB-Antwort).
- [ ] Verfügbarkeit in anderen Ländern („in DE nicht, aber in GB auf Netflix“); der TMDB-Aufruf liefert alle Länder ohne zusätzliche Abfragen.
- [ ] Anbieter-Logos statt Textnamen (TMDB liefert die Bilder).
- [ ] Qualität und Sprache: nur mit zusätzlicher Datenquelle möglich; aufwendig, zuletzt in dieser Etappe und optional.

### Etappe 13: Übersicht und Auswertung
- [ ] Watchlist-Statistik über Zeit: Zugänge, weggeschaute Filme, Abdeckung je Dienst (braucht gespeicherte Scan-Stände aus Etappe 6).
- [ ] „Staubfänger“: Filme, die lange auf der Liste stehen und seit Monaten verfügbar sind (braucht das Watchlist-Datum oder die Reihenfolge aus Etappe 12).
- [ ] Laufzeit-Summe der verfügbaren Filme je Dienst.
- [ ] Eigene Schlagworte pro Film und Filter danach (unter „More filters“).

### Etappe 14: Bedienung
- [ ] Listenansicht (kompakte, sortierbare Tabelle) neben der Kartenansicht.
- [ ] Gespeicherte Filter als Knöpfe.
- [ ] Filter auf dem Handy einklappbar: mit „More filters“ (Etappe 9h) ist der Bereich nur noch 243 px hoch; erst nach einer Woche Nutzung entscheiden, ob noch nötig.
- [ ] Favoriten-Status mit dem Letterboxd-Tagebuch abgleichen; gesehene Filme ausblenden.
- [ ] Helles Design und Farbwahl. Erst nach den Farb-Variablen aus Etappe 9h (DG #5); die App ist heute bewusst nur dunkel und bleibt es auch bei hellem System.
- [ ] Tastatur-Bedienung: `/` Suche, `r` Random, Pfeiltasten durch die Karten, `f` Favorit; nur wenn der Fokus nicht in einem Eingabefeld ist, Kürzel im `title` des Knopfs (ID #17).
- [ ] „Nicht interessiert“: Film in der App ausblenden, ohne die Letterboxd-Watchlist zu ändern; eigener Filter unter „More filters“, um ihn wieder zu zeigen.
- [ ] Erster Start: ohne Benutzernamen und ohne Watchlist-Datei öffnet die App die Einstellungsseite statt eines leeren Rasters.
- Rückgängig nach dem Entfernen eines Favoriten steht jetzt in Etappe 9i.

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
- [x] `.env` in `.dockerignore` aufnehmen (API-Key nicht ins Image; mit Etappe 9c erledigt).
- [ ] `TMDB_API_KEY`, `LETTERBOXD_USERNAME`, `COUNTRY` als Umgebungsvariablen in `docker-compose.yml`.
- [ ] `platforms.toml` aus `/data` lesen (entfällt, falls Etappe 7 die Datei ersetzt hat).
- [ ] Container als Nicht-root-Benutzer mit PUID/PGID.
- [x] `pytest` in `requirements-dev.txt` auslagern (mit Etappe 8 erledigt).
- Prüfung: Image bauen und starten (auf diesem PC nicht möglich, Docker fehlt).

## Nicht im Plan (frühere Ideen)

Direkt-Link in die App des Anbieters (TMDB liefert nur den Link zur JustWatch-Seite, siehe Etappe 9i), mehrere Letterboxd-Profile, weitere Letterboxd-Listen, Serien, Abgleich mit Plex/Jellyfin, deutsche Oberfläche (offene Frage aus der Design-Kritik: die Oberfläche ist englisch), Push-Nachrichten über Discord/Telegram, installierbare App im LAN (HTTPS, Icons), Zugriffsschutz, umgekehrte Suche (Vorschläge außerhalb der Watchlist), Filmsuche ohne Watchlist.
