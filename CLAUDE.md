# Ruflo — Claude Code Configuration

## Rules

- Do what has been asked; nothing more, nothing less
- NEVER create files unless absolutely necessary — prefer editing existing files
- NEVER create documentation files unless explicitly requested
- NEVER save working files or tests to root — use `/src`, `/tests`, `/docs`, `/config`, `/scripts`
- ALWAYS read a file before editing it
- NEVER commit secrets, credentials, or .env files
- NEVER add a `Co-Authored-By` trailer to user commits unless this project's `.claude/settings.json` has `attribution.commit` set (#2078). The Claude Code Bash tool may suggest one in its default commit-message template — ignore it. `Co-Authored-By` is semantic authorship attribution under git/GitHub convention; the tool is the facilitator, not a co-author.
- Keep files under 500 lines
- Validate input at system boundaries

## Ruflo Capability Brain & Implementation Loop

Ruflo is the coordination ledger and policy decision point. Claude Code is the
executor: after a Ruflo coordination call, continue implementing the task.

When it is registered, call
`guidance_brain({ mode: "recommend", task: "..." })` before complex Ruflo
work. Use its live registry instead of guessing tool names. Treat
`registered`, `configured`, `reachable`, `healthy`, and `authorized`
as separate facts. If the brain is unavailable, continue with the compatible
`guidance_recommend` tool, CLI discovery, and repository instructions.

Follow the returned loop:

1. Recall memory and ADR constraints.
2. Inspect source, runtime, dependencies, policy, and health.
3. Route to the smallest capable topology, agents, skills, and tools.
4. Plan acceptance criteria, safety envelope, ownership, and validation.
5. Execute in isolated scopes; the coding agent performs the work.
6. Test focused, regression, and failure paths.
7. Validate types, security, policy, compatibility, and artifacts.
8. Benchmark a source-bound candidate against a source-bound baseline.
9. Optimize measured bottlenecks without weakening safety.
10. Bind claims and evidence to exact source/build receipts.
11. Reconcile concurrent handoffs and disclose limitations.
12. Publish only through a separately authorized release gate.

### Concurrency and authority

- Never allow two writers in one worktree; give each writing agent an isolated
  worktree and explicit file ownership.
- Read-only research may run concurrently and report findings to the owner.
- Only the integration owner edits shared manifests and lockfiles or reconciles
  overlapping changes.
- A child may drop capabilities but cannot add tools, network, secrets, spend,
  concurrency, namespaces, or delegation depth.
- A lease or claim coordinates ownership; it does not authorize a side effect.
- Darwin, Flywheel, MetaHarness, memory, and neural systems may propose or
  evaluate candidates but cannot self-promote or expand their SafetyEnvelope.
- Bind tests, benchmarks, policy decisions, and release evidence to an exact
  commit or immutable dirty-worktree snapshot.

## Agent Comms (SendMessage-First Coordination)

Named agents coordinate via `SendMessage`, not polling or shared state.

```
Lead (you) ←→ architect ←→ developer ←→ tester ←→ reviewer
              (named agents message each other directly)
```

### Spawning a Coordinated Team

```javascript
// ALL agents in ONE message, each knows WHO to message next
Agent({ prompt: "Research the codebase. SendMessage findings to 'architect'.",
  subagent_type: "researcher", name: "researcher", run_in_background: true })
Agent({ prompt: "Wait for 'researcher'. Design solution. SendMessage to 'coder'.",
  subagent_type: "system-architect", name: "architect", run_in_background: true })
Agent({ prompt: "Wait for 'architect'. Implement it. SendMessage to 'tester'.",
  subagent_type: "coder", name: "coder", run_in_background: true })
Agent({ prompt: "Wait for 'coder'. Write tests. SendMessage results to 'reviewer'.",
  subagent_type: "tester", name: "tester", run_in_background: true })
Agent({ prompt: "Wait for 'tester'. Review code quality and security.",
  subagent_type: "reviewer", name: "reviewer", run_in_background: true })

// Kick off the pipeline
SendMessage({ to: "researcher", summary: "Start", message: "[task context]" })
```

