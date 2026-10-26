"""Turn ERVISS rows into weekly series and compare them with earlier seasons.

Seasons run from ISO week 40 to week 39 the following year. Each week of the
current season is compared with the same ISO week in every earlier season
(week 53 is compared with week 52 in seasons that have no week 53).
"""

import datetime as dt
import math

import pandas as pd

from .config import (
    COUNTRIES,
    INDICATORS,
    INTENSITY_LEVELS,
    MIN_SENTINEL_TESTS,
    SEASON_START_WEEK,
    SENTINEL_EPIDEMIC_THRESHOLD,
    SUBTYPE_LABELS,
    SUBTYPES,
)

MIN_WEEKS_FOR_SEASON = 20  # an earlier season counts as history only with this many weeks of data


# ---------------------------------------------------------------- weeks ----

def parse_yw(yw):
    year, week = yw.split("-W")
    return int(year), int(week)


def yw_str(year, week):
    return f"{year}-W{week:02d}"


def weeks_in_year(year):
    return dt.date(year, 12, 28).isocalendar()[1]


def season_start(year, week):
    return year if week >= SEASON_START_WEEK else year - 1


def season_label(start):
    return f"{start}/{str(start + 1)[2:]}"


def season_weeks(start):
    weeks = [(start, w) for w in range(SEASON_START_WEEK, weeks_in_year(start) + 1)]
    return weeks + [(start + 1, w) for w in range(1, SEASON_START_WEEK)]


def week_monday(year, week):
    return dt.date.fromisocalendar(year, week, 1)


# --------------------------------------------------------------- series ----

def _pick(raw, file, **filters):
    df = raw[raw["file"] == file]
    for col, val in filters.items():
        df = df[df[col] == val]
    return df


def _by_country(df):
    out = {}
    for code, c in COUNTRIES.items():
        s = df[df["countryname"] == c["erviss"]].groupby("yearweek")["value"].sum(min_count=1)
        s = s.dropna()
        if not s.empty:
            out[code] = s.sort_index()
    return out


def extract_series(raw):
    """Return {indicator: {country_code: Series indexed by 'YYYY-Www'}} plus sentinel test counts."""
    flu_total = dict(pathogentype="Influenza", pathogensubtype="total")
    lab = _pick(raw, "nonSentinelTestsDetections", age="total", **flu_total)
    lab_det = _by_country(lab[lab["indicator"] == "detections"])
    lab_tests = _by_country(lab[lab["indicator"] == "tests"])

    positivity = {}
    for code, det in lab_det.items():
        tests = lab_tests.get(code)
        if tests is None:
            continue
        joined = pd.concat([det, tests], axis=1, keys=["d", "t"]).dropna()
        joined = joined[joined["t"] > 0]
        if not joined.empty:
            positivity[code] = (joined["d"] / joined["t"] * 100).round(1)

    sent = _pick(raw, "sentinelTestsDetectionsPositivity", **flu_total)
    ili = _pick(raw, "ILIARIRates", indicator="ILIconsultationrate", age="total")
    sev = _pick(raw, "nonSentinelSeverity", pathogentype="Influenza", age="total")

    series = {
        "lab_cases": lab_det,
        "lab_positivity": positivity,
        "sentinel_positivity": _by_country(sent[sent["indicator"] == "positivity"]),
        "ili_rate": _by_country(ili),
        "icu": _by_country(sev[sev["indicator"] == "ICUadmissions"]),
        "deaths": _by_country(sev[sev["indicator"] == "deaths"]),
    }
    sentinel_tests = _by_country(sent[sent["indicator"] == "tests"])
    return series, sentinel_tests


def latest_week(series):
    return max(s.index.max() for by_c in series.values() for s in by_c.values())


# ---------------------------------------------------------- comparisons ----

def align_season(s, start, current_weeks):
    """Values of season `start` aligned to the week positions of the current season."""
    values = s.to_dict()
    has_w53 = weeks_in_year(start) == 53
    out = []
    for _, week in current_weeks:
        w = 52 if week == 53 and not has_w53 else week
        year = start if w >= SEASON_START_WEEK else start + 1
        v = values.get(yw_str(year, w))
        out.append(None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v))
    return out


def classify_intensity(value, peak_mean):
    if peak_mean is None or peak_mean <= 0 or value is None:
        return None
    ratio = value / peak_mean
    for limit, label in INTENSITY_LEVELS:
        if ratio < limit:
            return label
    return INTENSITY_LEVELS[-1][1]


def _stats(values):
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return None, None, None
    return sum(vals) / len(vals), min(vals), max(vals)


def _pct(a, b):
    if a is None or b is None or b == 0:
        return None
    return round((a - b) / b * 100, 1)


