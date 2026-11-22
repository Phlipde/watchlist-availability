# Design-Kritik (design-critique)

## Kontext

- **Gegenstand:** Watchlist Availability, ein Live-Produkt. Hauptseite `/` mit Seitenleiste, Filtern, Ergebnisraster und Dialogen, dazu die Seiten Settings, Costs, Matches und Status.
- **Datum:** 2026-11-15, Arbeitskopie mit uncommitteten Änderungen
- **Stand:** Live-Produkt. Die Befunde 1–19 sind aus dem Code beurteilt (Templates, `app.css`, JS). Danach im Browser nachgeprüft, siehe „Nachprüfung im Browser“ mit den neuen Befunden 20–25.
- **Persona:** Eine einzelne Person im Heimnetz, die ihre eigene Letterboxd-Watchlist kennt und die App immer wieder nutzt („perpetual intermediate“). Sie hat mehrere Abos und will abends schnell einen Film finden.
- **Hauptaufgabe:** „Welcher Film meiner Watchlist läuft heute Abend auf einem meiner Dienste?“ Nebenaufgaben: Abos durchrechnen (Costs), falsche Zuordnungen korrigieren (Matches).
- **Art der Prüfung:** Vollständige Kritik nach Nielsen-Heuristiken, UX-Gesetzen, Interaktions-Design, Informationsarchitektur und UX-Writing.
- **Abgrenzung:** Barrierefreiheit (Fokus, ARIA, Screenreader) steht in [web-design-guidelines.md](web-design-guidelines.md). Hier geht es um Bedienbarkeit und Struktur. Wo sich Punkte überschneiden, verweise ich auf die Nummer dort, z. B. „WDG #10“.
- **Schweregrad:** Nielsen-Skala 0–4.

---

## Erster Eindruck (5-Sekunden-Blick)

- **Worum geht es?** Die Überschrift „Find your next film.“ macht das klar.
- **Was ist die Hauptaktion?** Unklar. Unter der Überschrift folgen nacheinander ein Scan-Panel mit Fortschrittsbalken und „Retry scan“, ein Statistikblock, eine Werkzeugleiste mit 3 Selects und 10 Knöpfen und ein Raster mit 13 Filtern. Erst danach kommen die Filme.
- **Wo würde ich zuerst klicken?** Wahrscheinlich auf „Retry scan“ oder einen der vielen Knöpfe. Die Filme selbst sind auf dem ersten Bildschirm kaum zu sehen.
- **Verwirrt etwas?** Ja. „Free“ heißt an drei Stellen etwas anderes, und es gibt drei Begriffe für dasselbe (Service, Provider, Shop).

**Gesamteindruck:** Weitgehend klar, was die App kann. Unklar, wo man anfangen soll.

---

## Befunde

### 1. Aktive Filter können unsichtbar bleiben, und es gibt kein „Alle Filter zurücksetzen“
**Schweregrad:** 3, groß
**Prinzip:** H1 Sichtbarkeit des Systemzustands, H3 Kontrolle und Freiheit
**Ort:** `static/js/app.js:70` (Liste der Chips), `templates/partials/results.html:1`

**Was falsch ist:** Chips gibt es nur für 10 der 13 Filter. „Media“ (z. B. „With trailer“), „Availability changes“ und „Minimum providers“ erzeugen keinen Chip. Einen Knopf, der alles zurücksetzt, gibt es nicht. Die Filter landen in der URL (`syncUrl`), also bringt auch ein Lesezeichen sie zurück.

**Warum das zählt:** Man stellt einmal „With trailer“ ein und vergisst es. Tage später fehlen Filme, und kein Hinweis auf der Seite erklärt, warum.

**Empfehlung:** Die drei fehlenden IDs in die Liste in `app.js:70` aufnehmen. Wenn mindestens ein Chip aktiv ist, am Ende der Chips einen Knopf „Reset filters“ zeigen.

---

### 2. Kein leerer Zustand, wenn die Filter nichts übrig lassen
**Schweregrad:** 3, groß
**Prinzip:** Muster „Blank Slate“, H9 Fehlern abhelfen
**Ort:** `static/js/rendering.js:83-88` und `static/js/app.js:45`

**Was falsch ist:** Passt kein Film, wird `#results` einfach leer. Einen Hinweis gibt es nur in der Favoriten-Ansicht (`#favorites-empty`). „Clear“ in der Seitenleiste führt direkt zu einer leeren Fläche.

