# Plan: erst Fehler beheben, dann neue Features

Grundlage: Bildschirmaufnahme des Stands vom 22.11.2026 (Handy, Browser). Teil A behebt Fehler und Schwächen; **erst wenn Teil A abgenommen ist**, beginnt Teil B. Innerhalb jedes Teils in der angegebenen Reihenfolge arbeiten.

**Arbeitsweise**
1. Vor jedem Block kurz prüfen, wie der Code heute aussieht, und in 3–5 Zeilen berichten.
2. Nach jedem Block: was geändert wurde, welche Dateien, was zu testen ist (Handy **und** Desktop). Dann auf OK warten.
3. Nichts löschen, ohne vorher aufzulisten, was gelöscht wird.
4. Bestehende Regeln gelten: **Letterboxd ist die einzige Quelle für Geschautes** (kein Loggen/Seen/Bewerten in der App), **keine Filmpreise**, gleiche Kataloge zusammenfassen, Button-System und Tokens nutzen, Formate `1 h 48`, `FSK 12`, `TT.MM.JJJJ`.

Status: [ ] offen, [x] erledigt. Aufwand: S < 1 h, M halber Tag, L 1+ Tag.

---

# Teil A — Fehler und Schwächen (zuerst)

## A1. Watchlist-Kopf auf dem Handy auf zwei Zeilen (M) — höchste Priorität

Heute: „Filters“ (volle Breite) → Suche (volle Breite) → Ansicht-Icons + ♥ + 🔗 → Tabs + Zähler → „Save view“ → Poster. Das erste Poster beginnt bei ca. 45 % der Bildschirmhöhe.

- [ ] **< 640 px:**
    ```
    Zeile 1:  [🔍 Search films…              ] [⚙ Filters · 2]
    Zeile 2:  Films · Changes 0                    171 of 431
    (nur bei aktiven Filtern:) Chips, ab 5 Chips „+3 more“, rechts „Reset all“
    ```
- [ ] Ansicht-Umschalter (Grid/Compact/Table) und ♥-Schalter ins Filter-Sheet (Abschnitt „View“ ganz oben); Share-Link in ein ⋯-Menü rechts in Zeile 2.
- [ ] „Save view“ nur sichtbar, wenn Filter aktiv sind (in der Chip-Zeile).
- [ ] „Letterboxd @Phlipde“ aus der Zählzeile entfernen (steht in Settings).
- [ ] Zeile „Watchlist availability · DE“ auf dem Handy entfernen (Region in Settings; Sync-Punkt wandert in Zeile 2 neben den Zähler).
- [ ] Ziel: erstes Poster bei ≤ 25 % der Bildschirmhöhe (390 × 844).
- [ ] Desktop bleibt wie in `buttons-und-menues-prompt.md` Abschnitt 3 (zwei Zeilen, alles in der Filterleiste).

## A2. Laufzeit-Regler und Bewertungs-Anzeige reparieren (S–M)

- [ ] **Laufzeit-Regler:** Beschriftung bricht in „Up / to / 22 / 5 / mi / n“ um. Wert in **einer** Zeile über dem Regler: `Up to 3 h 45`. `white-space: nowrap`, eigene Zeile statt neben dem Regler.
- [ ] **Laufzeit-Trigger:** „≤ 225“ ohne Einheit → `≤ 3 h 45` (bzw. `≤ 95 min` unter 2 h).
- [ ] **Bewertung:** TMDB 7+ gewählt, Trigger zeigt „3+“, Chip „Rating: TMDB 3+“. Ursache finden (vermutlich wird beim Quellenwechsel der Wert der anderen Quelle übernommen). Erwartung: jede Quelle hat ihren eigenen Wert; beim Wechsel der Quelle wird der Filter **zurückgesetzt** auf „Any“ und das kurz angezeigt. Trigger und Chip zeigen immer Quelle + Wert: `Letterboxd 3.8+` / `TMDB 7+`.
- [ ] Unit-Tests für Bewertungsfilter (Quellenwechsel, Anzeige, URL-Zustand).

## A3. Compare-Leiste (S–M)

- [ ] **Handy:** volle Breite direkt über der Bottom-Navigation, Höhe 56 px: Mini-Cover (32 px) der gewählten Filme · `Compare` (Primary) · `Clear`. Kein Umbruch, kein abgeschnittener Text.
- [ ] **Ausgeblendet**, solange ein Drawer oder der Vergleich offen ist.
- [ ] Der Inhalt bekommt unten Platz (`padding-bottom`), damit die Leiste keine Kartentitel verdeckt.

