# Flu, COVID-19 & RSV tracker – Norway, Sweden and Denmark

A weekly status of influenza, COVID-19 and RSV in the Nordics, in Karo Healthcare design. It is published three ways, each
compared with previous seasons:

* a **dashboard** (GitHub Pages, `docs/index.html`)
* an **Outlook-compatible HTML e-mail**, downloadable from the dashboard (`docs/data/email_latest.html`, archived in
  `reports/YYYY-Www.html`). It is a one-screen executive summary: a short headline, the year-by-year chart (PNG in
  `docs/data/charts/`, embedded in the sent e-mail), a virus × country snapshot with the Nordic total and intensity, a
  short explanation of intensity, and the key points. The detail lives on the dashboard and in Excel
* an **Excel workbook** to download (`docs/data/flutracker_latest.xlsx`, archived in `reports/YYYY-Www.xlsx`),
  including a **sales tool** for correlation and forecasting

## Data source

The data comes from **ECDC's European Respiratory Virus Surveillance Summary (ERVISS)**
([erviss.org](https://erviss.org/), [open data](https://github.com/EU-ECDC/Respiratory_viruses_weekly_data)).
ECDC (the European Centre for Disease Prevention and Control) is the EU agency for disease surveillance. ERVISS holds the
weekly figures that each national public health institute reports to ECDC:

| Country | Reporting institute | National weekly report |
|---|---|---|
| Norway | Norwegian Institute of Public Health (FHI) | [fhi.no](https://www.fhi.no/tema/influensa/overvaakingssystemet) · [statistikk.fhi.no](https://statistikk.fhi.no/) |
| Sweden | Public Health Agency of Sweden (Folkhälsomyndigheten) | [Lägesrapport luftvägsvirus](https://www.folkhalsomyndigheten.se/statistik-och-data/lagesrapporter/luftvagsvirus-lagesrapporter/aktuell-lagesrapport-om-luftvagsvirus/) |
| Denmark | Statens Serum Institut (SSI) | [Overvågning af luftvejssygdomme](https://www.ssi.dk/sygdomme-beredskab-og-forskning/overvaagning-af-luftvejssygdomme) |

Using ERVISS gives one consistent, documented format for all three countries. ECDC publishes it every Friday, and
the full history is re-downloaded each week because recent weeks can be revised.

### Indicators (season 2026/27)

| Group | Indicator | NO | SE | DK |
|---|---|:-:|:-:|:-:|
| Influenza | Lab-confirmed cases, test positivity, sentinel GP positivity | ✓ | ✓ | ✓ |
| Influenza | Influenza-like illness (ILI) GP consultations per 100,000 | ✓ | – | ✓ |
| Influenza | Virus types (A(H1N1), A(H3N2), B) | ✓ | ✓ | ✓ |
| COVID-19 | Lab-confirmed cases, test positivity, sentinel GP positivity | ✓ | ✓ | ✓ |
| RSV | Lab-confirmed cases, test positivity, sentinel GP positivity | ✓ | ✓ | ✓ |
| Hospital & severity | Deaths with influenza / COVID-19 | – | ✓ | – |
| Hospital & severity | Hospital admissions, ICU admissions, SARI hospitalisations | supported, shown when reported to ECDC |

Norway and Denmark do not currently report hospital admissions to ECDC, and Sweden's ICU reporting has been paused since
April 2026. The tracker shows any of these automatically as soon as they appear in ERVISS, and links to the national
reports in the meantime. History starts with the 2022/23 season. Norway's laboratory RSV figures start in 2024/25 (Sweden's RSV sentinel figures too), so those
are compared with fewer seasons.

### Year by year and last 12 months

* **Year by year** (dashboard and e-mail): weekly lab-confirmed cases from January to December, one line per calendar
  year, for influenza, COVID-19 and RSV, per country and for the Nordics.
* **Last 12 months** (dashboard and Excel): the three viruses in one chart for the last 52 weeks.

The Nordic total is only given for weeks in which all three countries reported. Weeks a country did not report (for
example Sweden's RSV in summer) are left as gaps.

## Leading markets (ahead of the Nordics)

Influenza in some markets runs ahead of the Nordic season, so the dashboard, e-mail and Excel workbook (sheet
*Leading markets*) also follow them:

| Type | Markets | What it tells us |
|---|---|---|
| Southern hemisphere | Australia, New Zealand, Chile, South Africa | Their winter season (May–September) is over before the Nordic one starts. How big it was, and which virus dominated, is a first hint of the Nordic winter. |
| Early-season markets | Japan, United States, Canada, United Kingdom | Same season as the Nordics, but often a few weeks earlier. When they cross the threshold, the Nordics usually follow. |

The data comes from **WHO FluNet** ([who.int/tools/flunet](https://www.who.int/tools/flunet)), where every country's
National Influenza Centre reports its weekly influenza tests and positives to WHO (GISRS). One API gives one format for
all markets (`FLUNET_URL` in `flutracker/config.py`); the rows are saved in `data/flunet_leading.csv`, and if WHO cannot
be reached that copy is used so the weekly run never fails because of it.

* **Measure:** influenza test positivity (positives ÷ specimens tested, all surveillance systems summed). Case counts are
  not used because testing differs a lot between countries and years.
* **Southern hemisphere** (season = calendar year): peak positivity and peak week, intensity of the peak against the
  average peak of earlier years, weeks at or above 10% positivity, dominant virus and whether the season is over.
* **Early-season markets** (season week 40–39): this week against the same week in earlier seasons, intensity, the week
  positivity crossed 10% this season and the week it usually does. The Nordic countries' own lab positivity is shown
  alongside for comparison.
* 2020 and 2021 (2020/21 and 2021/22) are left out of the history: COVID-19 measures suppressed influenza.
* 10% positivity is a rough sign that a season is under way. This is an early hint, not a forecast – the link between
  the southern-hemisphere season and the Nordic one varies from year to year.

Markets are configured in `LEADING_MARKETS` in `flutracker/config.py` (any FluNet country code can be added).

## How the comparison with history works

* **Season:** week 40 to week 39.
* **Historical average / min / max:** the same ISO week in every previous season with at least 20 weeks of data
  (week 53 is compared with week 52).
* **Level:** above the historical maximum, within the range, or below the historical minimum.
* **Intensity:** this week against the average of previous season peaks (see below).
* **Season to date:** cumulative cases since week 40, against previous seasons summed to the same week.
* **Epidemic threshold:** sentinel positivity ≥ 10% (ECDC). Weeks with fewer than 20 sentinel samples are flagged.

### Intensity

Intensity shows how big this week is compared with the top of a typical season. It is calculated for every country
and indicator:

1. For each previous season (week 40 to 39) with at least 20 weeks of data, take the highest weekly value – that
   season's peak.
2. Average those peaks.
3. Divide this week's value by the average peak.
4. Classify the ratio:

| Ratio of the average peak | Intensity |
|---|---|
| under 10% | Baseline |
| 10% to under 40% | Low |
| 40% to under 70% | Medium |
| 70% to under 100% | High |
| 100% or more | Very high |

Example: 171 cases this week, with previous season peaks of 1,800, 2,400 and 1,950, gives an average peak of 2,050.
171 / 2,050 = 8%, so intensity is *baseline*.

Intensity shows how close we are to a normal season peak. With few previous seasons the average peak
is less reliable (RSV in Norway rests on two). ECDC and the national institutes publish intensity levels with their
own methods, so their labels can differ. The thresholds are `INTENSITY_LEVELS` in `flutracker/config.py`; the
dashboard has a worked example for every indicator.

In the Excel workbook, change, level, intensity and the historical average/min/max are live formulas.

## Sales tool in the Excel workbook

The workbook has a weekly and a monthly version of the same four sheets:

| Sheet | What it does |
|---|---|
| **Sales input** | Yellow cells: paste sales per country (units or NOK), one row per week (`2025-W45`) or month (`2025-11`). |
| **Correlation** | Pearson correlation of sales with every driver (flu cases, flu positivity, sentinel positivity, ILI, COVID-19 cases and positivity, RSV cases and positivity), at lags of 0–8 weeks or 0–3 months. Shows the best combination per country. |
| **Sales vs flu** | Pick a driver and lag per country. The sheet shows n, r, R², slope, intercept and standard error, and fits `sales = intercept + slope × driver`. It then forecasts the next 12 weeks or 3 months with a 95% band, plus a chart of sales against the fit. |
| **Flu by week / month** | The drivers per country. Forecast periods use the historical average for that week × the **flu scenario** (100% = a normal season; e.g. 130% for a heavy season). |

Everything after the input is an Excel formula, so the workbook recalculates as soon as sales are pasted in.
Monthly flu values assign each ISO week to the month of its Thursday; counts are summed and rates averaged.
At least 12 periods of sales are needed before the strength of the relationship is reported. Correlation shows
co-movement, not cause and effect.

**Sales data is confidential and must not be committed to this public repository.** Paste it into a downloaded
copy, or build a pre-filled workbook locally (files with `sales` in the name are git-ignored):

```bash
# my_sales.csv: columns country (Norway/NO…), week (2025-W45) or month (2025-11), sales
python -m flutracker excel --sales my_sales.csv --out flutracker_with_sales.xlsx
```

## Layout

```
flutracker/        Python package: fetch → analysis (+ leading) → emailer / excel (+ sales sheets)
docs/index.html    Dashboard (GitHub Pages), reads docs/data/flu.json
docs/data/         flu.json, flutracker_latest.xlsx and email_latest.html (the downloads)
data/              Nordic rows from ERVISS, leading markets from FluNet + state.json (last week e-mailed)
reports/           Each week's e-mail (HTML) and workbook (XLSX)
```

## Running locally

```bash
pip install -r requirements.txt
python -m flutracker all            # fetch data, analyse, write dashboard data, Excel and e-mail
python -m flutracker all --send     # ... and send the e-mail over SMTP with the Excel attached
python -m pytest
```

## Weekly automation

`.github/workflows/weekly.yml` runs on Fridays at 15:23 UTC (with a retry on Saturday morning). It refreshes the
data, commits the results and sends the e-mail once per new data week. It can also be started by hand under *Actions*.
It only runs from the default branch, so this work has to be merged into `main` first.

Setup:

1. **Dashboard:** *Settings → Pages → Build and deployment → Deploy from a branch*, branch `main`, folder **`/docs`**.
   The dashboard is then at `https://eirikwikheltne.github.io/flutracker/`. If the address is different, update
   `DASHBOARD_URL` in `flutracker/config.py`.
2. **E-mail:** add the repository secrets `SMTP_HOST`, `SMTP_PORT` (587 or 465), `SMTP_USER`, `SMTP_PASSWORD`,
   `MAIL_FROM` and `MAIL_TO` (comma-separated). For Office 365: `smtp.office365.com`, port 587. Without them the e-mail
   is still built in `reports/` but not sent.