**Warum das zählt:** Eine leere Fläche wirkt wie ein Fehler („ist der Scan kaputt?“). Man weiß nicht, ob die Daten fehlen oder die Filter zu streng sind.

**Empfehlung:** In `renderFilms` bei `visibleCount === 0` einen Hinweis zeigen: „No film matches these filters.“ Dazu Knöpfe „Reset filters“ und, wenn kein Dienst gewählt ist, „Select my subscriptions“.

---

### 3. „Free“ bedeutet drei verschiedene Dinge
**Schweregrad:** 3, groß
**Prinzip:** H4 Konsistenz, Labeling (Eindeutigkeit)
**Ort:** `static/js/filtering.js:3-6` (Abschnitt „Free“ = `free` + `ads`), `templates/partials/film-filters.html:3-4`, `templates/partials/provider-sidebar.html:6`, `:14`, `:22`

**Was falsch ist:**
- Der Abschnitt „Free“ im Raster enthält auch Filme mit Werbung.
- Die Option „Free“ im Filter „Offer type“ meint nur Angebote ohne Werbung.
- Das Abzeichen „Free“ und der Knopf „Free services“ markieren Dienste, die *überwiegend* gratis sind.

Dazu kommt der Filter „Availability“. Er mischt zwei Achsen: Preis („Free“, „Paid“) und Verfügbarkeit („Unavailable“, „Available only“, „Only on one of my services“). Der Unterschied zwischen „Free + Paid“ (zeigt auch nicht verfügbare Filme) und „Available only“ ist am Text nicht zu erkennen.

**Warum das zählt:** Wer „Free“ wählt und Filme mit Werbung erwartet, bekommt weniger Treffer als im Abschnitt „Free“ stehen. Das sieht nach einem Fehler aus.

**Empfehlung:** Den Abschnitt in „Free & with ads“ umbenennen. Das Abzeichen für Dienste „Mostly free“ nennen. Beim Filter „Availability“ heißt die erste Option „Everything (incl. unavailable)“, und „Only on one of my services“ bekommt ein eigenes Kontrollkästchen. Dann gehört jedes Select zu genau einer Achse.

---

### 4. Die Werkzeugleiste mischt den täglichen Gebrauch mit seltenen Export-Aktionen
**Schweregrad:** 3, groß
**Prinzip:** Hick's Law, H8 Minimalismus, Orchestrierung („Hide the ejector seat“)
**Ort:** `templates/partials/result-tools.html:1`

**Was falsch ist:** Die Leiste hat 3 Selects und 10 Knöpfe in einer Reihe. Dazu gehören „Favorites CSV“, „Favorites JSON“, „Import favorites“, „JSON“ und „CSV“, die man vielleicht einmal im Jahr braucht. Sie sehen genauso aus wie „Random“ oder „Evening mode“. Drei Knöpfe sind in der Akzentfarbe hervorgehoben („My favorites“, „Share“ und in der Seitenleiste „My subscriptions“), es gibt also keinen klaren Hauptknopf (Von-Restorff-Effekt). Auf dem Handy brechen alle Elemente auf mehrere Zeilen um (`app.css:158-161`).

**Warum das zählt:** Jeder Besuch kostet Zeit fürs Absuchen der Leiste. Dabei braucht man meist nur Sortierung, Favoriten und „Random“ oder „Evening“.

**Empfehlung:** Die Leiste auf Sortierung, Favoriten-Status, „My favorites“, „Random“, „Evening mode“, „Compare“ und „Share“ kürzen. Die fünf Export- und Import-Knöpfe in ein `<details>` „Export / import“ am Ende verschieben oder auf die Settings-Seite neben „Backup“. Nur ein Knopf hat die Akzentfarbe.

---

### 5. „Any / All selected services“ steht weit weg von den Diensten
**Schweregrad:** 2, mittel
**Prinzip:** Gesetz der Nähe, H6 Erkennen statt Erinnern
**Ort:** `templates/partials/result-tools.html:1` (`#match-mode`), erklärt aber in `templates/partials/provider-sidebar.html:5`

**Was falsch ist:** Der Hilfetext in der Seitenleiste erklärt **Any selected service** und **All selected services**. Das Select dafür sitzt aber in der Werkzeugleiste über den Ergebnissen, auf dem Handy sogar außerhalb des Panels.

**Warum das zählt:** Man liest die Erklärung, findet das Steuerelement nicht und muss es suchen.

**Empfehlung:** `#match-mode` in die Seitenleiste direkt unter `.provider-actions` verschieben. Der Hilfetext wird dann kürzer.

---

