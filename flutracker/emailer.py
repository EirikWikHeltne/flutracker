"""Weekly Karo-branded, Outlook-compatible HTML e-mail and SMTP sending.

Layout rules follow the Karo e-mail guide: table layout only, inline CSS,
bgcolor + background-color on coloured cells, spacer rows, VML button,
640px container, Georgia, and HTML entities for non-ASCII characters.
"""

import datetime as dt
import html
import os
import pathlib
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .analysis import fmt_num, fmt_pct, parse_yw
from .config import COUNTRIES, DASHBOARD_URL, EXCEL_NAME, INDICATORS

NAVY = "#110B36"
PEACH = "#FAD7C2"
TEXT = "#1a1a2e"
MUTED = "#6B7280"
DIVIDER = "#e8e8e8"
GREEN = "#16a34a"
RED = "#dc2626"
FONT = "Georgia, 'Times New Roman', serif"

NAMED = {"æ": "&aelig;", "ø": "&oslash;", "å": "&aring;", "ä": "&auml;", "ö": "&ouml;",
         "Æ": "&AElig;", "Ø": "&Oslash;", "Å": "&Aring;", "Ä": "&Auml;", "Ö": "&Ouml;"}


def entities(s):
    """Replace every non-ASCII character with an HTML entity."""
    return "".join(NAMED.get(ch, ch if ord(ch) < 128 else f"&#{ord(ch)};") for ch in s)


def esc(s):
    return html.escape(str(s), quote=True)


def week_range(result):
    start = dt.date.fromisoformat(result["latest_week_start"])
    end = start + dt.timedelta(days=6)
    if start.month == end.month:
        return f"{start.day}–{end.day} {end:%B %Y}"
    return f"{start.day} {start:%B} – {end.day} {end:%B %Y}"


def subject(result):
    return f"Respiratory virus update week {parse_yw(result['latest_week'])[1]} – Norway, Sweden and Denmark"


# ------------------------------------------------------------ components ----

def spacer(h):
    return (f'<tr><td style="height:{h}px; line-height:{h}px; font-size:1px; '
            f'mso-line-height-rule:exactly;">&nbsp;</td></tr>')


def label(text):
    return (f'<p style="margin:0 0 8px 0; font-family:{FONT}; font-size:11px; color:{MUTED}; '
            f'text-transform:uppercase; letter-spacing:2px;">{esc(text)}</p>')


def heading(text):
    return (f'<p style="margin:0 0 12px 0; font-family:{FONT}; font-size:20px; color:{NAVY}; '
            f'mso-line-height-rule:exactly; line-height:26px;">{esc(text)}</p>')


def row(inner, pad="0 45px"):
    return f'<tr><td style="padding:{pad}; font-family:{FONT}; font-size:15px; line-height:1.7; color:{TEXT};">{inner}</td></tr>'


def divider():
    return (f'<tr><td style="padding:0 45px;"><table role="presentation" width="100%" cellpadding="0" '
            f'cellspacing="0" border="0"><tr><td style="border-bottom:1px solid {DIVIDER}; height:1px; '
            f'line-height:1px; font-size:1px;">&nbsp;</td></tr></table></td></tr>')


def delta_color(v):
    """Rising disease activity is red, falling is green."""
    if v is None or v == 0:
        return MUTED
    return RED if v > 0 else GREEN


def bullets(items):
    rows = "".join(
        f'<tr><td width="20" valign="top" style="font-family:{FONT}; font-size:15px; color:{NAVY}; '
        f'line-height:1.7; padding:2px 0;">&#8226;</td><td style="font-family:{FONT}; font-size:15px; '
        f'color:{TEXT}; line-height:1.7; padding:2px 0;">{esc(t)}</td></tr>'
        for t in items
    )
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{rows}</table>'


def fmt_value(v, key):
    meta = INDICATORS[key]
    s = fmt_num(v, meta["decimals"])
    return f"{s}%" if meta["unit"] == "%" and v is not None else s


def position_text(p):
    return {"over": "Above hist. max", "under": "Below hist. min", "within": "Within range"}.get(p, "–")


def _shade(n):
    """Alternate rows: (bgcolor attribute, CSS background) for even rows."""
    if n % 2 == 1:
        return f' bgcolor="{PEACH}"', f" background-color:{PEACH};"
    return "", ""


TH = f"padding:9px 8px; font-weight:bold; border-bottom:2px solid {NAVY}; color:{NAVY}; font-size:12px;"


def _table(head, body):
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="font-family:{FONT}; font-size:13px; color:{TEXT};">{head}{"".join(body)}</table>')


# -------------------------------------------------------------- sections ----

