"""Conversion helpers for web API payloads."""

import hashlib

import pandas as pd


def public_result(result: dict, providers: dict[str, str]) -> dict:
    return {
        "title": result["Title"],
        "year": result["Year"],
        "poster_path": result.get("PosterPath"),
        "overview": result.get("overview", ""),
        "rating": result.get("rating"),
        "backdrop_path": result.get("backdrop_path"),
        "runtime": result.get("runtime"),
        "genres": result.get("genres", []),
        "tmdb_url": result.get("tmdb_url"),
        "trailer_url": result.get("trailer_url"),
        "providers": {
            provider: sorted(result.get(provider, set()))
            for provider in providers
            if result.get(provider)
        },
    }


def watchlist_key(dataframe: pd.DataFrame, source_name: str, country: str) -> str:
    rows = "|".join(f"{row['Name']}:{row['Year']}" for _, row in dataframe.iterrows())
    return hashlib.sha256(f"{country}|{source_name}|{rows}".encode()).hexdigest()


def result_stats(results: list[dict]) -> dict:
    provider_counts: dict[str, int] = {}
    for result in results:
        for provider in result["providers"]:
            provider_counts[provider] = provider_counts.get(provider, 0) + 1
    top = max(provider_counts.items(), key=lambda item: item[1], default=("-", 0))
    return {
        "total": len(results),
        "free": sum(
            any(kind in {"free", "ads"} for kinds in result["providers"].values() for kind in kinds)
            for result in results
        ),
        "paid": sum(
            any(kind in {"flatrate", "rent"} for kinds in result["providers"].values() for kind in kinds)
            for result in results
        ),
        "top_provider": top[0],
        "top_provider_count": top[1],
    }
