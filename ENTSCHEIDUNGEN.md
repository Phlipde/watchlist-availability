# Entscheidungen und Fortschritt der selbstständigen Arbeit (ab 2026-11-18)

Auftrag: Plan von oben nach unten abarbeiten, nach jedem Schritt prüfen, nach jeder Etappe committen, Fragen vermeiden und selbst abwägen. Jede eigene Entscheidung steht hier mit **[ENTSCHIEDEN]**, jede nicht erledigte oder nicht prüfbare Sache mit **[OFFEN]**, jeder gefundene Fehler außerhalb des Plans mit **[FEHLER]**. Der Plan selbst steht in `PLAN.md`.

## Legende
- **[ENTSCHIEDEN]** ich habe abgewogen und entschieden, ohne zu fragen
- **[OFFEN]** nicht fertig oder nicht überprüfbar (Grund dabei)
- **[FEHLER]** Fehler gefunden, der nicht im Plan stand (steht auch im Plan)
- **[ERLEDIGT]** fertig und geprüft (mit welchen Tests)

## Stand (2026-11-18, Ende der selbstständigen Arbeit)

Erledigt und committet (Reihenfolge der Commits): 17a Docker-Grundlage · K3c Filterleiste · A1 Abos-Mindestversion und Settings → My services · K4 Teil 1 (Schublade, Karten-Menü, Watched und Not now, Tastaturkürzel) · A2 Empfehlungen und Fristen · A3 Abdeckung, Tempo, Leih-Poster · A4 Wert und Dienst-Schublade · Barrierefreiheits-Durchgang (Kontrast, 44-px-Ziele, Detektor) · K5 Benachrichtigungen und Sensoren · A5 Budget-Planer, Rotation, Was-wäre-wenn · A6 Kalender-Feed und Überschneidung, PWA · 17b Schlüsselprüfung · K6 gespeicherte Ansichten und `content-visibility`.

Nicht gebaut oder offen (Gründe stehen in den Abschnitten und in PLAN.md):
- K4: Neuaufbau des Detailfensters nach Vorlage, Vergleichsleiste, Ausgrauen gesehener Filme, Vorladen beim Überfahren, Langdruck am Handy.
- K5: Zeitplan alle 6 Stunden und „checking…“ (bewusst entfallen), Nachricht pro Film mit `?film=`.
- A4/A6: Verlauf über 12 Monate, „andere Länder“, „Watch these first“ (keine Ablaufdaten), Channel-Preisvergleich.
- K6: Ansichten Grid/Compact/Table, Einrichtung unter 60 Sekunden, deutsche Titel, TV-Ansicht, Zoom- und Größenmessung.
- 17b: Datenbank aufräumen; Etappen 11 bis 16 der alten Liste, soweit nicht in K4 bis K6 aufgegangen.
- Nicht prüfbar hier: Lauf auf Unraid und GitHub-Prüfungen (kein Push von mir), Offline-Aufruf, Installation als App, echte Benachrichtigungen, Verhalten unter https.

Immer geprüft vor jedem Commit: `ruff check`, `ruff format --check`, `mypy`, Python-, JS- und Browser-Tests. Letzter Stand: Python 339, JS 50, Browser 33.

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

### Impeccable- und Barrierefreiheits-Prüfung (2026-11-18, nach A3)
- **[ERLEDIGT]** `impeccable detect` über CSS, JS und Vorlagen: zwei Funde „side-tab“ (3-px-Seitenrand an Banner und Empfehlungskarten) behoben: Punkt vor der Überschrift und feiner Rand statt Seitenstreifen (die Vorlage verlangte den Streifen; ich habe die Regel des Werkzeugs vorgezogen, weil sie als typisches KI-Merkmal gilt).
- **[OFFEN]** Der Detektor kann die Seiten nicht im Browser prüfen (`Failed to launch the browser process`, kein Chromium für Puppeteer); „flat-type-hierarchy“ in den Vorlagen ist ein Messartefakt (CSS wurde nicht gelesen, die Überschrift ist 1,5 rem gegen 0,875 rem Text).
- **[ERLEDIGT]** Eigene Kontrastprüfung im Browser (alle Textknoten, Seiten `/`, `/watchlist`, `/subscriptions`, `/settings`, `/settings/services`, `/settings/data`, `/stats`): Fund nur bei Optionen ohne Treffer (abgeblendet durch `opacity`, Verhältnis 2,2 bis 4,1); behoben (Farbe `--muted`, Logos halb durchsichtig). Danach keine Fehler. Nicht gemessen: Bild-Texte, Hover- und Fokus-Zustände.
- **[ERLEDIGT]** Touch-Ziele am Handy (375 px, `pointer: coarse`): Schaltflächen, Chips, Tabs, Sync-Punkt, Preis- und Datumsfelder, Zeilen der Dienste-Liste und Links in Karten jetzt mindestens 44 px; Titel auf Karten gelten über die ganze Karte, Fließtext-Links ausgenommen.

