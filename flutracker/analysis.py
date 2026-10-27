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
    GROUPS,
    INDICATORS,
    INTENSITY_LEVELS,
    MAX_STALE_WEEKS,
    MIN_SENTINEL_TESTS,
    RECENT_KEYS,
    RECENT_WEEKS,
    SEASON_START_WEEK,
    SENTINEL_EPIDEMIC_THRESHOLD,
    SOURCE,
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


def _positivity(det, tests):
    joined = pd.concat([det, tests], axis=1, keys=["d", "t"]).dropna()
    joined = joined[joined["t"] > 0]
    return None if joined.empty else (joined["d"] / joined["t"] * 100).round(1)


def _total_rows(raw, file, pathogen):
    """Rows for the pathogen total (influenza total, SARS-CoV-2 or RSV)."""
    sub = "total" if pathogen == "Influenza" else pathogen
    return _pick(raw, file, pathogentype=pathogen, pathogensubtype=sub)


def extract_series(raw):
    """Return ({indicator: {country: Series indexed by 'YYYY-Www'}}, {indicator: {country: sentinel tests}})."""
    series, sentinel_tests = {}, {}
    for key, meta in INDICATORS.items():
        kind, *args = meta["spec"]
        if kind in ("lab", "lab_pos"):
            lab = _total_rows(raw, "nonSentinelTestsDetections", args[0])
            lab = lab[lab["age"] == "total"]
            det = _by_country(lab[lab["indicator"] == "detections"])
            if kind == "lab":
                series[key] = det
            else:
                tests = _by_country(lab[lab["indicator"] == "tests"])
                pos = {c: _positivity(det[c], tests[c]) for c in det if c in tests}
                series[key] = {c: s for c, s in pos.items() if s is not None}
        elif kind in ("lab_type", "lab_type_pos"):
            typed = _pick(raw, "nonSentinelTestsDetections", pathogentype=args[0], indicator="detections", age="total")
            # ERVISS leaves out subtype rows with no detections, so a week in which the country
            # reported influenza but nothing of this type counts as 0.
            flu = _total_rows(raw, "nonSentinelTestsDetections", "Influenza")
            flu = _by_country(flu[(flu["age"] == "total") & (flu["indicator"] == "detections")])
            typed_by_country = _by_country(typed)
            det = {c: typed_by_country.get(c, pd.Series(dtype=float)).reindex(f.index).fillna(0.0)
                   for c, f in flu.items()}
            if kind == "lab_type":
                series[key] = det
            else:
                lab = _total_rows(raw, "nonSentinelTestsDetections", "Influenza")
                tests = _by_country(lab[(lab["age"] == "total") & (lab["indicator"] == "tests")])
                pos = {c: _positivity(det[c], tests[c]) for c in det if c in tests}
                series[key] = {c: s for c, s in pos.items() if s is not None}
        elif kind == "sentinel_pos":
            sent = _total_rows(raw, "sentinelTestsDetectionsPositivity", args[0])
            series[key] = _by_country(sent[sent["indicator"] == "positivity"])
            sentinel_tests[key] = _by_country(sent[sent["indicator"] == "tests"])
        elif kind == "ili":
            series[key] = _by_country(_pick(raw, "ILIARIRates", indicator="ILIconsultationrate", age="total"))
        elif kind == "sari":
            series[key] = _by_country(_pick(raw, "SARIRates", indicator="SARIrate", age="total"))
        elif kind == "severity":
            series[key] = _by_country(_pick(raw, "nonSentinelSeverity", pathogentype=args[0], indicator=args[1], age="total"))
    return series, sentinel_tests


def latest_week(series):
    return max(s.index.max() for key in ("flu_cases", "covid_cases") for s in series[key].values())


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
        position = "within"

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


def recent_weeks(series, latest, n=RECENT_WEEKS):
    """Lab-confirmed cases per virus for the last `n` weeks, per country and summed for the Nordics.

    The Nordic total is only given for weeks in which every country that reports the virus in
    the period has a value, so a missing report never shows up as a dip.
    """
    weeks = [latest]
    while len(weeks) < n:
        weeks.insert(0, yw_str(*_prev_week(*parse_yw(weeks[0]))))
    out = {"weeks": weeks, "countries": {}}
    for code in COUNTRIES:
        values = {}
        for key in RECENT_KEYS:
            s = series[key].get(code)
            vals = [None if s is None or s.get(w) is None else float(s[w]) for w in weeks]
            if any(v is not None for v in vals):
                values[key] = vals
        if values:
            out["countries"][code] = values
    nordic = {}
    for key in RECENT_KEYS:
        rows = [v[key] for v in out["countries"].values() if key in v]
        if rows:
            nordic[key] = [None if any(r[i] is None for r in rows) else sum(r[i] for r in rows) for i in range(n)]
    out["nordic"] = nordic
    return out


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
    return f"{v:,.{decimals}f}"


def fmt_pct(v, signed=True):
    if v is None:
        return "–"
    sign = "+" if signed and v > 0 else ""
    return f"{sign}{v:,.0f}%".replace("-", "−")


