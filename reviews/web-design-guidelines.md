# Web-Design-Review (web-design-guidelines)

Stand: 2026-11-15, Arbeitskopie mit uncommitteten Änderungen.

**Quelle der Regeln:** Der Skill `project-starter:web-design-guidelines` bringt seine Regeln selbst mit (A11Y, PERF, RD, CP, CSS, SEC, I18N). Es war kein Abruf aus dem Netz nötig. Wo ich eine Regel nutze, die nicht in dieser Liste steht, steht **„(eigene Regel)“** dabei.

**Umfang:** `templates/` samt `templates/partials/`, `static/css/app.css` und die selbst geschriebenen Dateien in `static/js/`. Vendor-Dateien habe ich ausgelassen. Nur in einem Punkt habe ich in `bootstrap.bundle.min.js` (v5.3.3) nachgesehen, ob Bootstrap den Fokus zurückgibt (Punkt 5).

**Wie ich geprüft habe:** Nur durch Lesen des Codes. Die App lief nicht, und ich habe keinen Screenreader benutzt. Punkte, die ich im Code nicht sicher belegen kann, sind mit **unverifiziert** markiert.

---

## Must fix

### 1. Die Filter-Seitenleiste ist auf dem Desktop für Screenreader unsichtbar
- **Ort:** `templates/partials/provider-sidebar.html:1` (`aria-hidden="true"` fest im HTML), `static/js/app.js:387-396` und `static/js/app.js:406-408`
- **Regel:** A11Y-01/A11Y-05. Inhalt, der sichtbar und bedienbar ist, darf nicht `aria-hidden` sein.
- **Problem:** Nur `openProviderPanel()` setzt `aria-hidden="false"`. Diese Funktion läuft nur über den Knopf „Filters“, und den gibt es nur im Mobil-Layout (`app.css:9` blendet ihn aus). Auf dem Desktop bleibt die ganze `<aside>` mit allen Dienst-Checkboxen, der Suche und „My subscriptions“ deshalb für Screenreader verborgen. Mit Tab kommt man trotzdem hinein: Man landet auf Checkboxen, die „nicht existieren“ und keinen Namen ansagen. Zusätzlich setzt jede Escape-Taste irgendwo auf der Seite (`app.js:406`) das Panel wieder auf `aria-hidden="true"`, auch auf dem Desktop.
- **Kleinste Lösung:** `aria-hidden="true"` aus dem Template entfernen. Im Mobil-Layout verbirgt `visibility: hidden` (`app.css:149`) das geschlossene Panel schon richtig. `closeProviderPanel`/`openProviderPanel` brauchen kein `aria-hidden` mehr. Den Escape-Handler auf `providerPanel.classList.contains('show')` beschränken.

### 2. Die Filmkarte ist ein `role="button"` mit Knöpfen, Links, Checkbox, Select und Textfeld darin
- **Ort:** `static/js/rendering.js:73` (`<article class="film" role="button" tabindex="0" aria-label="Open details for …">`), `static/js/rendering.js:79` (Karte „nicht verfügbar“), `static/js/app.js:465-469` und `static/js/app.js:487-493`
- **Regel:** A11Y-01. Steuerelemente nicht ineinander schachteln. Die Kinder eines `button` gelten als reine Darstellung.
- **Problem:** Ein Screenreader liest die ganze Karte als *einen* Knopf: „Open details for Alien, Taste“. Den Stern, „Compare“, „TMDB“, „Trailer“, „Details“, den Favoriten-Status und das Notizfeld darin sagt er nicht als eigene Elemente an, oder er sagt sie je nach Browser doppelt bzw. durcheinander an. Pro Karte gibt es außerdem einen zusätzlichen Tab-Stopp, der dasselbe tut wie der Knopf „Details“, der schon in der Karte steckt. Bei 200 Filmen sind das 200 Tab-Schritte mehr.
- **Kleinste Lösung:** `role="button"`, `tabindex="0"` und `aria-label` von beiden `<article>` entfernen und den Keydown-Handler `app.js:487-493` löschen. Der Knopf „Details“ öffnet den Dialog schon (`app.js:494-497`). Der Klick auf die Karte (`app.js:465-469`) kann als Abkürzung für die Maus bleiben. Die CSS-Selektoren `.film[role="button"]` (`app.css:107-109`) auf `.film` umstellen.