### A4 Wert und Detail
- **[ENTSCHIEDEN]** Wertformel ohne `leaving_boost` und mit fester Schwelle 3,8; keine Einstellung dafür (Plan-Entscheidung A-Teil).
- **[ENTSCHIEDEN]** Schublade als natives `<dialog>` (nicht Bootstrap), weil die Abo-Seite kein Bootstrap-JS braucht und `dialog` Fokusfalle und Escape mitbringt.
- **[ENTSCHIEDEN]** Preis bleibt monatlich; „geteilt mit n“ teilt den Preis (Summe und € / film rechnen mit dem Anteil).
- **[ENTSCHIEDEN]** Kündigungsseite nur http(s), keine Leerzeichen, höchstens 300 Zeichen (Server prüft, Link mit `rel=noreferrer noopener`).
- **[OFFEN]** Verlauf „Only here über Zeit“ (braucht 30 Tage gespeicherte Scans), „Watch these first“, „Add all to Today“, Laufzeit monatlich/jährlich, Channel-Preisvergleich: nicht gebaut (siehe PLAN, Ergebnis A4).
- **[ERLEDIGT]** A4: Python 321, Browser-Test Schublade; im Browser angesehen.

### K5 Benachrichtigungen
- **[ENTSCHIEDEN]** Läuft im vorhandenen Zeitplan-Thread (jede Minute geprüft), nicht als eigener Dienst; Fehlschläge werden dort wiederholt.
- **[ENTSCHIEDEN]** Ruhezeit 22 bis 8 Uhr fest; ein Tageslimit von einer Nachricht (Ereignisse werden gebündelt, ein Test ignoriert das Limit).
- **[ENTSCHIEDEN]** Token liegt in der Datenbank (`notify_token`), nicht in Sicherungen und nicht in `/api/settings` (nur „gesetzt“).
- **[ENTSCHIEDEN]** Nur http/https als Ziel. **Risiko:** der Server schickt Anfragen an die eingetragene Adresse (auch an Adressen im Heimnetz); wer die Einstellungen ändern kann, kann das lenken. Die App hat keine Anmeldung (siehe README); das war schon so, bleibt aber hier wichtig.
- **[ENTSCHIEDEN]** Zeitplan alle 6 Stunden entfällt (Plan 8b hat ihn bewusst entfernt, TMDB-Angebote werden 24 h wiederverwendet).
- **[OFFEN]** Kein echter Sendeversuch gegen ntfy/Gotify/einen Webhook (nur mit Atrappe getestet).
- **[ERLEDIGT]** K5: Python 331 (davon 7 Benachrichtigungen, 3 Web), ruff, mypy.

### A5 Planung
- **[ENTSCHIEDEN]** Preise für Dienste, die der Nutzer nicht hat, nur im Browser (`localStorage`), nicht in der Datenbank: Es gibt keine verlässlichen Preise (nichts schätzen), und `clean_costs` lässt Preise nur für eigene Dienste zu.
- **[ENTSCHIEDEN]** Rechnung im Browser (`planner.js`, getestet), nicht auf dem Server: der Regler soll sofort reagieren.
- **[ENTSCHIEDEN]** Die Mengensuche probiert alle Teilmengen von höchstens 14 Diensten (16 384 Fälle); mehr Dienste gibt es nicht auf der Seite (eigene plus die 12 mit dem größten Zuwachs).
- **[ENTSCHIEDEN]** Kein „Apply to my services“ im Was-wäre-wenn (Auswahl bleibt unter Settings → My services; sonst zwei Orte für dieselbe Sache).
- **[ERLEDIGT]** A5: Python 332, JS 50, Browser-Test; Abschnitt im Browser angesehen.

### A6 und K6 (PWA)
- **[ENTSCHIEDEN]** Kalender-Feed nur aus vom Nutzer eingetragenen Daten; zwei Termine, wenn eine Kündigungsfrist eingetragen ist.
- **[ENTSCHIEDEN]** Skripte und Stile im Service Worker „Netz zuerst“ statt „Speicher zuerst“: Module importieren einander ohne Versionsnummer, ein Mischstand aus alten und neuen Dateien würde die Seite zerbrechen. Preis: offline erst nach einem Besuch, online immer aktuell.
- **[ENTSCHIEDEN]** Symbole selbst gezeichnet (Filmstreifen mit Dreieck), ohne Bildbibliothek; das Skript liegt in `scripts/make_icons.py` und wird nur bei einer Designänderung gebraucht.
- **[ENTSCHIEDEN]** Ein Hinweis „Offline: showing the data from …“ als Toast, kein eigenes Banner.
- **[OFFEN]** Offline-Aufruf selbst nicht automatisch getestet (Playwright-Grenze), Installation auf einem Gerät und https nicht geprüft.
- **[OFFEN]** A6: „andere Länder“ und Verlauf über 12 Monate nicht gebaut (siehe PLAN).
- **[ERLEDIGT]** A6/K6-PWA: Python 336, Browser-Test Service Worker, ruff, mypy.

### 17b TMDB-Schlüssel prüfen
- **[ENTSCHIEDEN]** Der Knopf fragt TMDBs `/configuration` (billigste Anfrage mit Schlüssel); der Schlüssel erscheint nie in der Antwort oder im Fehlertext.
- **[OFFEN]** Datenbank aufräumen (`VACUUM`, alte Filmdaten) bleibt offen: sinnvoll erst nach Monaten Betrieb.
- **[ERLEDIGT]** Python 338.