def analyse_series(s, kind, cur_start, current_weeks, global_latest, tests=None):
    seasons = {}
    for start in range(season_start(*parse_yw(s.index.min())), cur_start):
        aligned = align_season(s, start, current_weeks)
        if sum(v is not None for v in aligned) >= MIN_WEEKS_FOR_SEASON:
            seasons[season_label(start)] = aligned
    current = align_season(s, cur_start, current_weeks)
    hist = list(seasons.values())

    band = {"mean": [], "min": [], "max": []}
    for i in range(len(current_weeks)):
        mean, lo, hi = _stats([h[i] for h in hist])
        band["mean"].append(None if mean is None else round(mean, 2))
        band["min"].append(lo)
        band["max"].append(hi)

    reported = [i for i, v in enumerate(current) if v is not None]
    result = {
        "seasons": {**seasons, season_label(cur_start): current},
        "band": band,
        "summary": None,
    }
    if not reported:
        return result

    i = reported[-1]
    year, week = current_weeks[i]
    value = current[i]
    prev = current[i - 1] if i > 0 else s.get(yw_str(*_prev_week(year, week)))
    prev = None if prev is None else float(prev)
    mean, lo, hi = band["mean"][i], band["min"][i], band["max"][i]
    peaks = [max(v for v in h if v is not None) for h in hist]
    peak_weeks = [current_weeks[h.index(p)][1] for h, p in zip(hist, peaks)]
    peak_mean = sum(peaks) / len(peaks) if peaks else None

    if mean is None:
        position = None
    elif value > hi:
        position = "over"
    elif value < lo:
        position = "under"
    else:
        position = "innenfor"

    summary = {
        "week": yw_str(year, week),
        "value": value,
        "prev": prev,
        "wow_pct": _pct(value, prev),
        "hist_mean": mean,
        "hist_min": lo,
        "hist_max": hi,
        "hist_by_season": {k: v[i] for k, v in seasons.items()},
        "index": None if not mean else round(value / mean * 100),
        "diff_pct": _pct(value, mean),
        "position": position,
        "peak_mean": None if peak_mean is None else round(peak_mean, 1),
        "peaks": {k: {"value": p, "week": w} for k, p, w in zip(seasons, peaks, peak_weeks)},
        "intensity": classify_intensity(value, peak_mean),
        "stale": yw_str(year, week) != global_latest,
        "n_seasons": len(hist),
    }
    if kind == "count":
        cum = sum(v for v in current[: i + 1] if v is not None)
        hist_cum = {k: sum(x for x in v[: i + 1] if x is not None) for k, v in seasons.items()}
        cum_mean = sum(hist_cum.values()) / len(hist_cum) if hist_cum else None
        summary.update({
            "season_to_date": cum,
            "season_to_date_hist": hist_cum,
            "season_to_date_mean": None if cum_mean is None else round(cum_mean, 1),
            "season_to_date_index": None if not cum_mean else round(cum / cum_mean * 100),
        })
    if tests is not None:
        t = tests.get(yw_str(year, week))
        summary["tests"] = None if t is None else float(t)
        summary["low_tests"] = bool(t is not None and t < MIN_SENTINEL_TESTS)
    result["summary"] = summary
    return result


def _prev_week(year, week):
    if week > 1:
        return year, week - 1
    return year - 1, weeks_in_year(year - 1)


def subtype_breakdown(raw, cur_start, week):
    df = _pick(raw, "activityFluTypeSubtype", survtype="non-sentinel", indicator="detections", age="total")
    season = {yw_str(*w) for w in season_weeks(cur_start)}
    out = {}
    for code, c in COUNTRIES.items():
        d = df[df["countryname"] == c["erviss"]]
        this_week = d[d["yearweek"] == week].groupby("pathogensubtype")["value"].sum()
        to_date = d[d["yearweek"].isin(season) & (d["yearweek"] <= week)].groupby("pathogensubtype")["value"].sum()
        out[code] = {
            "week": {SUBTYPE_LABELS[k]: int(this_week.get(k, 0)) for k in SUBTYPES},
            "season": {SUBTYPE_LABELS[k]: int(to_date.get(k, 0)) for k in SUBTYPES},
        }
    return out


# ------------------------------------------------------------- findings ----

def fmt_num(v, decimals=0):
    if v is None:
        return "–"
    s = f"{v:,.{decimals}f}"
    return s.replace(",", " ").replace(".", ",")


def fmt_pct(v, signed=True):
    if v is None:
        return "–"
    sign = "+" if signed and v > 0 else ""
    return f"{sign}{fmt_num(v, 0)} %".replace("-", "−")