### 3. Beim Favoriten-Status und der Notiz ist der Fokus praktisch unsichtbar
- **Ort:** `static/css/app.css:94` (`outline: none`, als Ersatz `border-color: var(--accent)` und ein Schatten mit 14 % Deckkraft) und `static/css/app.css:121` (`border-color: #4a554e !important` für `.favorite-status, .favorite-note`)
- **Regel:** A11Y-03. Fokus muss sichtbar sein, kein `outline: none` ohne Ersatz. Dazu CSS-01: kein `!important`.
- **Problem:** Wegen `!important` in Zeile 121 gewinnt die graue Randfarbe gegen die Akzentfarbe aus Zeile 94. Als Fokuszeichen bleibt nur ein Schatten mit `rgba(…,.14)` von 0.15rem auf dunklem Grund. Wer mit Tab durch die Karten geht, sieht nicht, ob gerade das Select oder das Notizfeld den Fokus hat.
- **Kleinste Lösung:** In Zeile 94 `outline: none` streichen und `.favorite-status:focus-visible, .favorite-note:focus-visible` in die Fokusregel in `app.css:42` aufnehmen (2px Outline in Akzentfarbe).

### 4. Der Fokus springt nach einem Favoriten-Klick oder einer Korrektur an den Anfang der Seite
- **Ort:** `static/js/app.js:364` (`renderFilms()` nach `toggleFavorite`) mit `static/js/rendering.js:84` (`containers.results.innerHTML = …`), außerdem `static/js/matches.js:53` und `static/js/matches.js:64` (`await load()` baut die Liste mit `replaceChildren` neu)
- **Regel:** A11Y-03. Tastaturbedienung darf den Ort nicht verlieren.
- **Problem:** Eine Tastaturnutzerin drückt bei Film 80 auf den Stern. Alle Karten werden neu gebaut, der fokussierte Knopf ist weg, und der Fokus landet auf `<body>`. Mit dem nächsten Tab geht es wieder oben in der Kopfzeile los. Auf der Seite „Matches“ ist es genauso nach „Looks right“, „Use this“ oder „Undo correction“.
- **Kleinste Lösung:** Vor dem Neuzeichnen `data-key` (und die Klasse des Steuerelements) des fokussierten Elements merken und danach `document.querySelector('.film[data-key="…"] .favorite')?.focus()` aufrufen. In `matches.js` genauso über `data-film-key` gehen.

### 5. Nach dem Schließen eines Dialogs geht der Fokus nicht zurück zum Auslöser
- **Ort:** `static/js/app.js:463` (Filmdetails), `static/js/app.js:115` (Abendmodus), `static/js/app.js:132` (Vergleich), `static/js/app.js:500` (Trailer)
- **Regel:** CP-05/A11Y-03. Nach dem Schließen den Fokus an den Auslöser zurückgeben.
- **Problem:** Alle Dialoge öffnen per `bootstrap.Modal…show()` aus JS. Bootstrap 5.3.3 gibt den Fokus nur zurück, wenn ein Element mit `[data-bs-toggle="modal"]` den Dialog geöffnet hat (im Bundle nachgesehen). Wer also „Details“ von Film 80 öffnet und mit Escape schließt, steht danach am Seitenanfang.
- **Kleinste Lösung:** Eine kleine Hilfsfunktion `openModal(id)`, die sich `document.activeElement` merkt und es in einem einmaligen `hidden.bs.modal`-Handler mit `.focus()` zurücksetzt. Alle vier `show()`-Aufrufe darüber laufen lassen. Beim Trailer, der aus dem Detail-Dialog kommt (`app.js:503-509`), den ursprünglichen Auslöser (den Knopf „Details“) weitergeben.

---

## Should fix

### 6. Die Dialoge haben keinen zugänglichen Namen
- **Ort:** `templates/partials/modals.html:2-5`
- **Regel:** A11Y-02/CP-05.
- **Problem:** Bootstrap setzt beim Öffnen `role="dialog"`, aber kein `aria-labelledby` verweist auf `.modal-title`. Ein Screenreader sagt nur „Dialog“ an, nicht „Trailer“, „Film comparison“, „Evening mode“ oder den Filmtitel.
- **Kleinste Lösung:** Jedem `<h5 class="modal-title">` eine `id` geben (bei den Filmdetails gibt es schon `film-details-title`) und am `.modal` `aria-labelledby="…"` setzen.