### K6 gespeicherte Ansichten und Leistung
- **[ENTSCHIEDEN]** Ansichten nur im Browser (`localStorage`), nicht in der Datenbank: kein neues Datenmodell, nichts in der Sicherung nötig; ein Gerätewechsel zeigt sie nicht (Preis, bewusst).
- **[ENTSCHIEDEN]** Keine Auswahl „links in der Leiste“: die Chips über dem Raster und auf Tonight reichen und kosten keinen Platz in der Leiste.
- **[ENTSCHIEDEN]** `content-visibility: auto` mit geschätzter Höhe 400 px je Karte; Messung siehe PLAN (Verbesserung etwa ein Drittel bis die Hälfte beim Neuzeichnen).
- **[ERLEDIGT]** JS 50, Browser 33.
- **[FEHLER]** (nicht im Plan, beim letzten Lauf gefunden) `app.js` enthielt eine alte Zeile, die beim Laden jeder Seite alle Service Worker abmeldete („The offline worker was removed“). Dadurch war die PWA-Anmeldung wirkungslos; der Browser-Test bestand nur zufällig einmal. Zeile entfernt, Test für das Wiederauftreten (`test_no_script_removes_the_service_worker_again`), Worker-Test 3 von 3 grün.

### K6-Rest (Ansichten, erster Start, Größe)
- **[ENTSCHIEDEN]** Compact und Table ohne Herz und „⋯“: dort steht die Schublade zur Verfügung; sonst würde die kleine Karte wieder voll.
- **[ENTSCHIEDEN]** Table-Spalten nicht sortierbar (die Sortierung gehört zur Leiste, eine zweite Sortierung wäre doppelt).
- **[ENTSCHIEDEN]** Erster Start als Hinweiskasten auf Tonight statt eines Assistenten: kleinster Weg, der „was jetzt?“ beantwortet.
- **[ENTSCHIEDEN]** Deutsche Titel nicht gebaut: die Scan-Daten tragen nur den englischen/Originaltitel, ein Umbau der Daten wäre ein eigener Schritt.
- **[OFFEN]** TV-Ansicht, Zustands-Texte, 200-%-Zoom-Prüfung.
- **[ERLEDIGT]** Python 340, JS 51, Browser 35; Compact im Browser angesehen.

### K4 Teil 2 (Hauptknopf)
- **[ENTSCHIEDEN]** Hauptknopf nennt den günstigsten eigenen Weg (gratis vor Werbung vor Abo); führt zur TMDB-Seite (keine Direkt-Links, entschieden).
- **[FEHLER]** (nicht im Plan) `.btn-accent` war mit Tabler wirkungslos (nur `--bs-btn-*` gesetzt). Behoben; betrifft alle Knöpfe dieser Klasse (z. B. „Pick for me“, Speichern).
- **[OFFEN]** Hero-Bild, Zeitleiste, Trailer-Vorschau, Vergleichsleiste.

### Übersprungenes, auf Wunsch gebaut: Detailfenster und Vergleichsleiste
- **[ENTSCHIEDEN]** Kein Trailer-Vorschaubild von YouTube (`img.youtube.com`): das wäre beim bloßen Öffnen eine Anfrage an Google. Statt dessen Wiedergabe-Knopf auf dem TMDB-Backdrop.
- **[ENTSCHIEDEN]** Das Backdrop-Feld gab es schon im Datenweg (`backdrop_path`), es war nichts umzubauen.
- **[ENTSCHIEDEN]** Vergleichsleiste statt Knopf und Modus; die Boxen auf den Postern erscheinen, solange die Leiste da ist.
- **[ENTSCHIEDEN]** „Best“ nur bei mindestens zwei Werten und ohne Gleichstand aller (sonst nichts hervorheben); für Screenreader „(best)“ im Text.
- **[OFFEN]** Zeitleiste je Dienst (braucht gespeicherte Scans über 12 Monate).
- **[ERLEDIGT]** Python 340, JS 51, Browser 37.

### Abgleich der alten Etappen 11 bis 16 (2026-11-18)
Erledigt durch K1 bis K6 und A1 bis A6 (im Plan abgehakt): Listenansicht, gespeicherte Filter, Tastatur, „Nicht interessiert“, erster Start, Kalender-Feed, Wochenzusammenfassung, Laufzeit je Dienst.
Noch offen (zur Auswahl): 11 Meldung, wenn ein „Demnächst“-Film streambar wird · 12 Aufnahmedatum und eigene Bewertung aus dem Letterboxd-CSV, Qualität und Sprache (braucht andere Quelle) · 13 Statistik über Zeit (Anfang gemacht: Verlauf „Only here“), „Staubfänger“, eigene Schlagworte · 14 Abgleich mit dem Letterboxd-Tagebuch (neue Quelle, entschieden: nein) · 15 Abstimmung und Gäste-Abos · 16 Startseiten-Kachel, RSS, Dokumentation der kleinen API.

### Übersprungenes, auf Wunsch gebaut: Zustände, andere Länder, Verlauf
- **[ENTSCHIEDEN]** Zustands-Banner statt weiterer Toasts: bleibt stehen, bis ein Scan gelingt; die alten Daten bleiben sichtbar.
- **[ENTSCHIEDEN]** Andere Länder nur aus gespeicherten Angeboten und nur, wenn für mindestens die Hälfte der Filme Angebote da sind (sonst wäre der Vergleich unfair).
- **[ENTSCHIEDEN]** Verlauf in eigener kleiner Tabelle (ein Eintrag je Dienst und Tag) statt aus alten Scans: Scans werden auf 30 je Land gekürzt, die Tabelle hält ein Jahr billig.
- **[OFFEN]** Der Verlauf ist leer, bis zwei verschiedene Tage gescannt wurden.
- **[ERLEDIGT]** Python 343, JS 52, Browser 38.

