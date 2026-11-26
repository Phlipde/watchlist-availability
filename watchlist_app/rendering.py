"""CLI and HTML rendering for availability results."""

from datetime import date
from html import escape
from pathlib import Path

from tabulate import tabulate

from .config import DOWNLOADS_DIR
from .models import Film
from .providers import _SECTION_ORDER
from .tmdb import _TMDB_IMAGE_BASE_URL

MONTHS_EN = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def _date_en(value: date) -> str:
    return f"{MONTHS_EN[value.month - 1]} {value.day}, {value.year}"


def _kinds(film: Film, display: str) -> set[str]:
    return set(film.providers.get(display, []))


def _split_by_section(
    results: list[Film],
    targets: dict[str, str],
) -> list[tuple[str, list[dict], dict[str, str]]]:
    """Split results into sections by each (film, provider)'s real monetization.

    A film is "✓" in a section when TMDB lists it on the provider under one of the
    section's monetization types. The same provider can appear in several sections,
    and a film available under several types appears in each matching section
    (e.g. M6+ as ads + flatrate → Free AND Paid).

    Returns:
        List of (section_label, view_results, view_targets) for non-empty sections.
    """
    sections = []
    for label, mon_set in _SECTION_ORDER:
        # Keep only columns with at least one film matching this section's types.
        active = [display for display in targets if any(mon_set & _kinds(film, display) for film in results)]
        if not active:
            continue

        view_results = []
        for film in results:
            checks = {name: ("✓" if (mon_set & _kinds(film, name)) else "") for name in active}
            if any(checks.values()):
                view_results.append(
                    {
                        "Title": film.title,
                        "Year": film.year,
                        "PosterPath": film.poster_path,
                        **checks,
                    }
                )

        view_targets = {display: targets[display] for display in active}
        sections.append((label, view_results, view_targets))

    return sections


def _sort_results(rows: list[dict], targets: dict[str, str]) -> list[dict]:
    """Sort section rows for display, by priority:

    1. number of available platforms (descending) — most available first;
    2. by platform, in column order (✓ before blank) — groups films by service;
    3. title alphabetical.
    """
    columns = list(targets)

    def sort_key(row: dict):
        marks = [row.get(column) == "✓" for column in columns]
        return (-sum(marks), *[not mark for mark in marks], str(row["Title"]))

    return [
        {"Title": row["Title"], "Year": row["Year"], **{column: row.get(column, "") for column in columns}}
        | ({"PosterPath": row["PosterPath"]} if "PosterPath" in row else {})
        for row in sorted(rows, key=sort_key)
    ]


def _summary_line(results: list[Film], targets: dict[str, str]) -> str:
    """One-line count per platform: number of watchlist films available on it
    (in any tracked tier), in targets order. Avoids per-section duplicates."""
    parts = []
    for display in targets:
        count = sum(1 for film in results if film.providers.get(display))
        if count:
            parts.append(f"{display}: {count}")
    return "\n\n".join(parts)


def _render_section(title: str, results: list[dict], targets: dict[str, str]) -> str:
    """Return the Markdown text of a section (heading + table, or empty message).

    Formatting: Title column right-aligned, Year right-aligned, platform columns
    (✓) centered.
    """
    lines = [f"## {title}\n"]
    if not results:
        lines.append("_No films available._\n")
    else:
        rows = [
            {key: value for key, value in row.items() if key != "PosterPath"}
            for row in _sort_results(results, targets)
        ]
        colalign = ["right", "right", *(["center"] * len(targets))]
        # "pipe" format carries the alignment markers (:---:) so the rendered
        # Markdown actually aligns (title right, ✓ centered), not just as text.
        lines.append(tabulate(rows, headers="keys", tablefmt="pipe", showindex=False, colalign=colalign))
        lines.append("")
    return "\n".join(lines)


def display_results(
    results: list[Film],
    targets: dict[str, str] | None = None,
) -> None:
    """Print the results grouped by section (Free / Paid)."""
    _targets = targets if targets is not None else {}

    print()

    if not results:
        print("No film from your watchlist is available on the selected platforms.")
        return

    sections = _split_by_section(results, _targets)

    if not sections:
        print("No film from your watchlist is available on the selected platforms.")
        return

    for label, view_results, view_targets in sections:
        print(_render_section(label, view_results, view_targets))

    print("---")
    print(_summary_line(results, _targets))