### 6. 13 Filter sind immer gleichzeitig sichtbar
**Schweregrad:** 2, mittel
**Prinzip:** Hick's Law, Progressive Disclosure, Design for the probable
**Ort:** `templates/partials/film-filters.html:1-15`

**Was falsch ist:** Suche, Verfügbarkeit, Angebotsart, Jahr von/bis, Bewertung, Stimmen, Genre, Keyword, Laufzeit, Medien, Änderungen und Anzahl der Dienste haben alle das gleiche Gewicht und stehen in einem Raster.

**Warum das zählt:** Im 80-Prozent-Fall braucht man Suche, Genre, Laufzeit und vielleicht die Bewertung. Der Rest ist Rauschen und schiebt die Filme weiter nach unten.

**Empfehlung:** Suche, Verfügbarkeit, Genre, Laufzeit und Bewertung sichtbar lassen. Den Rest in `<details><summary>More filters (n active)</summary>` legen. Die Zahl der aktiven Filter macht Befund 1 zusätzlich sichtbar.

---

### 7. Scan-Panel und Statistik verdrängen die Filme vom ersten Bildschirm
**Schweregrad:** 2, mittel
**Prinzip:** Visuelle Hierarchie, Serial Position Effect, Product Posture (wiederholt genutztes Werkzeug)
**Ort:** `templates/index.html:19-23`, `templates/partials/scan-status.html`, `templates/partials/statistics.html:3`, `static/css/app.css:10` (`h1` bis 5.5rem)

**Was falsch ist:** Die Reihenfolge ist: große Überschrift mit Einleitungstext, dann das komplette Scan-Panel, dann ein Block mit 7 Kennzahlen, 4 Analyse-Kacheln und bis zu 8 Balken. Das Scan-Panel bleibt auch zu sehen, wenn gespeicherte Ergebnisse angezeigt werden: Balken auf 100 %, „Complete“, „Retry scan“ (`app.js:660-668`).

**Warum das zählt:** Bei jedem Besuch muss man scrollen, bevor man den ersten Film sieht. Die Statistik ist interessant, beantwortet aber nicht die Frage „Was schaue ich heute?“.

**Empfehlung:** Ruht der Scan, das Panel auf eine Zeile kürzen: „Saved results from 14 Nov, 20:13 · [Scan now]“. Den Statistikblock unter die Ergebnisse legen oder in ein `<details>` „Statistics“. Die Überschrift für wiederkehrende Besuche kleiner setzen (z. B. höchstens 3rem).

---

### 8. „Retry scan“, wenn nichts fehlgeschlagen ist
**Schweregrad:** 2, mittel
**Prinzip:** H2 Sprache der Nutzer, UX-Writing (Knopf beschreibt die Aktion)
**Ort:** `templates/partials/scan-status.html:6`, `static/js/app.js:272` und `:668`

**Was falsch ist:** Nach einem erfolgreichen Scan und bei gespeicherten Ergebnissen heißt der Knopf „Retry scan“. „Retry“ klingt nach einem Fehler.

**Warum das zählt:** Man fragt sich, ob etwas schiefging, und sucht nach einer Fehlermeldung.

**Empfehlung:** Den Text abhängig vom Zustand setzen: „Scan again“ oder „Scan now“ nach Erfolg und bei gespeicherten Ergebnissen, „Retry scan“ nur nach `error`.

---

### 9. Der Knopf „Desktop layout“ tut auf dem Desktop scheinbar nichts
**Schweregrad:** 2, mittel
**Prinzip:** H1 Sichtbarkeit des Systemzustands, H2 (Technikbegriff statt Nutzersprache)
**Ort:** `templates/partials/header.html:3` (`#layout-toggle`), `static/css/app.css:182-193` (Regeln nur in `@media (max-width: 800px)`), `static/js/app.js:600-611`

**Was falsch ist:** Der Knopf ist überall zu sehen. Seine Wirkung gibt es aber nur unter 800 px. Auf dem Desktop ändert ein Klick nur die Beschriftung in „Responsive layout“.

**Warum das zählt:** Ein Knopf ohne sichtbare Wirkung lässt die Nutzerin an der ganzen App zweifeln.

**Empfehlung:** Den Knopf über 800 px ausblenden (`@media (min-width: 801px) { #layout-toggle { display: none; } }`) und ihn ehrlicher benennen, z. B. „Wide view“.

---

### 10. Mobiles Filterpanel schließt nach jedem Häkchen
**Schweregrad:** 3, groß
**Prinzip:** Excise (unnötige Arbeit), Fitts's Law
**Ort:** `static/js/app.js:401-405`. Die Tastatur-Seite steht in WDG #10.