### Rest der alten Etappen: selbst entschieden (2026-11-18, auf "versuche zu entscheiden")
- **[ERLEDIGT]** 16: Startseiten-Kachel `/tile`, RSS `/feed.xml`, API-Übersicht in der README. Kachel zeigt "neu diese Woche" (höchstens 5) und einen Tipp des Tages: gut bewerteter Film auf den eigenen Diensten, nicht gesehen und nicht zurückgestellt, über den Tag stabil (Auswahl nach Datum aus der besser bewerteten Hälfte). Zeitraum und Auswahl sind bewusst fest.
- **[ENTSCHIEDEN]** 11 (Meldung, wenn ein "Demnächst"-Film streambar wird): nichts Neues gebaut. Wird ein Film streambar, ist es für die App eine Änderung "added"; die Benachrichtigung "jeder neue Film" (K5), der RSS-Feed und "Newly available" melden das schon.
- **[ENTSCHIEDEN]** 13 "Staubfänger": steht schon auf der Statistik-Seite als "Waiting longest" (Watchlist-Position, nur eigene Dienste). Ein eigener Bildschirm brächte nichts dazu.
- **[ENTSCHIEDEN]** 13 eigene Schlagworte: nicht bauen. Bräuchte eine neue Tabelle, Eingabe, Filter und Backup-Pfad für etwas, das Letterboxd mit eigenen Tags und Listen besser kann.
- **[ENTSCHIEDEN]** 12 Aufnahmedatum und eigene Bewertung aus dem Letterboxd-CSV: nicht bauen. Die Position in der Watchlist ersetzt das Datum (K1), die eigene Bewertung hat keinen Zweck in einer App, die nur Verfügbarkeit zeigt.
- **[ENTSCHIEDEN]** 15 Abstimmung und Gäste-Abos: nicht bauen. Größter Umbau (neues Datenmodell, Zugriff ohne Anmeldung, Zweitprofile in Kosten und Planer) für einen Nutzer; die Empfehlung war schon im Plan "nur Heimnetz". Bleibt als Idee im Plan stehen.
- **[ERLEDIGT]** Gesehene Filme im Raster: Poster blasser (`is-watched`), Abzeichen "Watched" bleibt. JS 52 grün.

### Detailfenster fertiggestellt (2026-11-18)
- **[ENTSCHIEDEN]** Aktionen als Symbole in einer Zeile (Namen als `title` und im Screenreader-Text), weil sechs beschriftete Knöpfe in 480 px umbrechen; Favorit ist nur noch über `aria-pressed` und Farbe markiert, nicht mehr amber (nur der Hauptknopf ist amber).
- **[ENTSCHIEDEN]** Letterboxd-Link wandert aus den Chips unten in die Symbolleiste; "Share" kopiert die Adresse mit `?film=`.
- **[FEHLER]** Das Icon `ti-columns-gap` fehlt in der Schrift: Vergleichsknopf war leer. Ersetzt.
- **[OFFEN]** Mini-Poster bei "Similar", Zeitleiste je Dienst, Report-Link, Flaggen-Chips, Originaltitel: nicht gebaut, bleiben im Plan.
- **[OFFEN]** Ein Browser-Test (Dienst-Schublade) schlug einmal im Gesamtlauf fehl und lief danach allein 3-mal sowie im Gesamtlauf ohne meine Änderung durch: vermutlich ein Zeitproblem, nicht beobachtet wiederholt.
- **[ERLEDIGT]** Python 346, JS 52, Browser 39, ruff und mypy sauber.
- **[ERLEDIGT]** Detailfenster Rest: Originaltitel, Mini-Poster bei "Similar", JustWatch-Chip. Python 347, JS 52, Browser 39.
- **[ENTSCHIEDEN]** Nicht gebaut: Zeitleiste je Film (Daten gibt es nur je Dienst), "Report" (kein Ziel für Meldungen, ein toter Link wäre schlechter als keiner), Flaggen-Chips (Flaggen-Emoji erscheinen unter Windows als zwei Buchstaben).
- **[OFFEN]** Der Originaltitel erscheint erst nach dem nächsten Scan (`FILM_FORMAT` 3 erzwingt ihn).

### Kleine Restpunkte (2026-11-18)
- **[ERLEDIGT]** 200-%-Zoom: bei 640 px Breite (entspricht 200 % auf 1280 px) hat keine der acht Seiten waagerechtes Scrollen; breite Tabellen scrollen in ihrem eigenen Kasten (`.table-scroll`). JavaScript: 121 KB gzip für alle Dateien zusammen, unter 200 KB.
- **[ENTSCHIEDEN]** Deutsche Filmtitel: nicht gebaut. Die TMDB-Details werden einmal je Film gespeichert und von allen Ländern geteilt; ein Titel in Landessprache bräuchte Details je Sprache (mehr Abfragen, größere Datenbank). Der Originaltitel im Detailfenster deckt den Bedarf teilweise.
- **[ENTSCHIEDEN]** TV-Ansicht: nicht gebaut (im Plan "optional"; Tastatur-Bedienung und große Poster gibt es).
- **[ENTSCHIEDEN]** Datenbank aufräumen: nicht jetzt. Es lohnt erst nach Monaten Betrieb, und Löschen von Daten geht nur nach Rückfrage mit einer Liste, was entfällt.

