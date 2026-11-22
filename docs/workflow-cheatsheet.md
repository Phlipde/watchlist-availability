# Workflow-Spickzettel: gute Ergebnisse mit wenig Tokens

Für dieses Projekt (Flask, SQLite und reines JavaScript, Plan in `PLAN.md`). Stand: 16.11.2026.

## Die Grundregel

**Ein Werkzeug pro Schritt.** Jede geladene Skill und jeder Hook kostet bei jeder Nachricht Kontext. Kurze, genaue Aufträge sind am billigsten. Ein großer Schwarm von Agenten ist am teuersten.

## Der normale Ablauf einer Etappe

| Schritt | Befehl | Wann |
|---|---|---|
| 1. Klären | `/grill-me` (Plan) oder `/grill-with-docs` (Code und Begriffe) | Nur bei unklaren oder großen Etappen. Bei kleinen Aufträgen weglassen. |
| 2. Planen | `PLAN.md` direkt pflegen | Immer. Ein Plan reicht, keine Tickets oder Specs nötig. |
| 3. Bauen | normaler Auftrag mit ponytail lite (ist immer an) | Immer |
| 4. Testen | die Befehle aus `CLAUDE.md` (pytest, node --test, ruff, mypy) | Nach jeder Änderung |
| 5. Prüfen | `/code-review` (eingebaut) oder `/ponytail-review` | Vor dem Commit bei größeren Änderungen |
| 6. Merken | `/project-starter:save-session-learnings` | Am Ende einer langen Sitzung |
| 7. Commit | „comitte“ | Nur auf Zuruf. Gepusht wird nie. |

## Welches Werkzeug wofür

| Situation | Nimm | Nicht |
|---|---|---|
| Wo steht etwas im Code? | `graphify query "…"` oder `graphify explain "Name"` | lange Grep-Runden |
| Genauer Text oder Name bekannt | normales Grep | graphify (kostet etwa 2.000 Tokens pro Abfrage) |
| Neuer Code | normaler Auftrag mit ponytail lite | Ruflo-Schwarm |
| Schwerer Fehler | `/diagnosing-bugs` | raten und flicken |
| Logik mit klaren Ein- und Ausgaben (zum Beispiel `filtering.js`) | `/tdd` | |
| Oberfläche schöner oder klarer machen | `/impeccable polish …`, `bolder`, `quieter`, `layout` | mehrere Design-Skills nacheinander |
| UX-Bewertung | `/impeccable critique <ein Bereich>` | design-critique **und** impeccable doppelt |
| Technische UI-Prüfung (Barrierefreiheit, mobil) | `/impeccable audit <Bereich>` | |
| Code aufräumen | `/simplify`, `/ponytail-debt` | |
| Architektur, alle paar Wochen | `/improve-codebase-architecture` | |
| Übergabe an eine neue Sitzung | `/handoff` (Matt Pocock) | lange Sitzungen ohne Ende |
| Etwas lernen (Python, CSS …) | „teach me …“ startet socratic-tutor | |
| Unklare Antwort von Claude | `/wait-what` | |

**Tipp:** Kleine Ziele liefern bessere Ergebnisse, zum Beispiel `/impeccable critique die Filterleiste` statt „die ganze Seite“.

## Ruflo: sparsam einsetzen

- `CLAUDE.md` sagt „ab 3 Dateien einen Schwarm“. **Das ist der teuerste Weg.** Jeder Agent liest das Projekt neu ein.
- In diesem kleinen Projekt reicht fast immer eine einzige Sitzung.
- Ruflo lohnt sich nur für wirklich getrennte, große Arbeiten, die parallel laufen können.
- Die Ruflo-Hooks (Routing, Gedächtnis) laufen trotzdem bei jeder Nachricht mit. Den Daemon nicht starten: Er verbraucht dauerhaft Tokens.

## Ponytail

- Ist immer an, auf Stufe `lite`: Claude baut, was du willst, und nennt die kleinere Variante.
- `/ponytail full`: noch weniger Code. `/ponytail ultra`: Claude hinterfragt auch den Auftrag.
- `/ponytail-audit` prüft einmalig das ganze Repo. Das ist teuer, also selten nutzen.

## Einmal nach dem Neustart der App

1. Claude Code neu laden, damit die neuen Skills und Hooks gelten.
2. `/impeccable init` stellt Fragen und schreibt `PRODUCT.md`.
   Danach kann `/impeccable document` die Gestaltung in `DESIGN.md` festhalten. Das ist optional.
3. `/setup-matt-pocock-skills` fragt nach dem Issue-Tracker. Antwort: lokale Dateien.
4. Den Graph aktuell halten: `graphify update .` nach größeren Änderungen. Das kostet keine Tokens.

