# Plan: eingebaute Dienstlisten, jedes Land, kleinere Dateien (25.11.2026)

Reihenfolge: erst kleine, risikoarme Aufteilungen (spart sofort Tokens), dann die Funktionen, zuletzt die
großen Umbauten von `routes.py`, `store.py` und `app.js`. Jeder Schritt: Tests grün, eigener Commit.

## A. Dateien aufteilen, Teil 1 (risikoarm)

- [ ] A1 `static/js/drawer.js` → `places.js` (Orts-/Länderlisten), `film-meta.js` (reine Helfer), `drawer.js` (HTML);
      drawer.js exportiert die Helfer weiter, kein Import anderswo ändert sich.
- [ ] A2 `tests/browser/test_pages.py` → `conftest.py` (Fake-Daten, Fixtures) + Testdateien nach Bereich
      (watchlist, details, phone, keyboard, settings, stats).
- [ ] A3 `tests/test_web.py` → Paket `tests/web/` mit eigener `conftest.py` und 5 Dateien.
- [ ] A4 `static/css/app.css` → 6 Dateien in gleicher Reihenfolge, nur an Abschnittsgrenzen geschnitten,
      eingebunden über ein Partial `partials/styles.html` mit einer gemeinsamen Version.
- [ ] A5 `scan_service.py` → `scan_run.py` (Modulfunktionen); `costs.py` → `cost_settings.py`.

## B. Eingebaute Dienstlisten (Ergebnis der Prüfung: weitgehend durch TMDB-Daten ersetzbar)

- [x] B1 `MOSTLY_FREE`-Rückfall entfernen: "Mostly free" kommt nur noch aus den Angeboten des Scans.
- [x] B2 `RENTAL_SHOPS` durch `rental_from_scan` ersetzen (Dienste, die nur leihen/kaufen anbieten).
- [x] B3 `_FREE_SERVICES`/`_MAIN_SUBSCRIPTIONS` weg: Gruppen auf "My services" aus Scan-Angeboten,
      Reihenfolge nach TMDB-Priorität.
- [x] B4 `_ALL_PROVIDERS` auf eine kleine Namens-Alias-Tabelle schrumpfen (gespeicherte Kurznamen wie
      "Prime Video" bleiben gültig); `_DEFAULT_ENABLED` und `MATCHING_CHANGED` entfernen.
- [x] B5 `platforms.toml` nur noch als optionaler Startwert; ein Land ohne Abschnitt startet leer.
Behalten: `_SECTION_ORDER` (Angebotsarten → Free/Paid), die Alias-Tabelle für Anzeigenamen.

## C. Jedes Land, wählbar mit Suche und Flagge

Ursachen, warum ein Länderwechsel heute keinen Scan startet: der Wechsel überspringt den Scan absichtlich,
wenn der letzte jünger als ein Tag ist; auf der Watchlist wird das Land gar nicht gespeichert (Reload zeigt
wieder das alte); eine schnelle zweite Wahl kann von einer älteren Antwort überholt werden.

- [x] C1 Prüfung `valid_country` (zwei Großbuchstaben, Flagge vorhanden) statt der festen Liste mit 4 Ländern,
      überall an der API-Grenze; Schleifen über alle Länder auf "benutzte Länder" umstellen.
- [x] C2 Länderliste von TMDB (`/watch/providers/regions`), gespeichert; ohne Schlüssel die Flaggen als Rückfall.
- [x] C3 Wechsel: Land speichern, immer Scan starten (ein frischer Scan desselben Landes von heute wird
      wiederverwendet), ältere Antworten verwerfen, Dienste des Landes mit `/api/latest` liefern.
- [x] C4 Auswahl als Dropdown mit Suchfeld und Flaggen (Header und Einstellungen), Tastatur und Handy.
- [x] C5 Neues Land startet mit leerer Dienstauswahl; die Seite "My services" bittet um Auswahl.

## D. Dateien aufteilen, Teil 2 (größer)

- [x] D1 `web/routes.py` → mehrere Module mit je `register(...)`; Tests patchen Module, nicht Namen.
- [x] D2 `watchlist_app/store.py` → Schema-Datei + Mixins (Scans, Favoriten/Flags, Backup).
- [x] D3 `static/js/filterbar.js` → `popovers.js`.
- [x] D4 `static/js/app.js` → Toast/Sync, Tastatur, Handy-Sheet, Scan-Ablauf als eigene Module.

## Nicht Teil dieses Plans
Stats-Seite, Zugangsschutz, PWA, Bildoptimierung.