### Patterns

| Pattern | Flow | Use When |
|---------|------|----------|
| **Pipeline** | A → B → C → D | Sequential dependencies (feature dev) |
| **Fan-out** | Lead → A, B, C → Lead | Independent parallel work (research) |
| **Supervisor** | Lead ↔ workers | Ongoing coordination (complex refactor) |

### Rules

- ALWAYS name agents — `name: "role"` makes them addressable
- ALWAYS include comms instructions in prompts — who to message, what to send
- Spawn ALL agents in ONE message with `run_in_background: true`
- After spawning, continue independent local work; wait only when a dependency
  genuinely blocks progress
- Do not poll repeatedly — agents message back or complete automatically
- Give every writing agent an isolated worktree and a non-overlapping file scope

## Swarm & Routing

### Config
- **Topology**: hierarchical-mesh (anti-drift)
- **Max Agents**: 15
- **Memory**: hybrid
- **HNSW**: Enabled
- **Neural**: Enabled

```bash
npx @claude-flow/cli@latest swarm init --topology hierarchical --max-agents 8 --strategy specialized
```

### Agent Routing

| Task | Agents | Topology |
|------|--------|----------|
| Bug Fix | researcher, coder, tester | hierarchical |
| Feature | architect, coder, tester, reviewer | hierarchical |
| Refactor | architect, coder, reviewer | hierarchical |
| Performance | perf-engineer, coder | hierarchical |
| Security | security-architect, auditor | hierarchical |

### When to Swarm
- **YES**: 3+ files, new features, cross-module refactoring, API changes, security, performance
- **NO**: single file edits, 1-2 line fixes, docs updates, config changes, questions

### 3-Tier Model Routing

| Tier | Handler | Use Cases |
|------|---------|-----------|
| 1 | Agent Booster (WASM) | Simple transforms — skip LLM, use Edit directly |
| 2 | Haiku | Simple tasks, low complexity |
| 3 | Sonnet/Opus | Architecture, security, complex reasoning |

## Memory & Learning

### Before Any Task
```bash
npx @claude-flow/cli@latest memory search --query "[task keywords]" --namespace patterns
npx @claude-flow/cli@latest hooks route --task "[task description]"
```

### After Success
```bash
npx @claude-flow/cli@latest memory store --namespace patterns --key "[name]" --value "[what worked]"
npx @claude-flow/cli@latest hooks post-task --task-id "[id]" --success true --store-results true
```

### MCP Tools (use `ToolSearch("keyword")` to discover)

| Category | Key Tools |
|----------|-----------|
| **Memory** | `memory_store`, `memory_search`, `memory_search_unified` |
| **Bridge** | `memory_import_claude`, `memory_bridge_status` |
| **Swarm** | `swarm_init`, `swarm_status`, `swarm_health` |
| **Agents** | `agent_spawn`, `agent_list`, `agent_status` |
| **Hooks** | `hooks_route`, `hooks_post-task`, `hooks_worker-dispatch` |
| **Security** | `aidefence_scan`, `aidefence_is_safe`, `aidefence_has_pii` |
| **Hive-Mind** | `hive-mind_init`, `hive-mind_consensus`, `hive-mind_spawn` |

### Background Workers

| Worker | When |
|--------|------|
| `audit` | After security changes |
| `optimize` | After performance work |
| `testgaps` | After adding features |
| `map` | Every 5+ file changes |
| `document` | After API changes |

```bash
npx @claude-flow/cli@latest hooks worker dispatch --trigger audit
```

## Agents

**Core**: `coder`, `reviewer`, `tester`, `planner`, `researcher`
**Architecture**: `system-architect`, `backend-dev`, `mobile-dev`
**Security**: `security-architect`, `security-auditor`
**Performance**: `performance-engineer`, `perf-analyzer`
**Coordination**: `hierarchical-coordinator`, `mesh-coordinator`, `adaptive-coordinator`
**GitHub**: `pr-manager`, `code-review-swarm`, `issue-tracker`, `release-manager`

Any string works as a custom agent type.

## Build & Test