### 7. Fortschritt, Status und Fehler des Scans werden nicht angesagt
- **Ort:** `templates/partials/scan-status.html:4` (`role="progressbar"` ohne `aria-valuenow`/`aria-valuemin`/`aria-valuemax`) und `static/js/app.js:244` (setzt nur `style.width`); `templates/partials/scan-status.html:2` (`#status-message` ohne Live-Region); `templates/partials/scan-status.html:9` (`#error-message` ohne `role="alert"`), gefüllt in `static/js/app.js:237`, `:281`, `:302`
- **Regel:** A11Y-05 und CP-02.
- **Problem:** Ein Screenreader sagt auf dem Fortschrittsbalken immer „0 %“ oder gar nichts. Die Meldung „The previous scan is no longer available. Starting a new scan.“ oder ein Fehler beim Scan erscheint sichtbar, wird aber nicht vorgelesen. Bei einem Fehler kommt nur der Toast „Scan failed.“, ohne den Grund.
- **Kleinste Lösung:** In `app.js:244` zusätzlich `setAttribute('aria-valuenow', percent)` setzen, im Template `aria-valuemin="0" aria-valuemax="100"`. An `#error-message` `role="alert"` setzen, an `#status-message` `role="status"`. Achtung: Das Element ändert sich bei jedem Poll. `aria-live="polite"` ist dort in Ordnung, weil nur der Text der Meldung wechselt und nicht der Zähler.

### 8. Die Trefferzahl nach einem Filterwechsel wird nicht angesagt, beim Laden fehlt `aria-busy`
- **Ort:** `templates/partials/statistics.html:1` (`#result-meta`/`#visible-count`), `templates/partials/results.html:2` (`#results` mit Skeleton) und `static/js/app.js:290`
- **Regel:** A11Y-05 und CP-02.
- **Problem:** Wer „TMDB 8+“ wählt, hört nichts. Ob jetzt 3 oder 0 Filme passen, merkt man erst durch Suchen in der Liste. Während des ersten Scans gilt `#results` nicht als „lädt“.
- **Kleinste Lösung:** `aria-live="polite"` an `#result-meta`. Am `#results` `aria-busy="true"` setzen, solange das Skeleton zu sehen ist, und in `renderResults` wieder entfernen.

### 9. `aria-label` auf einfachen `<div>`s ohne Rolle hat keine Wirkung
- **Ort:** `templates/partials/film-filters.html:1` („Film filters“), `templates/partials/results.html:1` („Active filters“), `templates/partials/results.html:2` und `static/js/app.js:290` (Skeleton „Loading films“), `templates/partials/statistics.html:3` (`#coverage`, „Provider coverage“)
- **Regel:** A11Y-02.
- **Problem:** Screenreader ignorieren `aria-label` auf einem `div` ohne Rolle. Die Gruppe „Film filters“ oder die Ansage „Loading films“ gibt es für sie nicht.
- **Kleinste Lösung:** `role="group"` für die Filter, die Chips und die Abdeckung. Beim Skeleton `role="status"`, damit „Loading films“ angesagt wird.

### 10. Mobiles Filterpanel: schließt nach jeder Checkbox, Fokus kommt nicht hinein und nicht zurück
- **Ort:** `static/js/app.js:401-405` und `static/js/app.js:432` (schließen nach jeder Änderung), `static/js/app.js:392-396` (Öffnen ohne Fokus), `static/js/app.js:387-391` (Schließen ohne Fokus)
- **Regel:** A11Y-03 und CP-05 (Off-Canvas verhält sich wie ein Dialog).
- **Problem:** Auf dem Handy will man Netflix, Prime und Disney+ wählen. Nach jedem Häkchen klappt das Panel zu, man muss also dreimal „Filters“ antippen. Mit Tastatur: Nach dem Öffnen bleibt der Fokus auf dem Knopf „Filters“, und der nächste Tab geht in die Seite *hinter* dem Panel. Nach einer Auswahl wird die fokussierte Checkbox `visibility: hidden`, und der Fokus fällt auf `<body>`.
- **Kleinste Lösung:** Den Handler `app.js:401-405` löschen, denn das Panel schließt schon bei einem Klick außerhalb und bei Escape. Die Schnellwahl-Knöpfe (`:432`) dürfen weiter schließen. In `openProviderPanel` `document.getElementById('provider-search').focus()`, in `closeProviderPanel` `providerToggle.focus()`, das aber nur, wenn der Fokus im Panel war.