### Design-Kritik vom 2026-11-21 (24/40) abgearbeitet
- **[ERLEDIGT]** Sync-Status: Ursache war eine Reihenfolge: nach dem Scan setzte der Kopf den Status, bevor das neue Scan-Datum ankam ("Out of date" neben "synced just now"). Eine Funktion `updateSyncLabel` entscheidet jetzt, und sie läuft nochmal, wenn der Scan angekommen ist. Der Status steht auf dem Desktop als Text ("Synced just now"), auf dem Handy bleibt nur der Punkt (Text für Screenreader).
- **[ERLEDIGT]** Handy-Karten: Die Dienst-Logos waren 8x28 px (gemessen); jetzt eigene Zeile, 28x28 px. Das Herz blieb auf der Karte (kleinere Variante: nicht ins Menü verschoben).
- **[ERLEDIGT]** "Pick for me": Chance wächst mit der TMDB-Bewertung (Bewertung hoch 3), im Fenster steht der Grund ("Highly rated · 1h 47m · on Netflix") und "Pick another".
- **[ERLEDIGT]** Watchlist-Leiste: der alte "Compact"-Knopf samt zweitem Mechanismus und Regeln entfernt (der Schalter Grid/Compact/Table bleibt), "My favorites" mit Herz statt Stern.
- **[ERLEDIGT]** Tonight: ein Film unter "New" steht nicht mehr zusätzlich in den Dienst-Reihen. "Free" und Dienst-Reihen dürfen sich weiter überschneiden (so war es gewollt).
- **[OFFEN]** Die Reihenfolge "Favorites first, then rating" wird nur im Sortiermenü erklärt, nicht an den Tonight-Reihen. Filter auf dem Handy bleiben ein langer Block (die Watchlist-Leiste bleibt; nur die Doppelung ist weg).
- **[ERLEDIGT]** Python 347, JS 54, Browser 40, ruff und mypy sauber.

### Detailfenster nach `drawer-update-prompt.md` (2026-11-21)
- **[ERLEDIGT]** Blöcke 0 bis F. Neue Module: `static/js/drawer.js` (reine Funktionen: Haupt-Button, Gruppen, Schlagwörter, Formate, HTML des Fensters), `static/js/abroad.js` (Länder-Reihenfolge und Tabelle). Python 348, JS 64, Browser 41, ruff und mypy sauber.
- **[ENTSCHIEDEN]** Der Titel steht im Hero; die Kopfleiste zeigt ihn erst, wenn er aus dem Bild scrollt (IntersectionObserver). Das Element `#film-details-title` bleibt immer im DOM (Tests und `aria-labelledby`), nur die Deckkraft wechselt.
- **[ENTSCHIEDEN]** Der Haupt-Button sagt immer, was zu tun ist ("Watch on X · Free", "Rent on X", "On X (not your service)", "Not streaming in Germany"); "Where to watch" kommt nicht mehr vor. Nur der erste Fall (schaubar auf eigenem Dienst) ist golden. Ohne TMDB-Adresse zeigt er auf die JustWatch-Suche (nie ein leerer Link; ein Browser-Test hat das gefunden).
- **[ENTSCHIEDEN]** Neue Datenfelder: Angebotsart `buy` (vorher verworfen) und `imdb_id`; `FILM_FORMAT` 4, der nächste Scan holt beides. Ein Film, der nur zu kaufen ist, gilt nicht als verfügbar (kein Abschnitt dafür), erscheint aber im Fenster als "Buy on X".
- **[ENTSCHIEDEN]** Länder-Reihenfolge nach der Tabelle im Auftrag; Abweichung: `LU` steht nicht in `sameLanguage` von DE, sonst hätte Luxemburg 6 Punkte wie AT und CH. Konfiguration für DE, FR, GB, US (die Regionen der App). Flaggen: SVG aus dem npm-Paket `flag-icons` 7.6.0 (MIT), 258 Länder-Dateien, 2,1 MB, in `static/flags/` mit Lizenz; keine Anfrage an Dritte.
- **[ENTSCHIEDEN]** "Abroad" zeigt nur Dienste, die der Film in der eigenen Region nicht hat, und nur freie, werbefinanzierte und Abo-Angebote (wie bisher "Also on your services"). Ein Klick auf eine Flagge öffnet nichts, weil die Datenquelle keinen Link je Land liefert; es gibt nur den Tooltip.
- **[OFFEN]** Nicht in den Daten und deshalb weggelassen (Regel: Felder ohne Quelle weglassen): Preise (Leihen/Kaufen), Qualität HD/4K, Sprache/Untertitel, "until"-Datum, Datum je Dienst, Trailer-Länge, IMDb-Bewertung, Letterboxd-Stimmen, nicht vorgemerkte Teile einer Filmreihe. "since" steht nur im Status-Abzeichen und nur, wenn genau ein Dienst betroffen ist. Der Status "Leaving" fehlt (keine Ablaufdaten).
- **[OFFEN]** Nicht geprüft: der Letterboxd-Link `letterboxd.com/tmdb/<id>/` (Weiterleitung, nicht geöffnet), Kontrast des Titels auf sehr hellen Backdrops (nur der Text unter dem Hero wurde gemessen: 59 Elemente, alle ≥ 4,5:1), das Ziehen am Griff des Handy-Blatts per Touch (nur Anblick bei 60 % Höhe).
- **[OFFEN]** Toter Code, nicht gelöscht: `availabilityByOffer` (`rendering.js`) und `elsewhereOnServices` (`filtering.js`) samt ihren Tests werden vom Fenster nicht mehr benutzt.
- **[ERLEDIGT]** Entfernt (CSS, nicht mehr erzeugte Klassen): `.film-modal-layout`, `.film-modal-poster`, `.film-modal-actions`, die alten Hero-, Chip- und Haupt-Button-Regeln und der Block "details, finished".

