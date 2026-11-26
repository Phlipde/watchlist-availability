# Plan: Mehrere Profile und „Together“-Modus

Stand: 26.11.2026. Grundlage: `docs/PLAN-fehler-und-features.md`, Abschnitt B4. Entwurf von einem Opus-Agenten nach Lesen des Codes.

Ziel: Mehrere Profile. Jedes Profil hat einen eigenen Letterboxd-Namen, eigene Dienste und Kosten, eigene Favoriten, eigene Hidden- und Not-now-Markierungen und eigene Benachrichtigungen. Dazu kommt ein „Together“-Modus für zwei oder mehr Personen. Es gibt keinen Login; den Zugriff regelt Cloudflare Access oder das lokale Netz. Cloudflare Access darf das Startprofil vorschlagen, ist aber nie Pflicht.

Status: [ ] offen, [x] erledigt, [~] teilweise.

---

## 1. Voraussetzungen

### 1.1 Wem gehören die Daten?

| Tabelle | Heute | Neu | Wie |
|---|---|---|---|
| `film_ids`, `films`, `offers`, `provider_catalog` | geteilt | **bleibt geteilt** | keine Änderung |
| manuelle Matches (`film_ids.source='manual'`) | geteilt | **bleibt geteilt** | Ein Film ist für alle derselbe |
| `settings`: `tmdb_regions`, `matches_changed_at`, `scan_interval_hours` | global | **bleibt global** | keine Änderung |
| `settings`: `letterboxd_username`, `country`, `weekly_hours`, `notify_kind`, `notify_url`, `notify_token`, `notify_events`, `notify_state`, `subscriptions:*`, `subscription_costs:*` | global | **je Profil** | neue Tabelle `profile_settings (profile_id, key, value)` |
| `favorites` | PK `movie_key` | **je Profil** | Tabelle neu bauen, PK `(profile_id, movie_key)` |
| `flags` | PK `movie_key` | **je Profil** | Tabelle neu bauen, PK `(profile_id, movie_key)` |
| `service_history` | PK `(country, day, service)` | **je Profil** | Tabelle neu bauen, PK `(profile_id, country, day, service)` |
| `scans` | ohne Besitzer | **je Profil** | `ALTER TABLE ADD COLUMN profile_id INTEGER NOT NULL DEFAULT 1` |
| `changes` | ohne Besitzer | **je Profil** | `ADD COLUMN profile_id`. Der Vergleich in `history.diff_scans` läuft je Watchlist. |
| `jobs` | ohne Besitzer | **je Profil** | `ADD COLUMN profile_id` |
| neu: `profiles` | – | `id, name UNIQUE, email, created` | `email` nur für den CF-Header |
| neu: `watched` | – | `(profile_id, film_key)` PK | Cache der gesehenen Filme von Letterboxd. Kommt **nicht** ins Backup, weil man ihn neu laden kann. |

### 1.2 Migration ohne Datenverlust

- Vor jeder Migration kopiert die App die DB-Datei, z. B. `watchlist.db.pre-v2`. Nur diese Kopie garantiert wirklich, dass nichts verloren geht. Ein Downgrade geht nicht: `StoreBase` wirft bei `user_version > SCHEMA_VERSION` einen Fehler.
- **Falle in `store_base.py`:** `executescript(_SCHEMA)` läuft *vor* den Migrationen. Ein neuer Index auf `profile_id` in `_SCHEMA` bricht auf alten DBs ab, weil die Spalte dort noch fehlt. Neue Indizes gehören deshalb nur in die Migration. Oder `_SCHEMA` läuft nur bei einer leeren DB.
- `executescript` macht vorher selbst ein COMMIT. Jede Migration steht deshalb in einem eigenen `BEGIN; … COMMIT;`.
- Tabellen neu bauen: `CREATE TABLE x_new … ; INSERT INTO x_new (profile_id, <spalten>) SELECT 1, <spalten> FROM x; DROP TABLE x; ALTER TABLE x_new RENAME TO x;`
- Profil 1 bekommt als Namen den bisherigen `letterboxd_username`, sonst „Me“ (`COALESCE(NULLIF(...), 'Me')`).
- Alle neuen Spalten haben `DEFAULT 1`. Der alte Code mit `INSERT INTO scans (created, country, …)` und `INSERT OR REPLACE INTO favorites (movie_key, …)` läuft dadurch nach der Migration unverändert weiter.