### 11. „Restore from file“ und „Import favorites“ zeigen keinen Fokus
- **Ort:** `templates/settings.html:61` und `templates/partials/result-tools.html:1` (`<label class="btn" for="import-favorites">…<input class="visually-hidden" …>`)
- **Regel:** A11Y-03.
- **Problem:** Mit Tab kommt man auf das unsichtbare `<input type="file">`. Das Label, das wie ein Knopf aussieht, bekommt keinen Fokusrahmen. Man drückt also „irgendwo“ Enter und es öffnet sich ein Dateidialog.
- **Kleinste Lösung:** In `app.css` die Regel `.btn:has(> input:focus-visible) { outline: 2px solid var(--accent); outline-offset: 2px; }` ergänzen.

### 12. „Share“ funktioniert über http im Heimnetz nicht und meldet nichts
- **Ort:** `static/js/app.js:612` und `templates/partials/result-tools.html:1` (`#share-message` ohne `role="status"`)
- **Regel:** CP-03 (verständliche Fehlermeldung) und A11Y-05.
- **Problem:** `navigator.clipboard` gibt es nur in einem sicheren Kontext (https oder localhost). Wird die App wie üblich über `http://192.168.x.x:…` aufgerufen, ist `navigator.clipboard` `undefined`. Der Klick wirft einen TypeError in die Konsole, und es passiert sichtbar nichts. Auch wenn es klappt, wird „Link copied“ nicht vorgelesen, und die Meldung bleibt für immer stehen. **Unverifiziert:** Wie die App im Heimnetz tatsächlich aufgerufen wird.
- **Kleinste Lösung:** `try { await navigator.clipboard.writeText(location.href); showToast('Link copied.'); } catch { window.prompt('Copy this link:', location.href); }`. Der Toast hat schon `role="status"` (`modals.html:1`), dann kann `#share-message` weg.

### 13. Formulare: doppeltes Absenden möglich, kein Fehlertext bei Netzwerk- oder Serverfehler
- **Ort:** `static/js/settings.js:28-45`, `static/js/settings.js:47-64`, `static/js/costs.js:4-27`
- **Regel:** CP-01 (Absenden-Knopf während des Sendens sperren) und CP-03.
- **Problem:** „Save settings“ und „Save prices“ bleiben während des Requests klickbar. Ist der Server weg oder antwortet mit einer HTML-Fehlerseite (z. B. 502 vom Proxy), werfen `fetch` oder `response.json()` eine Ausnahme. Die Meldung bleibt leer, und die Nutzerin weiß nicht, ob gespeichert wurde.
- **Kleinste Lösung:** Submit-Knopf vor dem `fetch` auf `disabled` setzen und in `finally` wieder freigeben. Den Request in `try/catch` packen und im `catch` `show('settings-message', 'Could not reach the app.', true)` anzeigen, für die Kosten entsprechend. `matches.js:27-32` zeigt das Muster schon (`response.json().catch(() => ({}))`).

### 14. Knöpfe wiederholen sich ohne Filmnamen: „Add favorite“ und „Details“ hundertfach
- **Ort:** `static/js/rendering.js:69` (`aria-label="Add favorite"`), `static/js/rendering.js:73` und `static/js/rendering.js:79` (Knopf „Details“), `static/js/rendering.js:72` (`aria-label="Favorite status"`/`"Favorite note"`)
- **Regel:** A11Y-02. Zugängliche Namen müssen eindeutig sein.
- **Problem:** Heute verdeckt die `role="button"`-Karte das. Nach der Lösung von Punkt 2 hört man in der Liste der Steuerelemente 200-mal „Add favorite“ und „Details“, ohne zu wissen, für welchen Film. Der Stern hat außerdem kein `aria-pressed`, sein Zustand ändert sich nur über den Text.
- **Kleinste Lösung:** `aria-label="Add ${title} to favorites"` bzw. `"Remove ${title} from favorites"`, dazu `aria-label="Details for ${title}"`. Den Titel mit `escapeHtml` einsetzen. Status und Notiz genauso mit Titel benennen.