### Detailfenster: Rückmeldung zu Scrollen und "Other services" (2026-11-22)
- **[FEHLER]** Das Fenster ließ sich seitlich scrollen: Die Tooltips der Flaggen (`white-space: nowrap`, mittig) ragten über den Rand. Jetzt `overflow-x: hidden` am Inhalt, Tooltips mit Höchstbreite, die nach rechts wachsen und am rechten Rand nach links (`data-side`, gesetzt in `app.js`). Ein Browser-Test prüft `scrollWidth <= clientWidth`.
- **[ENTSCHIEDEN]** "Other services" und "Abroad" sind ein Block: ein eingeklapptes "Other services (10) · 3 abroad". Darin stehen die Dienste je Angebotsart als Logo-Reihe (Namen im Tooltip, eigene mit grünem Rand und Haken), darunter "Abroad on your services" mit Logo und drei Flaggen je Dienst. Statt eines Links je Dienst gibt es einen Link "All offers" unten (derselbe Weg wie der Haupt-Button) neben "Report". Das ist dem JustWatch-Muster nachempfunden; die Vorlage im Auftrag beschrieb nur Zeilen mit Link.
- **[ENTSCHIEDEN]** Der Zustand "Abroad aufgeklappt" wird nicht mehr gemerkt (der Block liegt im Aufklapp-Feld).
- **[ERLEDIGT]** Python 348, JS 64, Browser 43, ruff und mypy sauber.

### Pfeiltasten im Raster (2026-11-22)
- **[FEHLER]** Ursache: Es gab keine Pfeiltasten-Navigation im Raster, in keiner Ansicht. Der Plan-Punkt "Pfeiltasten im Raster" (K4) war nie gebaut worden; ←/→ blätterten nur im Fenster. Dass es in der normalen Ansicht "funktionierte", war vermutlich das Standard-Scrollen des Browsers bei ↑/↓. Zusätzlich blätterte das Fenster nur durch `article.film`, nicht durch Tabellenzeilen.
- **[ERLEDIGT]** Eine gemeinsame Navigation (`static/js/gridnav.js`, getestet): Spaltenzahl wird bei jedem Tastendruck aus den Positionen der Karten gemessen (kein fester Wert, Größenänderung inklusive), ←/→ eine Karte, ↑/↓ gleiche Spalte, unter einer kürzeren letzten Reihe die letzte Karte, Home/End, Tabelle = eine Spalte. Roving-Tabindex: nur der aktive Film hat die Tab-Stopps (Titel, Herz, "..."), Standard ist der erste; ein ausgefilterter Film fällt auf den ersten zurück. `scrollIntoView({block: "nearest"})` mit `scroll-margin` unter dem klebenden Kopf. Keine Abfangen in Eingabefeldern, Auswahlfeldern, Dialogen, offenen Menüs und bei offenem Fenster.
- **[ERLEDIGT]** Fenster: ←/→ blättern in allen drei Ansichten durch dieselbe Reihenfolge (Tabellenzeilen zählen mit). Escape gibt den Fokus an den Film zurück, den das Fenster zuletzt zeigte (nicht an den, der es geöffnet hat). Nach einem Neuzeichnen bleibt der Fokus auf demselben Film.
- **[ENTSCHIEDEN]** Beim Wechsel der Ansicht bleibt derselbe Film der aktive (Tab-Stopp) und wird ins Bild gerollt; der Fokus bleibt auf dem Umschalter (er würde sonst beim Klicken weggenommen).
- **[ERLEDIGT]** Tests: JS 67 (Spaltenberechnung und Zielindex), Browser 52 (Pfeile in Grid, Compact und Table bei 1400, 900 und 500 px, mit Enter, Escape und Blättern im Fenster). Die Test-Daten haben nur 2 Filme je Ansicht; die Spaltenberechnung für mehrere Reihen deckt der JS-Test ab.

### Tonight-Pfeiltasten und Antippen des Textes (2026-11-22)
- **[ERLEDIGT]** Tonight-Reihen: ←/→ entlang der Reihe, ↑/↓ in die Reihe darüber oder darunter (gleiche Stelle, soweit sie reicht), Home/End, ein Tab-Stopp für alle Reihen (`nextInRows` in `gridnav.js`, getestet). Dieselben Ausnahmen wie im Raster; die Pfeil-Knöpfe am Rand bleiben für die Maus.
- **[ERLEDIGT]** Detailfenster auf dem Handy (bis 800 px): Antippen des abgeschnittenen Beschreibungstextes klappt ihn auf (nur aufklappen; "less" bleibt der Knopf, damit ein Tippen beim Lesen nichts zuklappt). Auf dem Desktop bleibt es beim Knopf "more", damit Text markieren nichts auslöst.
- **[ERLEDIGT]** Python 348, JS 68, Browser 54, ruff und mypy sauber.

