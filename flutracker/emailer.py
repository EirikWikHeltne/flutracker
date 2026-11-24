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
from .charts import EMAIL_SIZE
from .config import AI_CHIP, AI_STATEMENT, AUTHORITY_SHORT, COUNTRIES, COUNTRY_COMMAS, COUNTRY_LIST, DASHBOARD_URL

NAVY = "#110B36"
PEACH = "#FAD7C2"
TEXT = "#1a1a2e"
MUTED = "#6B7280"
DIVIDER = "#e8e8e8"
MINT = "#9DE3C2"
GREY = "#53565A"
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
    return f"Respiratory virus update week {parse_yw(result['latest_week'])[1]} – {COUNTRY_LIST}"


# ------------------------------------------------------------ components ----

def spacer(h):
    return (f'<tr><td style="height:{h}px; line-height:{h}px; font-size:1px; '
            f'mso-line-height-rule:exactly;">&nbsp;</td></tr>')


def heading(text):
    return (f'<p style="margin:0 0 12px 0; font-family:{FONT}; font-size:20px; color:{NAVY}; '
            f'mso-line-height-rule:exactly; line-height:27px;">{esc(text)}</p>')


# Karo line icons from the dashboard, rendered to PNG by tools/render_email_icons.js (Outlook cannot show
# SVG). They are published with the dashboard and linked with a full https address and fixed width/height,
# so they survive copy-paste into classic and new Outlook; the e-mail sent over SMTP embeds them instead.
ICON_PX = 16
ICONS_DIR = pathlib.Path(__file__).resolve().parent.parent / "docs" / "data" / "icons"


def icon_base(dashboard_url=None):
    return (dashboard_url or DASHBOARD_URL).rstrip("/") + "/data/icons/"


def icon(name, base, color="navy", size=ICON_PX):
    return (f'<img src="{esc(base)}{name}-{color}.png" width="{size}" height="{size}" alt="" '
            f'style="display:block; width:{size}px; height:{size}px; border:0; outline:none; text-decoration:none;" />')


def with_icon(img, inner, gap=9, pad_bottom=0):
    """Icon and text side by side in a table: classic Outlook ignores vertical-align on inline images."""
    pb = f" padding-bottom:{pad_bottom}px;" if pad_bottom else ""
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
            f'<td width="{ICON_PX}" valign="middle" style="padding-right:{gap}px;{pb}">{img}</td>'
            f'<td valign="middle" style="{pb.strip()}">{inner}</td></tr></table>')


def label(text, ico=None, base=None):
    p = (f'<p style="margin:0{" 0 8px 0" if not ico else ""}; font-family:{FONT}; font-size:12px; color:{MUTED}; '
         f'text-transform:uppercase; letter-spacing:2px; mso-line-height-rule:exactly; line-height:17px;">{esc(text)}</p>')
    return with_icon(icon(ico, base), p, pad_bottom=10) if ico else p


def row(inner, pad="0 45px"):
    return f'<tr><td style="padding:{pad}; font-family:{FONT}; font-size:16px; line-height:1.65; color:{TEXT};">{inner}</td></tr>'


def delta_color(v):
    """Rising disease activity is red, falling is green."""
    if v is None or v == 0:
        return MUTED
    return RED if v > 0 else GREEN


def bullets(items):
    rows = "".join(
        f'<tr><td width="20" valign="top" style="font-family:{FONT}; font-size:16px; color:{NAVY}; '
        f'line-height:1.65; padding:2px 0;">&#8226;</td><td style="font-family:{FONT}; font-size:16px; '
        f'color:{TEXT}; line-height:1.65; padding:2px 0;">{esc(t)}</td></tr>'
        for t in items
    )
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{rows}</table>'


def _shade(n):
    """Alternate rows: (bgcolor attribute, CSS background) for even rows."""
    if n % 2 == 1:
        return f' bgcolor="{PEACH}"', f" background-color:{PEACH};"
    return "", ""


TH = f"padding:9px 8px; font-weight:bold; border-bottom:2px solid {NAVY}; color:{NAVY}; font-size:13px;"


def _table(head, body):
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="font-family:{FONT}; font-size:14px; color:{TEXT};">{head}{"".join(body)}</table>')


# -------------------------------------------------------------- sections ----

SNAPSHOT_LABELS = {"flu_cases": "Influenza", "covid_cases": "COVID-19", "rsv_cases": "RSV"}
VIRUS_ACCENTS = {"flu_cases": "#9DE3C2", "covid_cases": PEACH, "rsv_cases": "#9F9DB1"}  # Karo mint, peach, lavender
INTENSITY_BANDS = [("Baseline", "under 10%", "#EEEDF3"), ("Low", "10&ndash;40%", "#E7F7EF"),
                   ("Medium", "40&ndash;70%", "#9DE3C2"), ("High", "70&ndash;100%", "#FAD7C2"),
                   ("Very high", "100% or more", "#561A32")]
