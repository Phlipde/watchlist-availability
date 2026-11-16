# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Letterboxd users who self-host the app (open source). The typical moment: in the evening, on a laptop or a phone, they want to know which films from their own watchlist they can watch right now on the services they already pay for.

## Product Purpose

Watchlist Availability matches a public Letterboxd watchlist against streaming availability from TMDB (data from JustWatch) for one country. The main job is **choosing a film for tonight**: quickly find something good that is on the user's own services. Comparing subscriptions and prices (`/subscriptions`) is a secondary job.

Success: within a few seconds the user sees what is available on their services and can make a decision, without opening each film on another site.

## Positioning

It starts from the user's own Letterboxd watchlist, the films they already chose, rather than from a service's catalogue. It shows only their services and offer types, and tracks changes between scans ("recently gone from your services").

## Operating Context

- Self-hosted Flask app (later a Docker image for Unraid), one instance per person or household.
- Data comes in through a scan: the Letterboxd page (or a CSV/ZIP export as a fallback), then TMDB per film. A scan takes minutes, and its results are stored in SQLite.
- Used on a desktop browser and often on a phone.

## Capabilities and Constraints

- Results are split into Free (free/ads) and Paid (subscription/rent), with filters for availability, genre, runtime, rating and more, plus favorites with status (plan/watching/watched).
- Decision helpers: Random, Evening mode (three picks), Compare, weighted sorts, film series, recently removed films.
- Needs a TMDB API key, and the Letterboxd watchlist must be public.
- **Interface language: English** (binding).
- **Mobile must work well** (binding).
- Open: the stages in `PLAN.md` ("Similar films", stage 11 onwards, Docker).

## Brand Commitments

- Name: "Watchlist Availability".
- Wording in the UI: "service", not "provider".

## Evidence on Hand

- Real data: the user's own scan in the local data folder (not in the repo).
- Design reviews: `reviews/` (design critique, web design guidelines).
- No testimonials, user numbers or press. Do not invent any.

## Product Principles

1. Tonight's decision comes first: the fastest way to "what can I watch now" beats completeness.
2. Only what the user can actually watch: their services, their country, their offer types.
3. Data is honest about its source and age (TMDB/JustWatch, date of the last scan).
4. Self-hosted and private: no account, no tracking, data stays on the user's server.