## A4. Filmkarten im Grid (M)

**Vorgabe: im Grid keine Anbieter-Namen in den Kacheln.** (Ersetzt die Text-Variante `[N] Netflix · Subscription` aus `buttons-und-menues-prompt.md` Abschnitt 5.)

- [ ] **Genau ein Logo** (24 px) = bester Weg (eigener Gratis-Dienst → eigenes Abo → mit Werbung → Leihen → Kaufen → Ausland), daneben ein **kurzes Typ-Label ohne Namen**: `Free` · `Sub` · `Ads` · `Rent` · `Buy` · `Abroad` (12 px, `--text-2`; `Free` in `--free`). Danach `+10` als kleiner Text (kein Kreis in Logo-Größe).
    ```
    [ARD]  Free      +10
    [N]    Sub        +8
    [▶]    Rent       +6
    ```
- [ ] Antippen des Logos zeigt weiterhin den Tooltip „ZDF · Free“ (Name nur im Tooltip).
- [ ] Kompakt-Ansicht: nur das Logo, kein Label.
- [ ] **Unterstrichene Titel** (Grown Ups 2, Rocky, Shoplifters) beheben: kein `text-decoration` auf Kartentiteln, auch nicht für besuchte Links; Fokus nur über den Karten-Fokusring.
- [ ] Alle Karten einer Reihe gleich hoch, Anbieter-Zeile unten bündig.

## A5. Drawer: Daten- und Darstellungsfehler (M)

- [ ] **Filmreihe „Start with …“:** Bei Grown Ups 2 steht „Start with Grown Ups **3**“. Regel: Teile nach Erscheinungsdatum sortieren; empfohlen wird der früheste **bereits erschienene** Teil, der laut Letterboxd-Daten noch nicht gesehen ist. Unveröffentlichte Teile ausgegraut mit Jahr, nie als „Start with“. Unit-Test.
- [ ] **Schlagwörter ohne Orte:** noch „los angeles, california“, „beverly hills“, „philadelphia, pennsylvania“, „boston, massachusetts“, „italian american“. Alle TMDB-Keywords entfernen, die Orte, Länder, Bundesstaaten oder Herkunftsbezeichnungen sind (Komma + Region, Orts-/Länderliste, „X american“). Unit-Test mit diesen Beispielen.
- [ ] **Anbieter unter Mini-Postern** (Filmreihe, Similar): heute ein breiter Streifen mit abgeschnittenem Logo. Stattdessen kleines rundes Logo-Badge (20 px) unten rechts auf dem Poster, vollständig sichtbar.
- [ ] **„Other services“ auf dem Handy:** eigene Dienste als **Liste mit Namen** (Logo · Name · Typ · ✓). Rent/Buy dürfen Logo-Raster bleiben, aber **jedes Logo antippbar mit Namen** und keine doppelten Logos (zweimal „WOW“: WOW vs. WOW-Channel zusammenfassen oder unterscheidbar benennen).
- [ ] **„Grey out“ klären:** berichten, was die Aktion heute tut. Danach:
    - blendet sie einen Film lokal aus/dunkelt ihn ab → mit „Not now“ zusammenlegen: **eine** Aktion `Not now` mit `30 days · 90 days · Until I undo`; „Grey out“ entfällt.
    - simuliert sie „gesehen“ → entfernen (Letterboxd-Regel).
    - In beiden Fällen vorher auflisten, welche gespeicherten Daten betroffen sind, und fragen, bevor etwas gelöscht oder migriert wird.

## A6. Kleinere Fehler (S)

- [ ] **Doppelter Toast:** „Link copied.“ und „Copied.“ gleichzeitig → nur ein Toast „Link copied“.
- [ ] **Tabellenansicht:** Titelspalte bleibt beim horizontalen Scrollen kleben (`position: sticky; left: 0`), mit Mini-Poster.
- [ ] **Tonight-Chips:** horizontal scrollbar in einer Zeile statt Umbruch.
- [ ] **Abos-Seite:** Aktionen („Set reminder“, „Show the 4 films“, „Not interested“) als Secondary-Buttons sm (≥ 36 px Tippziel) statt unterstrichener Textlinks.
- [ ] **Katalog-Zusammenfassung prüfen:** „RTL+ Max“ vs. „RTL+“, „WOW“ vs. „WOW Fiction Amazon Channel“, „Sky Go“ vs. „Sky Store“ (Letzteres ist Leihen, getrennt lassen, klar beschriftet).
- [ ] **Aktive Filter-Chips:** ab 5 Chips einklappen (`+3 more`).

