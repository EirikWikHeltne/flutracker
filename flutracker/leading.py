"""Leading markets: influenza outside Europe that tends to run ahead of the Nordic season.

Two kinds of market (config.LEADING_MARKETS):

* southern hemisphere (Australia, ...): the winter season runs May–September, so it is
  over before the Nordic one starts. Its size and its dominant virus are an early hint
  of what the Nordic winter may bring.
* early northern markets (Japan, US, ...): the same season as the Nordics, but often
  a few weeks earlier. When they cross the epidemic threshold, the Nordics usually follow.

The measure is influenza test positivity from WHO FluNet (positives / specimens tested).
Positivity is used instead of case counts because testing volumes differ a lot between
countries and years. Seasons hit by COVID-19 measures are left out of the history.
"""

import json
import statistics
import urllib.parse

import pandas as pd

from . import analysis
from .analysis import parse_yw, season_start, season_weeks, yw_str
from .config import (
    COUNTRIES,
    FLUNET_FIRST_YEAR,
    FLUNET_SOURCE,
    FLUNET_SUBTYPES,
    FLUNET_URL,
    LEADING_EPIDEMIC_THRESHOLD,
    LEADING_MARKETS,
    LEADING_MAX_LAG_WEEKS,
    LEADING_SKIP_YEARS,
)
from .fetch import _download

MIN_TESTS = 10  # weeks with fewer specimens tested give no positivity
MIN_WEEKS = 20  # an earlier year/season counts as history only with this many weeks of data
CHART_YEARS = 5
COLUMNS = ["market", "yearweek", "tests", "tested_positives", "positives", *FLUNET_SUBTYPES]


# ---------------------------------------------------------------- fetch ----

def _flunet_rows(country, url=FLUNET_URL, first_year=FLUNET_FIRST_YEAR):
    query = urllib.parse.urlencode({
        "$format": "json",
        "$filter": f"COUNTRY_CODE eq '{country}' and ISO_YEAR ge {first_year}",
    }, quote_via=urllib.parse.quote, safe="$'")
    next_url, rows = f"{url}?{query}", []
    while next_url:
        page = json.loads(_download(next_url))
        rows += page.get("value", [])
        next_url = page.get("@odata.nextLink")
    return rows


def _num(df, col):
    return pd.to_numeric(df[col], errors="coerce") if col in df.columns else pd.Series(float("nan"), index=df.index)


def tidy(records, market):
    """One row per week: specimens tested, positives (all, and among rows with a test count) and virus groups.

    FluNet has a row per surveillance system (sentinel, non-sentinel, ...) and week; they are summed.
    """
    df = pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame(columns=COLUMNS)
    df["yearweek"] = [yw_str(int(y), int(w)) for y, w in zip(df["ISO_YEAR"], df["ISO_WEEK"])]
    a, b = _num(df, "INF_A").fillna(0), _num(df, "INF_B").fillna(0)
    positives = _num(df, "INF_ALL").fillna(a + b)
    tests = _num(df, "SPEC_PROCESSED_NB")
    tests = tests.where(tests > 0, positives + _num(df, "INF_NEGATIVE"))  # fall back to positives + negatives
    has_tests = tests > 0
    out = pd.DataFrame({
        "yearweek": df["yearweek"],
        "tests": tests.where(has_tests, 0),
        "tested_positives": positives.where(has_tests, 0),
        "positives": positives,
    })
    for group, cols in FLUNET_SUBTYPES.items():
        out[group] = sum((_num(df, c).fillna(0) for c in cols), pd.Series(0.0, index=df.index))
    out = out.groupby("yearweek", as_index=False).sum()
    out.insert(0, "market", market)
    return out[COLUMNS]


def fetch_flunet(url=FLUNET_URL):
    """Weekly FluNet figures for every leading market (markets that fail to download are skipped)."""
    frames = []
    for code, m in LEADING_MARKETS.items():
        try:
            frames.append(tidy(_flunet_rows(m["flunet"], url), code))
        except (OSError, ValueError) as e:
            print(f"FluNet: {m['name']} could not be downloaded ({e})")
    frames = [f for f in frames if not f.empty]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLUMNS)


# --------------------------------------------------------------- series ----

def positivity(df):
    """Weekly influenza positivity (%) indexed by 'YYYY-Www', from weeks with enough specimens."""
    d = df[df["tests"] >= MIN_TESTS].set_index("yearweek").sort_index()
    return (d["tested_positives"] / d["tests"] * 100).round(1)


def _skipped(yw):
    return season_start(*parse_yw(yw)) in LEADING_SKIP_YEARS


def _onset(values, labels):
    """First week label at or above the epidemic threshold, or None."""
    for v, label in zip(values, labels):
        if v is not None and v >= LEADING_EPIDEMIC_THRESHOLD:
            return label
    return None


def _median_week(weeks):
    return round(statistics.median(weeks)) if weeks else None