def save_results(
    results: list[Film],
    source_name: str,
    targets: dict[str, str],
    output_dir: Path | None = None,
) -> Path:
    """Save the results to a dated HTML file with TMDB poster cards.

    Args:
        source_name: where the watchlist came from (Letterboxd username or CSV name).
        output_dir: destination folder (Downloads by default).

    Returns:
        The path of the created file.
    """
    out_dir = output_dir or DOWNLOADS_DIR
    today = date.today()
    out_path = out_dir / f"watchlist_{today.isoformat()}.html"

    sections = _split_by_section(results, targets)
    provider_options = "".join(
        f'<option value="{escape(display)}">{escape(display)}</option>' for display in targets
    )
    rendered_sections = [
        _render_html_section(label, view_results, view_targets)
        for label, view_results, view_targets in sections
    ]
    summary_items = "".join(
        f"<li><strong>{escape(part.split(':', 1)[0])}</strong>: {escape(part.split(':', 1)[1].strip())}</li>"
        for part in _summary_line(results, targets).split("\n\n")
        if ":" in part
    )
    content = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Watchlist streaming availability</title>
  <style>
    :root {{ color-scheme: dark; font-family: system-ui, sans-serif; }}
    body {{ margin: 0; background: #111827; color: #f3f4f6; }}
    main {{ max-width: 1280px; margin: 0 auto; padding: 32px 20px 56px; }}
    h1 {{ margin: 0 0 8px; font-size: clamp(1.8rem, 4vw, 3rem); }}
    .meta {{ color: #9ca3af; margin: 0 0 36px; }}
    .filters {{ display: grid; grid-template-columns: minmax(220px, 2fr) repeat(4, minmax(120px, 1fr)); gap: 10px; margin-bottom: 34px; }}
    .filters input, .filters select {{ width: 100%; box-sizing: border-box; padding: 10px 12px; border: 1px solid #4b5563; border-radius: 6px; background: #1f2937; color: #f3f4f6; font: inherit; }}
    section {{ margin-top: 34px; }}
    h2 {{ border-bottom: 1px solid #374151; padding-bottom: 10px; }}
    .films {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 20px; }}
    .film {{ overflow: hidden; background: #1f2937; border: 1px solid #374151; border-radius: 8px; }}
    .poster {{ aspect-ratio: 2 / 3; background: #374151; }}
    .poster img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
    .no-poster {{ height: 100%; display: grid; place-items: center; color: #9ca3af; text-align: center; padding: 16px; }}
    .film-info {{ padding: 12px; }}
    .film-title {{ margin: 0; font-weight: 700; }}
    .year {{ color: #9ca3af; }}
    .providers {{ margin: 10px 0 0; color: #d1d5db; font-size: .9rem; }}
    footer {{ margin-top: 44px; color: #9ca3af; }}
    footer ul {{ padding-left: 20px; }}
        .no-results {{ display: none; margin: 28px 0; color: #9ca3af; }}
        @media (max-width: 760px) {{ .filters {{ grid-template-columns: 1fr 1fr; }} .filters input[type="search"] {{ grid-column: 1 / -1; }} }}
  </style>
</head>
<body>
  <main>
    <h1>Watchlist streaming availability</h1>
    <p class="meta">{escape(_date_en(today))} · Source: {escape(source_name)}</p>
        <div class="filters" aria-label="Filter films">
            <input id="search" type="search" placeholder="Search films..." aria-label="Search films">
            <select id="section-filter" aria-label="Filter by section">
                <option value="all">All sections</option>
                <option value="Free">Free</option>
                <option value="Paid">Paid</option>
            </select>
            <select id="provider-filter" aria-label="Filter by provider">
                <option value="all">All providers</option>
                {provider_options}
            </select>
            <input id="year-from" type="number" min="1888" max="2100" placeholder="Year from" aria-label="Year from">
            <input id="year-to" type="number" min="1888" max="2100" placeholder="Year to" aria-label="Year to">
        </div>
    {"".join(rendered_sections) or "<p>No films available on the selected platforms.</p>"}
        <p id="no-results" class="no-results">No films match the selected filters.</p>
    <footer><strong>Available films per platform</strong><ul>{summary_items or "<li>None</li>"}</ul></footer>
  </main>
    <script>
        const filters = document.querySelectorAll('.filters input, .filters select');
        const cards = document.querySelectorAll('.film');
        const sections = document.querySelectorAll('section');
        const noResults = document.getElementById('no-results');
        function applyFilters() {{
            const query = document.getElementById('search').value.toLowerCase().trim();
            const selectedSection = document.getElementById('section-filter').value;
            const selectedProvider = document.getElementById('provider-filter').value;
            const from = Number(document.getElementById('year-from').value) || 0;
            const to = Number(document.getElementById('year-to').value) || 9999;
            let visible = 0;
            cards.forEach(card => {{
                const title = card.dataset.title;
                const year = Number(card.dataset.year) || 0;
                const providers = card.dataset.providers.split('|');
                const sectionMatch = selectedSection === 'all' || card.closest('section').dataset.section === selectedSection;
                const providerMatch = selectedProvider === 'all' || providers.includes(selectedProvider);
                const match = sectionMatch && title.includes(query) && providerMatch && year >= from && year <= to;
                card.hidden = !match;
                if (match) visible++;
            }});
            sections.forEach(section => {{
                const hasVisibleCard = section.querySelector('.film:not([hidden])');
                section.hidden = !hasVisibleCard;
            }});
            noResults.style.display = visible ? 'none' : 'block';
        }}
        filters.forEach(filter => filter.addEventListener('input', applyFilters));
        filters.forEach(filter => filter.addEventListener('change', applyFilters));
    </script>
</body>
</html>
"""
    out_path.write_text(content, encoding="utf-8")
    return out_path


def _render_html_section(title: str, results: list[dict], targets: dict[str, str]) -> str:
    """Return an HTML section containing poster cards for available films."""
    cards = []
    for result in _sort_results(results, targets):
        poster_path = result.get("PosterPath")
        poster = (
            f'<img src="{_TMDB_IMAGE_BASE_URL}{escape(poster_path)}" '
            f'alt="Poster for {escape(str(result["Title"]))}" loading="lazy">'
            if poster_path
            else '<div class="no-poster">No poster available</div>'
        )
        providers = [display for display in targets if result.get(display) == "✓"]
        year = result.get("Year")
        year_text = "" if year is None else str(int(year))
        provider_data = escape("|".join(providers))
        cards.append(
            f'<article class="film" data-title="{escape(str(result["Title"]).lower())}" '
            f'data-year="{escape(year_text)}" data-providers="{provider_data}">'
            f'<div class="poster">{poster}</div>'
            f'<div class="film-info"><p class="film-title">{escape(str(result["Title"]))}</p>'
            f'<span class="year">{escape(year_text)}</span>'
            f'<p class="providers">{escape(", ".join(providers))}</p></div></article>'
        )
    return f'<section data-section="{escape(title)}"><h2>{escape(title)}</h2><div class="films">{"".join(cards)}</div></section>'