**Was falsch ist:** Wer drei Dienste wählen will, muss das Panel dreimal öffnen.

**Warum das zählt:** Die häufigste Handlung in der Seitenleiste wird dreimal so teuer.

**Empfehlung:** Nach dem Wechsel einer Checkbox nicht mehr automatisch schließen. Oben im Panel einen sichtbaren Knopf „Done · 42 films“ anzeigen.

---

### 11. Beim Entfernen eines Favoriten gehen Status und Notiz ohne Rückfrage verloren
**Schweregrad:** 2, mittel
**Prinzip:** H3 Kontrolle und Freiheit (Undo), H5 Fehlervermeidung
**Ort:** `static/js/app.js:350-352` (`DELETE /api/favorites/…`), `static/js/rendering.js:69` (Stern oben rechts auf dem Poster)

**Was falsch ist:** Ein Tipp auf den Stern löscht den Favoriten samt „Watching/Watched“ und der Notiz. Ein Rückgängig gibt es nicht. Der Stern liegt auf dem Poster, das auf dem Handy auch die Details öffnet. Ein falscher Tipp passiert also leicht.

**Warum das zählt:** Notizen tippt man mühsam ein, und ein falscher Tipp löscht sie still.

**Empfehlung:** Keine Rückfrage, sondern Undo: Der Toast „Removed from favorites“ bekommt einen Knopf „Undo“. Der stellt den gemerkten Eintrag `previous` (ist in `app.js:345` schon da) per POST und PATCH wieder her. Dafür den Toast etwa 5 s statt 2,4 s stehen lassen.

---

### 12. Der Vergleich ist kaum zu entdecken und gibt erst nach dem Klick Rückmeldung
**Schweregrad:** 2, mittel
**Prinzip:** H6 Erkennen statt Erinnern, Affordanz, Doherty-Schwelle
**Ort:** `static/js/rendering.js:73` (Checkbox ohne sichtbaren Text oben links auf dem Poster), `templates/partials/result-tools.html:1` (`#compare-films`), `static/js/app.js:127`

**Was falsch ist:** Was die kleine Checkbox auf dem Poster bedeutet, sieht man nicht. Der Knopf „Compare“ ist immer aktiv und meldet erst nach dem Klick „Select 2 to 4 films to compare.“

**Warum das zählt:** Die Funktion bleibt unentdeckt, oder man probiert sie aus und bekommt einen Fehlertoast.

**Empfehlung:** Den Knopf mit Zähler beschriften: „Compare (0)“, aktiv erst ab 2. Die Checkbox sichtbar beschriften, z. B. ein kleines „Compare“ neben dem Kästchen. Auf dem Handy reicht ein Tooltip nicht.

---

### 13. Evening mode endet in einer Sackgasse und nutzt eine andere Dienst-Auswahl
**Schweregrad:** 2, mittel
**Prinzip:** Kontextlinks (keine Sackgassen), H4 Konsistenz, Mentales Modell
**Ort:** `static/js/app.js:117-124`, `static/js/filtering.js:131-139`, `templates/partials/modals.html:4`

**Was falsch ist:** Die drei Vorschläge sind reiner Text. Man kann sie nicht anklicken, um Details, Trailer oder den Anbieter zu sehen. Außerdem gelten die in den Settings gespeicherten Abos, nicht die gerade in der Seitenleiste gewählten Dienste. Das steht nirgends.

**Warum das zählt:** Der Abendmodus soll die Entscheidung abkürzen. Nach dem Vorschlag muss man den Film aber im Raster suchen. Wer in der Seitenleiste nur Netflix gewählt hat, wundert sich über einen Vorschlag auf Prime.

**Empfehlung:** Jeden Vorschlag als Knopf ausführen, der `showFilmDetails(key)` öffnet, mit dem Dienst dahinter: „· on Netflix“. Unter dem Formular einen Satz: „Uses the subscriptions saved in Settings.“

---

### 14. Dienst, Provider, Shop: drei Wörter für eine Sache
**Schweregrad:** 2, mittel
**Prinzip:** H4 Konsistenz, Labeling (kontrolliertes Vokabular)
**Ort:** `templates/partials/provider-sidebar.html:3` („Services“), `:4` („Search providers...“, „Provider sort“), `templates/partials/statistics.html:3` („Top provider“, „providers/film“, „Selected providers“), `templates/partials/film-filters.html:14` („Any provider count“), `templates/partials/provider-sidebar.html:6` („Rental shops“)

