"""Data classes shared by the CLI, the scan and the web API."""

from dataclasses import asdict, dataclass, field, fields

OFFER_KINDS = ("free", "ads", "flatrate", "rent")


def sort_kinds(kinds) -> list[str]:
    """Offer types in a fixed order, without duplicates."""
    unique = set(kinds)
    return [kind for kind in OFFER_KINDS if kind in unique] + sorted(unique - set(OFFER_KINDS))


def legacy_key(title: str | None, year: int | None) -> str:
    """The old `Title|Year` key, written the way the browser used to build it."""
    return f"{title}|{'null' if year is None else year}"


@dataclass
class WatchlistEntry:
    """One film as listed on the Letterboxd watchlist or in an exported CSV."""

    title: str
    year: int | None = None
    slug: str | None = None


@dataclass
class Film:
    """A film with its TMDB data and offers. `providers` maps display name -> offer types."""

    title: str
    year: int | None = None
    tmdb_id: int | None = None
    poster_path: str | None = None
    overview: str = ""
    rating: float | None = None
    popularity: float | None = None
    vote_count: int | None = None
    director: str | None = None
    cast: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    backdrop_path: str | None = None
    runtime: int | None = None
    genres: list[str] = field(default_factory=list)
    release_date: str | None = None
    tmdb_url: str | None = None
    trailer_url: str | None = None
    providers: dict[str, list[str]] = field(default_factory=dict)

    @property
    def key(self) -> str:
        """Stable identifier: the TMDB id, or `Title|Year` when the film is not on TMDB."""
        return str(self.tmdb_id) if self.tmdb_id is not None else legacy_key(self.title, self.year)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["key"] = self.key
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Film":
        names = {item.name for item in fields(cls)}
        values = {name: data[name] for name in names if name in data and data[name] is not None}
        values["providers"] = {
            provider: sort_kinds(kinds) for provider, kinds in (data.get("providers") or {}).items()
        }
        values["genres"] = list(data.get("genres") or [])
        values["cast"] = list(data.get("cast") or [])
        values["keywords"] = list(data.get("keywords") or [])
        return cls(**values)
