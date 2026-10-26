# Influensatracker – Norge, Sverige og Danmark

Ukentlig influensastatus for Norden i Karo Healthcare-design: et dashboard (GitHub Pages) og en
Outlook-kompatibel HTML-e-post med ukens funn, begge sammenlignet med tidligere sesonger.

## Datakilde

Data hentes fra **ECDC ERVISS** ([erviss.org](https://erviss.org/),
[rådata på GitHub](https://github.com/EU-ECDC/Respiratory_viruses_weekly_data)). Dette er de ukentlige
overvåkingsdataene som **Folkehelseinstituttet (FHI)**, **Folkhälsomyndigheten** og **Statens Serum Institut (SSI)**
rapporterer til ECDC, i ett felles format. ERVISS oppdateres hver fredag. Tall kan bli revidert bakover, så hele
historikken hentes på nytt hver uke.

| Indikator | Norge | Sverige | Danmark |
|---|:-:|:-:|:-:|
| Laboratoriebekreftede tilfeller | ✓ | ✓ | ✓ |
| Andel positive prøver (lab.bekreftede / testede) | ✓ | ✓ | ✓ |
| Sentinel-positivitet (primærhelsetjenesten) | ✓ | ✓ | ✓ |
| ILI-konsultasjoner per 100 000 | ✓ | – | ✓ |
| Intensivinnleggelser / dødsfall | – | ✓ (når rapportert) | – |
| Virustyper (A(H1N1), A(H3N2), B) | ✓ | ✓ | ✓ |

Historikk finnes fra sesongen 2022/23.

## Beregning mot historikk

* **Sesong:** uke 40 til uke 39.
* **Historisk snitt / min / maks:** samme ISO-uke i alle tidligere sesonger med minst 20 uker data
  (uke 53 sammenlignes med uke 52).
* **Indeks** = ukens verdi / historisk snitt × 100 (100 = normalt for uka).
* **Nivå:** over historisk maks, innenfor spennet, eller under historisk min.
* **Intensitet:** ukens verdi mot snittet av tidligere sesongtopper — under 10 % basisnivå, 10–40 % lav,
  40–70 % moderat, 70–100 % høy, over 100 % svært høy.
* **Sesongen hittil:** akkumulerte tilfeller fra uke 40, mot samme periode i tidligere sesonger.
* **Epidemisk terskel:** sentinel-positivitet ≥ 10 % (ECDC). Uker med færre enn 20 sentinel-prøver markeres.

## Struktur

```
flutracker/        Python-pakken (fetch → analysis → emailer)
docs/index.html    Dashboard (GitHub Pages), leser docs/data/flu.json
docs/data/flu.json Siste beregning
data/              Nordiske influensarader fra ERVISS + state.json (siste sendte e-postuke)
reports/           Ukens e-post som HTML (YYYY-Www.html og latest.html)
```

## Kjøre lokalt

```bash
pip install -r requirements.txt
python -m flutracker all            # hent data, beregn, skriv dashboard-data og e-post
python -m flutracker all --send     # ... og send e-posten over SMTP
python -m pytest
```

## Ukentlig automatisering

`.github/workflows/weekly.yml` kjører fredag 15:23 UTC (med ny sjekk lørdag morgen), oppdaterer data,
committer endringene og sender e-posten én gang per ny datauke. Den kan også kjøres manuelt under *Actions*.

Oppsett:

1. **E-post:** legg inn repository secrets `SMTP_HOST`, `SMTP_PORT` (587 eller 465), `SMTP_USER`,
   `SMTP_PASSWORD`, `MAIL_FROM` og `MAIL_TO` (kommaseparert). For Office 365: `smtp.office365.com`, port 587.
   Uten disse bygges e-posten fortsatt i `reports/`, men sendes ikke.
2. **Dashboard:** *Settings → Pages → Deploy from a branch*, velg `main` og mappen `/docs`.
   Oppdater `DASHBOARD_URL` i `flutracker/config.py` hvis adressen blir en annen.
