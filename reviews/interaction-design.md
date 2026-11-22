# Interaction-Design-Review (interaction-design)

Stand: 2026-11-15, Arbeitskopie mit uncommitteten Änderungen. Beurteilt nur aus dem Code (`static/js/*.js`, Templates). Die App lief nicht.

**Abgrenzung:** Hier geht es um das *Verhalten*: Auslöser, Regeln, Rückmeldung, Zustände, Schleifen und Modi. Barrierefreiheit steht in [web-design-guidelines.md](web-design-guidelines.md) (WDG), Struktur und Begriffe in [design-critique.md](design-critique.md) (DC). Was dort schon steht, nenne ich nur mit Verweis, z. B. „DC #11“.

---

## 1. Haltung des Produkts

| Seite | Haltung | Passt das Verhalten? |
|---|---|---|
| `/` Watchlist | **Transient**: abends kurz öffnen, einen Film finden, fertig | Teilweise. Gespeicherte Ergebnisse erscheinen sofort (gut). Die Oberfläche ist aber dicht wie bei einem souveränen Werkzeug (DC #4, #6, #7) |
| Automatischer Scan | **Daemonisch**: läuft im Hintergrund nach Plan | Gut. Er ist unsichtbar und steht auf `/status`. Auf `/` ist das Scan-Panel aber immer sichtbar, auch im Ruhezustand (DC #7) |
| Settings, Costs, Matches | Transient, selten | Passt. Kurze Formulare, ein Speichern-Knopf |

**Folgerung:** Die Nutzerin ist eine „perpetual intermediate“. Die Hauptseite sollte im Ruhezustand nur den Weg „Dienste → Film → Wo schaue ich ihn?“ zeigen. Alles andere kommt bei Bedarf dazu.

---

## 2. Der Ablauf als Geschichte: „Ein Film für heute Abend“

| Wendepunkt | Was heute passiert | Bewertung |
|---|---|---|
| **Einstieg** | Die Seite lädt, der letzte Scan ist sofort da (`app.js:652-670`) | Stark |
| **Auslöser** | „Was schaue ich?“ Die Nutzerin wählt Dienste oder „My subscriptions“ | Gut. Ein Klick, mit Toast „Showing your 4 subscriptions.“ |
| **Steigerung** | Filtern, sortieren, scrollen | Schnell (unter 100 ms, kein Request). Aber viele Regler (DC #6) |
| **Krise** | Zu viele Treffer oder plötzlich gar keine | Schwach. Kein leerer Zustand (DC #2), versteckte Filter (DC #1) |
| **Höhepunkt** | „Random“ oder „Evening mode“ schlagen einen Film vor | **Verpufft.** „Random“ scrollt nur (DC #19), Evening mode zeigt Text ohne Link (DC #13) |
| **Ausklang** | Details zeigen, *wo* der Film läuft | Gut gruppiert, aber **ohne Link zum Dienst** (Befund 11) |
| **Ende** | Man verlässt die App und sucht den Film in der Netflix-App | Kein gestaltetes Ende. Dass man ihn angeschaut hat, merkt die App sich nicht (Befund 10) |

**Peak-End-Regel:** Den Höhepunkt (Vorschlag → Details) und das Ende (direkt zum Dienst, danach „Watched“) zu gestalten, bringt mehr als jede weitere Filteroption.

---

## 3. Zustandsmaschine des Scans (aus `app.js:220-311` abgeleitet)

```
[Gespeichert] --Retry scan / Country--> [Starte]
[Starte] --POST ok--> [Läuft]            --POST-Fehler (HTTP)--> [Fehler]
         --Netzwerkfehler--> ??? (unbehandelt, Befund 4)
[Läuft] --Poll ok--> [Läuft]
        --Poll: Netzwerk weg--> [Läuft] (alle 2 s, endlos, ohne Hinweis, Befund 4)
        --Poll: 404--> [Starte] (startet selbst einen neuen Scan)
        --complete--> [Fertig]
        --cancelled--> [Abgebrochen] (Balken 100 %, Befund 5)
        --interrupted--> [Starte]
        --error--> [Fehler]
[Fertig]/[Abgebrochen]/[Fehler] --Retry scan--> [Starte]
```

**Lücken:**
- Der Netzwerkfehler beim Start hat keinen Zustand.
- „Server dauerhaft weg“ sieht genauso aus wie „läuft“.
- „Rescan“ ist ein eigener Modus (`scanState.rescanInProgress`, `app.js:285`). Er zeigt alte Ergebnisse, auch wenn sie zu einem anderen Land gehören (Befund 3). Diesen Zustand dürfte es nicht geben.

---

## 4. Mikrointeraktionen im Überblick

| Interaktion | Auslöser | Regeln | Rückmeldung | Schleifen / Modi | Lücke |
|---|---|---|---|---|---|
| Favorit an/aus | Stern auf dem Poster | Wartet auf den Server, Knopf ist so lange gesperrt (`app.js:341-373`) | Stern wechselt, Toast | – | Kein Undo (DC #11). Toast bei jedem Klick (Befund 12) |
| Status / Notiz | `change` am Select oder Feld | PATCH beim Verlassen des Feldes (`app.js:374-380`) | Toast „Favorite updated.“ | – | **Fehler bleiben still** (Befund 1) |
| Filter ändern | `input` an 13 Reglern | Sofort filtern, URL mitschreiben | Raster aktualisiert sich, Chips | – | Zahl der Treffer wird nicht angesagt (WDG #8), Chips fehlen (DC #1) |
| Dienst-Schnellwahl | 3 Knöpfe | Ersetzt die Auswahl komplett | Toast mit Anzahl | – | Gut. Mobil schließt das Panel (passt hier) |
| Vergleich | Checkbox auf dem Poster | Sammelt Keys in `state.compareKeys` | Nur das Häkchen | **Versteckter Modus** | Befund 8 |
| Favoriten-Ansicht | Knopf „My favorites“ | Schaltet `favoritesOnly` um | Text wird zu „All films“ | **Modus** | Befund 9 |
| Evening mode | Knopf → Dialog → Formular | Top 3 nach Bewertung auf gespeicherten Abos | Liste aus reinem Text | One-off | Sackgasse (DC #13), vergisst die Eingaben (Befund 13) |
| Share | Knopf | Kopiert die URL | „Link copied“ bleibt stehen | – | Befund 14, http-Problem in WDG #12 |
| Kosten speichern | Submit | PUT, dann Reload | „Saved.“ für einen Augenblick | – | Befund 6 |
| Match korrigieren | „Correct“ klappt auf und sucht sofort | Gute Vorgabe: die Suche startet mit dem Titel | Meldung oben in der Leiste | – | Befund 7 |

---

## Befunde

### Must fix

#### 1. Notiz und Status gehen bei einem Fehler still verloren
- **Ort:** `static/js/app.js:374-380` (`updateFavoriteField`), ausgelöst über `app.js:511-512`
- **Prinzip:** Regeln: „Define every edge case“. Rückmeldung: Stärke passend zur Wichtigkeit. Datenverlust muss auffallen.
- **Problem:** `if (response.ok) { … showToast('Favorite updated.') }` hat keinen `else`-Zweig und kein `try/catch`. Ist die App gerade neu gestartet oder das WLAN weg, bleibt die getippte Notiz im Feld stehen und *sieht gespeichert aus*. Nach dem nächsten Neuzeichnen ist sie weg.
- **Kleinste Lösung:** Einen `else`- und `catch`-Zweig mit `showToast('Could not save the note. It is still in the field; try again.')`. Dazu am Feld `classList.add('is-invalid')`, bis ein erneuter Versuch klappt.

#### 2. Ein Länderwechsel in den Settings verwirft ungespeicherte Abo-Häkchen
- **Ort:** `static/js/settings.js:18-24` (`showSubscriptions` bei `country` → `change`)
- **Prinzip:** Fehlervermeidung (Poka-Yoke), „Don't punish the user“
- **Problem:** Die Nutzerin hakt für DE drei neue Abos an und stellt dann das Land auf AT, um nachzusehen. Die Häkchen werden aus `subscriptions[AT]` neu gesetzt. Zurück auf DE sind ihre drei neuen Häkchen weg, denn `subscriptions[DE]` ändert sich erst beim Speichern (`settings.js:43`). Einen Hinweis gibt es nicht.
- **Kleinste Lösung:** In `showSubscriptions` vor dem Umschalten die aktuellen Häkchen unter dem *vorherigen* Land in `subscriptions` merken (das vorherige Land in einer Variable halten). Das Speichern schickt dann ohnehin die Liste des gewählten Landes.

#### 3. Nach einem Länderwechsel zeigt die Seite während des Scans Filme des alten Landes
- **Ort:** `static/js/app.js:599` (`country-select` → `startScan`), `static/js/app.js:285-291` (`rescanInProgress = state.films.length > 0` behält die alten Filme)
- **Prinzip:** Zustandsmaschine: „Make impossible states impossible“
- **Problem:** Man wechselt von DE auf US. Der Kopf zeigt „US“, aber das Raster zeigt minutenlang die deutschen Angebote mit deutschen Diensten. Gleichzeitig sind die Dienst-Häkchen und „My subscriptions“ schon auf US umgestellt (`app.js:16`). Man sieht also Filme, die angeblich auf US-Diensten laufen. Erst bei `complete` wird ersetzt.
- **Kleinste Lösung:** Beim Länderwechsel zuerst `loadLatestResult()` für das neue Land aufrufen (das deckt sich mit DC #15). Nur wenn es keinen Scan gibt, mit `rescanInProgress = false` starten, also mit Skeleton statt alten Daten.

### Should fix

#### 4. Kein Zustand für „Server nicht erreichbar“
- **Ort:** `static/js/app.js:227-231` (Poll-Fehler: still alle 2 s erneut versuchen, endlos), `static/js/app.js:300-301` (`fetch('/api/scan')` ohne `try/catch`)
- **Prinzip:** Schleifen mit Bedingung brauchen sichtbaren Zustand. Antwortzeit: über 10 s muss man erklären.
- **Problem:** Ist die App gestoppt, steht der Fortschrittsbalken einfach still, und die Phase heißt weiter „Scanning“. Man wartet ohne Ende. Scheitert der Start selbst, wirft das Promise einen Fehler, und das Panel zeigt weiter „Preparing your watchlist...“.
- **Kleinste Lösung:** Fehlversuche zählen. Ab dem 3. Versuch `status-message` auf „Lost connection to the app, retrying…“ setzen und den Text bei Erfolg zurücksetzen. `startScan` in `try/catch` packen und dieselbe Fehlerausgabe wie in `app.js:302` nutzen.

#### 5. Ein abgebrochener Scan sieht aus wie ein fertiger, und vorher kommt eine unnötige Rückfrage
- **Ort:** `static/js/app.js:272` (bei `cancelled` wird `progress-bar` auf 100 % gesetzt), `static/js/app.js:580` (`window.confirm`)
- **Prinzip:** Gleiche Rückmeldung für verschiedene Ergebnisse vermeiden. Für umkehrbare Aktionen keine Rückfrage.
- **Problem:** Ein voller Balken heißt „fertig“, auch wenn daneben „Cancelled“ steht. Die Rückfrage vor dem Abbrechen unterbricht, obwohl nichts verloren geht. Die alten Ergebnisse bleiben ja, und „Retry scan“ ist einen Klick entfernt.
- **Kleinste Lösung:** Bei `cancelled` den Balken stehen lassen (oder auf 0 %) und grau färben. Die Rückfrage entfernen. Der Toast „Scan cancelled. Previous results kept.“ (`app.js:278`) reicht.

#### 6. Kosten-Seite: „Saved.“ verschwindet sofort durch den Reload
- **Ort:** `static/js/costs.js:25-26`
- **Prinzip:** Rückmeldung nahe am Auslöser, Peak-End-Regel (das Ende einer Aktion gestalten)
- **Problem:** Die Meldung wird gesetzt und im selben Moment lädt die Seite neu. Man sieht nur ein Flackern, und die Seite springt nach oben. Ob gespeichert wurde, erkennt man nur an den geänderten Zahlen „Per film“.
- **Kleinste Lösung:** `location.replace('/costs?saved=1')` aufrufen und im Template bei `request.args.saved` die Meldung „Prices saved.“ direkt anzeigen. Oder wie in `settings.js:63` 1 s warten und einen Hinweis zeigen.

#### 7. Matches: Die Bestätigung an der Zeile wird sofort wieder entfernt
- **Ort:** `static/js/matches.js:50-53` (`row.classList.add('match-saved')` und direkt danach `await load()`, das die Liste ersetzt)
- **Prinzip:** Rückmeldung nahe am Auslöser
- **Problem:** Der Akzent-Rahmen „gespeichert“ ist nach einem Neuzeichnen weg. Ist die Zuordnung jetzt sicher, verschwindet die Zeile ganz. Die einzige Rückmeldung steht oben in der Leiste, weit weg von der Stelle, an der man geklickt hat. Bei einer langen Liste sieht man sie gar nicht.
- **Kleinste Lösung:** Nach `load()` die Zeile mit dem gleichen `data-film-key` suchen. Gibt es sie noch, `match-saved` setzen. Ist sie verschwunden, einen Toast oder die Meldung per `scrollIntoView` zeigen. Das deckt sich mit WDG #4 (Fokus).

#### 8. Der Vergleich ist ein versteckter Modus
- **Ort:** `static/js/app.js:125-138`, `static/js/state.js:10`. Kein Code leert `state.compareKeys` (per `grep` geprüft).
- **Prinzip:** Modi möglichst vermeiden. Wenn es einen gibt, muss er gut sichtbar sein. „Bring the data forward“ (die Zahl gehört auf den Auslöser).
- **Problem:** Gewählte Filme bleiben gewählt, auch wenn ein Filter sie ausblendet. Man klickt „Compare“ und bekommt „Select 2 to 4 films“, obwohl man glaubt, zwei gewählt zu haben. Oder man bekommt einen Film, den man längst vergessen hat. Es gibt kein „Auswahl leeren“.
- **Kleinste Lösung:** Den Knopf mit Zähler beschriften, „Compare (n)“, aktiv ab 2 (siehe DC #12). Im Vergleichsdialog unten einen Knopf „Clear selection“, der `compareKeys.clear()` aufruft und neu zeichnet.

#### 9. Die Favoriten-Ansicht ist ein Modus, den nur die Beschriftung des Knopfs zeigt
- **Ort:** `static/js/app.js:569-573`
- **Prinzip:** Den aktuellen Modus unübersehbar machen. Ein Knopf zeigt den Zustand *oder* die Aktion, nicht beides vermischt.
- **Problem:** Im Modus steht auf dem Knopf „All films“, also die Aktion. Wer die App über einen gespeicherten Link mit `favorites=1` öffnet, sieht nur ein paar Filme. Dass ein Modus aktiv ist, verrät nur ein Knopf unter vielen.
- **Kleinste Lösung:** Im Modus über dem Raster eine Zeile zeigen: „Showing your favorites only · [Show all films]“. Der Knopf heißt fest „My favorites“ und bekommt `aria-pressed`.

#### 10. „Watched“ hat außerhalb der Favoriten-Ansicht keine Wirkung
- **Ort:** `static/js/filtering.js:56-59` (`favoriteStatus` gilt nur, wenn `favoritesOnly` an ist), `static/js/app.js:104-110` (Random), `static/js/filtering.js:131-139` (Evening)
- **Prinzip:** Schleifen über lange Zeit („The Long Wow“): Die App soll aus dem Gebrauch lernen. „Don't start from zero“.
- **Problem:** Man setzt einen Film auf „Watched“. „Random“ und „Evening mode“ schlagen ihn weiter vor, und im Raster sieht er aus wie jeder andere. Der Status ist eine Notiz ohne Folgen.
- **Kleinste Lösung:** In `eveningSuggestions` und `showRandomFilm` Filme mit `favorites.get(key)?.status === 'watched'` überspringen. Optional im Raster ein kleines Abzeichen „Watched“ zeigen.

#### 11. Am Ende fehlt der Weg zum Ansehen
- **Ort:** `static/js/app.js:462` (die Aktionen im Detail-Dialog sind Favorit, Vergleich, TMDB, Trailer und Letterboxd). `watchlist_app/tmdb.py` speichert kein `link` aus der TMDB-Antwort „watch/providers“ (per `grep` geprüft).
- **Prinzip:** Peak-End-Regel, Kontextlinks (keine Sackgasse am Ziel)
- **Problem:** Der Dialog sagt „Netflix (Subscription)“. Um den Film zu starten, muss man die App verlassen und ihn dort erneut suchen. Der eigentliche Abschluss der Aufgabe findet außerhalb statt, ohne Brücke.
- **Kleinste Lösung:** TMDB liefert pro Land ein Feld `link` zur Watch-Seite (JustWatch). Dieses Feld speichern und im Dialog als Hauptknopf „Where to watch ↗“ zeigen. **Unverifiziert:** ob das Feld in den gespeicherten Scans schon steckt. In `tmdb.py` habe ich es nicht gefunden.

#### 12. Erfolg und Fehler sehen im Toast gleich aus, Routine wird jedes Mal angesagt
- **Ort:** `static/js/app.js:19-20` (ein einziger Toast), `static/css/app.css:125` (ein Stil), u. a. `app.js:361` („Could not update favorite.“) und `app.js:372` („Added to favorites.“)
- **Prinzip:** Unterschiedliche Rückmeldung für unterschiedliche Ergebnisse. Rückmeldung soll mit der Wiederholung abnehmen.
- **Problem:** Ein Fehler erscheint in derselben Farbe am selben Ort und für dieselben 2,4 s wie „Added to favorites.“. Man übersieht ihn leicht. Umgekehrt meldet sich jeder Stern-Klick mit einem Toast, obwohl der Stern selbst schon die Rückmeldung ist.
- **Kleinste Lösung:** `showToast(message, {error})`: Bei Fehlern rote Randfarbe und etwa 6 s Anzeige (und WDG #7: `role="alert"`). Bei „Added/Removed from favorites“ und „Favorite updated.“ keinen Toast, außer beim Undo-Toast aus DC #11.

### Nice to have

#### 13. Evening mode vergisst die Eingaben
- **Ort:** `static/js/app.js:111-116` (das Genre-Select wird bei jedem Öffnen per `innerHTML` neu gebaut, dabei geht die Auswahl verloren)
- **Prinzip:** „Don't start from zero“ (die letzte Wahl merken)
- **Problem:** Wer jeden Abend „Horror, 100 min“ einstellt, wählt das Genre bei jedem Öffnen neu, nach einem Neuladen auch die Laufzeit.
- **Kleinste Lösung:** Beide Werte in `localStorage` merken und nach dem Neuaufbau setzen, so wie es `greyUnavailableDuringRescan` schon macht (`app.js:594`).

#### 14. „Link copied“ bleibt für immer stehen
- **Ort:** `static/js/app.js:612`
- **Prinzip:** Rückmeldung mit Ablauf
- **Problem:** Nach einem Filterwechsel stimmt die kopierte URL nicht mehr, aber die Meldung steht noch da.
- **Kleinste Lösung:** Den vorhandenen Toast nutzen und `#share-message` entfernen (siehe WDG #12).

#### 15. Status und Notiz erscheinen erst nach dem Favorisieren, und die Karte springt
- **Ort:** `static/js/rendering.js:72` (`hidden`, solange der Film kein Favorit ist)
- **Prinzip:** Übergänge zwischen Zuständen ruhig gestalten (kein Layout-Sprung)
- **Problem:** Nach dem Klick auf den Stern wird die Karte höher. Die Nachbarkarten in derselben Zeile verschieben sich, und der nächste Klick geht leicht daneben.
- **Kleinste Lösung:** Die Felder nur in der Favoriten-Ansicht und im Detail-Dialog zeigen, nicht auf jeder Karte im Raster. Oder ihren Platz immer reservieren (`visibility: hidden` statt `hidden`).

#### 16. „Grey out films found unavailable“ ist immer zu sehen, wirkt aber nur bei einem neuen Scan
- **Ort:** `templates/partials/scan-status.html:6`, Regel in `static/js/app.js:22-25`
- **Prinzip:** Sichtbarkeit passend zur Nutzung (Trigger nach Häufigkeit)
- **Problem:** Im Ruhezustand ändert ein Klick nichts Sichtbares.
- **Kleinste Lösung:** Die Option nur zeigen, solange `scanState.rescanInProgress` gilt. Oder sie auf die Settings-Seite verschieben.

#### 17. Keine Tastenkürzel für wiederkehrende Handgriffe
- **Ort:** `static/js/app.js` (es gibt keinen globalen `keydown` außer Escape in `:406`)
- **Prinzip:** Perpetual intermediates: mehrere Wege zum selben Befehl (sichtbarer Knopf plus Kürzel)
- **Problem:** Suche, „Random“ und „My subscriptions“ gehen nur mit der Maus.
- **Kleinste Lösung:** `/` fokussiert `#film-search`, `r` startet „Random“. Nur auslösen, wenn der Fokus nicht in einem Eingabefeld ist. Das Kürzel im `title` des Knopfs nennen, damit man es entdeckt.

---

## Was gut funktioniert

- **Sofort sichtbare Ergebnisse** dank gespeichertem Scan. Ein neuer Scan läuft nur, wenn der alte veraltet ist.
- **Filtern ohne Request** in unter 100 ms. Das ist die richtige Regel für die häufigste Handlung.
- **Ein Scan lässt sich fortsetzen:** Über `?scan=<id>` hängt sich die Seite nach einem Neuladen wieder an den laufenden Scan. Der Server startet nach einem Neustart selbst neu (`interrupted`).
- **Abklingendes Polling:** Ändert sich nichts, verlängert sich der Abstand von 350 ms bis 2 s (`app.js:262-264`). So wird der Server geschont, ohne dass die Seite träge wirkt.
- **Gute Vorgaben auf Matches:** Die Suche startet beim Aufklappen mit Titel und Jahr. „Looks right“ bestätigt mit einem Klick.
- **Rückfragen nur bei Gewicht:** Backup wiederherstellen fragt nach, Filter ändern nicht.

---

## Zusammenfassung

| Gruppe | Anzahl | Befunde |
|---|---|---|
| Must fix | 3 | 1 Notiz geht still verloren, 2 Settings verwerfen Häkchen, 3 Filme des alten Landes während des Scans |
| Should fix | 9 | 4–12 |
| Nice to have | 5 | 13–17 |

**Die größte Wirkung bei wenig Aufwand:** Befunde 1–3 verhindern Datenverlust und falsche Anzeigen, jeweils mit ein paar Zeilen. Befunde 10 und 11 machen aus „Film finden“ einen geschlossenen Ablauf: Vorschlag → wo läuft er → ansehen → „Watched“ → wird nicht mehr vorgeschlagen.

**Nicht geprüft:** Das Verhalten im echten Browser, die Zeiten (alle Angaben in ms stammen aus dem Code, nicht aus Messungen) und die genaue TMDB-Antwort für Befund 11.