### Abgeschnittenes Detailfenster (2026-11-22, nach Bildschirmfoto "Jurassic Park")
- **[FEHLER]** Text, Haupt-Button, "Share" und die Poster-Reihe waren rechts abgeschnitten. Ursache: Das Fenster ist ein Grid; eine Spalte ist mindestens so breit wie ihr breitester Inhalt. Der Block "Part of ..." (ein `div` um die scrollende Poster-Reihe mit 8 Teilen) hat eine Mindestbreite von rund 620 px, die Spalte wurde breiter als das Fenster, und mein früheres `overflow-x: hidden` hat das nur abgeschnitten statt behoben. Jetzt `grid-template-columns: minmax(0, 1fr)` für `.film-modal-body` und `.film-modal-about`.
- **[FEHLER]** Mein erster Test dazu maß die Breite des Grids selbst und lief auch ohne die Korrektur durch (das Grid behält seine Breite, nur die Spalte wächst). Neu: Der Test prüft, dass jeder Block im Fenster rechts im Fenster endet, und er schlägt ohne die Korrektur fehl (gegengeprüft).
- **[ERLEDIGT]** Python 348, JS 68, Browser 55, ruff und mypy sauber. Im Browser mit "Jurassic Park" angesehen: Text bricht am Rand um, der Button hat seine runde Ecke.

### Flaggen laden zu langsam (2026-11-22)
- **[FEHLER]** Ursache: 26 Flaggen mit Wappen waren über 20 KB groß (Serbien 181 KB, Bolivien 103 KB, Mexiko 85 KB, Spanien 81 KB); die 258 Dateien hatten zusammen 2,1 MB, und ohne Cache-Kopf fragte der Browser bei jedem Öffnen neu.
- **[ERLEDIGT]** `scripts/shrink_flags.py` zeichnet jede Flagge über 5 KB einmal im Browser (80x60 px) und schreibt eine kleine SVG-Datei, die das PNG enthält: 59 Dateien, 1477 KB wurden 206 KB (Spanien 81 KB auf 2 KB). Dateinamen und Code bleiben gleich; die kleinen Flaggen bleiben Vektoren. Die Originale stammen aus dem npm-Paket `flag-icons` 7.6.0 und lassen sich neu holen. Überschrieben wurden genau diese 59 Dateien in `static/flags/`.
- **[ERLEDIGT]** `Cache-Control: public, max-age=2592000` für `/static/flags/` (ein Monat); der Test prüft Kopf und Größe unter 12 KB.
- **[ERLEDIGT]** Handy (375 px) mit "Jurassic Park" (13 Dienste, 104 Länder): kein Überlaufen (`scrollWidth` = `clientWidth`), im aufgeklappten Raster mit 101 Flaggen werden nur die sichtbaren geladen (lazy): 74 Anfragen, 91 KB. Die langsamste dauerte 2,4 s, weil der Vorschau-Server (Flask) sie nacheinander abarbeitet; unter gunicorn mit mehreren Threads ist das kürzer (nicht gemessen).
- **[OFFEN]** Eine einzige Bilddatei für alle Flaggen (Sprite) würde die Anfragen auf eine senken, kostet aber bei der ersten Flagge alles; nicht gebaut.
- **[ERLEDIGT]** Python 349, JS 68, Browser 55, ruff und mypy sauber.