### 1.3 Backup-Format

- `BACKUP_VERSION = 2` (in `watchlist_app/store.py`). Aufbau:
  `{"version": 2, "exported_at", "settings": {global}, "matches": [...], "profiles": [{"name", "email", "settings", "favorites", "flags", "changes", "scans"}]}`
- `export_backup` (`store_backup.py`) holt den letzten Scan je **(Profil, Land)**. Heute steht dort `GROUP BY country`.
- `import_backup` nimmt v1 **und** v2 an:
  - v1 geht in ein Zielprofil, Standard ist das aktive Profil. `AppSettings.restore` schreibt dann in dieses Profil.
  - v2 ordnet die Profile über den Namen zu. Fehlende Profile legt der Import an.
- Doppelte Einträge: Changes über `CHANGE_IDENTITY` plus `profile_id`, Scans über `(created, country, profile_id)`.
- `validation.py` bekommt `clean_profile` (Name ≤ 60 Zeichen, E-Mail optional).
- Der Filter `INTERNAL_SETTINGS` muss weiter `notify_token` und `notify_state` treffen, auch wenn sie in `profile_settings` liegen.

### 1.4 Scans und Cache

- **Doppelte TMDB-Anfragen sind schon fast gelöst.** `lookup.lookup_film` liest aus den geteilten Tabellen `film_ids`, `films` und `offers` (TTL 24 h). Es braucht **keinen** neuen Cache; Scans laufen nacheinander.
- Zu reparieren ist die Buchführung der Scans:
  - `save_scan` kürzt `MAX_SCANS` je Land, künftig je (Profil, Land).
  - `latest_scan(country)` filtert nicht nach Besitzer. Aufrufer: `api_scan.latest_result`, `pages.py` (4×), `feeds.py` (3×), `common.status_overview`.
  - `latest_scan_created` (Header, `scheduler.next_scan_at`) braucht `profile_id`.
  - `recent_scans` und `find_scan` brauchen `profile_id` (zwei Profile mit derselben CSV dürfen sich nicht vermischen).
  - `recent_changes`, `add_changes`, `record_service_counts` und `service_history` brauchen `profile_id`.
- **CSV-Rückfall:** `scan_run.load_watchlist` nimmt `watchlist*.csv` aus dem globalen `downloads_dir`. Der Rückfall gilt nur für Profil 1; andere Profile brauchen einen Namen oder einen Upload.

### 1.5 ScanService, Scheduler und Benachrichtigungen

- Probleme in `ScanService.start` heute: Ein laufender Job mit gleichem `country` wird übernommen (Profil B bekäme den Scan von A); ein manueller Scan bricht *jeden* anderen ab; `run` liest `self._settings`.
- Lösung: Der Job trägt `profile_id` im Live-Dict und in `jobs`; Übernahme nur bei gleichem `(profile_id, country)`; Abbruch nur manueller Scans desselben Profils; `run` nutzt `AppSettings(store, profile_id)`; `recover_interrupted` mit dem Profil des Jobs.
- **Threads erben keinen Request-Kontext.** Hintergrundcode nutzt immer ein an das Profil gebundenes Objekt, kein `flask.g`, keine contextvar.
- Scheduler: `scan_interval_hours` bleibt global; `run_due_scan` geht alle Profile mit Letterboxd-Namen durch und startet das erste fällige; ein Scan zur Zeit; `RETRY_SECONDS` je Profil.
- Benachrichtigungen je Profil (eigenes Ziel, Token, `notify_state`). Ruhezeiten global. Ein tägliches Backup für die ganze DB.