## Abnahme Teil A

- [x] Handy 390 × 844: erstes Poster der Watchlist bei ≤ 25 % Höhe.
- [x] Laufzeit- und Bewertungsfilter zeigen korrekte Werte mit Einheit/Quelle, einzeilig.
- [x] Compare-Leiste verdeckt nie Drawer, Vergleich oder Kartentitel.
- [x] Grid-Kacheln: auf Wunsch alle eigenen Dienste (max. 4) mit Typ-Icon in der Ecke statt ein Logo + Wort; kein Anbieter-Name, keine unterstrichenen Titel.
- [x] Keine Orte in Schlagwörtern; „Start with“ nur für erschienene Teile.
- [x] „Grey out“ bleibt als Aktion; die Markierung heißt „Hidden away“ (so entschieden).
- [x] Tabellentitel bleibt sichtbar, mit Mini-Poster; doppelter Toast nicht reproduzierbar.
- [x] Neue Unit-Tests grün (Bewertungsfilter, Filmreihe, Schlagwort-Filter, bester Weg).

---

# Teil B — Neue Features (danach)

## Abwägung

| Idee | Nutzen | Aufwand | Entscheidung |
|---|---|---|---|
| Zugriffsschutz | Hoch | S–M | B1 |
| PWA installierbar + Offline | Hoch | M | B1 |
| Bilder/Liste optimieren | Mittel–hoch | M | B1 |
| Tests für Kernlogik | Hoch | M | B1 |
| Endzeit + „Fits tonight“ | Hoch | S | B2 |
| Globale Suche inkl. TMDB + Personen | Hoch | M | B2 |
| Pick for me mit Gedächtnis + Gewichtung | Mittel | S | B2 |
| Digest + Push (ntfy) + Home Assistant | Mittel–hoch | M | B3 |
| Stats-Seite mit Aktionen | Mittel | M | B3 |
| Stimmungs-Chips | Mittel | S–M | B3 |
| Gemeinsamer Modus (zweiter Letterboxd-Name) | Hoch, falls oft zu zweit | L | B4 |
| Swipe-Abstimmung zu zweit | Mittel | L | B4, optional |
| Haptik, Sprache DE/EN | Gering–mittel | S | B3 (nebenbei) |
| Mehr Bewertungsquellen | Gering | M | nicht machen |
| Social (Kommentare, Feed) | Gering | L | nicht machen |
| Eigene Empfehlungs-KI | Gering | L | nicht machen |
| Serien | nur bei echtem Bedarf | L | nicht machen (vorerst) |

## B1. Grundlage absichern

- [ ] **Zugriffsschutz:** alle Seiten **und** API-Endpunkte (Sync/Scan, Einstellungen, Export, Abo-Daten) nur nach Anmeldung. Bevorzugt über den Reverse-Proxy mit SSO (in der App prüfen, dass nichts am Proxy vorbei erreichbar ist); sonst App-Login. Sync-Endpunkt zusätzlich mit Token für geplante Aufrufe. Vorher sagen, welche Variante zum Setup passt.
- [ ] **Rate-Limits/Caching** externer Quellen: Scan gestaffelt (z. B. 5 Anfragen/s), Antworten 24 h cachen, manueller Scan max. 1× pro 10 min.
- [ ] **Backups** der App-Daten: täglicher JSON-Export in ein konfigurierbares Verzeichnis, letzte 14 behalten.
- [ ] **Fehlerlog** unter Settings → Data: letzter Sync je Quelle, Fehler der letzten 7 Tage, Filme ohne TMDB-Treffer mit „Match manually“.
- [ ] **PWA:** Manifest, Service Worker (App-Shell + letzte Daten offline, „Stand von …“-Hinweis), Install-Hinweis einmalig.
- [ ] **Bilder:** Poster in passender Größe (Raster w185, Retina w342, Drawer w500), WebP/AVIF wenn möglich, `loading="lazy"`, feste Seitenverhältnisse, Blur-Platzhalter.
- [ ] **Virtualisierte Liste** ab ca. 200 Karten.
- [ ] **Tests** für: bester Weg, Katalog-Mapping, Länder-Reihenfolge, Ereignisse Neu/Bald weg/Weg, Zählung mit/ohne Ausland, Filmreihen-Reihenfolge, Schlagwort-Filter, Bewertungsfilter.