### Auftrag "Buttons, Menüs und Filter-Panel" (2026-11-22, `buttons-und-menues-prompt.md`)
- **[ENTSCHIEDEN]** "Seen" bleibt (auf deinen Wunsch), heißt aber "Grey out" / "Greyed out"; Zurücksetzen auf der Daten-Seite (`POST /api/greyouts/reset`: löscht die Markierungen `watched` und setzt Favoriten mit Status "watched" auf "plan"). Taste `s` und Karten-Leiste bleiben. Letterboxd-Link ist der erste Link-Chip, Tooltip "Log or rate on Letterboxd", Taste `l`.
- **[ERLEDIGT]** Abschnitt 1: ein CSS-Satz für Primary, Secondary, Ghost, Dropdown-Auslöser, Segmented, Chip, Tab und Menü, Zustände und Größen sm/md/lg als Tokens (`--surface-2`, `--h-md` ...); die bisherigen Klassen (`.btn-outline-secondary`, `.filter-button`, `.segmented`, `.chip`) wurden überschrieben, nicht umbenannt. Segmente haben keinen goldenen Unterstrich mehr. Übersichtsseite `/dev/ui` (nur mit `WATCHLIST_DEV=1` oder Debug).
- **[ERLEDIGT]** Abschnitt 2: "More" ist weg; Teilen ist ein Link-Symbol in der Leiste; Export (Filme und Favoriten, CSV und JSON) und Import mit Vorschau ("2 favorites found · 0 already set · 2 new") liegen unter Settings -> Data.
- **[ERLEDIGT]** Abschnitt 3: Zeile 1 mit allen Bedienelementen (Herz-Symbol, Abroad, More filters, Sort, Link, Ansicht), Zeile 2 Tabs mit Zähler rechts, Zeile 3 aktive Filter mit "Reset all" und "Save view" (Ghost, öffnet Namensfeld); "Views" als Auswahl ganz links, nur wenn es welche gibt; "All" heißt "Available".
- **[ERLEDIGT]** Abschnitt 3b: Schalter "Abroad +N" (Zähler unter den anderen Filtern), Cost-Segmente mit Anteil ("383 (214 abroad)"), "383 of 430 films · 214 via VPN", Chip "Where: Here and abroad", URL `where=both|abroad`, Feld "Where" im Panel (Schalter und Feld sind eine Einstellung), Karte mit Logo, Flagge und "Abroad", Tonight mit letzter Reihe "On your services abroad". Server: `GET /api/abroad` aus gespeicherten Angeboten, im Speicher zwischengelagert (Schlüssel: Land, Scan, Version der Angebote, Dienste). Ein Film, der hier auf einem Dienst läuft, zählt nur als Inland.
- **[ERLEDIGT]** Abschnitt 4: Panel "More filters" mit Content, Availability, Extras, nur noch ein "Number of services" (Any, Only 1, 2+, 3+; die Doppelung "Only on one of my services" ist weg, alte Links mit `only=1` funktionieren), Zähler an den Chips als "12 · 80", Kopf mit "Reset", rechtsbündig im Fenster, Hintergrund 30 % abgedunkelt.
- **[ERLEDIGT]** Abschnitt 5: Karte mit kleinem Herz oben rechts auf dem Poster, Aktionsleiste (Compare, Not now, Grey out) am Posterfuß bei Hover und Fokus, Langdruck auf Touch, genau eine Anbieter-Zeile und "+N" (öffnet das Fenster bei "Other services"); `bestway.js` ist die eine Funktion für Karte und Haupt-Button; Tabelle mit Spalte "Services" aus kleinen Logos. Keine Preise, keine "..."-Menüs.
- **[OFFEN]** Nicht gebaut: das Verschieben von Year und Runtime in "More filters" bei schmalem Fenster (die Leiste bricht stattdessen um), ein kleines × je Feld im Panel, die Sortier-Option "Available here first" (Inlandsfilme stehen immer vor den Auslandsfilmen), Länder-Auswahl "Kleinststaaten" auf der Karte (gleiche Funktion wie im Fenster, aber nur an einem Beispiel geprüft), Marke "Watchlist availability" in Satzschreibung und das Land-Auswahlfeld als reiner Text, Tooltips "No rental shops selected" an "Rent 0".
- **[FEHLER]** In `.env` (deine lokale Datei, nicht im Repository) steht `WATCHLIST_DEV=1`; das machte den Test für `/dev/ui` rot. Der Test löscht die Variable jetzt vorher. Wer die Zeile dort eingetragen hat, weiß ich nicht.
- **[ERLEDIGT]** Python 353, JS 81, Browser 58, ruff und mypy sauber.

### Karte: nur das Logo, der Text bei Hover oder Tippen (2026-11-22)
- **[ERLEDIGT]** Die Anbieter-Zeile auf der Karte zeigt nur noch das Logo (ohne Logo den Namen als kleine Pille) und "+N"; der Text ("Free", "Netflix · Subscription", "Rent · 6 shops", "Abroad in Italy, on Prime Video" ...) kommt als Blase bei Hover und Tastaturfokus. Der Text bleibt für Screenreader immer im Dokument. "Not streaming" ist ein gedämpftes Symbol, "nur auf fremdem Abo" ein gedämpftes Logo.
- **[ERLEDIGT]** Touch: Das erste Tippen auf das Logo zeigt die Blase, das zweite geht zum Dienst; ein Tippen daneben schließt sie. Auf dem echten Handy nicht getestet (nur die Logik und ein Browser-Test für Hover).
- **[ERLEDIGT]** Python 353, JS 81, Browser 59, ruff und mypy sauber.

### Kartenreihe, Panel und README (2026-11-22)
- **[ERLEDIGT]** Karte: eine Reihe Logo-Kacheln nur für die eigenen Services (€-Badge bei reinem Leihen/Kaufen, +N für den Rest; ohne eigenen Service die eine beste Möglichkeit). Das weicht von der Vorgabe "genau eine Anbieter-Zeile, kein €-Badge" ab, auf Wunsch des Nutzers.
- **[ERLEDIGT]** Kosten-Tooltips ("No rental shops selected", "Films can be in several groups"), × je Dropdown im Panel, Marke in Satzschreibung, Land als Text, Year/Runtime/Rating wandern bei zu schmaler Leiste ins Panel (Liste `GIVE_WAY` in `filterbar.js`). "Available here first" bewusst nicht gebaut (Inlandsfilme stehen immer vorn).
- **[ERLEDIGT]** README komplett neu mit Screenshots (`docs/screenshots/`, echte Watchlist, Letterboxd-Name ersetzt).
- **[FEHLER]** Im Panel "More filters" bricht die Beschriftung des Runtime-Reglers ("Up to 180 min") um ("Up / to"). Nicht behoben.
- **[FEHLER]** Bei 1440 px Fensterbreite steht der Ansichten-Schalter (Grid/Compact/Table) auf einer zweiten Zeile, obwohl Year, Runtime und Rating schon im Panel sind; die Leiste passt erst ab etwa 1600 px in eine Zeile. Nicht behoben (Idee: Services-Feld schmaler oder Genre früher ins Panel).
- **[FEHLER]** Year steht oft im Panel, auch bei sehr breiten Fenstern, weil die Zeile bei etwa 1750 px endet. Gewollt, aber ungewohnt.
- **[OFFEN]** Das automatische Verschieben (ResizeObserver) feuert im Vorschau-Fenster der Desktop-App nicht (Fenster wird nicht gezeichnet); nur im Playwright-Browser-Test belegt, nicht mit eigenen Augen gesehen.