### 1.6 Aktuelles Profil je Request, ohne Login

- Reihenfolge: `?profile=<id>` (nur GET), Cookie `wl_profile`, Header `Cf-Access-Authenticated-User-Email` = `profiles.email`, sonst Profil 1. Ungültige Werte fallen still auf die nächste Stufe.
- `before_request` in `web/routes.py` setzt `g.profile_id`; `common.active_settings(settings)` gibt `AppSettings(store, g.profile_id)` zurück.
- **Größte Baustelle:** Alle Routenmodule (`pages`, `api_scan`, `api_data`, `feeds`) bekommen bei `register(...)` *ein* festes `settings`-Objekt. Jede Route beginnt künftig mit `s = active_settings(settings)`.
- URLs bleiben gleich und gelten für das aktive Profil.
- Neue Endpunkte: `GET/POST /api/profiles`, `PUT/DELETE /api/profiles/<id>`, `POST /api/profiles/active` (Cookie, `SameSite=Lax`, 1 Jahr).
- Feeds (`/calendar.ics`, `/feed.xml`, `/tile`, `/api/sensors`) nehmen `?profile=<id>`, sonst Profil 1.
- Profilumschalter im Header (`templates/partials/header.html`) als Dropdown; nach dem Wechsel lädt die Seite neu. `header_context` liefert Profilliste und aktives Profil.
- `is_cross_site_write` schützt auch den Profilwechsel.

### 1.7 Service Worker und localStorage

- `static/sw.js` speichert API-Antworten und Seiten unter ihrer URL. Beim Profilwechsel schickt der Client `clear-pages`, der Worker leert den `PAGES`-Cache.
- localStorage (gespeicherte Ansichten, Tonight-Chips, `abroadOn`, `viewMode`) gilt **je Profil**, gespeichert weiter auf dem Gerät: die Schlüssel bekommen die Profil-ID (`p2:savedViews`). Teilen zwischen Profilen kommt ganz am Ende (M5.7). (Entschieden 26.11.2026, Frage 4.)

### 1.8 Tests und Fixtures

- `tests/test_store.py`, `tests/test_backups.py`: Migrationstest v1 → v2 mit echten Zeilen; Import eines alten v1-Backups; Rundlauf eines v2-Backups mit zwei Profilen.
- `tests/web/*`: Fixture mit zwei Profilen; Varianten „Profil 2 sieht die Daten von Profil 1 nicht“.
- `tests/browser/conftest.py`: falscher Letterboxd-Server mit `/<user>/films/page/N/`; zweites Profil.
- `tests/js`: neue reine Funktionen in eigenen Modulen mit node-Tests.

### 1.9 Risiken

- **Keine Privatsphäre zwischen den Profilen.** Jeder mit Zugriff kann jedes Profil öffnen und ändern. Gewollt, soll in der UI stehen.
- Den CF-Header kann man im lokalen Netz fälschen; harmlos, er wählt nur das Startprofil.
- Mehr Last auf Letterboxd (N Watchlists plus Gesehen-Seiten): nacheinander, höchstens einmal am Tag, 429-Retry behalten. Private Profile liefern nichts.
- Die Seiten `/{user}/films/` sind **nicht geprüft** (Markup, Filme pro Seite).
- „Gesehen“ geht nur für Einträge mit Slug (Letterboxd-Web), nicht für CSV-Importe.
- Die DB wird größer: `MAX_SCANS` je (Profil, Land).
- Ein v2-Backup lässt sich nicht in eine alte App-Version einspielen.
- Ein vergessener Aufruf mit Standard `profile_id = 1` liest still Profil 1; dagegen hilft M2.6.

---

## 2. Design-Entscheidungen