**Was falsch ist:** Dasselbe heißt je nach Stelle Service, Provider oder Shop.

**Warum das zählt:** Man fragt sich, ob „providers“ in der Statistik etwas anderes sind als „services“ in der Seitenleiste.

**Empfehlung:** Überall „service“ verwenden. „Rental shops“ darf bleiben, weil es eine Untergruppe beschreibt.

---

### 15. Ein Länderwechsel im Kopf startet sofort einen vollen Scan
**Schweregrad:** 2, mittel
**Prinzip:** H5 Fehlervermeidung, H4 (zwei Orte für dieselbe Einstellung)
**Ort:** `templates/partials/header.html:2` (`#country-select`, ohne Rahmen im Fließtext versteckt), `static/js/app.js:599`, `templates/settings.html:23-24`

**Was falsch ist:** Das Select sieht aus wie Text („WATCHLIST AVAILABILITY · DE“). Eine Auswahl startet ohne Rückfrage einen Scan mit vielen TMDB-Anfragen. Das Land steht außerdem in den Settings, und es bleibt unklar, welcher Wert gilt.

**Warum das zählt:** Ein versehentliches Scrollen oder Tippen auf dem Handy wirft die aktuelle Ansicht weg und startet einen langen Scan.

**Empfehlung:** Hat das Land schon einen gespeicherten Scan, diesen laden (`loadLatestResult`) statt neu zu scannen. Nur ohne Daten scannen. Das Select sichtbar als Steuerelement gestalten (Rahmen, Pfeil).

---

### 16. Fehlermeldungen ohne nächsten Schritt
**Schweregrad:** 2, mittel
**Prinzip:** H9 Fehler erkennen, verstehen, beheben
**Ort:** `static/js/matches.js:30` („Request failed (500).“), `static/js/app.js:361` („Could not update favorite.“), `:586` („The scan could not be cancelled.“), `:302` (Fehlertext des Servers direkt durchgereicht)

**Was falsch ist:** Die Meldungen sagen *dass* etwas schiefging, aber nicht *warum* und was man tun kann. „Request failed (500).“ ist ein Technik-Code.

**Warum das zählt:** Die Nutzerin kann nichts tun als es noch einmal zu versuchen und hoffen.

**Empfehlung:** Das Muster „was passiert ist, was jetzt hilft“ verwenden. Beispiel: „Could not save the favorite. The app may have restarted. Reload the page and try again.“ Bei 5xx auf die Statusseite verlinken.

---

### 17. Die Navigation unterscheidet sich je nach Seite
**Schweregrad:** 1, klein
**Prinzip:** H4 Konsistenz, Navigation („Wo bin ich?“)
**Ort:** `templates/costs.html:13` (ohne „Matches“), `templates/matches.html:13` (ohne „Costs“), `templates/settings.html:13` und `templates/status.html:13` (ohne die eigene Seite), `templates/partials/header.html:3` (Knöpfe statt Links)

**Was falsch ist:** Jede Unterseite hat eine eigene, unvollständige Linkzeile. Die aktuelle Seite ist nicht markiert. Von „Costs“ kommt man nicht direkt zu „Matches“.

**Warum das zählt:** Man muss den Umweg über die Startseite nehmen, und die Unterseiten wirken wie lose verbundene Einzelseiten.

**Empfehlung:** Eine gemeinsame Partial `partials/page-nav.html` mit allen fünf Zielen. Die aktuelle Seite wird mit `aria-current="page"` hervorgehoben, nicht verlinkt.

---

### 18. Der Einleitungstext ist Technik-Sprache
**Schweregrad:** 1, klein
**Prinzip:** H8 Minimalismus („happy talk“), H2
**Ort:** `templates/partials/header.html:3` (`.intro`), `templates/partials/provider-sidebar.html:30` („Changing services only changes the visible films.“)

**Was falsch ist:** „…changes apply immediately without another request.“ beschreibt die Technik, nicht den Nutzen. Wiederkehrende Nutzer lesen das nicht mehr, es kostet aber Platz im Kopf.

**Warum das zählt:** Es schiebt die Inhalte nach unten und spricht über Requests statt über Filme.

**Empfehlung:** Den Text streichen oder auf einen Satz kürzen: „Pick your services on the left. Filters apply instantly.“

---

### 19. „Random“ zeigt den Film nicht deutlich
**Schweregrad:** 1, klein
**Prinzip:** H1 Sichtbarkeit, Peak-End-Regel
**Ort:** `static/js/app.js:104-110`. Die Tastatur-Seite steht in WDG #26.

