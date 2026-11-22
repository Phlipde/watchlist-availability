"""One-off tool: shrink the big flag files in static/flags/ (coats of arms made some 80 to 180 KB each).

A flag over 3 KB is drawn once with the browser at 40x30 px (twice its shown size, 20x15 or less) and
written back as a small SVG that wraps the PNG, so the file names and the code stay the same. Run it from the project root:

    .venv/Scripts/python.exe scripts/shrink_flags.py
"""

import base64
from pathlib import Path

from playwright.sync_api import sync_playwright

FLAGS = Path(__file__).resolve().parent.parent / "static" / "flags"
LIMIT = 3000  # bytes; smaller flags are already tiny and stay sharp as vectors
WIDTH, HEIGHT = 40, 30


def main() -> None:
    big = sorted(path for path in FLAGS.glob("??.svg") if path.stat().st_size > LIMIT)
    before = sum(path.stat().st_size for path in big)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        for path in big:
            source = base64.b64encode(path.read_bytes()).decode()
            page.set_content(
                f'<body style="margin:0;background:transparent">'
                f'<img id="flag" width="{WIDTH}" height="{HEIGHT}" '
                f'src="data:image/svg+xml;base64,{source}"></body>'
            )
            page.wait_for_function("document.getElementById('flag').complete")
            png = page.locator("#flag").screenshot(omit_background=True)
            data = base64.b64encode(png).decode()
            wrapped = (
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 480">'
                f'<image width="640" height="480" href="data:image/png;base64,{data}"/></svg>'
            )
            path.write_text(wrapped, encoding="utf-8")
        browser.close()
    after = sum(path.stat().st_size for path in big)
    print(f"{len(big)} flags: {before // 1024} KB -> {after // 1024} KB")


if __name__ == "__main__":
    main()