| # | Frage | Empfehlung | Grund |
|---|---|---|---|
| D1 | Spalte `profile_id` oder eine DB je Person | **Spalte** | Film-Cache und Backup bleiben gemeinsam; Together braucht Abfragen über Profile. |
| D2 | Profil-Einstellungen: Präfix, Spalte oder eigene Tabelle | **eigene Tabelle `profile_settings`** | Globaler Code bleibt unberührt. |
| D3 | Scan je Profil oder ein gemeinsamer Scan | **je Profil** | Wiederverwendung, Änderungen und Statistik bleiben je Person; der TMDB-Cache ist schon geteilt. |
| D4 | Together auf dem Server oder im Client | **Server** (`watchlist_app/together.py`), Anzeige mit `filtering.js` | Gesehen-Listen und Markierungen liegen auf dem Server; Logik an einer Stelle getestet. |
| D5 | Profil im Store: contextvar oder Parameter | **Parameter `profile_id`** | Scan-Threads und Scheduler erben keinen Kontext. |
| D6 | Profil per URL-Präfix oder Cookie | **Cookie, CF-Header, Profil 1, `?profile=` für GET** | Alle URLs, Lesezeichen und die PWA bleiben gültig. |
| D7 | `changes` je Profil oder geteilt | **je Profil** | Der Vergleich läuft je Watchlist. |
| D8 | Woher „gesehen“ kommt | **`/{user}/films/` laden, Slugs je Profil speichern** | Der RSS-Feed hat nur ~50 Einträge. Nur Lesen. |
| D9 | Scan-Intervall | **global**, Benachrichtigungen je Profil | Ein Zeitplan schont TMDB und Letterboxd. |
| D10 | Abgleich in Together | **über `tmdb_id`** (Rückfall `film_key`) | CSV- und Web-Quellen haben verschiedene Schlüssel. |
| D11 | Land in Together | **Land des aktiven Profils**, Partnerliste bei Bedarf dort scannen | Angebote gibt es je (`tmdb_id`, Land). |
| D12 | Service Worker | **`PAGES`-Cache beim Wechsel leeren** | Eine Zeile statt `?profile=` an jedem Fetch. |

---

## 3. Stufenplan

Legende: **[stark]** = schwieriges Design oder Migration (Opus). **[einfach]** = mechanisch (Haiku/Sonnet).
Für jede Stufe gilt: `pytest -q`, `node --test tests/js/*.mjs`, ruff und mypy grün; ein Commit je Stufe.

### M0 – Vorarbeiten ohne Änderung im Verhalten