def kpi_tiles(result):
    cells = []
    for code, c in COUNTRIES.items():
        ind = result["summary"].get(code, {})
        flu, cov, rsv = ind.get("flu_cases"), ind.get("covid_cases"), ind.get("rsv_cases")
        flu_a, flu_b = ind.get("flu_a_cases"), ind.get("flu_b_cases")
        if not flu:
            continue
        cov_line = (f"COVID-19: <b>{fmt_num(cov['value'])}</b> cases &middot; index {cov['index'] if cov['index'] is not None else '–'}"
                    if cov else "COVID-19: –")
        rsv_line = (f"RSV: <b>{fmt_num(rsv['value'])}</b> cases &middot; index {rsv['index'] if rsv['index'] is not None else '–'}"
                    if rsv else "RSV: –")
        ab_line = (f"Influenza A <b>{fmt_num(flu_a['value'] if flu_a else None)}</b> &middot; "
                   f"B <b>{fmt_num(flu_b['value'] if flu_b else None)}</b>")
        cells.append(f"""
<td width="33%" valign="top" style="padding:0 5px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr><td bgcolor="{NAVY}" style="background-color:{NAVY}; padding:14px 16px 4px 16px; font-family:{FONT}; font-size:11px; color:{PEACH}; text-transform:uppercase; letter-spacing:2px;">{esc(c['name'])} &middot; influenza</td></tr>
    <tr><td bgcolor="{NAVY}" style="background-color:{NAVY}; padding:0 16px; font-family:{FONT}; font-size:30px; color:#ffffff; mso-line-height-rule:exactly; line-height:38px;">{fmt_num(flu['value'])}</td></tr>
    <tr><td bgcolor="{NAVY}" style="background-color:{NAVY}; padding:0 16px 14px 16px; font-family:{FONT}; font-size:12px; color:#ffffff;">lab-confirmed &middot; {fmt_pct(flu['wow_pct'])} week on week</td></tr>
    <tr><td bgcolor="{PEACH}" style="background-color:{PEACH}; padding:10px 16px; font-family:{FONT}; font-size:12px; color:{NAVY};">Index vs history: <b>{flu['index'] if flu['index'] is not None else '–'}</b><br />Intensity: <b>{esc(flu.get('intensity') or '–')}</b><br />{ab_line}<br />{cov_line}<br />{rsv_line}</td></tr>
  </table>
</td>""")
    return (f'<tr><td style="padding:0 40px;"><table role="presentation" width="100%" cellpadding="0" '
            f'cellspacing="0" border="0"><tr>{"".join(cells)}</tr></table></td></tr>')


