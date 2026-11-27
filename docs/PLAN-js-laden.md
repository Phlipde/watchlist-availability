# Plan: Skripte und Styles schneller laden (Punkt 17 der Prüfung vom 27.11.2026)

Stand 27.11.2026: Schritte 0 bis 2 gebaut, dazu ein Fund beim Messen (Tonight-Seite langsam auf dem Server). Schritt 3 gibt es schon, Schritt 4 ist nicht nötig.

## Ergebnis (27.11.2026)

Gemessen mit Playwright (Chromium, Service Worker aus) gegen eine Kopie der Daten, Mittelwert aus mehreren Läufen.

| | vorher | nachher |
|---|---|---|
| JS beim kalten Laden | 42 Dateien, 504 KB | 42 Dateien, 177 KB (gzip) |
| CSS beim kalten Laden | 8 Dateien, 1001 KB | 8 Dateien, 156 KB (gzip) |
| CSS beim warmen Laden | 8 Anfragen (304) | aus dem Cache, keine Anfrage |
| Alles beim kalten Laden | 2605 KB | 1433 KB |
| Watchlist: Karten sichtbar, kalt / warm | ~2,1 s / ~2,0 s | ~1,6 s / ~1,3 s |
| Tonight: HTML vom Server | ~1,4 s | ~0,2 s |

- **Schritt 1:** `compress()` packt jetzt auch JS und CSS aus `/static/`, einmal je Dateiversion, im Speicher gehalten.
- **Schritt 2:** Jedes `url_for('static', ...)` bekommt `?v=<Hash des Inhalts>` (`static_version`). Solche Adressen werden ein Jahr gecacht (`immutable`). Die eigenen JS-Module bekommen bewusst **kein** `?v=`: Sie importieren einander ohne, und `index.html` lädt sie per `modulepreload` vor. Eine zweite Adresse hätte jedes Modul doppelt geladen; das zeigte die erste Messung nach dem Umbau (78 statt 42 Dateien). Die von Hand geschriebenen `v=` in den Vorlagen sind entfernt.
- **Schritt 3 gibt es schon:** `index.html` schreibt `modulepreload` für alle Module.
- **Fund:** Die Tonight-Seite rechnete für den Spar-Tipp `costs.overview()` mit 190 000 Aufrufen von `service_group()`, die jedes Mal Regex auswerteten. `service_group` und `catalog_name` merken sich jetzt ihre Ergebnisse (`functools.cache`).
- **Abo-Seite:** `_other_countries` liest die Angebote aller Länder; die Antwort wird jetzt je Scan, Angebotsstand (`offers_version`), Diensten und Land gemerkt, wie bei `/api/abroad`. `/subscriptions` braucht damit rund 0,3 s statt 1 bis 1,5 s; nur der erste Aufruf nach einem Scan oder Neustart rechnet noch einmal (rund 1,5 s).

Die Planung von vorher folgt unverändert.

## 1. Ausgangslage (gemessen am 27.11.2026)

- **Einstiegsskripte:** Jede Seite lädt ein Einstiegsskript als ES-Modul: `app.js` auf Tonight und der Watchlist, `header.js` plus ein Seitenskript auf den übrigen Seiten. Es gibt 59 Dateien in `static/js/`, etwa 500 KB eigener Code ohne Kompression. Dazu kommen `tabler.min.js` (135 KB) und `bootstrap.bundle.min.js` (81 KB).
- **Ladekette:** Die Module laden einander nacheinander. Der Browser findet die Imports erst, wenn die vorherige Datei da ist; daraus entsteht eine Kette von 4 bis 5 Stufen.
- **Kompression:** JS und CSS kommen unkomprimiert. `compress()` in `web/routes.py` packt nur JSON und HTML.
- **Caching:** JS und CSS kommen mit `Cache-Control: no-cache`. Jede Datei wird bei jedem Laden neu angefragt, meist mit 304 als Antwort.
- **Service Worker:** `static/sw.js` holt Skripte und Styles network-first, also bei jedem Seitenaufruf übers Netz, nur offline aus dem Cache.
- **Netz:** Über Cloudflare kommen HTTP/2 und Kompression durch Cloudflare dazu. Im Heimnetz direkt auf Port 5000 ist es HTTP/1.1 mit höchstens etwa 6 Verbindungen gleichzeitig.
- **Antwortzeit:** Der Server antwortet schnell, etwa 0,4 s für `/api/latest` mit 900 KB JSON. Langsam ist, wenn überhaupt, die Ladekette der Module.
- **Offen:** Die Ladezeit im Browser (kalt und warm) ist noch nicht gemessen; das ist Schritt 0.

## 2. Schritte

### Schritt 0: Messen [einfach]

- **Was:** Die Seiten Tonight und Watchlist laden, jeweils kalt (Cache leer, ohne Service Worker) und warm.
- **Wie:** In den Entwickler-Werkzeugen des Browsers, Reiter Netzwerk und Leistung, einmal im Heimnetz (Port 5000) und einmal über Cloudflare. Notieren: Zahl der Anfragen, übertragene KB, Zeit bis zu den ersten Karten (LCP).
- **Ergebnis:** eine kleine Tabelle in diesem Plan.
- **Abbruch:** Liegt warm alles unter etwa 1 s, nur Schritt 1 machen und dann aufhören.

### Schritt 1: Kompression für JS und CSS [einfach]