**Was falsch ist:** Die Seite scrollt zur Karte und zeigt 2,4 s lang einen Toast. Die Karte selbst wird nicht hervorgehoben.

**Warum das zählt:** In einem Raster mit 2 Spalten auf dem Handy oder 6 auf dem Desktop sucht man, welche Karte gemeint ist. Der spielerische Moment verpufft.

**Empfehlung:** Gleich `showFilmDetails(key)` öffnen. Der Dialog ist die Belohnung und enthält schon Trailer und Anbieter.

---

## Nachprüfung im Browser (2026-11-15)

Die App lief mit einer Kopie der echten Daten (DE, 456 Filme, 10 Abos), angesehen bei 1440×900, 1024×768 und 375×812 (Handy). Geprüft durch Ansehen, Messen im Browser und einzelne Klicks. Nicht geprüft: alles, was schreibt (Favoriten, Notizen, Speichern), ein laufender Scan, der Länderwechsel und echte Geräte.

### Stand der Befunde 1–19

| Befund | Ergebnis im Browser |
|---|---|
| 1 Chips fehlen | Bestätigt: „With trailer“ senkt die Trefferzahl von 169 auf 167, es erscheint kein Chip |
| 2 Kein leerer Zustand | Bestätigt: „Clear“ ergibt „0 visible films“ über einer leeren Fläche |
| 3 „Free“ | Bestätigt: Unter der Überschrift „Free“ stehen Karten mit dem Abzeichen „With ads“ |
| 4 Werkzeugleiste | Bestätigt, wenn sie zu sehen ist (3 Selects, 10 Knöpfe, zwei Zeilen bei 1440 px). Im Normalfall ist sie aber gar nicht da, siehe Befund 20 |
| 5 „Any / All“ | Bestätigt |
| 6 13 Filter | Bestätigt. Auf dem Handy steht jeder Filter in einer eigenen Zeile, zusammen 578 px hoch |
| 7 Erster Bildschirm | Bestätigt und gemessen: Der erste Film beginnt bei 1440×900 auf Höhe 839 px, auf dem Handy (812 px hoch) bei 1272 px. Mit Statistik und Werkzeugleiste wären es am Desktop 1270 px |
| 8 „Retry scan“ | Bestätigt. Dazu füllt sich der Balken bei jedem Laden von 0 auf 100 %, als liefe ein Scan |
| 9 „Desktop layout“ | Knopf ist bei 1440 px zu sehen. Die Wirkung habe ich nicht angeklickt |
| 10 Mobiles Panel | Bestätigt: Nach einem Häkchen ist das Panel zu. Es hat außerdem keinen sichtbaren Knopf zum Schließen |
| 12 Vergleich | Checkbox ohne Beschriftung bestätigt. Den Knopf habe ich nicht geprüft |
| 14 Begriffe | Bestätigt: „Services“ als Überschrift, darunter „Search providers...“, in der Statistik „providers/film“ |
| 17 Navigation | Bestätigt: Costs und Matches zeigen „Settings · Status“, Settings zeigt „Status · Costs · Matches“ |
| 18 Einleitungstext | Bestätigt. Bei 1024 px steht er in einer Spalte von rund 80 px Breite, neun Zeilen hoch |
| 11, 13, 15, 16, 19 | Nicht geprüft |

### Neue Befunde

### 20. Werkzeugleiste und Statistik fehlen, wenn gespeicherte Ergebnisse geladen werden
**Schweregrad:** 4, Katastrophe
**Prinzip:** H1 Sichtbarkeit, H7 Flexibilität (Funktionen nicht erreichbar)
**Ort:** `static/js/app.js`, `loadLatestResult` (blendet nur `result-meta` und `film-filters` ein). `stats-section` und `result-tools` blendet nur die Fortschritts-Abfrage eines laufenden Scans ein.

**Was falsch ist:** Öffnet man die Seite mit einem Stand, der jünger als 24 Stunden ist, läuft kein Scan. Dann bleiben Sortierung, „My favorites“, „Random“, „Evening mode“, „Compare“, „Share“, alle Exporte und die Statistik versteckt. Seit Etappe 9c ist das der Normalfall.

**Warum das zählt:** Die halbe Hauptseite ist nicht erreichbar, außer man drückt „Retry scan“. Der Abend-Modus, für den die App gedacht ist, lässt sich nicht öffnen.

