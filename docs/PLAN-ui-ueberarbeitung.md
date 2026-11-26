# Später: UI-Überarbeitung (Auftrag vom 26.11.2026, noch nicht begonnen)

Vom Nutzer zum Merken gegeben. Erst angehen, wenn er es sagt.

You're improving the UI of my movie app. Before changing anything, read the repo and the existing plan (CLAUDE.md / plan file) so you match the current stack, components, and conventions. Don't introduce new libraries unless I approve it.

## Fixed product decisions (do not change)
- All data comes from Letterboxd. No logging or "mark as seen" features anywhere in the app.
- No rent/buy prices. Do not show or imply them.
- Streaming providers appear as logos/icons only, and countries as flags only. Never write out their names inline. Names appear only in a tooltip (hover on desktop, tap on mobile).

## Working method
Create a task list from the subtasks below and work through them in order. After each subtask: run the app/build, check the result at 375px and 1280px width, and commit with a clear message. Don't start the next subtask while the current one has errors. Report briefly after each one (what changed, what you skipped and why).

## Subtasks

1. Audit and strip slop
   - List every instance of: filler badges/pills, eyebrow labels, arrows on buttons, sparkle icons, glows, fake stats, numbered sections, colored left borders, unnecessary cards-in-cards, decorative fade-ins.
   - Remove them. Wrap every poster in a card only if the card adds function.

2. Movie card hierarchy
   - Poster is the dominant element. Title is second. Everything else is visibly secondary.
   - One clear primary action per card/screen; make that one stand out (Von Restorff). Remove or demote everything else.
   - Group related info by proximity and whitespace, not boxes.
   - Show essentials first (poster, title, year, provider logos). Put the rest (runtime, director, genres, full cast) in a detail view or expandable area (progressive disclosure).

3. Providers and countries
   - Provider logos at a consistent size, with matching visual weight; flags consistent in size and shape.
   - Tooltip on hover/focus/tap with the full name. Must be keyboard accessible, with an accessible label (aria-label) so icons aren't mute for screen readers.
   - Tooltip behavior: delay only the first one; show subsequent ones instantly.
   - Handle a missing logo/flag gracefully with a neutral fallback, not a broken image.

4. Grid layout and typography
   - Responsive grid; poster aspect ratio fixed (2:3) so nothing jumps while loading.
   - Left-align text, sentence case, regular body weight, tight headline line height, more space above headings than below, balanced headline wrapping, tabular numbers for years/runtimes/ratings.
   - More padding on the sides than top/bottom for buttons and chips.
   - Use 100dvh (not 100vh) for full-height layouts.

5. Color, depth, and dark mode
   - Define tokens (colors, spacing scale, radii, type scale) in one place and reuse them.
   - Palette in OKLCH, one hue per color family, grays tinted slightly blue, one accent color for the primary action.
   - Alpha borders instead of solid hex, layered small shadows instead of one large shadow.
   - Nested radii: inner radius = outer radius − padding.
   - Dark mode: muted brand colors; show depth with lighter surfaces, not shadows. Text contrast must pass WCAG AA.
   - If poster images have white backgrounds anywhere, use mix-blend-mode: multiply.

6. Search, filter, and sort
   - Persistent labels (no placeholder-as-label).
   - Recognition over recall: show available filters (provider, genre, year, etc.) on screen instead of requiring typed input.
   - Sensible defaults pre-selected (default effect); advanced filters behind "More filters".
   - Active filters visible, with a one-tap way to clear them.
   - Every empty state ("no results") has a clear call to action, e.g. "Clear filters".

7. States and feedback
   - Skeleton/loading states that match the real card layout.
   - Error state for failed fetch with a retry button.
   - Descriptive button labels ("Clear filters", "Show details"), never "Submit" or "OK".
   - If anything destructive exists, keep it away from primary actions and visually distinct.

8. Motion (last, and subtle)
   - Card/detail entrances: start from scale 0.97 + opacity 0.
   - Press feedback: scale 0.97 on :active, 150ms ease-out.
   - Animate transform and opacity only, never top/left/width/height.
   - Detail view/accordion: interpolate-size: allow-keywords for height auto.
   - Icon swaps: blur the outgoing icon slightly while it fades.
   - Nothing decorative. Respect prefers-reduced-motion.

9. Final audit
   - Re-check every subtask above against the result, plus accessibility (focus states, contrast, tap targets ≥ 44px, tooltips work without hover).
   - Confirm the fixed product decisions at the top are still respected.
   - Give me a short summary: what changed, anything you deliberately did differently from these rules, and anything you'd recommend next.

## Rules while working
- Make the smallest change that achieves each goal. Don't refactor unrelated code.
- If a rule conflicts with an existing product decision or the data I actually have, the product decision wins; tell me about it instead of silently working around it.
- If something is ambiguous, pick the most reasonable option, say which one you picked, and continue. Only stop to ask for destructive or hard-to-reverse changes.

## Entscheidungen des Nutzers (26.11.2026, Start)
- "Hide" und "Not now" bleiben (Ausblenden, kein Loggen).
- "Namen nur im Tooltip" gilt für Karten, Details und Filter; Tabellen auf Subscriptions und Stats behalten Namen, Stats bleibt unberührt.
- Grautöne leicht blau wie im Plan.

## Notizen von Claude zu möglichen Konflikten (vor dem Start ansprechen)
- "No mark as seen": die App hat "Hide" (Flag `watched`) und "Not now"; das ist Ausblenden, kein Loggen. Vor dem Start klären, ob das bleiben darf.
- "Names only in tooltip": die Kosten-/Abo-Seiten und die Stats-Seite schreiben Dienstnamen in Tabellen aus; klären, ob die Regel nur für Karten/Details gilt. Die Stats-Seite sollte bisher nicht angefasst werden.
- "Grays tinted slightly blue": die heutige Palette ist leicht grün getönt (OKLCH-Hue ~160); das wäre eine sichtbare Änderung.