### 15. Die Karten „nicht verfügbar“ haben zu wenig Kontrast
- **Ort:** `static/css/app.css:76` (`.unavailable { opacity: .78 }`), `static/css/app.css:77-78` (`.unavailable-card { filter: grayscale(1); opacity: .58 }` mit Text `#89938b`), `static/css/app.css:79` (`.rescan-unavailable`)
- **Regel:** A11Y-04, mindestens 4,5:1.
- **Problem:** Die Deckkräfte multiplizieren sich zu ≈ 0,45. Nach meiner Rechnung liegt der Text `#89938b` dann bei etwa 2,5:1 auf dem dunklen Hintergrund. Titel und Jahr der nicht verfügbaren Filme sind schwer zu lesen. **Unverifiziert:** Geschätzt, nicht im Browser gemessen.
- **Kleinste Lösung:** `opacity` nur auf das Poster bzw. auf Abzeichen anwenden, nicht auf die ganze Karte. Den Text in `--muted` (`#a9a397`) lassen, das ergibt etwa 6,6:1 auf `#18201c`.

### 16. Das mobile Panel nutzt `100vh`, der untere Teil liegt unter der Browserleiste
- **Ort:** `static/css/app.css:23` (`max-height: calc(100vh - 16px)`) und `static/css/app.css:149` (`max-height: 100vh; height: 100vh`)
- **Regel:** CSS-02 (`100dvh` statt `100vh`).
- **Problem:** In Safari auf dem iPhone und in Chrome auf Android ist `100vh` höher als der sichtbare Bereich. Das Ende des Panels („Use CSV watchlist“, letzte Dienste) verschwindet hinter der Adressleiste und lässt sich manchmal nicht hochscrollen. **Unverifiziert:** Nicht auf einem Gerät getestet.
- **Kleinste Lösung:** `100vh` durch `100dvh` ersetzen. Wer alte Browser abdecken will, schreibt zuerst `height: 100vh;` und danach `height: 100dvh;`.

### 17. Zu kleine Touch-Ziele auf dem Handy
- **Ort:** `static/css/app.css:134` (`.comparison-check` 19×19 px), `static/css/app.css:131` (`.filter-chip`, Padding 3px, Schrift .72rem, also etwa 22 px hoch), `static/css/app.css:93` und `:171-172` (Favoriten-Select und Notiz mit 4px Padding), `static/js/rendering.js:64` („Trailer“ als Textlink im Fließtext)
- **Regel:** RD-01, Touch-Ziele mindestens 44×44 px.
- **Problem:** In der zweispaltigen Ansicht auf dem Handy trifft man statt der Vergleichs-Checkbox oben links leicht das Poster. Das öffnet die Details. Die Chips zum Entfernen von Filtern sind schwer zu treffen.
- **Kleinste Lösung:** Im Mobil-Block (`@media (max-width: 800px)`) `.filter-chip { min-height: 44px; padding: 8px 12px; }`. Die Checkbox in ein `<label>` mit Padding legen (Trefferfläche etwa 44 px), und Favoriten-Select/Notiz bekommen `min-height: 44px`.

---

## Nice to have

### 18. Icon-Schrift ohne `aria-hidden`
- **Ort:** u. a. `templates/partials/header.html:3`, `templates/partials/result-tools.html:1`, `templates/partials/provider-sidebar.html:6`, `templates/partials/scan-status.html:6` und `:8`, `templates/partials/modals.html`-Formulare, `static/js/rendering.js:73` und `:79` (`ti-info-circle`), `static/js/app.js:76` (`ti-x` im Chip), `static/js/app.js:367`, `:453`, `:462`, `:480`, `static/js/matches.js:38`, `:101`, `:120`. Zum Vergleich: `rendering.js:14` und `:30` machen es richtig.
- **Regel:** A11Y-02 (dekorative Bilder ausblenden).
- **Problem:** Tabler-Icons sind Zeichen aus dem Private-Use-Bereich, die über `::before` eingefügt werden. Manche Screenreader-Kombinationen lesen sie als „unbekanntes Zeichen“ oder als Kästchen vor. **Unverifiziert:** Wie stark das stört, hängt vom Screenreader ab.
- **Kleinste Lösung:** `aria-hidden="true"` an jedes `<i class="ti …">` setzen, das neben Text steht.