**Empfehlung:** In `loadLatestResult` beide Bereiche einblenden und `updateStats()` aufrufen, wenn Filme da sind. Ein Browser-Test: Seite mit gespeichertem Stand laden, „Random“ ist sichtbar.

---

### 21. Die Kopfzeile bricht auf dem Handy und bei mittlerer Breite
**Schweregrad:** 3, groß
**Prinzip:** Fitts's Law, visuelle Hierarchie
**Ort:** `templates/partials/header.html`, Kopf-Regeln in `static/css/app.css`

**Was falsch ist:** Bei 375 px stehen sechs Knöpfe in einer Zeile. Die Icons liegen über der Beschriftung des Nachbarn, „Status“ ist am Rand abgeschnitten. Bei 1024 px wird der Einleitungstext zu einer schmalen Spalte (siehe Befund 18).

**Warum das zählt:** „Filters“ ist auf dem Handy der wichtigste Knopf und liegt 16 px breit neben „Desktop layout“.

**Empfehlung:** Die Knöpfe umbrechen lassen (`flex-wrap`) oder auf dem Handy nur „Filters“ als Knopf zeigen und die Seitenlinks in die gemeinsame Navigation aus Befund 17 legen. Den Einleitungstext streichen (Befund 18), dann entfällt die schmale Spalte.

---

### 22. Das Detailfenster zeigt nicht, welche Dienste die eigenen sind
**Schweregrad:** 2, mittel
**Prinzip:** H6 Erkennen statt Erinnern, Tesler's Law
**Ort:** `availabilityByOffer` in `static/js/rendering.js`

**Was falsch ist:** Bei „Good Time“ stehen unter „Subscription“ MUBI, MUBI Amazon Channel und Superfresh Amazon Channel. Keiner davon ist ein eigenes Abo, sie sehen aber genauso aus wie „filmfriend“ unter „Free“, das eines ist.

**Warum das zählt:** Die Frage „Kann ich den jetzt sehen?“ beantwortet das Fenster nicht. Man muss die eigenen Abos im Kopf abgleichen.

**Empfehlung:** Eigene Abos in jeder Gruppe zuerst nennen und markieren (z. B. Häkchen und „yours“). Die Liste der Abos kennt die Seite schon („My subscriptions“).

---

### 23. Die Kosten-Tabelle passt nicht aufs Handy und fragt Preise für kostenlose Dienste ab
**Schweregrad:** 2, mittel
**Prinzip:** H8 Minimalismus, Responsive Layout
**Ort:** `templates/costs.html`

**Was falsch ist:** Die Tabelle ist 622 px breit in einem Fenster von 375 px. „Films“, „Per film“ und „Only here“, also die eigentliche Auswertung, liegen außerhalb und sind nur durch seitliches Wischen zu sehen. Das Datumsfeld ist abgeschnitten. Sechs der zehn Zeilen sind kostenlose Dienste (ARD Mediathek, ZDF, Arte …) mit einem leeren Preisfeld.

**Warum das zählt:** Auf dem Handy sieht die Seite aus wie ein leeres Formular. Den Nutzen („0,19 pro Film“) sieht man nicht.

**Empfehlung:** Kostenlose Dienste ohne Preis- und Datumsfeld zeigen oder in einer eigenen kurzen Liste darunter. Auf dem Handy jede Zeile als Block untereinander. Gehört in die neue Seite aus Etappe 9e.

---

### 24. Die Zahlen in der Statistik gehen nicht auf
**Schweregrad:** 1, klein
**Prinzip:** H2 Sprache der Nutzer
**Ort:** `templates/partials/statistics.html`, `updateStats` in `static/js/app.js`

**Was falsch ist:** „169 films · 8 free · 162 paid“: 8 und 162 ergeben 170, weil ein Film in beiden Bereichen steht. **Unverifiziert:** Nach „Clear“ stand die Statistik weiter auf 169 Filmen und „Netflix (74)“. Ich hatte den Bereich von Hand eingeblendet (Befund 20), das kann daran liegen.

**Empfehlung:** „8 free · 162 paid (1 in both)“ oder die Zeile auf „169 films“ kürzen. Nach dem Beheben von Befund 20 prüfen, ob die Statistik „Clear“ folgt.

---

### 25. Das Zeitplan-Select ragt auf dem Handy aus seiner Karte
**Schweregrad:** 1, klein
**Prinzip:** Sorgfalt im Layout
**Ort:** `templates/settings.html`, Select „Scan the watchlist“

**Was falsch ist:** „Never (only when the page is opened)“ ist bei 375 px breiter als die Karte.

**Empfehlung:** `max-width: 100%` am Select.