def findings(result):
    """Plain Norwegian sentences describing this week's situation."""
    out = []
    for code, c in COUNTRIES.items():
        ind = result["summary"].get(code, {})
        lab = ind.get("lab_cases")
        if not lab:
            continue
        sentence = f"{c['name']}: {fmt_num(lab['value'])} laboratoriebekreftede tilfeller i uke {parse_yw(lab['week'])[1]}"
        if lab["wow_pct"] is not None:
            sentence += f" ({fmt_pct(lab['wow_pct'])} fra uka før)"
        sentence += "."
        if lab["hist_mean"]:
            direction = "over" if lab["diff_pct"] >= 0 else "under"
            sentence += (
                f" Det er {fmt_num(abs(lab['diff_pct']))} % {direction} snittet for samme uke"
                f" i de {lab['n_seasons']} foregående sesongene (indeks {lab['index']})"
            )
            if lab["position"] == "over":
                sentence += ", og høyere enn i alle tidligere sesonger"
            elif lab["position"] == "under":
                sentence += ", og lavere enn i alle tidligere sesonger"
            sentence += "."
        if lab.get("intensity"):
            sentence += f" Intensitet: {lab['intensity'].lower()}."
        out.append(sentence)

    for code, c in COUNTRIES.items():
        sp = result["summary"].get(code, {}).get("sentinel_positivity")
        if sp and not sp.get("low_tests") and sp["value"] >= SENTINEL_EPIDEMIC_THRESHOLD:
            out.append(
                f"{c['name']} er over ECDCs epidemiske terskel: {fmt_num(sp['value'], 1)} % positive"
                f" sentinel-prøver i uke {parse_yw(sp['week'])[1]}."
            )

    ranked = [
        (result["summary"][code]["lab_cases"]["index"], COUNTRIES[code]["name"])
        for code in COUNTRIES
        if result["summary"].get(code, {}).get("lab_cases", {}).get("index") is not None
    ]
    if len(ranked) > 1:
        top = max(ranked)
        out.append(f"Høyest nivå mot historikk: {top[1]} (indeks {top[0]}, der 100 = historisk snitt).")

    totals = {}
    for code in COUNTRIES:
        for k, v in result["subtypes"].get(code, {}).get("season", {}).items():
            totals[k] = totals.get(k, 0) + v
    typed = {k: v for k, v in totals.items() if "ikke" not in k}
    if sum(typed.values()) >= 10:
        dom = max(typed, key=typed.get)
        share = typed[dom] / sum(typed.values()) * 100
        out.append(
            f"Dominerende virus hittil i sesongen (subtypede prøver, alle tre land): {dom} ({fmt_num(share)} %)."
        )
    return out


# ----------------------------------------------------------------- main ----

def analyse(raw, now=None):
    series, sentinel_tests = extract_series(raw)
    latest = latest_week(series)
    cur_start = season_start(*parse_yw(latest))
    weeks = season_weeks(cur_start)
    latest_year, latest_wk = parse_yw(latest)

    result = {
        "generated_at": (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "latest_week": latest,
        "latest_week_start": week_monday(latest_year, latest_wk).isoformat(),
        "season": season_label(cur_start),
        "season_weeks": [f"U{w}" for _, w in weeks],
        "season_week_keys": [yw_str(*w) for w in weeks],
        "countries": {k: {x: c[x] for x in ("name", "authority", "url")} for k, c in COUNTRIES.items()},
        "indicators": INDICATORS,
        "series": {},
        "summary": {},
        "source": {
            "name": "ECDC ERVISS – European Respiratory Virus Surveillance Summary",
            "url": "https://erviss.org/",
            "data": "https://github.com/EU-ECDC/Respiratory_viruses_weekly_data",
            "note": "Data rapporteres ukentlig av FHI, Folkhälsomyndigheten og SSI til ECDC. Tallene kan bli revidert i etterkant.",
        },
    }

    latest_dt = parse_yw(latest)
    for key, meta in INDICATORS.items():
        for code, s in series[key].items():
            # Skip indicators that a country has stopped reporting.
            last = parse_yw(s.index.max())
            if (week_monday(*latest_dt) - week_monday(*last)).days > 8 * 7:
                continue
            tests = sentinel_tests.get(code) if key == "sentinel_positivity" else None
            r = analyse_series(s, meta["kind"], cur_start, weeks, latest, tests)
            result["series"].setdefault(code, {})[key] = {"seasons": r["seasons"], "band": r["band"]}
            if r["summary"]:
                result["summary"].setdefault(code, {})[key] = r["summary"]

    result["subtypes"] = subtype_breakdown(raw, cur_start, latest)
    result["findings"] = findings(result)
    return result