- [x] **M0.1 Sicherungskopie vor der Migration [einfach]** — `store_base.py`: vor einer Migration (`version < SCHEMA_VERSION`, Datei-DB) `shutil.copy2` nach `<db>.pre-v<version>`. Abnahme: alte DB erzeugt die Kopie, neue DB und `:memory:` nicht. Test: `test_migration_keeps_copy`.
- [x] **M0.2 Migration v2: Profile und Besitzer-Spalten [stark]** — `store_schema.py` (`SCHEMA_VERSION = 2`, `_MIGRATIONS[2]`, `_SCHEMA` gleich ziehen, Indizes nur in der Migration), `store_base.py` (Migration in `BEGIN/COMMIT`; `_SCHEMA` nur bei leerer DB oder nach den Migrationen). Inhalt: `profiles` mit Profil 1; `favorites`, `flags`, `service_history` neu bauen; `profile_id` bei `scans`, `changes`, `jobs`; Indizes `scans(profile_id, country, created)`, `changes(profile_id, country, created)`. Store-Methoden bleiben gleich. Abnahme: Kopie der echten DB startet, gleiche Zahlen und Zeilenzahlen. Tests: v1-DB mit Zeilen in jeder Tabelle migrieren; zweiter Start ändert nichts.
- [x] **M0.3 Migration v3: `profile_settings` [stark]** — `store_schema.py` (`PROFILE_SETTING_KEYS`, Präfixe), `store_marks.py` (`get_profile_setting`, `set_profile_setting`, `profile_setting_keys`, Standard 1), `settings.py` (`AppSettings(store, defaults=None, profile_id=1)`), `notifications.py` (`STATE_KEY` über `profile_settings`). Migration verschiebt die Profilschlüssel nach `profile_settings` (Profil 1). Abnahme: Einstellungsseiten zeigen dieselben Werte, Speichern wirkt. Tests: Migration der Schlüssel, `AppSettings`-Tests grün, `restore` schreibt in `profile_settings`.
- [x] **M0.4 Store-Methoden mit `profile_id` (Standard 1): Marken [einfach]** — `store_marks.py` (Favoriten, Flags, `greyed_out_counts`, `reset_greyed_out`). Test: Favorit in Profil 2 erscheint nicht in Profil 1.
- [x] **M0.5 Store-Methoden mit `profile_id`: Scans, Changes, History, Jobs [einfach]** — `store_scans.py` (`save_scan` kürzt je (Profil, Land); `latest_scan`, `latest_scan_created`, `recent_scans`, `find_scan`, `add_changes`, `recent_changes`, `record_service_counts`, `service_history`, `create_job`, `list_jobs`). Tests: Scans von Profil 2 drängen die von Profil 1 nicht aus `MAX_SCANS`; `latest_scan` trennt die Profile.
- [x] **M0.6 Backup v2 schreiben, v1 und v2 lesen [stark]** — `store.py` (`BACKUP_VERSION = 2`), `store_backup.py`, `validation.py` (`clean_profile`), `settings.py` (`restore` je Profil), `web/feeds.py` (Import ins aktive Profil). Abnahme: echtes v1-Tagesbackup lässt sich einspielen; v2-Export in leere DB ergibt dieselben Zahlen. Tests: v1 → Profil 1; v2 mit zwei Profilen als Rundlauf; doppelter Import fügt nichts hinzu; kaputtes Profil wird übersprungen und gezählt.

### M1 – Profile anlegen und wählen

- [x] **M1.1 Profil-CRUD in Store und API [einfach]** — `store_profiles.py` (`list_profiles`, `add_profile`, `rename_profile`, `delete_profile` in einer Transaktion; letztes Profil nicht löschbar), `web/api_data.py` (`/api/profiles`). Tests: gelöschtes Profil hinterlässt keine Zeilen; Name eindeutig; letztes Profil bleibt (400).
- [x] **M1.2 Aktives Profil je Request [stark]** — `web/routes.py` (`before_request` setzt `g.profile_id`), `web/common.py` (`active_settings`, `active_profile_id`), `POST /api/profiles/active`. Tests: alle vier Stufen der Reihenfolge; ungültiges `?profile=abc` wird ignoriert. Offen: `profiles.id` ohne AUTOINCREMENT, ein gelöschtes höchstes Profil gibt seine ID an das nächste neue weiter (ein altes Cookie wählt dann dieses).
- [x] **M1.3 Routen auf das aktive Profil: Marken und Einstellungen [einfach]** — `web/api_data.py`, `web/feeds.py` (`/api/settings`, notify test), `web/pages.py` (Settings, `/subscriptions`). Tests: Varianten mit zwei Profilen.
- [x] **M1.4 Routen umstellen: Scans, Seiten, Feeds [einfach]** — `web/api_scan.py`, `web/pages.py`, `web/feeds.py` (`?profile=`), `web/common.py` (`status_overview`), `header_context`. Tests: `test_web_pages.py`, `test_feeds.py`. Bis M2: Scan-Start nur in Profil 1, sonst 409; Scheduler und Benachrichtigungen laufen für Profil 1.
- [x] **M1.5 Profilumschalter im Header [einfach]** — `templates/partials/header.html`, `static/js/header.js`, `static/js/register-sw.js`, `static/sw.js` (`clear-pages`), `v=` erhöhen. Test: Browser „wechseln, Favoriten leer, zurück, Favoriten da“; Worker-Test erweitern.
- [x] **M1.6 Seite `/settings/profiles` [einfach]** — auflisten, anlegen, umbenennen, CF-E-Mail, löschen mit Bestätigung; Hinweis „Profiles are not private“. Test: Browser mit Tastatur. Umsetzung: Umschalter als `<details class="filter-pop">` (kein Bootstrap-Dropdown); auf dem Handy nur auf Watchlist und Stats sichtbar, sonst über diese Seite. Löschen des aktiven Profils löscht das Cookie (IDs werden wiederverwendet). Offen: `/settings/data` zählt Favoriten und Änderungen noch über alle Profile (M3.2).