---

## Was gut funktioniert

- **Gespeicherte Ergebnisse sofort:** `loadLatestResult` zeigt den letzten Scan ohne Wartezeit und scannt nur, wenn er veraltet ist. Das passt gut zu einem Werkzeug, das man oft öffnet.
- **Skeleton statt Spinner** beim ersten Laden (`results.html:2`), und Ergebnisse erscheinen schon während des Scans.
- **Filter in der URL:** Der Zustand lässt sich teilen und als Lesezeichen speichern (`syncUrl`).
- **Detail-Dialog:** Die Angebote sind nach Free / With ads / Subscription / Rent gruppiert, mit Logos. Die Ansicht ist klar und folgt dem mentalen Modell „Wo kann ich das sehen und was kostet es?“.
- **Costs-Seite:** „Only here“ und „Rotation“ sind echte Entscheidungshilfen („Cancel X: you lose no watchlist film“). Der Hilfetext erklärt die Begriffe direkt an der Stelle.
- **Matches-Seite:** Sie erklärt in einem Absatz, warum es die Seite gibt, bietet „Looks right“ als schnellen Weg und kann Korrekturen rückgängig machen („Undo correction“).
- **Sinnvolle Rückfragen:** Backup wiederherstellen und Scan abbrechen fragen nach. Das sind seltene Aktionen mit großer Wirkung.

---

## Prüfung der Zustände

| Zustand | Vorhanden? | Anmerkung |
|---|---|---|
| Standard | Ja | |
| Hover | Ja | Knöpfe, Karten, Dienste (`app.css:32`, `:41`, `:108`) |
| Fokus | Teilweise | Siehe WDG #3–#5 und #11 |
| Deaktiviert | Teilweise | Stern und „Cancel scan“ ja. Formulare beim Speichern nein (WDG #13). „Compare“ nie (Befund 12) |
| Laden | Ja | Skeleton und Scan-Fortschritt. Auf Matches „Searching…“ |
| Fehler | Teilweise | Scan-Fehler sichtbar, sonst meist nur ein Toast für 2,4 s (Befund 16) |
| Erfolg | Ja | Toasts, „Saved.“ |
| Leer | Teilweise | Favoriten, Matches, Costs und Status ja. **Hauptraster nach Filtern nein** (Befund 2) |

---

## Zusammenfassung

| Schweregrad | Anzahl |
|---|---|
| 4 – Katastrophe | 1 (20) |
| 3 – Groß | 6 (1, 2, 3, 4, 10, 21) |
| 2 – Mittel | 13 (5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 22, 23) |
| 1 – Klein | 5 (17, 18, 19, 24, 25) |
| 0 – Kosmetisch | 0 |

### Die 3 wichtigsten Punkte

Vor allen dreien: **Befund 20 beheben.** Ohne Werkzeugleiste sind Sortierung, Favoriten-Ansicht, „Random“ und Abend-Modus im Normalfall nicht erreichbar.

1. **Filterzustand sichtbar und rücksetzbar machen** (Befunde 1 und 2): fehlende Chips ergänzen, „Reset filters“ einbauen, einen leeren Zustand mit Ausweg zeigen. Das ist wenig Code und beseitigt die häufigste Quelle für „Warum fehlt mein Film?“.
2. **Begriffe aufräumen** (Befunde 3 und 14): „Free“ eindeutig machen, überall „service“ sagen und das Select „Availability“ auf eine Achse beschränken.
3. **Den ersten Bildschirm den Filmen geben** (Befunde 4, 6 und 7): Werkzeugleiste kürzen, seltene Filter einklappen, Scan-Panel und Statistik zurücknehmen.

### Nächste Schritte

- [ ] Befunde 1, 2, 8 und 9 sind jeweils nur wenige Zeilen. Sie gehen sofort.
- [ ] Befunde 3, 4, 5, 6 und 7 verändern Struktur und Texte. Am besten in einem Rutsch, damit die Seite nur einmal „umzieht“.
- [ ] **Testen statt raten:** Ob 3 Selects plus „More filters“ besser funktionieren als 13 offene Filter, zeigt eine Woche echte Nutzung. Notieren, welche Filter tatsächlich gesetzt werden. Die URL-Parameter zeigen das schon.
- [ ] **Offene Frage:** Die Oberfläche ist englisch, die Nutzerin schreibt Deutsch. Falls das nicht bewusst so ist, wäre eine deutsche Oberfläche der größte Einzelgewinn bei H2. Das habe ich nicht als Befund gezählt.