### 19. Filter-Chips sagen nicht, dass ein Klick den Filter entfernt
- **Ort:** `static/js/app.js:76`
- **Regel:** A11Y-02.
- **Problem:** Vorgelesen wird „Genre: Drama, Taste“. Dass das ✕ den Filter entfernt, sieht man nur.
- **Kleinste Lösung:** `aria-label="Remove filter ${label}: ${text}"` am Chip-Knopf (escaped).

### 20. Zahlen ohne Bedeutung in der Dienstliste
- **Ort:** `templates/partials/provider-sidebar.html:14` und `:22` (`.provider-film-count`), `templates/partials/provider-sidebar.html:3` (`#provider-count`, z. B. „3/40“), `templates/settings.html:38` (`#subscription-count`)
- **Regel:** A11Y-02.
- **Problem:** Vorgelesen wird „Netflix Free 12, Kontrollkästchen“. Was 12 heißt, bleibt offen.
- **Kleinste Lösung:** In der Zähl-Span einen versteckten Text ergänzen, z. B. `<span class="visually-hidden"> films</span>`. Bei `#provider-count` analog „services selected“.

### 21. Filmtitel sind keine Überschriften
- **Ort:** `static/js/rendering.js:73` und `:79` (`<p class="film-title">`), dazu `rendering.js:86` (Abschnitt als `<h2>`)
- **Regel:** A11Y-01 (semantisches HTML).
- **Problem:** Screenreader-Nutzer springen gern mit „H“ von Film zu Film. Das geht nur zwischen „Free“ und „Paid“.
- **Kleinste Lösung:** `<h3 class="film-title">` statt `<p>`. Die CSS-Klasse bleibt, und `h3` aus `app.css:12` wird durch `.film-title` überschrieben. Dabei prüfen, dass Farbe und Großschreibung von `h3` nicht durchschlagen, sonst `.film-title` um `color`/`text-transform`/`letter-spacing` ergänzen.

### 22. Die Navigation steht nicht in `<nav>`
- **Ort:** `templates/costs.html:13`, `templates/matches.html:13`, `templates/settings.html:13`, `templates/status.html:13`, `templates/partials/header.html:3` (Links Settings/Costs/Matches/Status)
- **Regel:** A11Y-01 (Landmarks).
- **Problem:** Über die Landmark-Liste findet man keine Navigation.
- **Kleinste Lösung:** Den `<p class="meta">` mit den Links in `<nav aria-label="Pages">` legen (die Klasse kann bleiben).

### 23. Bei den Jahresfeldern verschwindet die Beschriftung, sobald man tippt
- **Ort:** `templates/partials/film-filters.html:5-6`
- **Regel:** CP-01 (Formulare). Zugänglich ist das schon, `aria-label` ist da.
- **Problem:** Wer in beide Felder ein Jahr tippt, sieht danach „1990“ und „2005“, ohne zu wissen, welches „von“ und welches „bis“ ist.
- **Kleinste Lösung:** Sichtbare Mini-Labels oder ein gemeinsames Label „Year“ mit den Feldern „from“/„to“ daneben.

### 24. Kein `prefers-reduced-motion` (eigene Regel)
- **Ort:** `static/css/app.css:40-41` (`.btn:hover` translateY), `:87-88` (`.favorite` scale), `:108` (Karte bei Hover), `:149` (Panel rutscht herein), `static/js/app.js:108` (`scrollIntoView({behavior: 'smooth'})`)
- **Regel:** Eigene Regel (WCAG 2.3.3 / gängige Praxis), passt zu PERF-03.
- **Problem:** Wer im System „Bewegung reduzieren“ eingestellt hat, bekommt trotzdem Hüpf- und Rutsch-Effekte.
- **Kleinste Lösung:** `@media (prefers-reduced-motion: reduce) { *, *::before, *::after { transition: none !important; animation: none !important; } .btn:hover, .favorite:hover, .film:hover { transform: none !important; } }`. In JS `behavior` nur auf `'smooth'` setzen, wenn `!matchMedia('(prefers-reduced-motion: reduce)').matches`.