### M2 – Scans und Einstellungen je Profil

- [x] **M2.1 Profil im Scan-Job [stark]** — `scan_service.py`, `scan_run.perform_scan`, `web/api_scan.py`. Tests: Scan von B übernimmt nicht den Job von A, bricht A nicht ab; Neustart behält das Profil. Dabei `list_jobs` in `scan_service.py` (Wiederaufnahme: alle Profile), `scheduler.py`, `web/common.py` und `app.py` auf das richtige Profil stellen (seit M0.5 sehen sie nur Profil 1). Jobs werden je Profil auf `MAX_JOBS` gekürzt.
- [x] **M2.2 Watchlist je Profil laden [einfach]** — `scan_run.load_watchlist`: CSV-Rückfall nur für Profil 1, sonst klare Fehlermeldung.
- [x] **M2.3 Der zweite Scan nutzt den Cache [einfach]** — nur ein Test: zweiter Scan zählt TMDB-Anfragen nur für neue Filme.
- [x] **M2.4 Scheduler je Profil [einfach]** — `scheduler.py`, `web/common.py`. Test: zwei Profile am selben Tag nacheinander gescannt.
- [x] **M2.5 Benachrichtigungen je Profil [einfach]** — `scheduler.py`, `notifications.py`. Test: Profil 2 bekommt nur seine Meldungen; „höchstens 1 am Tag“ je Profil. Umsetzung M2.1–M2.5: manuelle Scans verschiedener Profile laufen parallel, Zeitplan und Erst-Scan nur wenn nichts läuft; Letterboxd-Name aus `.env` gilt nur für Profil 1. Offen: `tmdb_requests` eines Jobs ist bei parallelen Scans gemischt; ein neuer Name während eines anderen Scans bei abgeschaltetem Zeitplan startet keinen Scan.
- [ ] **M2.6 `profile_id` wird Pflicht [einfach, viele Dateien]** — Standardwert entfernen, nur Keyword; alle Aufrufer und Tests anpassen. mypy und Tests finden jeden vergessenen Aufruf.

### M3 – Statistik und Daten je Profil

- [ ] **M3.1 Stats und Abo-Seite je Profil [einfach]** — `web/pages.py` (`service_history`, `costs` des Profils).
- [ ] **M3.2 Settings → Data zeigt Profil und Job [einfach]** — `status_overview` mit Profilname je Job; Backup-Import fragt bei v1 nach dem Zielprofil.

### M4 – Together-Modus