INTENSITY_SHADES = {name: shade for name, _, shade in INTENSITY_BANDS}


def _this_week(result, s):
    return s if s and s["week"] == result["latest_week"] else None


def _trend(wow, size=13):
    if wow is None:
        return f'<span style="font-size:{size}px; color:{MUTED};">&ndash;</span>'
    arrow = "&#9650;" if wow > 0 else "&#9660;" if wow < 0 else "&#9654;"
    return (f'<span style="font-size:{size}px; color:{delta_color(wow)};">{arrow} '
            f'{fmt_pct(abs(wow), signed=False)}</span>')


def pill(s, size=12):
    """Intensity as a small coloured label in the colour of its band on the scale."""
    name = s.get("intensity") if s else None
    if not name:
        return f'<span style="font-size:{size}px; color:{MUTED};">&ndash;</span>'
    fg = "#ffffff" if name == "Very high" else NAVY
    pct = f" &middot; {fmt_num(s['intensity_pct'])}%" if s.get("intensity_pct") is not None else ""
    return (f'<span style="display:inline-block; background-color:{INTENSITY_SHADES[name]}; color:{fg}; '
            f'font-size:{size}px; padding:2px 9px; border-radius:10px; white-space:nowrap;">{esc(name)}{pct}</span>')


def status_cards(result):
    """Three cards with the Nordic picture: cases, change on last week and intensity."""
    cells = []
    for key in SNAPSHOT_KEYS:
        s = _this_week(result, result["nordic"].get(key))
        accent = VIRUS_ACCENTS[key]
        value = fmt_num(s["value"]) if s else "&ndash;"
        cells.append(f"""<td width="33%" valign="top" style="padding:0 5px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
<tr><td bgcolor="{accent}" style="background-color:{accent}; height:5px; line-height:5px; font-size:1px;">&nbsp;</td></tr>
<tr><td bgcolor="#F7F6FA" style="background-color:#F7F6FA; padding:14px 14px 16px 14px; font-family:{FONT};">
<p style="margin:0; font-size:12px; letter-spacing:2px; text-transform:uppercase; color:{MUTED};">{esc(SNAPSHOT_LABELS[key])}</p>
<p style="margin:6px 0 0 0; font-size:30px; line-height:34px; color:{NAVY}; mso-line-height-rule:exactly;">{value}</p>
<p style="margin:2px 0 10px 0; font-size:13px; color:{MUTED};">cases &middot; {_trend(s["wow_pct"] if s else None, 13)}</p>
{pill(s)}
</td></tr></table></td>""")
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
            f'<tr>{"".join(cells)}</tr></table>'
            f'<p style="margin:10px 0 0 0; font-size:13px; color:{MUTED};">Lab-confirmed cases in {COUNTRY_LIST} '
            f'combined, change on last week, and intensity (share of an average season peak).</p>')


def country_table(result):
    """Countries as rows, viruses as columns: cases, change on last week and intensity."""
    head = (f'<tr><td style="{TH}">Week {parse_yw(result["latest_week"])[1]}</td>'
            + "".join(f'<td style="{TH} text-align:right;">{esc(SNAPSHOT_LABELS[k])}</td>' for k in SNAPSHOT_KEYS) + "</tr>")
    body = []
    line = f" border-bottom:1px solid {DIVIDER};"
    for code, c in COUNTRIES.items():
        bg, bgs = "", line  # plain rows, so the intensity colours stand out
        cells = []
        for key in SNAPSHOT_KEYS:
            s = _this_week(result, result["summary"].get(code, {}).get(key))
            if not s:
                cells.append(f'<td{bg} align="right" style="padding:10px 8px; color:{MUTED};{bgs}">&ndash;</td>')
                continue
            cells.append(f'<td{bg} align="right" style="padding:10px 8px; text-align:right;{bgs}">'
                         f'<span style="font-size:16px; font-weight:bold; color:{NAVY};">{fmt_num(s["value"])}</span> '
                         f'{_trend(s["wow_pct"], 12)}<br /><span style="line-height:24px;">{pill(s, 12)}</span></td>')
        body.append(f'<tr><td{bg} style="padding:10px 8px; font-weight:bold;{bgs}">{esc(c["name"])}</td>{"".join(cells)}</tr>')
    return _table(head, body)


CHART_W, CHART_H = EMAIL_SIZE  # both set on the <img>: Outlook on Windows needs fixed dimensions