def index_bars(result, key):
    """Horizontal bars of this week's index; 100 is the historical average."""
    scale_max = 300
    rows = []
    for code, c in COUNTRIES.items():
        s = result["summary"].get(code, {}).get(key)
        if not s or s["index"] is None:
            continue
        width = max(2, min(s["index"], scale_max) * 100 // scale_max)
        rows.append(f"""
<tr>
  <td width="90" style="padding:6px 0; font-family:{FONT}; font-size:13px; color:{TEXT};">{esc(c['name'])}</td>
  <td style="padding:6px 0;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
      <td width="{width}%" bgcolor="{NAVY}" style="background-color:{NAVY}; height:16px; line-height:16px; font-size:1px;">&nbsp;</td>
      <td style="padding-left:8px; font-family:{FONT}; font-size:13px; color:{NAVY}; font-weight:bold;">{s['index']}</td>
    </tr></table>
  </td>
</tr>""")
    if not rows:
        return ""
    scale = (f'<tr><td></td><td style="padding-top:4px; font-family:{FONT}; font-size:11px; color:{MUTED};">'
             f'Index 100 = average for the same week in previous seasons (scale 0&ndash;{scale_max})</td></tr>')
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{"".join(rows)}{scale}</table>'


def indicator_table(result, group):
    head = (f'<tr><td style="{TH}">Indicator</td><td style="{TH} text-align:right;">This week</td>'
            f'<td style="{TH} text-align:right;">Change</td><td style="{TH} text-align:right;">Hist. avg</td>'
            f'<td style="{TH} text-align:right;">Index</td><td style="{TH}">Level</td></tr>')
    body = []
    keys = [k for k, m in INDICATORS.items() if m["group"] == group]
    for code, c in COUNTRIES.items():
        ind = {k: result["summary"].get(code, {}).get(k) for k in keys}
        ind = {k: v for k, v in ind.items() if v}
        if not ind:
            continue
        body.append(f'<tr><td colspan="6" style="padding:14px 8px 6px 8px; font-size:11px; color:{MUTED}; '
                    f'text-transform:uppercase; letter-spacing:2px;">{esc(c["name"])} &middot; {esc(c["authority"])}</td></tr>')
        for n, (key, s) in enumerate(ind.items()):
            bg, bgs = _shade(n)
            td = f'style="padding:8px;{bgs}'
            note = " *" if s.get("stale") else ""
            if s.get("low_tests"):
                note += " &dagger;"
            body.append(
                f'<tr><td{bg} {td}">{esc(INDICATORS[key]["short"])}{note}</td>'
                f'<td{bg} {td} text-align:right;">{fmt_value(s["value"], key)}<br /><span style="font-size:11px; color:{MUTED};">w{parse_yw(s["week"])[1]}</span></td>'
                f'<td{bg} {td} text-align:right; color:{delta_color(s["wow_pct"])};">{fmt_pct(s["wow_pct"])}</td>'
                f'<td{bg} {td} text-align:right;">{fmt_value(s["hist_mean"], key)}</td>'
                f'<td{bg} {td} text-align:right; font-weight:bold; color:{delta_color(s["diff_pct"])};">{s["index"] if s["index"] is not None else "–"}</td>'
                f'<td{bg} {td} font-size:12px;">{position_text(s["position"])}</td></tr>'
            )
    missing = [c["name"] for code, c in COUNTRIES.items()
               if not any(result["summary"].get(code, {}).get(k) for k in keys)]
    if not body:
        return f'<p style="margin:0; font-size:13px; color:{MUTED};">No country currently reports these figures to ECDC.</p>'
    note = ""
    if missing:
        note = (f'<p style="margin:8px 0 0 0; font-size:12px; color:{MUTED};">Not reported to ECDC this season: '
                f'{esc(", ".join(missing))}. See the national institutes&rsquo; weekly reports.</p>')
    return _table(head, body) + note


def season_table(result, key):
    rows = []
    # Countries can have different histories (e.g. RSV), so show every season any of them has.
    hist_labels = sorted({h for code in COUNTRIES
                          for h in result["summary"].get(code, {}).get(key, {}).get("season_to_date_hist", {})})
    for n, (code, c) in enumerate(COUNTRIES.items()):
        s = result["summary"].get(code, {}).get(key)
        if not s or "season_to_date" not in s:
            continue
        bg, bgs = _shade(n)
        cells = "".join(f'<td{bg} style="padding:8px; text-align:right;{bgs}">{fmt_num(s["season_to_date_hist"].get(h))}</td>' for h in hist_labels)
        idx = s["season_to_date_index"]
        rows.append(
            f'<tr><td{bg} style="padding:8px;{bgs}">{esc(c["name"])}</td>'
            f'<td{bg} style="padding:8px; text-align:right; font-weight:bold;{bgs}">{fmt_num(s["season_to_date"])}</td>{cells}'
            f'<td{bg} style="padding:8px; text-align:right; font-weight:bold; color:{delta_color(None if idx is None else idx - 100)};{bgs}">{idx if idx is not None else "–"}</td></tr>'
        )
    if not rows:
        return ""
    head = (f'<tr><td style="{TH}">Country</td><td style="{TH} text-align:right;">{esc(result["season"])}</td>'
            + "".join(f'<td style="{TH} text-align:right;">{esc(h)}</td>' for h in hist_labels)
            + f'<td style="{TH} text-align:right;">Index</td></tr>')
    return _table(head, rows)


def subtype_table(result):
    codes = [c for c in COUNTRIES if c in result["subtypes"]]
    names = list(result["subtypes"][codes[0]]["season"]) if codes else []
    head = f'<tr><td style="{TH}">Virus (season to date)</td>' + "".join(
        f'<td style="{TH} text-align:right;">{esc(COUNTRIES[c]["name"])}</td>' for c in codes) + "</tr>"
    rows = []
    for n, name in enumerate(names):
        bg, bgs = _shade(n)
        rows.append(f'<tr><td{bg} style="padding:8px;{bgs}">{esc(name)}</td>' + "".join(
            f'<td{bg} style="padding:8px; text-align:right;{bgs}">{fmt_num(result["subtypes"][c]["season"][name])}</td>'
            for c in codes) + "</tr>")
    return _table(head, rows)


def cta(url):
    excel = url.rstrip("/") + "/data/" + EXCEL_NAME
    return f"""<tr>
  <td align="center" style="padding:10px 45px 0 45px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
    <td bgcolor="{PEACH}" align="center" style="background-color:{PEACH}; padding:22px 25px;">
    <p style="margin:0 0 14px 0; font-family:{FONT}; font-size:13px; color:{TEXT};">Charts per country and indicator, with every previous season</p>
    <!--[if mso]>
    <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word" href="{esc(url)}" style="height:44px;v-text-anchor:middle;width:280px;" arcsize="10%" strokecolor="{NAVY}" fillcolor="{NAVY}">
    <w:anchorlock/>
    <center style="color:#ffffff;font-family:Georgia,'Times New Roman',serif;font-size:15px;font-weight:bold;">Open the tracker</center>
    </v:roundrect>
    <![endif]-->
    <!--[if !mso]><!-->
    <a href="{esc(url)}" style="display:inline-block; background-color:{NAVY}; color:#ffffff; font-family:Georgia,'Times New Roman',serif; font-size:15px; font-weight:bold; text-decoration:none; padding:12px 40px; border-radius:4px;">Open the tracker</a>
    <!--<![endif]-->
    <p style="margin:14px 0 0 0; font-family:{FONT}; font-size:13px;"><a href="{esc(excel)}" style="color:{NAVY}; font-weight:bold; text-decoration:underline;">Download the Excel workbook &rarr;</a></p>
    </td></tr></table>
  </td>
</tr>"""


def footnote(text):
    return (f'<tr><td style="padding:0 45px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
            f'<tr><td width="3" bgcolor="{PEACH}" style="background-color:{PEACH};"></td>'
            f'<td style="padding:12px 0 12px 15px; font-family:{FONT}; font-size:12px; color:{MUTED}; line-height:1.6;">{text}</td>'
            f'</tr></table></td></tr>')


def link(url, text):
    return f'<a href="{esc(url)}" style="color:{MUTED}; text-decoration:underline;">{esc(text)}</a>'


# ------------------------------------------------------------------ page ----

def render(result, dashboard_url=None):
    url = dashboard_url or DASHBOARD_URL
    week = parse_yw(result["latest_week"])[1]
    seasons = sorted({s for c in result["summary"].values() for i in c.values() for s in i.get("hist_by_season", {})})
    hist_span = f"{seasons[0]}–{seasons[-1]}" if seasons else "previous seasons"
    src = result["source"]
    authorities = "; ".join(f'{esc(c["name"])}: {link(c["url"], c["authority"])}' for c in COUNTRIES.values())

    parts = [
        f"""<tr><td bgcolor="{NAVY}" style="background-color:{NAVY}; padding:35px 45px 30px 45px;">
<p style="margin:0 0 10px 0; font-family:{FONT}; font-size:11px; color:{PEACH}; letter-spacing:2px; text-transform:uppercase;">Karo Healthcare Norway &middot; Flu tracker</p>
<p style="margin:0; font-family:{FONT}; font-size:28px; font-weight:normal; color:#ffffff; mso-line-height-rule:exactly; line-height:36px;">Respiratory virus update, week {week}</p>
<p style="margin:10px 0 0 0; font-family:{FONT}; font-size:13px; color:{PEACH}; letter-spacing:1px; text-transform:uppercase;">{esc(week_range(result))} &middot; Season {esc(result['season'])}</p>
</td></tr>""",
        spacer(30),
        row(f'<p style="margin:0;">Weekly status for influenza (A and B), COVID-19 and RSV in Norway, Sweden and Denmark. '
            f'Each figure is compared with the same week in the {esc(hist_span)} seasons. '
            f'Index 100 means the same level as the historical average.</p>'),
        spacer(25),
        kpi_tiles(result),
        spacer(30),
        row(label("Key findings this week") + bullets(result["findings"])),
        spacer(25),
        divider(),
        spacer(25),
        row(label("Lab-confirmed influenza against history") + index_bars(result, "flu_cases")),
        spacer(25),
        divider(),
        spacer(25),
        row(label("Influenza") + heading("Level against the same week in previous seasons") + indicator_table(result, "Influenza")),
        spacer(25),
        row(label("Influenza season to date") + heading("Cumulative lab-confirmed cases since week 40")
            + season_table(result, "flu_cases")
            + f'<p style="margin:8px 0 0 0; font-size:12px; color:{MUTED};">Previous seasons are summed to the same week.</p>'),
        spacer(25),
        row(label("Influenza virus types") + subtype_table(result)),
        spacer(25),
        divider(),
        spacer(25),
        row(label("COVID-19") + heading("COVID-19 against previous seasons") + indicator_table(result, "COVID-19")),
        spacer(25),
        row(label("RSV") + heading("RSV against previous seasons") + indicator_table(result, "RSV")),
        spacer(25),
        row(label("RSV season to date") + heading("Cumulative lab-confirmed RSV cases since week 40")
            + season_table(result, "rsv_cases")),
        spacer(25),
        row(label("Hospital & severity") + heading("Hospital admissions, intensive care and deaths")
            + indicator_table(result, "Hospital & severity")),
        spacer(25),
        cta(url),
        spacer(25),
        footnote(
            f"Source: {link(src['url'], src['name'])} ({link(src['data'], 'open data')}), published by the "
            f"{esc(src['publisher'])}. {esc(src['note'])} National reports: {authorities}.<br /><br />"
            "Index = this week&rsquo;s value / average for the same ISO week in previous seasons &times; 100. "
            "Intensity: for each previous season we take the highest weekly value (the season peak) and average those "
            "peaks; this week&rsquo;s value divided by that average peak gives the intensity (&lt;10% baseline, "
            "10&ndash;40% low, 40&ndash;70% medium, 70&ndash;100% high, &ge;100% very high). "
            f"{intensity_example(result)}"
            f"* = latest reported week is older than week {week}. "
            "&dagger; = fewer than 20 sentinel samples, interpret with care."
        ),
        spacer(10),
        f'<tr><td style="padding:25px 45px 30px 45px; border-top:1px solid {DIVIDER};">'
        f'<p style="margin:0; font-family:{FONT}; font-size:12px; color:{MUTED}; line-height:1.6;">'
        f'Karo Healthcare Norway &middot; Internal communication &middot; Generated automatically {esc(result["generated_at"][:10])}</p></td></tr>',
    ]

    doc = f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<!--[if gte mso 9]>
<xml>
<o:OfficeDocumentSettings>
<o:AllowPNG/>
<o:PixelsPerInch>96</o:PixelsPerInch>
</o:OfficeDocumentSettings>
</xml>
<![endif]-->
<title>{esc(subject(result))}</title>
</head>
<body style="margin:0; padding:0; background-color:#f4f4f4; font-family:{FONT};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f4f4f4;">
<tr>
<td align="center" style="padding:20px 0;">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" border="0" style="background-color:#ffffff; max-width:640px;">
{chr(10).join(parts)}
</table>
</td>
</tr>
</table>
</body>
</html>
"""
    return entities(doc)


def intensity_example(result):
    """One worked intensity example from this week's data, for the footnote."""
    for code, c in COUNTRIES.items():
        s = result["summary"].get(code, {}).get("flu_cases")
        if s and s.get("peak_mean") and s.get("intensity"):
            vals = [fmt_num(p["value"]) for p in s["peaks"].values()]
            peaks = ", ".join(vals[:-1]) + " and " + vals[-1] if len(vals) > 1 else vals[0]
            return (f"Example: {esc(c['name'])} had {fmt_num(s['value'])} influenza cases this week; previous season "
                    f"peaks of {peaks} average {fmt_num(s['peak_mean'])}, and {fmt_num(s['value'])} / "
                    f"{fmt_num(s['peak_mean'])} = {fmt_num(s['value'] / s['peak_mean'] * 100)}% &rarr; "
                    f"{esc(s['intensity'].lower())}. ")
    return ""


def plain_text(result):
    lines = [subject(result), "", *[f"- {f}" for f in result["findings"]], "", f"Dashboard: {DASHBOARD_URL}"]
    return "\n".join(lines)


def send(html_body, subj, result=None, attachment=None):
    """Send over SMTP using SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, MAIL_FROM, MAIL_TO."""
    host = os.environ.get("SMTP_HOST")
    to = [a.strip() for a in os.environ.get("MAIL_TO", "").split(",") if a.strip()]
    if not host or not to:
        print("SMTP_HOST/MAIL_TO not set – e-mail was not sent.")
        return False
    user = os.environ.get("SMTP_USER")
    sender = os.environ.get("MAIL_FROM") or user
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subj
    msg["From"] = sender
    msg["To"] = ", ".join(to)
    body = MIMEMultipart("alternative")
    body.attach(MIMEText(plain_text(result) if result else subj, "plain", "utf-8"))
    body.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(body)
    if attachment:
        path = pathlib.Path(attachment)
        part = MIMEApplication(path.read_bytes(), _subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        part.add_header("Content-Disposition", "attachment", filename=path.name)
        msg.attach(part)
    port = int(os.environ.get("SMTP_PORT") or "587")
    if port == 465:
        server = smtplib.SMTP_SSL(host, port, timeout=60)
    else:
        server = smtplib.SMTP(host, port, timeout=60)
        server.starttls()
    with server:
        if user:
            server.login(user, os.environ.get("SMTP_PASSWORD", ""))
        server.sendmail(sender, to, msg.as_string())
    print(f"E-mail sent to {', '.join(to)}")
    return True
