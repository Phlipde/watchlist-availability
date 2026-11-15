"""
Checks which films from your Letterboxd watchlist are available to stream
via the TMDB API, grouped into two sections: Free and Paid.

The watchlist is fetched automatically from your public Letterboxd page
(via LETTERBOXD_USERNAME in .env). Otherwise, an exported ZIP or CSV is used
as a fallback.

Usage: python watchlist_availability.py
"""

from watchlist_app.cli import main

if __name__ == "__main__":
    main()