def chart_block(src):
    return (f'<img src="{esc(src)}" width="{CHART_W}" height="{CHART_H}" alt="Lab-confirmed cases per week, each year as a line" '
            f'style="display:block; width:100%; max-width:{CHART_W}px; height:auto; border:0; outline:none; '
            f'text-decoration:none; -ms-interpolation-mode:bicubic;" />'
            f'<p style="margin:8px 0 0 0; font-size:13px; color:{MUTED};">{COUNTRY_LIST} combined. One line per '
            f'year; the thick dark line is this year. Gaps are weeks when not every country reported, such as Swedish RSV in summer.</p>')


def intensity_block(result):
    """How intensity is calculated, with the scale and where Nordic influenza is now."""
    flu = _this_week(result, result["nordic"].get("flu_cases"))
    now = flu.get("intensity") if flu else None
    cells, marks = [], []
    for name, rng, shade in INTENSITY_BANDS:
        fg = "#ffffff" if name == "Very high" else NAVY
        edge = f" border-bottom:3px solid {NAVY};" if name == now else ""
        cells.append(f'<td width="20%" bgcolor="{shade}" style="background-color:{shade}; padding:8px 4px; font-family:{FONT}; '
                     f'font-size:13px; text-align:center; color:{fg};{edge}"><b>{name}</b><br />{rng}</td>')
        mark = (f"&#9650; Influenza now<br />{fmt_num(flu['intensity_pct'])}% of peak" if name == now else "&nbsp;")
        marks.append(f'<td width="20%" style="padding:6px 4px 0 4px; font-family:{FONT}; font-size:12px; text-align:center; '
                     f'color:{NAVY}; font-weight:bold;">{mark}</td>')
    return (f'<p style="margin:0 0 12px 0; font-size:15px; line-height:1.6; color:{TEXT};">Take the busiest week of each '
            f'earlier season and average them. <b>This week&rsquo;s cases &divide; that average peak</b> is the intensity. '
            f'It shows how close we are to the top of a normal season.</p>'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
            f'<tr>{"".join(cells)}</tr><tr>{"".join(marks)}</tr></table>')


def cta(url):
    return f"""<tr>
  <td align="center" style="padding:10px 45px 0 45px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
    <td bgcolor="{PEACH}" align="center" style="background-color:{PEACH}; padding:22px 25px;">
    <p style="margin:0 0 14px 0; font-family:{FONT}; font-size:14px; color:{TEXT};">Charts per country and indicator, with every previous season</p>
    <!--[if mso]>
    <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word" href="{esc(url)}" style="height:44px;v-text-anchor:middle;width:280px;" arcsize="10%" strokecolor="{NAVY}" fillcolor="{NAVY}">
    <w:anchorlock/>
    <center style="color:#ffffff;font-family:Georgia,'Times New Roman',serif;font-size:15px;font-weight:bold;">Open the tracker</center>
    </v:roundrect>
    <![endif]-->
    <!--[if !mso]><!-->
    <a href="{esc(url)}" style="display:inline-block; background-color:{NAVY}; color:#ffffff; font-family:Georgia,'Times New Roman',serif; font-size:15px; font-weight:bold; text-decoration:none; padding:12px 40px; border-radius:4px;">Open the tracker</a>
    <!--<![endif]-->
    </td></tr></table>
  </td>
</tr>"""


def footnote(text, img=None):
    lead = (f'<td width="{ICON_PX}" valign="top" style="padding:14px 0 0 15px;">{img}</td>' if img else "")
    return (f'<tr><td style="padding:0 45px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
            f'<tr><td width="3" bgcolor="{PEACH}" style="background-color:{PEACH};"></td>{lead}'
            f'<td style="padding:12px 0 12px {10 if img else 15}px; font-family:{FONT}; font-size:13px; color:{MUTED}; line-height:1.6;">{text}</td>'
            f'</tr></table></td></tr>')


