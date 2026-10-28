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
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .analysis import SNAPSHOT_KEYS, fmt_num, fmt_pct, parse_yw
from .config import COUNTRIES, DASHBOARD_URL, EXCEL_NAME

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


def row(inner, pad="0 45px"):
    return f'<tr><td style="padding:{pad}; font-family:{FONT}; font-size:15px; line-height:1.7; color:{TEXT};">{inner}</td></tr>'


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

SNAPSHOT_LABELS = {"flu_cases": "Influenza", "covid_cases": "COVID-19", "rsv_cases": "RSV"}
INTENSITY_SHADES = {"Baseline": "#EEEDF3", "Low": "#E7F7EF", "Medium": "#9DE3C2", "High": "#FAD7C2", "Very high": "#561A32"}


def _snapshot_cell(s, bg, bgs, bold_border=False):
    if not s:
        return f'<td{bg} align="right" style="padding:9px 8px; text-align:right; color:{MUTED};{bgs}">&ndash;</td>'
    wow = s.get("wow_pct")
    arrow = "" if wow is None or wow == 0 else ("&#9650; " if wow > 0 else "&#9660; ")
    sub = (f'<span style="color:{delta_color(wow)};">{arrow}{fmt_pct(abs(wow), signed=False) if wow is not None else "&ndash;"}</span>'
           f'<span style="color:{MUTED};"> &middot; {esc((s.get("intensity") or "–").lower())}</span>')
    edge = f" border-left:2px solid {NAVY};" if bold_border else ""
    return (f'<td{bg} align="right" style="padding:9px 8px; text-align:right;{edge}{bgs}">'
            f'<span style="font-size:15px; font-weight:bold; color:{NAVY};">{fmt_num(s["value"])}</span><br />'
            f'<span style="font-size:11px;">{sub}</span></td>')


def snapshot_table(result):
    """Virus x country grid with this week's cases, change on last week and intensity."""
    codes = list(COUNTRIES)
    head = (f'<tr><td style="{TH}">Cases this week</td>'
            + "".join(f'<td style="{TH} text-align:right;">{esc(COUNTRIES[c]["name"])}</td>' for c in codes)
            + f'<td style="{TH} text-align:right; border-left:2px solid {NAVY};">Nordics</td></tr>')
    body = []
    for n, key in enumerate(SNAPSHOT_KEYS):
        bg, bgs = _shade(n)
        cells = "".join(_snapshot_cell(result["summary"].get(c, {}).get(key), bg, bgs) for c in codes)
        nordic = result["nordic"].get(key)
        cells += _snapshot_cell(nordic if nordic and nordic["week"] == result["latest_week"] else None, bg, bgs, True)
        body.append(f'<tr><td{bg} style="padding:9px 8px; font-weight:bold;{bgs}">{esc(SNAPSHOT_LABELS[key])}</td>{cells}</tr>')
    return _table(head, body) + (
        f'<p style="margin:8px 0 0 0; font-size:12px; color:{MUTED};">Lab-confirmed cases in week {parse_yw(result["latest_week"])[1]}, '
        f'&#9650;/&#9660; change on last week, and intensity (see below). Nordics only when all three countries reported.</p>')


def chart_block(src):
    return (f'<img src="{esc(src)}" width="550" alt="Lab-confirmed cases per week, each year as a line" '
            f'style="display:block; width:100%; max-width:550px; height:auto; border:0;" />'
            f'<p style="margin:8px 0 0 0; font-size:12px; color:{MUTED};">Norway, Sweden and Denmark combined, January to '
            f'December. The thick dark line is this year. Gaps are weeks not every country reported (e.g. Swedish RSV in summer).</p>')


