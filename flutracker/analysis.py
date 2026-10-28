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
        "position": position,
        "peak_mean": None if peak_mean is None else round(peak_mean, 1),
        "peaks": {k: {"value": p, "week": w} for k, p, w in zip(seasons, peaks, peak_weeks)},
        "intensity": classify_intensity(value, peak_mean),
        "intensity_pct": None if not peak_mean else round(value / peak_mean * 100),
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


def yearly(series):
    """Weekly cases per calendar year (ISO weeks 1–53), per country and for the Nordics."""
    areas = {"ALL": nordic_series(series)}
    for code in COUNTRIES:
        areas[code] = {k: series[k][code] for k in RECENT_KEYS if code in series[k]}
    years = sorted({int(w[:4]) for a in areas.values() for s in a.values() for w in s.index})
    out = {"years": years, "weeks": list(range(1, 54)), "areas": {}}
    for area, by_key in areas.items():
        out["areas"][area] = {}
        for key, s in by_key.items():
            values = s.to_dict()
            out["areas"][area][key] = {
                str(y): [None if (v := values.get(yw_str(y, w))) is None else float(v) for w in range(1, 54)]
                for y in years
            }
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


def _intensity_text(s):
    if not s.get("intensity"):
        return ""
    return f" Intensity: {s['intensity'].lower()} ({fmt_num(s['intensity_pct'])}% of an average season peak)."


def _case_sentence(name, s, what):
    text = f"{name}: {fmt_num(s['value'])} {what} in week {parse_yw(s['week'])[1]}"
    if s["wow_pct"] is not None:
        text += f" ({fmt_pct(s['wow_pct'])} on the week before)"
    return text + "." + _intensity_text(s)


def _threshold_points(summary):
    out = []
    for code, c in COUNTRIES.items():
        sp = summary.get(code, {}).get("flu_sentinel")
        if sp and not sp.get("low_tests") and sp["value"] >= SENTINEL_EPIDEMIC_THRESHOLD:
            out.append(
                f"{c['name']} is above ECDC's epidemic threshold: {fmt_num(sp['value'], 1)}% of sentinel"
                f" samples were positive for influenza in week {parse_yw(sp['week'])[1]}."
            )
    return out


def _ranking_points(summary):
    ranked = [(summary[c]["flu_cases"]["intensity_pct"], COUNTRIES[c]["name"])
              for c in COUNTRIES if summary.get(c, {}).get("flu_cases", {}).get("intensity_pct") is not None]
    if len(ranked) < 2:
        return []
    top = max(ranked)
    return [f"Highest influenza level: {top[1]}, at {fmt_num(top[0])}% of an average season peak."]


def _dominant_points(result):
    totals = {}
    for code in COUNTRIES:
        for k, v in result["subtypes"].get(code, {}).get("season", {}).items():
            totals[k] = totals.get(k, 0) + v
    typed = {k: v for k, v in totals.items() if "not " not in k}
    if sum(typed.values()) < 10:
        return []
    dom = max(typed, key=typed.get)
    share = typed[dom] / sum(typed.values()) * 100
    return [f"Dominant influenza virus so far this season (subtyped samples, all three countries): {dom} ({fmt_num(share)}%)."]


def _hospital_points(summary):
    hospital = []
    for code, c in COUNTRIES.items():
        for key, meta in INDICATORS.items():
            s = summary.get(code, {}).get(key)
            if meta["group"] == "Hospital & severity" and s:
                label = meta["label"][0].lower() + meta["label"][1:]
                hospital.append(f"{c['name']} {fmt_num(s['value'], meta['decimals'])} {label}")
    return ["Hospital and severity this week: " + "; ".join(hospital) + "."] if hospital else []