def _vs_history(s):
    if not s.get("hist_mean"):
        return ""
    direction = "above" if s["diff_pct"] >= 0 else "below"
    text = (f" That is {fmt_num(abs(s['diff_pct']))}% {direction} the average for the same week"
            f" in the previous {s['n_seasons']} seasons (index {s['index']})")
    if s["position"] == "over":
        text += ", and higher than in any previous season"
    elif s["position"] == "under":
        text += ", and lower than in any previous season"
    return text + "."


def _case_sentence(name, s, what):
    text = f"{name}: {fmt_num(s['value'])} {what} in week {parse_yw(s['week'])[1]}"
    if s["wow_pct"] is not None:
        text += f" ({fmt_pct(s['wow_pct'])} on the week before)"
    return text + "." + _vs_history(s)


def findings(result):
    """Plain English sentences describing this week's situation."""
    summary = result["summary"]
    out = []
    for code, c in COUNTRIES.items():
        s = summary.get(code, {}).get("flu_cases")
        if s:
            text = _case_sentence(c["name"], s, "lab-confirmed influenza cases")
            if s.get("intensity"):
                text += f" Intensity: {s['intensity'].lower()}."
            out.append(text)

    for code, c in COUNTRIES.items():
        sp = summary.get(code, {}).get("flu_sentinel")
        if sp and not sp.get("low_tests") and sp["value"] >= SENTINEL_EPIDEMIC_THRESHOLD:
            out.append(
                f"{c['name']} is above ECDC's epidemic threshold: {fmt_num(sp['value'], 1)}% of sentinel"
                f" samples were positive for influenza in week {parse_yw(sp['week'])[1]}."
            )

    ranked = [(summary[c]["flu_cases"]["index"], COUNTRIES[c]["name"])
              for c in COUNTRIES if summary.get(c, {}).get("flu_cases", {}).get("index") is not None]
    if len(ranked) > 1:
        top = max(ranked)
        out.append(f"Highest influenza level against history: {top[1]} (index {top[0]}, where 100 = historical average).")

    totals = {}
    for code in COUNTRIES:
        for k, v in result["subtypes"].get(code, {}).get("season", {}).items():
            totals[k] = totals.get(k, 0) + v
    typed = {k: v for k, v in totals.items() if "not " not in k}
    if sum(typed.values()) >= 10:
        dom = max(typed, key=typed.get)
        share = typed[dom] / sum(typed.values()) * 100
        out.append(f"Dominant influenza virus so far this season (subtyped samples, all three countries): {dom} ({fmt_num(share)}%).")

    split = []
    for code, c in COUNTRIES.items():
        a, b = (summary.get(code, {}).get(k) for k in ("flu_a_cases", "flu_b_cases"))
        if a or b:
            split.append(f"{c['name']} A {fmt_num(a['value'] if a else None)}, B {fmt_num(b['value'] if b else None)}")
    if split:
        out.append("Influenza A and B, lab-confirmed cases this week: " + "; ".join(split) + ".")

    for key, name in (("covid_cases", "COVID-19"), ("rsv_cases", "RSV")):
        parts = []
        for code, c in COUNTRIES.items():
            s = summary.get(code, {}).get(key)
            if s:
                idx = f", index {s['index']}" if s.get("index") is not None else ""
                parts.append(f"{c['name']} {fmt_num(s['value'])} ({fmt_pct(s['wow_pct'])}{idx})")
        if parts:
            out.append(f"{name}, lab-confirmed cases this week: " + "; ".join(parts) + ".")

    hospital = []
    for code, c in COUNTRIES.items():
        for key, meta in INDICATORS.items():
            s = summary.get(code, {}).get(key)
            if meta["group"] == "Hospital & severity" and s:
                label = meta["label"][0].lower() + meta["label"][1:]
                hospital.append(f"{c['name']} {fmt_num(s['value'], meta['decimals'])} {label}")
    if hospital:
        out.append("Hospital and severity this week: " + "; ".join(hospital) + ".")
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
        "season_weeks": [f"W{w}" for _, w in weeks],
        "season_week_keys": [yw_str(*w) for w in weeks],
        "countries": {k: {x: c[x] for x in ("name", "authority", "url", "data_url")} for k, c in COUNTRIES.items()},
        "indicators": {k: {x: v for x, v in m.items() if x != "spec"} for k, m in INDICATORS.items()},
        "groups": GROUPS,
        "series": {},
        "summary": {},
        "source": SOURCE,
    }

    latest_dt = parse_yw(latest)
    for key, meta in INDICATORS.items():
        for code, s in series[key].items():
            # Skip indicators that a country has stopped reporting.
            last = parse_yw(s.index.max())
            if (week_monday(*latest_dt) - week_monday(*last)).days > MAX_STALE_WEEKS * 7:
                continue
            tests = sentinel_tests.get(key, {}).get(code)
            r = analyse_series(s, meta["kind"], cur_start, weeks, latest, tests)
            result["series"].setdefault(code, {})[key] = {"seasons": r["seasons"], "band": r["band"]}
            if r["summary"]:
                result["summary"].setdefault(code, {})[key] = r["summary"]

    result["recent"] = recent_weeks(series, latest)
    result["subtypes"] = subtype_breakdown(raw, cur_start, latest)
    result["findings"] = findings(result)
    return result