def _dominant(totals):
    typed = {k: v for k, v in totals.items() if "not " not in k}
    total = sum(typed.values())
    if total < 10:
        return None
    dom = max(typed, key=typed.get)
    return {"virus": dom, "share": round(typed[dom] / total * 100)}


def _virus_mix(df, weeks):
    d = df[df["yearweek"].isin(weeks)]
    totals = {k: int(d[k].sum()) for k in FLUNET_SUBTYPES}
    return {"totals": totals, "dominant": _dominant(totals)}


def yearly(pos, latest_year):
    """Positivity per calendar year (ISO weeks 1–53) for the last CHART_YEARS years with data."""
    values = pos.to_dict()
    years = [y for y in range(latest_year - 8, latest_year + 1) if y not in LEADING_SKIP_YEARS]
    out = {}
    for y in years:
        row = [values.get(yw_str(y, w)) for w in range(1, 54)]
        if any(v is not None for v in row):
            out[str(y)] = [None if v is None else float(v) for v in row]
    return dict(list(out.items())[-CHART_YEARS:])


# ------------------------------------------------------------ southern ----

def southern_summary(df, pos, year):
    """Season = calendar year. Size = peak positivity against the average peak of earlier years."""
    labels = list(range(1, 54))

    def year_values(y):
        return [pos.get(yw_str(y, w)) for w in labels]

    current = year_values(year)
    reported = [i for i, v in enumerate(current) if v is not None]
    if not reported:
        return None
    hist = {}
    for y in range(FLUNET_FIRST_YEAR, year):
        vals = year_values(y)
        if y not in LEADING_SKIP_YEARS and sum(v is not None for v in vals) >= MIN_WEEKS:
            hist[str(y)] = vals

    def peak(vals):
        v = max(x for x in vals if x is not None)
        return v, labels[vals.index(v)]

    def above(vals):
        return sum(1 for x in vals if x is not None and x >= LEADING_EPIDEMIC_THRESHOLD)

    peak_v, peak_w = peak(current)
    peaks = {y: peak(v) for y, v in hist.items()}
    peak_mean = sum(p for p, _ in peaks.values()) / len(peaks) if peaks else None
    onsets = [o for v in hist.values() if (o := _onset(v, labels))]
    last_i = reported[-1]
    latest_v = current[last_i]
    onset = _onset(current, labels)
    if onset is None:
        status = "Not started"
    elif latest_v < LEADING_EPIDEMIC_THRESHOLD:
        status = "Over" if latest_v < peak_v / 2 else "Easing"
    else:
        status = "Under way"
    return {
        "season": str(year),
        "week": yw_str(year, labels[last_i]),
        "value": latest_v,
        "peak": peak_v,
        "peak_week": peak_w,
        "peak_mean": None if peak_mean is None else round(peak_mean, 1),
        "peaks": {y: {"value": p, "week": w} for y, (p, w) in peaks.items()},
        "intensity": analysis.classify_intensity(peak_v, peak_mean),
        "intensity_pct": None if not peak_mean else round(peak_v / peak_mean * 100),
        "weeks_above": above(current),
        "weeks_above_mean": round(sum(above(v) for v in hist.values()) / len(hist), 1) if hist else None,
        "onset_week": onset,
        "usual_onset_week": _median_week(onsets),
        "status": status,
        "n_seasons": len(hist),
        "mix": _virus_mix(df, [yw_str(year, w) for w in labels]),
    }


# ------------------------------------------------------------ northern ----

def northern_summary(df, pos, cur_start, latest):
    """Same season as the Nordics (week 40–39): this week against the same week of earlier seasons."""
    weeks = season_weeks(cur_start)
    s = pos[[not _skipped(w) for w in pos.index]]
    r = analysis.analyse_series(s, "rate", cur_start, weeks, latest)
    summary = r["summary"]
    if not summary or season_start(*parse_yw(summary["week"])) != cur_start:
        return None
    labels = [w for _, w in weeks]
    seasons = r["seasons"]
    current = seasons[analysis.season_label(cur_start)]
    onsets = [o for k, v in seasons.items() if k != analysis.season_label(cur_start) and (o := _onset(v, labels))]
    keys = [yw_str(*w) for w in weeks]
    summary.update({
        "season": analysis.season_label(cur_start),
        "onset_week": _onset(current, labels),
        "usual_onset_week": _season_median(onsets),
        "mix": _virus_mix(df, [k for k in keys if k <= summary["week"]]),
    })
    return summary


def _season_median(onset_weeks):
    """Median of season weeks (40, 41, ..., 52, 1, 2, ...), keeping the season order."""
    if not onset_weeks:
        return None
    order = [w if w >= 40 else w + 53 for w in onset_weeks]
    m = round(statistics.median(order))
    return m if m <= 53 else m - 53


