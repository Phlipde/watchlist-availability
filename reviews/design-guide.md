# Gestaltungs-Empfehlungen (design-guide)

Stand: 2026-11-15, Arbeitskopie mit uncommitteten Änderungen. Geprüft im Browser mit einer Kopie der echten Daten (Schriftgrößen und Kontraste gemessen) und durch Lesen von `static/css/app.css`.

**Abgrenzung:** Hier geht es um Farbe, Schrift und einheitliche Bausteine. Bedienung steht in [design-critique.md](design-critique.md) (DC), Barrierefreiheit in [web-design-guidelines.md](web-design-guidelines.md) (WDG), Verhalten in [interaction-design.md](interaction-design.md) (ID).

**Ausgangslage:** Die App nutzt Tabler mit einem eigenen dunklen Thema: grün getönte Grautöne und ein Bernstein-Akzent (`#e8b86b`). Das bleibt so. Es gibt keine gespeicherten Vorlieben zu diesem Projekt (`LEARNINGS.md` fehlt beim Skill).

---

## Was schon passt

- **Kontrast:** Alle gemessenen Texte liegen über 4,5:1 (Fließtext 16,5:1, graue Hinweise 6,6–7,4:1, Abzeichen 7–9:1, nicht verfügbare Titel 5,5:1 ohne die Deckkraft aus WDG #15).
- **Grautöne passen zur Akzentfarbe:** Sie sind leicht grün getönt statt neutral grau. Das wirkt ruhig und einheitlich.
- **Kein Zustand nur über Farbe:** Jedes Abzeichen trägt auch Text („Free“, „With ads“, „complete“).
- **Hell und dunkel:** Die App ist bewusst nur dunkel (`color-scheme: dark`). Mit hellem System bleibt sie dunkel und sieht gleich aus; geprüft auf Hauptseite und Status-Seite.
- **Überschrift und Zeile darüber:** „WATCHLIST AVAILABILITY · DE“ ist klein und steht klar über der großen Überschrift.

---

## Empfehlungen

### 1. Bernstein nur noch für Bedienung, nicht für Angaben
- **Ort:** `--accent` in `static/css/app.css`, u. a. `.provider-badge`, `.offer-ads` (Zeile 70), `.status-running` (221), `.match-reason` (233)
- **Problem:** Dieselbe Farbe steht für Links und Knöpfe, für den Namen des Dienstes auf der Karte, für „With ads“, für „läuft gerade“ und für „Zuordnung prüfen“. Auf einer Karte stehen „YouTube Free“ (Dienst) und „With ads“ (Angebotsart) als zwei gleich aussehende Bernstein-Pillen untereinander.
- **Empfehlung:** Bernstein bleibt für alles, was man anklicken kann (Links, Knöpfe, Häkchen, Fokus). Der Dienstname auf der Karte wird neutral: Hintergrund `#252d29`, Text `#d9d3c7`. „With ads“ behält Bernstein, weil es zwischen „Free“ (grün) und bezahlt liegt.
- **Warum:** Eine Farbe mit einer Bedeutung liest sich schneller als eine Farbe mit fünf.

### 2. Zustände als weiche Pille, überall gleich
- **Ort:** `.status-complete`, `.status-error`, `.status-running` (Zeilen 219–221, nur Textfarbe), `.offer-badge` (68–72), `.free-tag` (31), `.match-reason` (233–234, Rahmen statt Fläche)
- **Problem:** Vier Bausteine für dieselbe Sache: farbiger Text (Status-Seite), gefüllte Pille (Angebotsart), kleinere gefüllte Pille („Free“ am Dienst), Pille mit Rahmen (Matches).
- **Empfehlung:** Eine Klasse `.pill` mit vier Tönen, jeweils blasse Fläche und heller Text:

  | Ton | Fläche | Text | Verwendung |
  |---|---|---|---|
  | ok | `rgba(76,175,80,.18)` | `#b9e6c2` | Free, complete |
  | warn | `rgba(232,184,107,.16)` | `#f3d18b` | With ads, running, Zuordnung prüfen |
  | danger | `rgba(168,92,77,.25)` | `#ffb4a6` | error, interrupted, not found |
  | neutral | `rgba(150,160,153,.18)` | `#c9d2cb` | cancelled, Zähler |

  „Subscription“ (blau) und „Rent“ (violett) bleiben als eigene Töne der Angebotsart. Die Farben stehen alle schon im CSS, es kommen keine neuen dazu.
- **Warum:** Einheitliche Pillen bleiben in dichten Tabellen lesbar, und ein Zustand sieht auf jeder Seite gleich aus.

### 3. Schrift: vier Größen statt zwölf, nichts unter 12 px
- **Ort:** `static/css/app.css`, gemessen im Browser
- **Problem:** Die Größen reichen von 9,9 px bis 16,8 px in vielen Zwischenstufen: „Free“ am Dienst 9,9 px, Angebotsart 10,6 px, Zähler 11,2 px, Dienst auf der Karte 11,5 px, Knöpfe und Hinweise 12,5 px, Filter 13,1 px, Fließtext 14 px. Die wichtigste Angabe der Karte („Free“, „With ads“) ist am kleinsten.
- **Empfehlung:** Vier Stufen als Variablen:

  | Stufe | Größe | Verwendung |
  |---|---|---|
  | `--text-xs` | `.75rem` (12 px) | Pillen, Zähler |
  | `--text-sm` | `.875rem` (14 px) | Knöpfe, Filter, Tabellen, Angaben auf der Karte |
  | `--text-md` | `1rem` (16 px) | Erklärtexte (Einleitung, Hilfetext der Seitenleiste, Absätze auf Costs und Matches), Filmtitel |
  | Überschriften | wie heute | `h1`, `h2` |

  Ersetzt WDG #28 (dort nur „mindestens .75rem“ für die Abzeichen).
- **Warum:** Wenige feste Stufen wirken geordnet; 12 px ist die Untergrenze für bequemes Lesen.
- Nebenbei: `font-family: Georgia, serif` in Zeile 1 hat keine Wirkung, Tabler setzt überall `system-ui`. Die Angabe kann weg.

### 4. Zeitpunkte ohne Sekunden
- **Ort:** `static/js/app.js:270` und `:324` („Last updated“), `static/js/rendering.js:50`, `templates/status.html:66`
- **Problem:** „Last updated 15/11/2026, 23:10:54“. Die Sekunden sagen nichts und machen die Zeile länger; auf dem Handy bricht sie um.
- **Empfehlung:** Eine Hilfsfunktion in `static/js/ui.js`: `toLocaleString([], {dateStyle: 'medium', timeStyle: 'short'})`, ergibt „15 Nov 2026, 23:10“. An allen vier Stellen nutzen. Die Erinnerungen auf der Kosten-Seite bleiben reine Datumsangaben.
- **Warum:** Genauigkeit ohne Bedeutung ist Rauschen.

### 5. Farben als benannte Variablen
- **Ort:** `static/css/app.css`, 51 verschiedene Farbwerte bei 6 Variablen
- **Problem:** Fast gleiche Werte stehen mehrfach im CSS: drei Grüntöne für „gut“ (`#8fe0ad`, `#8fd19e`, `#b9e6c2`), vier dunkle Flächen (`#151a18`, `#18201c`, `#17140f`, `#1b211f`), vier graue Linien (`#3b403d`, `#435047`, `#4a554e`, `#59655d`).
- **Empfehlung:** Die vorhandenen sechs Variablen um diese ergänzen und die Einzelwerte ersetzen:

  | Variable | Wert | ersetzt |
  |---|---|---|
  | `--panel-2` | `#18201c` | `#151a18`, `#17140f` |
  | `--line-strong` | `#59655d` | `#435047`, `#4a554e` |
  | `--ok` | `#b9e6c2` | `#8fe0ad`, `#8fd19e` |
  | `--danger` | `#ffb4a6` | `#ffd7ce` |
  | `--accent-hover` | `#f4cf91` | (fünfmal einzeln) |

- **Warum:** Danach ist ein helles Design (Etappe 14) eine zweite Liste von Werten statt eine Suche durch 250 Zeilen. Ohne diesen Schritt würde ich das helle Design nicht anfangen.
- Kleinere Variante: nur zusammen mit Empfehlung 2 die Töne der Pillen als Variablen anlegen, den Rest lassen.

### 6. Ein Knopf-Stil auf der Karte
- **Ort:** `.film-details-button` (Zeile 52), `.film-link` (54), `.btn` (39)
- **Problem:** „Details“ ist ein eigener, von Hand gebauter Knopf neben den Tabler-Knöpfen: andere Höhe (30 px statt 36 px), eigener Rahmen, eigene Hover-Farbe.
- **Empfehlung:** „Details“ wird `btn btn-sm btn-outline-secondary`, die eigene Klasse entfällt. `.film-link` bleibt (Textlinks „TMDB · Trailer“).
- **Warum:** Ein Baustein weniger, und Fokus, Hover und Mindestgröße kommen vom gemeinsamen Stil.

---

## Bewusst nicht empfohlen

- **Rückfrage vor dem Entfernen eines Favoriten:** Ein Stern ist ein Schalter. „Undo“ im Toast (DC #11, Etappe 9i) reicht und stört weniger als ein Dialog.
- **Eigener Dialog statt `window.confirm` beim Wiederherstellen der Sicherung:** Die Rückfrage des Browsers nennt die Datei und die Folge, ist zugänglich und kommt einmal im Jahr vor.
- **Neue Farben oder eine andere Akzentfarbe:** Die Palette trägt. Es fehlen Regeln, keine Farben.

## Nicht geprüft

- Die Empfehlungen 1–3 sind nicht als Vorschau gebaut; wie die neutrale Dienst-Pille und die größere Schrift auf der Karte wirken, zeigt erst ein Bildschirmfoto vorher/nachher.
- Die Kontraste der Tabler-Knöpfe (Farben in `oklch`) konnte mein Skript nicht berechnen.