## B2. Tonight und Suche

- [ ] **Endzeit:** ab 17 Uhr zeigen Karten auf Tonight statt der Laufzeit `ends 22:41` (Start = jetzt, auf 5 min gerundet). Im Drawer immer zusätzlich zur Laufzeit.
- [ ] **Chip „Fits tonight“:** nur Filme, die vor einer einstellbaren Uhrzeit enden (Standard 23:30, Settings); steht vor „Under 2 h“.
- [ ] **Pick for me:** Gewichtung Favoriten ×3, „Leaving soon“ ×2, hoch bewertet ×1,5; übersprungene Vorschläge 7 Tage seltener; Begründung nur aus echten Daten („Leaving Netflix on 30.11.“, „Favorite“, „★ 4.3 on Letterboxd“, „Director of 2 films you rated 4+“).
- [ ] **Globale Suche** (Taste `/`, mobil Lupe): gruppiert „In your watchlist“ · „Other films“ (TMDB); bester Weg auch für Filme außerhalb der Watchlist; Personen-Treffer („Christopher Nolan · 6 films in your watchlist“) filtern die Watchlist; tippfehlertolerant, deutsche und Originaltitel; `Add on Letterboxd ↗` (die App schreibt nicht selbst).

## B3. Benachrichtigungen, Stats, Stimmung

- [ ] **Digest** wöchentlich (Fr 17 Uhr, einstellbar) per ntfy/Gotify-Webhook: neu verfügbar, bald weg, ein Abo-Tipp. Max. 1 Nachricht/Tag, Ruhezeiten 22–8 Uhr.
- [ ] **Push** nur für Favoriten, die in ≤ 7 Tagen verschwinden, und für Kündigungsfristen (3 Tage + 1 Tag vorher); öffnet direkt Drawer bzw. Abos-Seite.
- [ ] **Home Assistant:** Endpunkte `films_leaving_soon`, `next_subscription_deadline`, `watchlist_coverage` (JSON, mit Token).
- [ ] **Stats-Seite** (jede Zahl mit Aktion): Abdeckung über Zeit → „Show uncovered films“; exklusive Filme pro Dienst über Monate → „Plan a Disney+ month“; Watchlist-Zuwachs vs. gesehene Filme pro Monat (aus Letterboxd gelesen); Ø Wartezeit bis ein Film gratis/im Abo verfügbar wird.
- [ ] **Stimmungs-Chips** auf Tonight mit festen Regeln aus Genres + Schlagwörtern (keine KI): `Light`, `Dark`, `Mind-bending`, `Feel-good`; Regeln in einer Konfigurationsdatei, Unit-Tests mit Beispielfilmen.
- [ ] **Nebenbei:** Haptik (`navigator.vibrate(10)`) bei Favorit und Pick for me; Oberflächensprache konsequent EN mit Umschalter DE/EN in Settings.

## B4. Filmabend zu zweit (nur wenn B1–B3 abgenommen)

- [ ] **Zweites Profil:** Letterboxd-Name + eigene Dienste der zweiten Person in Settings.
- [ ] **Together-Modus** (Schalter auf Tonight): Filme auf **beiden** Watchlists zuerst, danach Filme auf einer Watchlist, die laut Letterboxd keiner von beiden gesehen hat. Dienste = Vereinigung; Karte zeigt, wessen Dienst es ist.
- [ ] **Optional — Swipe-Abstimmung:** Link teilen, beide wischen durch 10 Vorschläge (♥ / ✕), Ergebnis „You both liked 3 films“ mit Haupt-Button. Kein Konto nötig (Token-Link, 24 h gültig).

## Abnahme Teil B

- [ ] Ohne Anmeldung ist weder Seite noch Endpunkt erreichbar; Backups laufen.
- [ ] App lässt sich installieren und zeigt offline den letzten Stand.
- [ ] Tonight zeigt abends Endzeiten; „Fits tonight“ filtert korrekt.
- [ ] Globale Suche findet Watchlist-Filme, andere Filme und Personen.
- [ ] Benachrichtigungen höchstens 1× täglich und führen direkt zum Ziel.
- [ ] Jede Kennzahl auf der Stats-Seite hat eine Aktion.
- [ ] Nirgends Loggen/Seen/Bewerten in der App, nirgends Filmpreise.