def ai_disclosure():
    """Karo AI disclosure: mint chip plus a quiet grey statement, one row above the signature."""
    chip = (f'<td bgcolor="{MINT}" style="background-color:{MINT}; padding:4px 8px; font-family:Arial, Helvetica, sans-serif; '
            f'font-size:10px; font-weight:bold; color:{NAVY}; letter-spacing:1px; text-transform:uppercase; white-space:nowrap; '
            f'mso-line-height-rule:exactly; line-height:14px;">{entities(AI_CHIP.upper())}</td>')
    text = (f'<td style="padding:0 0 0 10px; font-family:{FONT}; font-size:11px; color:{GREY}; '
            f'mso-line-height-rule:exactly; line-height:16px;">{esc(AI_STATEMENT)}</td>')
    return (f'<tr><td style="padding:0 45px 18px 45px;"><table role="presentation" cellpadding="0" cellspacing="0" border="0">'
            f'<tr>{chip}{text}</tr></table></td></tr>')


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
    ib = icon_base(dashboard_url)

    preheader = " ".join(result["headline"])
    parts = [
        f'<tr><td style="display:none; font-size:1px; line-height:1px; max-height:0; max-width:0; opacity:0; overflow:hidden; '
        f'mso-hide:all; color:#ffffff;">{esc(preheader)}</td></tr>',
        f"""<tr><td bgcolor="{NAVY}" style="background-color:{NAVY}; padding:35px 45px 30px 45px;">
{with_icon(icon("virus", ib, "peach"), f'<p style="margin:0; font-family:{FONT}; font-size:12px; color:{PEACH}; letter-spacing:2px; text-transform:uppercase; mso-line-height-rule:exactly; line-height:17px;">Karo Healthcare Norway &middot; Flu tracker</p>', pad_bottom=12)}
<p style="margin:0; font-family:{FONT}; font-size:28px; font-weight:normal; color:#ffffff; mso-line-height-rule:exactly; line-height:36px;">Respiratory virus update, week {week}</p>
<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr><td style="height:12px; line-height:12px; font-size:1px; mso-line-height-rule:exactly;">&nbsp;</td></tr></table>
{with_icon(icon("calendar", ib, "peach"), f'<p style="margin:0; font-family:{FONT}; font-size:13px; color:{PEACH}; letter-spacing:1px; text-transform:uppercase; mso-line-height-rule:exactly; line-height:18px;">{esc(week_range(result))} &middot; {esc(COUNTRY_COMMAS)}</p>')}
</td></tr>""",
        spacer(28),
        *([row(f'<p style="margin:0; font-family:{FONT}; font-size:18px; line-height:1.55; color:{NAVY};">'
               f'{esc(" ".join(result["headline"]))}</p>'), spacer(24)] if result["headline"] else []),
        row(label("This week in the Nordics", "pulse", ib) + status_cards(result)),
        spacer(26),
        *([row(label("Worth knowing", "bulb", ib) + bullets(result["key_points"])), spacer(26)] if result["key_points"] else []),
        row(label("Year by year", "layers", ib) + heading("Lab-confirmed cases, January to December") + chart_block(chart_src or chart_url(result, url))),
        spacer(28),
        row(label("By country", "globe", ib) + country_table(result)),
        spacer(28),
        row(label("How to read intensity", "gauge", ib) + intensity_block(result)),
        spacer(28),
        cta(url),
        spacer(25),
        footnote(
            f"Source: {link(src['url'], src['name'])}, reported by {entities(AUTHORITY_SHORT)}. "
            f"Figures for week {week} are preliminary: the latest week is often incomplete and is usually revised upwards, "
            "so the week-on-week change can understate growth. "
            f"Intensity compares with the {esc(hist_span)} seasons ({link(url.rstrip('/') + '/#intensity', 'worked example')}). "
            "Season curves, all indicators, virus types and hospital figures are on the dashboard and in the Excel workbook.",
            icon("book", ib),
        ),
        spacer(22),
        ai_disclosure(),
        f'<tr><td style="padding:25px 45px 30px 45px; border-top:1px solid {DIVIDER};">'
        f'<p style="margin:0; font-family:{FONT}; font-size:13px; color:{MUTED}; line-height:1.6;">'
        f'Karo Healthcare Norway &middot; Internal communication &middot; Sent every second week &middot; Generated automatically {esc(result["generated_at"][:10])}</p></td></tr>',
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
             f"Dashboard: {DASHBOARD_URL}", "",
             "Figures for the latest week are preliminary and are usually revised upwards.", "",
             "This update is sent every second week."]
    return "\n".join(lines)


def send(html_body, subj, result=None, attachment=None, chart=None, chart_src=None, dashboard_url=None):
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
    # Embed the chart and icons in the message so they show even when remote images are blocked.
    inline = []
    if chart and chart_src:
        html_body = html_body.replace(esc(chart_src), "cid:yearchart")
        inline.append(("yearchart", pathlib.Path(chart), "year_by_year.png"))
    base = esc(icon_base(dashboard_url))
    for path in sorted(ICONS_DIR.glob("*.png")):
        if base + path.name in html_body:
            html_body = html_body.replace(base + path.name, f"cid:icon-{path.stem}")
            inline.append((f"icon-{path.stem}", path, path.name))
    if inline:
        related = MIMEMultipart("related")
        related.attach(MIMEText(html_body, "html", "utf-8"))
        for cid, path, name in inline:
            img = MIMEImage(path.read_bytes(), "png")
            img.add_header("Content-ID", f"<{cid}>")
            img.add_header("Content-Disposition", "inline", filename=name)
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