def nordic_onsets(result):
    """When each Nordic country's influenza test positivity usually crosses the threshold, and this season."""
    out = {}
    labels = [int(w[1:]) for w in result["season_weeks"]]
    for code in COUNTRIES:
        s = result["series"].get(code, {}).get("flu_positivity")
        if not s:
            continue
        seasons = s["seasons"]
        current = seasons[result["season"]]
        past = [o for k, v in seasons.items() if k != result["season"] and (o := _onset(v, labels))]
        latest = result["summary"].get(code, {}).get("flu_positivity")
        out[code] = {
            "name": COUNTRIES[code]["name"],
            "value": latest and latest["value"],
            "week": latest and latest["week"],
            "onset_week": _onset(current, labels),
            "usual_onset_week": _season_median(past),
            "n_seasons": len(past),
        }
    return out


# --------------------------------------------------------------- points ----

def _fmt(v, d=0):
    return analysis.fmt_num(v, d)


def _mix_text(mix):
    dom = mix and mix.get("dominant")
    return f"mostly {dom['virus']} ({dom['share']}% of subtyped samples)" if dom else "virus mix not yet known"


def points(leading):
    """Plain sentences on the leading markets for the findings and the e-mail."""
    out = []
    south = [(c, m) for c, m in leading["markets"].items() if m["hemisphere"] == "south" and m.get("summary")]
    for code, m in south[:1]:  # the lead market (Australia) in full
        s = m["summary"]
        text = (f"{m['name']}'s {s['season']} flu season peaked at {_fmt(s['peak'], 1)}% test positivity in week "
                f"{s['peak_week']}")
        if s.get("intensity"):
            text += f" – {s['intensity'].lower()} ({s['intensity_pct']}% of an average peak)"
        text += f", {_mix_text(s['mix'])}."
        out.append(text)
    others = [f"{m['name']} {m['summary']['intensity'].lower()}" for _, m in south[1:] if m["summary"].get("intensity")]
    if others:
        out.append("Other southern-hemisphere seasons: " + ", ".join(others) + ".")
    mix = leading.get("south_mix")
    if mix:
        out.append(f"Southern hemisphere overall: {_mix_text(mix)} – a first hint of the virus mix for the Nordic winter.")

    north = [m for m in leading["markets"].values() if m["hemisphere"] == "north" and m.get("summary")]
    started = [f"{m['name']} (since week {m['summary']['onset_week']})" for m in north if m["summary"].get("onset_week")]
    waiting = [m["name"] for m in north if not m["summary"].get("onset_week")]
    if started:
        out.append(f"Above {_fmt(LEADING_EPIDEMIC_THRESHOLD)}% influenza positivity already: " + ", ".join(started) + "."
                   + (f" Not yet: {', '.join(waiting)}." if waiting else ""))
    elif north:
        out.append(f"No early-season market is above {_fmt(LEADING_EPIDEMIC_THRESHOLD)}% influenza positivity yet "
                   f"({', '.join(waiting)}).")
    return out


# ----------------------------------------------------------------- main ----

def analyse(flunet, result):
    """Leading-market summaries; `result` is the Nordic analysis (for the season and latest week)."""
    latest = result["latest_week"]
    cur_start = season_start(*parse_yw(latest))
    markets = {}
    south_totals = {k: 0 for k in FLUNET_SUBTYPES}
    for code, meta in LEADING_MARKETS.items():
        df = flunet[flunet["market"] == code]
        pos = positivity(df)
        if pos.empty:
            continue
        last = pos.index.max()
        lag = max(0, (analysis.week_monday(*parse_yw(latest)) - analysis.week_monday(*parse_yw(last))).days // 7)
        latest_year = parse_yw(last)[0]
        if meta["hemisphere"] == "south":
            summary = southern_summary(df, pos, latest_year)
            if summary:
                for k, v in summary["mix"]["totals"].items():
                    south_totals[k] += v
        else:
            summary = northern_summary(df, pos, cur_start, last)
        markets[code] = {
            "name": meta["name"],
            "hemisphere": meta["hemisphere"],
            "report": meta.get("report"),
            "latest_week": last,
            "lag_weeks": lag,
            "stale": lag > LEADING_MAX_LAG_WEEKS,
            "summary": summary,
            "yearly": yearly(pos, latest_year),
        }
    leading = {
        "source": FLUNET_SOURCE,
        "threshold": LEADING_EPIDEMIC_THRESHOLD,
        "skip_years": list(LEADING_SKIP_YEARS),
        "markets": markets,
        "south_mix": _dominant(south_totals) and {"totals": south_totals, "dominant": _dominant(south_totals)},
        "nordic_onsets": nordic_onsets(result),
    }
    leading["points"] = points(leading)
    return leading


def add_to(result, flunet):
    """Attach the leading markets to the Nordic result (no-op without FluNet data)."""
    if flunet is None or flunet.empty:
        result["leading"] = None
        return result
    result["leading"] = analyse(flunet, result)
    return result