def intensity_block():
    """Short explanation of the intensity measure and its intervals."""
    bands = [("Baseline", "under 10%"), ("Low", "10&ndash;40%"), ("Medium", "40&ndash;70%"),
             ("High", "70&ndash;100%"), ("Very high", "100% or more")]
    cells = "".join(
        f'<td width="20%" bgcolor="{INTENSITY_SHADES[n]}" style="background-color:{INTENSITY_SHADES[n]}; padding:8px 6px; '
        f'font-family:{FONT}; font-size:12px; text-align:center; color:{"#ffffff" if n == "Very high" else NAVY};">'
        f'<b>{n}</b><br />{r}</td>' for n, r in bands)
    return (f'<p style="margin:0 0 10px 0; font-size:14px; line-height:1.6; color:{TEXT};">For each earlier season we take '
            f'the highest week (the season peak) and average those peaks. This week&rsquo;s cases divided by that average peak '
            f'gives the intensity &ndash; how close we are to a normal season peak.</p>'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>{cells}</tr></table>')


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

def chart_url(result, dashboard_url=None):
    """Public address of this week's chart (the PNG is published with the dashboard)."""
    return (dashboard_url or DASHBOARD_URL).rstrip("/") + f"/data/charts/{result['latest_week']}.png"


def render(result, dashboard_url=None, chart_src=None):
    url = dashboard_url or DASHBOARD_URL
    week = parse_yw(result["latest_week"])[1]
    seasons = sorted({s for c in result["summary"].values() for i in c.values() for s in i.get("hist_by_season", {})})
    hist_span = f"{seasons[0]}–{seasons[-1]}" if seasons else "previous seasons"
    src = result["source"]

    parts = [
        f"""<tr><td bgcolor="{NAVY}" style="background-color:{NAVY}; padding:35px 45px 30px 45px;">
<p style="margin:0 0 10px 0; font-family:{FONT}; font-size:11px; color:{PEACH}; letter-spacing:2px; text-transform:uppercase;">Karo Healthcare Norway &middot; Flu tracker &middot; Executive summary</p>
<p style="margin:0; font-family:{FONT}; font-size:28px; font-weight:normal; color:#ffffff; mso-line-height-rule:exactly; line-height:36px;">Respiratory virus update, week {week}</p>
<p style="margin:10px 0 0 0; font-family:{FONT}; font-size:13px; color:{PEACH}; letter-spacing:1px; text-transform:uppercase;">{esc(week_range(result))} &middot; Season {esc(result['season'])} &middot; Norway, Sweden, Denmark</p>
</td></tr>""",
        spacer(30),
        row(label("In short") + "".join(
            f'<p style="margin:0 0 8px 0; font-size:16px; line-height:1.6; color:{TEXT};">{esc(t)}</p>' for t in result["headline"])),
        spacer(20),
        row(label("Year by year") + chart_block(chart_src or chart_url(result, url))),
        spacer(25),
        row(label("Snapshot") + snapshot_table(result)),
        spacer(25),
        row(label("How intensity is calculated") + intensity_block()),
        spacer(25),
        *([row(label("Worth knowing") + bullets(result["key_points"])), spacer(25)] if result["key_points"] else []),
        cta(url),
        spacer(25),
        footnote(
            f"Source: {link(src['url'], src['name'])}, reported by FHI, Folkh&auml;lsomyndigheten and SSI. "
            f"Intensity compares with the {esc(hist_span)} seasons ({link(url.rstrip('/') + '/#intensity', 'worked example')}). "
            "Season curves, all indicators, virus types and hospital figures are on the dashboard and in the Excel workbook."
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


def plain_text(result):
    lines = [subject(result), "", *result["headline"], "", *[f"- {f}" for f in result["key_points"]], "",
             f"Dashboard: {DASHBOARD_URL}"]
    return "\n".join(lines)


def send(html_body, subj, result=None, attachment=None, chart=None, chart_src=None):
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
    if chart and chart_src:
        # Embed the chart in the message so it shows even when remote images are blocked.
        html_body = html_body.replace(esc(chart_src), "cid:yearchart")
        related = MIMEMultipart("related")
        related.attach(MIMEText(html_body, "html", "utf-8"))
        img = MIMEImage(pathlib.Path(chart).read_bytes(), "png")
        img.add_header("Content-ID", "<yearchart>")
        img.add_header("Content-Disposition", "inline", filename="year_by_year.png")
        related.attach(img)
        body.attach(related)
    else:
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