### 25. Die Suche zeichnet bei jedem Tastendruck alle Karten neu
- **Ort:** `static/js/app.js:543` (`input` führt direkt zu `renderFilms`), `static/js/rendering.js:84`
- **Regel:** PERF-04 (INP < 200 ms).
- **Problem:** Bei einer großen Watchlist wird bei jedem Buchstaben das ganze Raster per `innerHTML` neu gebaut. Auf schwachen Handys kann das Tippen hakeln. **Unverifiziert:** Nicht gemessen.
- **Kleinste Lösung:** Nur für `film-search` einen Debounce von etwa 150 ms vor `renderFilms` setzen.

### 26. „Random“ scrollt zum Film, lässt den Fokus aber oben
- **Ort:** `static/js/app.js:104-110`
- **Regel:** A11Y-03.
- **Problem:** Tastatur- und Screenreader-Nutzer hören „Random pick: X“, stehen aber weiter auf dem Knopf „Random“ und finden den Film nicht.
- **Kleinste Lösung:** Nach `scrollIntoView` den Knopf „Details“ dieser Karte fokussieren (`card.querySelector('.film-details-button')?.focus({preventScroll: true})`) oder gleich `showFilmDetails(key)` öffnen.

### 27. Die Vorschläge im Abendmodus werden nicht angesagt
- **Ort:** `templates/partials/modals.html:4` (`#evening-results`), gefüllt in `static/js/app.js:121-123`
- **Regel:** A11Y-05.
- **Problem:** Nach „Suggest films“ erscheint die Liste unter dem Knopf. Ein Screenreader sagt nichts an.
- **Kleinste Lösung:** `aria-live="polite"` an `#evening-results`.

### 28. Sehr kleine Schrift bei den Abzeichen
- **Ort:** `static/css/app.css:31` (`.free-tag` .62rem ≈ 10 px), `:68` (`.offer-badge` .66rem), `:169` (`.provider-badge` mobil .62rem)
- **Regel:** A11Y-04 / RD-02 (eigene Wertung: unter etwa 12 px wird es knapp lesbar).
- **Problem:** „Free“, „With ads“ und „Rent“ sind die wichtigste Information auf der Karte, aber am kleinsten gedruckt.
- **Kleinste Lösung:** Auf mindestens `.75rem` anheben.

### 29. Fehlendes Leerzeichen „Database:“ auf der Statusseite
- **Ort:** `templates/status.html:27` (`Database:<strong>`)
- **Regel:** Allgemeine Sorgfalt. Alle anderen Kacheln haben das Leerzeichen.
- **Problem:** Angezeigt wird „Database:1.2 MB“.
- **Kleinste Lösung:** Leerzeichen nach dem Doppelpunkt.

### 30. Das Poster auf der Seite „Matches“ wiederholt den Titel als `alt`
- **Ort:** `static/js/matches.js:39`
- **Regel:** A11Y-02. Dekorative Bilder bekommen `alt=""`.
- **Problem:** Vorgelesen wird „Alien, Bild. Alien (1979)“. Der Titel steht direkt daneben noch einmal als Text.
- **Kleinste Lösung:** `alt: ''`.

### 31. Die Abo-Checkboxen in den Einstellungen sind nicht gruppiert
- **Ort:** `templates/settings.html:41-49`
- **Regel:** A11Y-01 (semantisches HTML für Formulargruppen).
- **Problem:** Beim Springen in die Liste hört man nur „Netflix, Kontrollkästchen“, nicht, zu welcher Gruppe es gehört („Services“, „Amazon Channels“ …).
- **Kleinste Lösung:** In jedem `<details>` die `.settings-providers` mit `role="group" aria-label="{{ group }}"` versehen, bei Untergruppen mit `{{ subgroup }}`.

---

## Was ich nicht geprüft habe
- Kein Test mit echtem Screenreader, Gerät oder Browser. Kontraste habe ich gerechnet, nicht gemessen.
- Sicherheit (XSS) nur am Rand angeschaut: Das HTML in `rendering.js`/`app.js` setzt Daten durchgehend über `escapeHtml` ein. Mir ist dabei nichts aufgefallen, ich habe es aber nicht vollständig durchgeprüft.
- Den Desktop-Layout-Modus auf dem Handy (`app.css:183`, `min-width: 1050px`) habe ich als bewusste Entscheidung gewertet und nicht als Fehler gezählt.
- Die UI-Texte sind englisch, `lang="en"` passt (I18N-01). i18n habe ich nicht weiter bewertet.