## Größte Token-Ersparnis: Unnötiges abschalten

In jeder Sitzung sind Hunderte fremde Skills geladen (Social Media, Banking, Legal, Equity Research, YouTube und andere). Ihre Beschreibungen kosten bei **jeder** Nachricht Kontext.

- Plugins, die du hier nicht brauchst, in den Plugin-Einstellungen der App für dieses Projekt abschalten.
- Das spart mehr als jedes einzelne neue Werkzeug.

## Nicht tun

- Nicht mehrere Review-Skills auf dieselbe Änderung ansetzen.
- Nicht `/graphify .` ohne Grund ausführen. Der Durchgang über Texte und Bilder nutzt das Sprachmodell. `graphify update .` reicht für Code.
- Impeccable `live` nur mit `IMPECCABLE_LIVE_COPY_AGENT=chat` starten. Sonst kann es `claude` ohne Rechteabfrage starten.
- Nicht „mach alles“ sagen. Lieber eine Etappe pro Auftrag.

## Was wo installiert ist

| Werkzeug | Ort | Wirkung |
|---|---|---|
| graphify 0.9.111 | `pip --user`, Skill in `.claude/skills/graphify` | Hooks erinnern vor Read, Grep und Bash an den Graph. Abschnitt in `CLAUDE.md`. Graph liegt in `graphify-out/` (nicht in Git). |
| impeccable | `.claude/skills/impeccable`, `.claude/agents/impeccable-*` | Hooks in `.claude/settings.local.json`: Design-Prüfung nach dem Bearbeiten von UI-Dateien und am Ende jeder Antwort. Telemetrie ist aus. |
| Matt Pocock Skills (26) | `.claude/skills/*`, `skills-lock.json` | Aktualisieren mit `npx skills@latest update`. Die Skill `code-review` wurde weggelassen, weil sie mit der eingebauten kollidiert. |
| socratic-tutor (Jane Street) | `~/.claude/skills/` (gilt für alle Projekte) | Startet nur bei „teach me / quiz me“ |
| ruflo | `.claude/helpers`, `.claude-flow`, Hooks in `.claude/settings.json` | Routing und Gedächtnis bei jeder Nachricht |
| ponytail | Plugin | Stufe lite |
| caveman (juliusbrussee) | `.claude/skills/caveman`, `skills-lock.json` | `/caveman`: sehr knappe Antworten. Nicht zusammen mit ponytail lite nutzen, beide regeln die Antwortlänge; „stop caveman“ beendet es. |
| find-skills (Vercel) | `.claude/skills/find-skills` | Sucht passende Skills auf skills.sh (`npx skills find`). Doppelt mit dem Plugin `zizi-skills:find-skills`. |
| agent-browser (Vercel) | `.claude/skills/agent-browser` | Braucht die CLI (`npm i -g agent-browser && agent-browser install`, lädt Chrome). Für diese App reicht meist der eingebaute Browser und Playwright in den Tests. |
| antislop + antislop-ui (miqdadbadjuber) | `.claude/skills/antislop*` | Regeln gegen den generischen KI-Look. Überschneidet sich mit impeccable; bei Widerspruch gilt impeccable mit PRODUCT.md. |
| UI UX Pro Max 2.15.0 (nextlevelbuilder) | `.claude/skills/ui-ux-pro-max`, dazu `design`, `design-system`, `ui-styling`, `brand`, `banner-design`, `slides` | Installiert mit `npx -y -p ui-ux-pro-max-cli uipro init --ai claude` (nicht global, nicht in `skills-lock.json`); aktualisieren mit `… uipro update`. Suche lokal ohne Netz: `python .claude/skills/ui-ux-pro-max/scripts/search.py "<frage>" --design-system`. Seine Vorschläge sind allgemein (für diese App: Landing-Page-Muster, Inter, rote Akzentfarbe); PRODUCT.md und impeccable haben Vorrang. Logo- und Icon-Skripte in `design` lesen `.env` und brauchen einen Gemini-Schlüssel. |
| ui-detail-pass (eigene) | `~/.claude/skills/ui-detail-pass` (gilt für alle Projekte) | Feinschliff für Typografie und Barrierefreiheit: jede Technik erst live messen, dann übernehmen. Enthält die Fallen aus dieser App (Fett-Breite mit `data-text`, text-box-trim wirkungslos bei `inline-flex`, Bootstrap-Dialog beim Einblenden). |
| Grill Me, Web Design Guidelines | `.claude/skills/grill-me` (Matt Pocock), Plugin `project-starter:web-design-guidelines` | Schon vorher installiert. |