- ALWAYS run tests after code changes
- ALWAYS verify build succeeds before committing

For this project see "Project: watchlist-availability" below (pytest, node --test, ruff, mypy).

## CLI Quick Reference

```bash
npx @claude-flow/cli@latest init --wizard           # Setup
npx @claude-flow/cli@latest swarm init --v3-mode     # Start swarm
npx @claude-flow/cli@latest memory search --query "" # Vector search
npx @claude-flow/cli@latest hooks route --task ""    # Route to agent
npx @claude-flow/cli@latest doctor --fix             # Diagnostics
npx @claude-flow/cli@latest security scan            # Security scan
npx @claude-flow/cli@latest performance benchmark    # Benchmarks
```

26 commands, 140+ subcommands. Use `--help` on any command for details.

## Setup

```bash
claude mcp add claude-flow -- npx -y ruflo@latest mcp start
npx ruflo@latest doctor --fix
```

> The background `daemon` is optional. It runs interval workers that each spawn
> a headless `claude` session, so it consumes tokens continuously. Start it only
> if you want those sweeps: `npx ruflo@latest daemon start` (self-stops after 12h
> by default; `--ttl 0` to disable, `daemon status --all` to audit running daemons).

**Agent tool** handles execution (agents, files, code, git). **MCP tools** handle coordination (swarm, memory, hooks). **CLI** is the same via Bash.

## Project: watchlist-availability

Flask app (`app.py`, `web/routes.py`, `watchlist_app/`) with SQLite, Tabler/Bootstrap 5.3 and plain ES modules in `static/js/` (no build step). Plan and progress live in `PLAN.md` (German); design reviews in `reviews/`.

### Commands

- `.venv/Scripts/python.exe -m pytest -q` -- Python tests (browser tests are deselected by default)
- `.venv/Scripts/python.exe -m pytest -q -m browser tests/browser` -- Playwright browser tests against a fake TMDB/Letterboxd
- `node --test tests/js/*.mjs` -- tests for the pure JS modules (`filtering.js`, `filters.js`, `rendering.js`)
- `.venv/Scripts/python.exe -m ruff check . && .venv/Scripts/python.exe -m ruff format --check . && .venv/Scripts/python.exe -m mypy .` -- lint, format, types
- Preview with real data: `.claude/launch.json` config `web-copy` (port 5001, `WATCHLIST_DATA_DIR` = a copy of the data, `WATCHLIST_DISABLE_SCHEDULER=1`)

### Gotchas

- `CRLF line endings` -- most files use CRLF; scripted edits must match `\r\n` or the replace finds nothing
- `Stale templates in the preview` -- Flask caches templates; restart the preview server after template edits, or the old HTML loads the new JS and throws
- `Asset version` -- bump `v=` in `templates/*.html` (`url_for(..., v='YYYYMMDD-n')`) after CSS/JS changes, else browsers keep the old files
- `.btn beats display:none` -- a later `.btn { display: inline-flex }` overrides `.x { display: none }`; hide buttons with a more specific selector (`.header-buttons .provider-toggle`)
- `Disabled button loses focus` -- remember `document.activeElement` before `button.disabled = true` if focus must be restored
- `Bootstrap modal and Escape` -- Escape only works after the modal has faded in; tests wait until focus is inside the dialog
- `Bootstrap modal focus` -- Bootstrap does not return focus; use `openModal(id, opener)` in `app.js`, which also finds a redrawn card's button by `data-key`
- `ruff and ruflo` -- `pyproject.toml` excludes `.claude`, `.agents`, `.claude-flow`, else ruff formats code samples in the ruflo agent docs
- `Header compact flicker` -- the sticky header slims down at scrollY > 64 and grows back under 8; one threshold made short pages oscillate (Playwright: "element is not stable")
- `Stretched card link` -- the title link (`.film-open::after`) covers the whole card; Playwright refuses clicks on a child under it, click the `article` (with `position`) or the link instead
- `Old saved scans` -- new film fields (`collection`, `watchlist_position`) are empty until the next scan refetches TMDB data

### Patterns

