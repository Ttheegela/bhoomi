"""Daily values -> monthly values, so a variable means the same thing from every source."""
MIN_DAYS = 20  # a month with fewer valid days is None


def daily_to_monthly(dates: list[str], values: list[float | None], how: str) -> tuple[list[str], list[float | None]]:
    """`how` is "mean" or "max". Regular monthly axis from first to last month, None for gaps."""
    if not dates:
        return [], []
    by_month: dict[str, list[float]] = {}
    for d, v in zip(dates, values):
        if v is not None:
            by_month.setdefault(d[:7], []).append(v)
    y0, m0, y1, m1 = int(dates[0][:4]), int(dates[0][5:7]), int(dates[-1][:4]), int(dates[-1][5:7])
    times, out = [], []
    for k in range(y0 * 12 + m0 - 1, y1 * 12 + m1):
        y, m = divmod(k, 12)
        t = f"{y:04d}-{m + 1:02d}"
        vs = by_month.get(t, [])
        times.append(t)
        out.append(None if len(vs) < MIN_DAYS else round(max(vs) if how == "max" else sum(vs) / len(vs), 2))
    return times, out
