"""Command line: python -m flutracker [update|email|all|excel] ..."""

import argparse
import json
import pathlib
import shutil
import sys

import pandas as pd

from . import analysis, charts, emailer, excel, fetch, leading, sales
from .config import ERVISS_BASE, EXCEL_NAME, FLUNET_URL

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_JSON = ROOT / "docs" / "data" / "flu.json"
EXCEL = ROOT / "docs" / "data" / EXCEL_NAME
EMAIL_HTML = ROOT / "docs" / "data" / "email_latest.html"
CHARTS = ROOT / "docs" / "data" / "charts"  # weekly e-mail charts, published with the dashboard
RAW_CSV = ROOT / "data" / "erviss_nordic.csv"
FLUNET_CSV = ROOT / "data" / "flunet_leading.csv"
STATE = ROOT / "data" / "state.json"
REPORTS = ROOT / "reports"


def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save_state(state):
    STATE.write_text(json.dumps(state, indent=2) + "\n")


def load_flunet(url):
    """FluNet data for the leading markets; falls back to last week's copy if WHO cannot be reached."""
    flunet = leading.fetch_flunet(url)
    have = set(flunet["market"])
    if FLUNET_CSV.exists():
        cached = pd.read_csv(FLUNET_CSV)
        missing = cached[~cached["market"].isin(have)]
        if not missing.empty:
            print(f"FluNet: using the saved copy for {', '.join(sorted(set(missing['market'])))}")
            flunet = pd.concat([flunet, missing], ignore_index=True)
    if not flunet.empty:
        flunet.sort_values(["market", "yearweek"]).to_csv(FLUNET_CSV, index=False)
    return flunet


def cmd_update(args):
    raw = fetch.fetch_erviss(args.source)
    RAW_CSV.parent.mkdir(parents=True, exist_ok=True)
    raw.sort_values(["file", "countryname", "yearweek"]).to_csv(RAW_CSV, index=False)
    result = analysis.analyse(raw)
    leading.add_to(result, load_flunet(args.flunet))
    DATA_JSON.parent.mkdir(parents=True, exist_ok=True)
    DATA_JSON.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    excel.build(result, EXCEL)
    REPORTS.mkdir(exist_ok=True)
    shutil.copyfile(EXCEL, REPORTS / f"{result['latest_week']}.xlsx")
    print(f"Data up to {result['latest_week']} (season {result['season']})")
    for line in result["findings"] + (result["leading"] or {}).get("points", []):
        print(" -", line)
    return result


def cmd_email(args, result=None):
    if result is None:
        result = json.loads(DATA_JSON.read_text())
    CHARTS.mkdir(parents=True, exist_ok=True)
    chart = charts.year_chart(result, CHARTS / f"{result['latest_week']}.png")
    html = emailer.render(result, dashboard_url=args.dashboard_url)
    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / f"{result['latest_week']}.html"
    out.write_text(html, encoding="utf-8")
    (REPORTS / "latest.html").write_text(html, encoding="utf-8")
    EMAIL_HTML.write_text(html, encoding="utf-8")  # downloadable from the dashboard
    print(f"E-mail written to {out.relative_to(ROOT)}")

    if not args.send:
        return
    state = load_state()
    if state.get("last_email_week") == result["latest_week"] and not args.force:
        print(f"E-mail for {result['latest_week']} has already been sent – skipping.")
        return
    attachment = EXCEL if EXCEL.exists() else None
    if emailer.send(html, emailer.subject(result), result, attachment, chart,
                    emailer.chart_url(result, args.dashboard_url)):
        state["last_email_week"] = result["latest_week"]
        save_state(state)


def cmd_excel(args):
    """Build a workbook locally with your own sales filled in (never committed)."""
    result = json.loads(DATA_JSON.read_text())
    rows = sales.read_sales(args.sales)
    out = pathlib.Path(args.out)
    excel.build(result, out, rows)
    print(f"Workbook with {len(rows)} sales values written to {out}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="flutracker", description=__doc__)
    p.add_argument("command", choices=["update", "email", "all", "excel"])
    p.add_argument("--source", default=ERVISS_BASE, help="Base URL for ERVISS CSV files")
    p.add_argument("--flunet", default=FLUNET_URL, help="WHO FluNet API for the leading markets")
    p.add_argument("--send", action="store_true", help="Send the e-mail over SMTP (env: SMTP_*, MAIL_*)")
    p.add_argument("--force", action="store_true", help="Send even if this week was already sent")
    p.add_argument("--dashboard-url", default=None)
    p.add_argument("--sales", help="excel: CSV/XLSX with columns country, week or month, sales")
    p.add_argument("--out", default="flutracker_with_sales.xlsx", help="excel: output workbook")
    args = p.parse_args(argv)

    if args.command == "excel":
        if not args.sales:
            p.error("excel needs --sales FILE")
        return cmd_excel(args)
    result = None
    if args.command in ("update", "all"):
        result = cmd_update(args)
    if args.command in ("email", "all"):
        cmd_email(args, result)


if __name__ == "__main__":
    sys.exit(main())
