"""An iCalendar feed of the renewal and cancellation dates the user entered (for a calendar app)."""

import datetime

PRODUCT = "-//Watchlist Availability//Subscriptions//EN"


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> list[str]:
    """Lines longer than 75 bytes continue on the next line, starting with a space (RFC 5545)."""
    raw = line.encode("utf-8")
    parts: list[str] = []
    while len(raw) > 75:
        cut = 75
        while cut > 0 and (raw[cut] & 0xC0) == 0x80:  # never cut inside a multi-byte character
            cut -= 1
        parts.append(raw[:cut].decode("utf-8"))
        raw = b" " + raw[cut:]
    parts.append(raw.decode("utf-8"))
    return parts


def build_ics(costs_by_country: dict[str, dict[str, dict]], now: datetime.datetime | None = None) -> str:
    """One all-day event per renewal date; with a notice period also one for the last day to cancel."""
    stamp = (now or datetime.datetime.now(datetime.UTC)).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODUCT}", "CALSCALE:GREGORIAN"]
    lines.append("X-WR-CALNAME:Subscriptions")
    for country, costs in sorted(costs_by_country.items()):
        for name, entry in sorted(costs.items()):
            if not entry.get("remind_on"):
                continue
            date = datetime.date.fromisoformat(entry["remind_on"])
            events = [("renewal", date, f"{name}: renewal or cancellation date")]
            if entry.get("notice_days"):
                events.append(
                    (
                        "cancel-by",
                        date - datetime.timedelta(days=int(entry["notice_days"])),
                        f"{name}: last day to cancel",
                    )
                )
            for kind, day, summary in events:
                lines += [
                    "BEGIN:VEVENT",
                    f"UID:{kind}-{country}-{_escape(name)}-{day.isoformat()}@watchlist-availability",
                    f"DTSTAMP:{stamp}",
                    f"DTSTART;VALUE=DATE:{day.strftime('%Y%m%d')}",
                    f"DTEND;VALUE=DATE:{(day + datetime.timedelta(days=1)).strftime('%Y%m%d')}",
                    f"SUMMARY:{_escape(summary)}",
                    "TRANSP:TRANSPARENT",
                    "END:VEVENT",
                ]
    lines.append("END:VCALENDAR")
    out: list[str] = []
    for line in lines:
        out += _fold(line)
    return "\r\n".join(out) + "\r\n"