- [ ] **M4.1 Gesehene Filme von Letterboxd laden [stark]** — `letterboxd.fetch_watched_slugs(username)` über `/{user}/films/page/N/`; Seitengröße und Abbruch aus dem echten Markup; 404/privat → `LetterboxdError`. Tests: echte HTML-Seite als Fixture; mehrere Seiten mit gemockter Session.
- [ ] **M4.2 Gesehene Filme speichern und auffrischen [einfach]** — Migration v4 (`watched`), `replace_watched`, `watched_keys`, `watched_fetched_at`; nach erfolgreichem Scan höchstens einmal am Tag laden, Fehler bricht den Scan nicht ab. Schlüssel `lb:{slug}`. Nicht im Backup.
- [ ] **M4.3 Zusammenführen als reine Funktion [stark]** — `watchlist_app/together.py`, `merge(members)`. Abgleich über `tmdb_id`, Rückfall `film_key`; Gruppe `both` (auf allen Listen) und `one` (auf einer Liste, keiner hat ihn gesehen); Gesehenes und Hidden/Not now irgendeines Mitglieds fällt raus; `subscriptions` = Vereinigung, `service_owners`. Tests: Überschneidung, gesehen, versteckt, CSV ohne Slug, drei Mitglieder.
- [ ] **M4.4 API `/api/together` [einfach]** — `GET /api/together?with=2,3`, Land des aktiven Profils, Form wie `/api/latest` plus Together-Felder; `missing` für Partner ohne frischen Scan; `sw.js` network-first.
- [ ] **M4.5 Together-Schalter auf Tonight [stark, UI]** — `tonight-page.js` („Together with …“, Reihen „On both lists“ und „One of you, unseen“), `index.html`, `v=`. Test: Browser mit falschem Letterboxd.
- [ ] **M4.6 Wessen Dienst ist es [einfach]** — `static/js/owners.js` (`ownersOf`), Initialen-Marke an Logos in Together, Drawer „Anna's Netflix“. Tests: `owners.test.mjs`, Browser.

### M5 – Feinschliff

- [ ] **M5.1 Benachrichtigungsseite je Profil [einfach]** — klar, für welches Profil sie gilt; Test-Button an das Ziel des Profils.
- [ ] **M5.2 Pick for me in Together [einfach]** — Gruppe `both` zählt mehr, Begründung „On both lists“.
- [ ] **M5.3 Raster in Together [einfach, optional]** — `/watchlist?together=2`.
- [ ] **M5.4 Feeds und Sensoren mit Profil-Link [einfach]** — Settings → Data zeigt URLs mit `?profile=`.
- [ ] **M5.6 Gerätewerte je Profil [einfach]** — kleines Modul `static/js/profile-storage.js` (`profileKey(name)` = `p<id>:<name>`; Profil-ID aus einem `data-profile` am `<body>`), alle `localStorage`-Zugriffe (`saved-views.js`, Tonight-Chips, `abroadOn`, `viewMode`, versteckte Vorschläge) darüber; beim ersten Lesen für Profil 1 den alten Schlüssel ohne Präfix übernehmen, damit nichts verloren geht. Tests: node-Test für `profileKey` und die Übernahme; Browser: Profil 2 sieht die gespeicherten Ansichten von Profil 1 nicht.
- [ ] **M5.7 Gespeicherte Ansichten teilen [einfach]** — eine Ansicht als Link teilen (die Filter stehen schon in der URL) und „Copy to profile …“ in der Liste der gespeicherten Ansichten. Ganz am Ende.
- [ ] **M5.5 Doku [einfach]** — `CLAUDE.md` und `PLAN.md` aktualisieren.

---

## 4. Fragen (alle entschieden)

1. **Hidden/Not now in Together:** Fliegt ein Film raus, wenn *eine* Person ihn versteckt hat? **Entschieden (26.11.2026): ja.**
2. **Land in Together bei verschiedenen Ländern:** **Entschieden (26.11.2026): Land des aktiven Profils, Partnerliste dort scannen.**
3. **Wer darf Profile anlegen und löschen?** **Entschieden (26.11.2026): jeder; Löschen mit Bestätigung, letztes Profil nicht löschbar.**
4. **localStorage (gespeicherte Ansichten, Tonight-Chips):** ~~je Gerät oder je Profil?~~ **Entschieden: je Profil, auf dem Gerät gespeichert; teilbar ganz am Ende** (M5.6, M5.7).
5. **Neues Profil und Scan:** sofort scannen, danach im globalen Zeitplan? **Entschieden (26.11.2026): ja.**

Nicht geprüft: das Markup der Letterboxd-Seiten `/{user}/films/`, und ob `save_bundle` die Angebote aller Länder auf einmal speichert (zeigt der Test in M2.3).