- **Wo:** `compress()` in `web/routes.py`.
- **Was:** Auch `text/javascript` und `text/css` packen. Statische Dateien kommen als `direct_passthrough` und werden heute übersprungen.
- **Variante:** Beim Start jede Datei einmal packen und im Speicher halten, statt bei jeder Anfrage. Es sind nur rund 60 Dateien.
- **Test:** Eine Route-Prüfung, dass `/static/js/app.js` mit `Content-Encoding: gzip` kommt und sich wieder entpacken lässt.
- **Erwartung:** etwa 70 % weniger Daten im Heimnetz. Über Cloudflare ändert sich wenig, das packt dort schon.

### Schritt 2: Lange cachen, was eine Version in der Adresse hat [einfach]

- **Was:** Adressen mit `?v=` bekommen `Cache-Control: public, max-age=31536000, immutable`. Der Browser fragt dann gar nicht mehr nach.
- **Problem:** Module importieren einander **ohne** `?v=` (siehe CLAUDE.md, PWA). Diese Dateien dürfen nicht lange gecacht werden, sonst sieht man nach einem Update alten Code.
- **Darum:** Nur die Einstiegsskripte und die CSS-Dateien, deren `v=` in den Templates steht, bekommen den langen Cache. Die übrigen Module bleiben `no-cache`, dafür sorgt Schritt 3.

### Schritt 3: `modulepreload` statt Ladekette [mittel]

- **Was:** Beim Start liest der Server einmal alle `import … from './x.js'` aus `static/js/` und bildet je Einstiegsskript die Liste aller Module, die es braucht. Das ist ein Regex über rund 60 Dateien, kein Build-Schritt.
- **Ausgabe:** Ein Partial schreibt für jedes Modul `<link rel="modulepreload" href="…?v=<Hash>">` in den `<head>`. Der Browser lädt dann alle Module gleichzeitig statt nacheinander.
- **Hash:** Der Hash kommt aus dem Dateiinhalt. Ein vergessenes `v=` gibt es dann nicht mehr: Die Vorlagen bekommen die Adresse samt Hash aus einer Hilfsfunktion.
- **Achtung:**
  - Der Browser lädt ein vorgeladenes Modul nur dann aus diesem Vorrat, wenn die Adresse genau gleich ist.
  - Die Imports in den Modulen selbst haben kein `?v=`. Darum nur das Einstiegsskript mit `?v=` laden und die Preloads ohne `?v=` schreiben, oder Schritt 2 auf die Einstiegsskripte begrenzen.
  - Das im Browser ausprobieren, bevor es gebaut wird.
- **Test:** Eine reine Funktion `module_graph(js_dir)` mit einem kleinen Beispielordner. Eine Route-Prüfung, dass die Watchlist für jedes Modul von `app.js` ein Preload hat.
- **Nutzen:** Die Kette von 4 bis 5 Stufen wird zu einer. Das hilft vor allem im Heimnetz mit HTTP/1.1.

### Schritt 4 (nur wenn 1 bis 3 nicht reichen): Bündeln mit esbuild [schwer]

- **Was:** Pro Seite eine gebündelte und verkleinerte Datei (`static/dist/app.<hash>.js` und so weiter), dazu eine CSS-Datei aus den sechs `app*.css` in derselben Reihenfolge.
- **Wo gebaut wird:** Im Dockerfile, in einer zusätzlichen Node-Stufe (Multi-Stage-Build). Ins Laufzeit-Image kommt nur `static/dist/`. Der Unraid-Server baut aus dem Git-Klon, braucht also kein Node auf dem Host.
- **Lokal:** Ohne `static/dist/manifest.json` liefern die Vorlagen weiter die einzelnen Module aus. Entwicklung, `node --test` und die Browser-Tests bleiben wie heute.
- **CI:** Ein zusätzlicher Job baut das Bündel und lässt die Browser-Tests einmal gegen das Bündel laufen.
- **Service Worker:** Gehashte Dateien können cache-first laufen. Die network-first-Regel für Skripte gilt nur noch ohne Bündel.
- **Neue Abhängigkeit:** `esbuild` als Dev-Abhängigkeit (`package.json` gibt es noch nicht). Das ist der erste Build-Schritt im Projekt.
- **Risiken:**
  - Fehler, die nur im Bündel auftreten, etwa Import-Reihenfolge oder Top-Level-Code.
  - Source Maps sind nötig für lesbare Fehlermeldungen.
  - Ein Build-Schritt mehr bei jeder Änderung.
- **Aufwand:** Ein bis zwei Etappen, plus Doku in CLAUDE.md. Die Regel „`v=` hochzählen“ entfällt dann.

### Nicht vorgesehen

- **`tabler.min.js` und `bootstrap.bundle.min.js` ersetzen:** Das sind zusammen 216 KB. Prüfen, ob `tabler.min.js` überhaupt gebraucht wird. CLAUDE.md erwähnt, dass es ein zweites Bootstrap mitbringt. Das wäre eine eigene, kleine Untersuchung, kein Teil dieses Plans.
- **CSS zusammenlegen ohne Bündler:** Sechs Dateien sind mit Schritt 1 und 2 unkritisch.

## 3. Empfehlung

Erst Schritt 0 bis 2, weil sie wenig Code brauchen und keine neue Abhängigkeit. Dann wieder messen.

Schritt 3 nur, wenn die Ladekette im Heimnetz noch spürbar ist. Schritt 4 nur, wenn auch das nicht reicht.

## 4. Fragen

1. Nach Schritt 0: Ist die Ladezeit überhaupt ein Problem, das du merkst, vor allem auf dem Handy?
2. Darf das Projekt einen Node-Build-Schritt bekommen (nur für Schritt 4)?