- Filters -- pure logic in `filtering.js`/`filters.js` (tested with a fake `doc`), the bar's DOM in `filterbar.js`, wiring in `app.js`; `FILTER_CONTROLS` drives chips, "Reset all" and the "Filters (n)" counter. Custom controls keep a hidden input with `data-default` and `data-text`. The ticked services live in `state.selected` (one source for grid, Tonight and details); per-option counts use `facetCounts`
- The filter bar stays one row (search, services, cost, genre, runtime, rating, Filters, sort); every new filter goes under "Filters"
- New film field -- add it in `models.Film`, `tmdb._details_from_movie`, `results.make_film` and `validation.clean_film` (backups and the client go through validation)
- Wording -- "service", not "provider", in the UI; one `.pill` class with tones ok/warn/danger/neutral; amber only for controls
- Colours -- all in OKLCH in `static/css/app.css`; surfaces `--bg` < `--surface`/`--panel` < `--surface-raised` (dialogs, menus, toasts); borders `--line`, `--line-card`, `--line-field`, `--line-strong` are white with alpha. No new hex values; error and status colours stay solid on purpose
- Font sizes -- `--fs-small/.75rem`, `--fs-body/.875rem`, `--fs-text/1rem`, `--fs-heading/2rem`; nothing under 12px

### Decisions

- Pages: `/` is Tonight (rows from `events.js`), `/watchlist` the grid; both render `index.html` with `view`, and the watchlist controls stay in the DOM (hidden) on Tonight because `app.js` wires them at load. Old `/?<filter>` links 301 to `/watchlist`
- Header: one partial `partials/header.html` on every page (brand, country, nav, sync); a context processor gives it country and sync state. The film pages show the scan panel in it, the others a link plus `header.js`. The phone "Filters" button lives in the page (`.phone-filters`), not in the header. Grid: one list from `filterFilms().films`; `sectionOf` says which offers a card lists ("All" when both sections match). Sort is a menu of radios with a hidden `#sort-order` (`SORTS` in `routes.py` has group and text)
- Film flags: `flags` table (`watched`, `not_now` with a server-set date 30 days ahead), `/api/flags`, part of the backup; the card's ... menu, the drawer buttons and the keys `s`/`n` call `setFlag` in `app.js`. The details are a Bootstrap modal styled as a drawer (`#film-details-modal`, right on desktop, bottom sheet on phones)
- Settings sub-pages: `/settings`, `/settings/data` (was `/status`), `/settings/matches` (was `/matches`); old paths 301. The scan panel lives in the header sync dropdown (`#sync-toggle`), its element ids are unchanged
- "Where to watch" uses `tmdb_url + /watch?locale=XX` instead of storing TMDB's `link` field (same page, no DB/backup change)
- The services are chosen on `/settings/services` (saves on tick, `PUT /api/settings` with `subscriptions`); prices and renewal dates live on `/subscriptions` and save on blur (`costs`); `subscriptions_country` still lets the API edit another country; `/costs` redirects (301). `costs.overview` returns paid rows sorted by films only there, a free-services block and `book` with Amazon Channels folded into their main service (`catalog_name`)
- Letterboxd CSV is sorted by its `Date` column newest first, to match the website order (assumed newest first, not verified)
- 44px touch targets only under `pointer: coarse`, so the desktop stays dense

## Session Log

- 2026-11-16: [Decisions] Stages 9e-9j and most of 10 done (see PLAN.md); "Ähnliche Filme" left open because it needs extra TMDB requests per suggestion
- 2026-11-16: [Gotchas] Filter bugs found by comparing each filter's count against counts computed from `/api/latest` data; repeat this method after filter changes

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- When graphify-out/graph.json exists, run `graphify query "<question>"` before your first grep, search or source-file read for a codebase question, and put this rule in every subagent prompt that explores code. Read raw files only for lines the graph or an earlier read already located. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. When the answer is under a Markdown heading, `graphify section "<heading>"` prints that section's text, so the .md need not be opened. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
- A committed graphify-out/graph.json is rewritten whole on every build, so a large diff to it in a pull request is expected. Do not flag it as churn or suggest skipping the graph rebuild or its hooks.
