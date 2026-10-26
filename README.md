# Flu & COVID-19 tracker – Norway, Sweden and Denmark

A weekly status of influenza and COVID-19 in the Nordics, in Karo Healthcare design. It is published three ways, each
compared with previous seasons:

* a **dashboard** (GitHub Pages, `docs/index.html`)
* an **Outlook-compatible HTML e-mail** with the week's findings (`reports/`)
* an **Excel workbook** to download (`docs/data/flutracker_latest.xlsx`, archived in `reports/YYYY-Www.xlsx`)

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
| Hospital & severity | Deaths with influenza / COVID-19 | – | ✓ | – |
| Hospital & severity | Hospital admissions, ICU admissions, SARI hospitalisations | supported, shown when reported to ECDC |

Norway and Denmark do not currently report hospital admissions to ECDC, and Sweden's ICU reporting has been paused since
April 2026. The tracker shows any of these automatically as soon as they appear in ERVISS, and links to the national
reports in the meantime. History starts with the 2022/23 season.

## How the comparison with history works

* **Season:** week 40 to week 39.
* **Historical average / min / max:** the same ISO week in every previous season with at least 20 weeks of data
  (week 53 is compared with week 52).
* **Index** = this week / historical average × 100 (100 = normal for the time of year).
* **Level:** above the historical maximum, within the range, or below the historical minimum.
* **Intensity:** this week against the average of previous season peaks: below 10% baseline, 10–40% low,
  40–70% medium, 70–100% high, above 100% very high.
* **Season to date:** cumulative cases since week 40, against previous seasons summed to the same week.
* **Epidemic threshold:** sentinel positivity ≥ 10% (ECDC). Weeks with fewer than 20 sentinel samples are flagged.

In the Excel workbook, change, index, level, intensity and the historical average/min/max are live formulas.

## Layout

```
flutracker/        Python package: fetch → analysis → emailer / excel
docs/index.html    Dashboard (GitHub Pages), reads docs/data/flu.json
docs/data/         flu.json and flutracker_latest.xlsx
data/              Nordic rows from ERVISS + state.json (last week e-mailed)
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