def findings(result):
    """Plain English sentences describing this week's situation."""
    summary = result["summary"]
    out = []
    for code, c in COUNTRIES.items():
        s = summary.get(code, {}).get("flu_cases")
        if s:
            out.append(_case_sentence(c["name"], s, "lab-confirmed influenza cases"))

    out += _threshold_points(summary) + _ranking_points(summary) + _dominant_points(result)

    for key, name in (("covid_cases", "COVID-19"), ("rsv_cases", "RSV")):
        parts = []
        for code, c in COUNTRIES.items():
            s = summary.get(code, {}).get(key)
            if s:
                level = f", {s['intensity'].lower()}" if s.get("intensity") else ""
                parts.append(f"{c['name']} {fmt_num(s['value'])} ({fmt_pct(s['wow_pct'])}{level})")
        if parts:
            out.append(f"{name}, lab-confirmed cases this week: " + "; ".join(parts) + ".")

    return out + _hospital_points(summary)


# ------------------------------------------------------ executive summary ----

SNAPSHOT_KEYS = RECENT_KEYS


def nordic_series(series):
    """Weekly sum over the three countries, only for weeks in which all of them reported."""
    out = {}
    for key in RECENT_KEYS:
        per_country = [series[key].get(c) for c in COUNTRIES]
        if any(s is None for s in per_country):
            continue
        joined = pd.concat(per_country, axis=1).dropna()
        if not joined.empty:
            out[key] = joined.sum(axis=1).sort_index()
    return out


def _trend_word(wow):
    if wow is None:
        return "no change data"
    if wow >= 10:
        return f"up {fmt_num(wow)}%"
    if wow <= -10:
        return f"down {fmt_num(abs(wow))}%"
    return "stable"


def _level_text(s):
    if not s.get("intensity"):
        return ""
    return f"{s['intensity'].lower()} intensity ({fmt_num(s['intensity_pct'])}% of an average season peak)"


def headline(result):
    """Two or three short sentences for the top of the executive summary."""
    summary, nordic = result["summary"], result["nordic"]
    out = []
    flu = nordic.get("flu_cases")
    if flu and flu["week"] == result["latest_week"]:
        text = (f"Influenza: {fmt_num(flu['value'])} lab-confirmed cases in the Nordics this week, "
                f"{_trend_word(flu['wow_pct'])} on last week")
        if flu.get("intensity"):
            text += f" – {_level_text(flu)}"
        out.append(text + ".")
    above = [COUNTRIES[c]["name"] for c in COUNTRIES
             if (sp := summary.get(c, {}).get("flu_sentinel")) and not sp.get("low_tests")
             and sp["value"] >= SENTINEL_EPIDEMIC_THRESHOLD]
    if above:
        out.append(f"{' and '.join(above)} {'is' if len(above) == 1 else 'are'} above ECDC's epidemic threshold.")
    others = []
    for key, name in (("covid_cases", "COVID-19"), ("rsv_cases", "RSV")):
        n = nordic.get(key)
        if n and n["week"] == result["latest_week"]:
            level = f", {n['intensity'].lower()} intensity" if n.get("intensity") else ""
            others.append(f"{name} {fmt_num(n['value'])} cases ({_trend_word(n['wow_pct'])}{level})")
    if others:
        out.append("Nordics: " + "; ".join(others) + ".")
    return out


def key_points(result):
    """The few findings worth an executive's attention; the dashboard has the rest."""
    summary = result["summary"]
    return _ranking_points(summary) + _dominant_points(result) + _hospital_points(summary)


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

    result["nordic"] = {}
    for key, s in nordic_series(series).items():
        r = analyse_series(s, INDICATORS[key]["kind"], cur_start, weeks, latest)
        if r["summary"]:
            result["nordic"][key] = r["summary"]
    result["recent"] = recent_weeks(series, latest)
    result["yearly"] = yearly(series)
    result["subtypes"] = subtype_breakdown(raw, cur_start, latest)
    result["findings"] = findings(result)
    result["headline"] = headline(result)
    result["key_points"] = key_points(result)
    return result
