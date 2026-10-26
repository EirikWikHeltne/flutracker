"""Weekly Karo-branded, Outlook-compatible HTML e-mail and SMTP sending.

Layout rules follow the Karo e-mail guide: table layout only, inline CSS,
bgcolor + background-color on coloured cells, spacer rows, VML button,
640px container, Georgia, and HTML entities for Norwegian characters.
"""

import datetime as dt
import html
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .analysis import fmt_num, fmt_pct, parse_yw
from .config import COUNTRIES, DASHBOARD_URL, INDICATORS

NAVY = "#110B36"
PEACH = "#FAD7C2"
TEXT = "#1a1a2e"
MUTED = "#6B7280"
DIVIDER = "#e8e8e8"
GREEN = "#16a34a"
RED = "#dc2626"
FONT = "Georgia, 'Times New Roman', serif"

MONTHS = ["januar", "februar", "mars", "april", "mai", "juni", "juli",
          "august", "september", "oktober", "november", "desember"]
NAMED = {"æ": "&aelig;", "ø": "&oslash;", "å": "&aring;", "Æ": "&AElig;", "Ø": "&Oslash;", "Å": "&Aring;"}


def entities(s):
    """Replace every non-ASCII character with an HTML entity."""
    return "".join(NAMED.get(ch, ch if ord(ch) < 128 else f"&#{ord(ch)};") for ch in s)


def esc(s):
    return html.escape(str(s), quote=True)


def week_range(result):
    start = dt.date.fromisoformat(result["latest_week_start"])
    end = start + dt.timedelta(days=6)
    if start.month == end.month:
        return f"{start.day}.–{end.day}. {MONTHS[end.month - 1]} {end.year}"
    return f"{start.day}. {MONTHS[start.month - 1]} – {end.day}. {MONTHS[end.month - 1]} {end.year}"


def subject(result):
    return f"Influensaoversikt uke {parse_yw(result['latest_week'])[1]} – Norge, Sverige og Danmark"


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


def delta_color(v, good_when_down=True):
    if v is None or v == 0:
        return MUTED
    rising = v > 0
    return RED if rising == good_when_down else GREEN


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
    return f"{s} %" if meta["unit"] == "%" else s


def position_text(p):
    return {"over": "Over hist. maks", "under": "Under hist. min", "innenfor": "Innenfor spenn"}.get(p, "–")


# -------------------------------------------------------------- sections ----

def kpi_tiles(result):
    cells = []
    for code, c in COUNTRIES.items():
        lab = result["summary"].get(code, {}).get("lab_cases")
        if not lab:
            continue
        idx = lab["index"]
        idx_txt = "–" if idx is None else str(idx)
        cells.append(f"""
<td width="33%" valign="top" style="padding:0 5px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr><td bgcolor="{NAVY}" style="background-color:{NAVY}; padding:14px 16px 4px 16px; font-family:{FONT}; font-size:11px; color:{PEACH}; text-transform:uppercase; letter-spacing:2px;">{esc(c['name'])}</td></tr>
    <tr><td bgcolor="{NAVY}" style="background-color:{NAVY}; padding:0 16px; font-family:{FONT}; font-size:30px; color:#ffffff; mso-line-height-rule:exactly; line-height:38px;">{fmt_num(lab['value'])}</td></tr>
    <tr><td bgcolor="{NAVY}" style="background-color:{NAVY}; padding:0 16px 14px 16px; font-family:{FONT}; font-size:12px; color:#ffffff;">lab.bekreftede &middot; {fmt_pct(lab['wow_pct'])} uke/uke</td></tr>
    <tr><td bgcolor="{PEACH}" style="background-color:{PEACH}; padding:10px 16px; font-family:{FONT}; font-size:12px; color:{NAVY};">Indeks mot historikk: <b>{idx_txt}</b><br />Intensitet: <b>{esc(lab.get('intensity') or '–')}</b></td></tr>
  </table>
</td>""")
    return (f'<tr><td style="padding:0 40px;"><table role="presentation" width="100%" cellpadding="0" '
            f'cellspacing="0" border="0"><tr>{"".join(cells)}</tr></table></td></tr>')


def index_bars(result):
    """Horizontal bars of this week's lab-confirmed index; the 100-line is the historical mean."""
    scale_max = 300
    rows = []
    for code, c in COUNTRIES.items():
        lab = result["summary"].get(code, {}).get("lab_cases")
        if not lab or lab["index"] is None:
            continue
        width = max(2, min(lab["index"], scale_max) * 100 // scale_max)
        rows.append(f"""
<tr>
  <td width="90" style="padding:6px 0; font-family:{FONT}; font-size:13px; color:{TEXT};">{esc(c['name'])}</td>
  <td style="padding:6px 0;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
      <td width="{width}%" bgcolor="{NAVY}" style="background-color:{NAVY}; height:16px; line-height:16px; font-size:1px;">&nbsp;</td>
      <td style="padding-left:8px; font-family:{FONT}; font-size:13px; color:{NAVY}; font-weight:bold;">{lab['index']}</td>
    </tr></table>
  </td>
</tr>""")
    if not rows:
        return ""
    scale = (f'<tr><td></td><td style="padding-top:4px; font-family:{FONT}; font-size:11px; color:{MUTED};">'
             f'Indeks 100 = snitt for samme uke i tidligere sesonger (skala 0&ndash;{scale_max})</td></tr>')
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{"".join(rows)}{scale}</table>'


def indicator_table(result):
    th = f"padding:9px 8px; font-weight:bold; border-bottom:2px solid {NAVY}; color:{NAVY}; font-size:12px;"
    head = (f'<tr><td style="{th}">Indikator</td><td style="{th} text-align:right;">Uke</td>'
            f'<td style="{th} text-align:right;">Endring</td><td style="{th} text-align:right;">Hist. snitt</td>'
            f'<td style="{th} text-align:right;">Indeks</td><td style="{th}">Nivå</td></tr>')
    body = []
    for code, c in COUNTRIES.items():
        ind = result["summary"].get(code, {})
        if not ind:
            continue
        body.append(f'<tr><td colspan="6" style="padding:14px 8px 6px 8px; font-size:11px; color:{MUTED}; '
                    f'text-transform:uppercase; letter-spacing:2px;">{esc(c["name"])} &middot; {esc(c["authority"])}</td></tr>')
        for n, (key, s) in enumerate((k, ind[k]) for k in INDICATORS if k in ind):
            bg = f' bgcolor="{PEACH}"' if n % 2 == 1 else ""
            bgs = f" background-color:{PEACH};" if n % 2 == 1 else ""
            td = f'style="padding:8px;{bgs}'
            name = INDICATORS[key]["short"]
            week = parse_yw(s["week"])[1]
            note = " *" if s.get("stale") else ""
            if s.get("low_tests"):
                note += " &dagger;"
            hist = fmt_value(s["hist_mean"], key) if s["hist_mean"] is not None else "–"
            body.append(
                f'<tr><td{bg} {td}">{esc(name)}{note}</td>'
                f'<td{bg} {td} text-align:right;">{fmt_value(s["value"], key)}<br /><span style="font-size:11px; color:{MUTED};">u{week}</span></td>'
                f'<td{bg} {td} text-align:right; color:{delta_color(s["wow_pct"])};">{fmt_pct(s["wow_pct"])}</td>'
                f'<td{bg} {td} text-align:right;">{hist}</td>'
                f'<td{bg} {td} text-align:right; font-weight:bold; color:{delta_color(s["diff_pct"])};">{s["index"] if s["index"] is not None else "–"}</td>'
                f'<td{bg} {td} font-size:12px;">{position_text(s["position"])}</td></tr>'
            )
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="font-family:{FONT}; font-size:13px; color:{TEXT};">{head}{"".join(body)}</table>')


def season_table(result):
    th = f"padding:9px 8px; font-weight:bold; border-bottom:2px solid {NAVY}; color:{NAVY}; font-size:12px;"
    rows = []
    hist_labels = None
    for n, (code, c) in enumerate(COUNTRIES.items()):
        lab = result["summary"].get(code, {}).get("lab_cases")
        if not lab or "season_to_date" not in lab:
            continue
        hist_labels = hist_labels or list(lab["season_to_date_hist"])
        bg = f' bgcolor="{PEACH}"' if n % 2 == 1 else ""
        bgs = f" background-color:{PEACH};" if n % 2 == 1 else ""
        cells = "".join(f'<td{bg} style="padding:8px; text-align:right;{bgs}">{fmt_num(lab["season_to_date_hist"].get(s))}</td>' for s in hist_labels)
        rows.append(
            f'<tr><td{bg} style="padding:8px;{bgs}">{esc(c["name"])}</td>'
            f'<td{bg} style="padding:8px; text-align:right; font-weight:bold;{bgs}">{fmt_num(lab["season_to_date"])}</td>{cells}'
            f'<td{bg} style="padding:8px; text-align:right; font-weight:bold; color:{delta_color((lab["season_to_date_index"] or 100) - 100)};{bgs}">{lab["season_to_date_index"] or "–"}</td></tr>'
        )
    if not rows:
        return ""
    head = (f'<tr><td style="{th}">Land</td><td style="{th} text-align:right;">{esc(result["season"])}</td>'
            + "".join(f'<td style="{th} text-align:right;">{esc(s)}</td>' for s in hist_labels)
            + f'<td style="{th} text-align:right;">Indeks</td></tr>')
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="font-family:{FONT}; font-size:13px; color:{TEXT};">{head}{"".join(rows)}</table>')


def subtype_table(result):
    th = f"padding:9px 8px; font-weight:bold; border-bottom:2px solid {NAVY}; color:{NAVY}; font-size:12px;"
    codes = [c for c in COUNTRIES if c in result["subtypes"]]
    names = list(next(iter(result["subtypes"].values()))["season"]) if codes else []
    head = f'<tr><td style="{th}">Virus (hittil i sesongen)</td>' + "".join(
        f'<td style="{th} text-align:right;">{esc(COUNTRIES[c]["name"])}</td>' for c in codes) + "</tr>"
    rows = []
    for n, name in enumerate(names):
        bg = f' bgcolor="{PEACH}"' if n % 2 == 1 else ""
        bgs = f" background-color:{PEACH};" if n % 2 == 1 else ""
        rows.append(f'<tr><td{bg} style="padding:8px;{bgs}">{esc(name)}</td>' + "".join(
            f'<td{bg} style="padding:8px; text-align:right;{bgs}">{fmt_num(result["subtypes"][c]["season"][name])}</td>'
            for c in codes) + "</tr>")
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="font-family:{FONT}; font-size:13px; color:{TEXT};">{head}{"".join(rows)}</table>')


def cta(url):
    return f"""<tr>
  <td align="center" style="padding:10px 45px 0 45px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
    <td bgcolor="{PEACH}" align="center" style="background-color:{PEACH}; padding:22px 25px;">
    <p style="margin:0 0 14px 0; font-family:{FONT}; font-size:13px; color:{TEXT};">Se grafer per land og indikator, med alle tidligere sesonger</p>
    <!--[if mso]>
    <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word" href="{esc(url)}" style="height:44px;v-text-anchor:middle;width:280px;" arcsize="10%" strokecolor="{NAVY}" fillcolor="{NAVY}">
    <w:anchorlock/>
    <center style="color:#ffffff;font-family:Georgia,'Times New Roman',serif;font-size:15px;font-weight:bold;">&Aring;pne influensatrackeren</center>
    </v:roundrect>
    <![endif]-->
    <!--[if !mso]><!-->
    <a href="{esc(url)}" style="display:inline-block; background-color:{NAVY}; color:#ffffff; font-family:Georgia,'Times New Roman',serif; font-size:15px; font-weight:bold; text-decoration:none; padding:12px 40px; border-radius:4px;">&Aring;pne influensatrackeren</a>
    <!--<![endif]-->
    </td></tr></table>
  </td>
</tr>"""


def footnote(text):
    return (f'<tr><td style="padding:0 45px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
            f'<tr><td width="3" bgcolor="{PEACH}" style="background-color:{PEACH};"></td>'
            f'<td style="padding:12px 0 12px 15px; font-family:{FONT}; font-size:12px; color:{MUTED}; line-height:1.6;">{text}</td>'
            f'</tr></table></td></tr>')


# ------------------------------------------------------------------ page ----

def render(result, dashboard_url=None):
    url = dashboard_url or DASHBOARD_URL
    week = parse_yw(result["latest_week"])[1]
    seasons = sorted({s for c in result["summary"].values() for i in c.values() for s in i.get("hist_by_season", {})})
    hist_span = f"{seasons[0]}–{seasons[-1]}" if seasons else "tidligere sesonger"

    parts = [
        f"""<tr><td bgcolor="{NAVY}" style="background-color:{NAVY}; padding:35px 45px 30px 45px;">
<p style="margin:0 0 10px 0; font-family:{FONT}; font-size:11px; color:{PEACH}; letter-spacing:2px; text-transform:uppercase;">Karo Healthcare Norway &middot; Influensatracker</p>
<p style="margin:0; font-family:{FONT}; font-size:28px; font-weight:normal; color:#ffffff; mso-line-height-rule:exactly; line-height:36px;">Influensaoversikt uke {week}</p>
<p style="margin:10px 0 0 0; font-family:{FONT}; font-size:13px; color:{PEACH}; letter-spacing:1px; text-transform:uppercase;">{esc(week_range(result))} &middot; Sesong {esc(result['season'])}</p>
</td></tr>""",
        spacer(30),
        row(f'<p style="margin:0;">Ukentlig status for influensa i Norge, Sverige og Danmark. '
            f'Tallene sammenlignes med samme uke i sesongene {esc(hist_span)}. '
            f'Indeks 100 betyr samme nivå som historisk snitt.</p>'),
        spacer(25),
        kpi_tiles(result),
        spacer(30),
        row(label("Hovedfunn denne uka") + bullets(result["findings"])),
        spacer(25),
        divider(),
        spacer(25),
        row(label("Laboratoriebekreftede tilfeller mot historikk") + index_bars(result)),
        spacer(25),
        divider(),
        spacer(25),
        row(label("Alle indikatorer") + heading("Nivå mot samme uke tidligere sesonger") + indicator_table(result)),
        spacer(25),
        row(label("Sesongen hittil") + heading("Akkumulerte lab.bekreftede tilfeller fra uke 40")
            + season_table(result)
            + f'<p style="margin:8px 0 0 0; font-size:12px; color:{MUTED};">Tidligere sesonger er summert til og med samme uke.</p>'),
        spacer(25),
        row(label("Virustyper") + subtype_table(result)),
        spacer(25),
        cta(url),
        spacer(25),
        footnote(
            "Kilde: " + esc(result["source"]["name"]) + ". " + esc(result["source"]["note"])
            + " Indeks = ukens verdi / snitt for samme ISO-uke i tidligere sesonger &times; 100. "
            "Intensitet er ukens verdi sett mot snittet av tidligere sesongtopper (&lt;10 % basisniv&aring;, "
            "10&ndash;40 % lav, 40&ndash;70 % moderat, 70&ndash;100 % h&oslash;y, &gt;100 % sv&aelig;rt h&oslash;y). "
            "* = siste rapporterte uke er eldre enn uke " + str(week) + ". "
            "&dagger; = f&aelig;rre enn 20 sentinel-pr&oslash;ver, tolk med forsiktighet."
        ),
        spacer(10),
        f'<tr><td style="padding:25px 45px 30px 45px; border-top:1px solid {DIVIDER};">'
        f'<p style="margin:0; font-family:{FONT}; font-size:12px; color:{MUTED}; line-height:1.6;">'
        f'Karo Healthcare Norway &middot; Intern kommunikasjon &middot; Generert automatisk {esc(result["generated_at"][:10])}</p></td></tr>',
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
    lines = [subject(result), "", *[f"- {f}" for f in result["findings"]], "", f"Dashboard: {DASHBOARD_URL}"]
    return "\n".join(lines)


def send(html_body, subj, result=None):
    """Send over SMTP using SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, MAIL_FROM, MAIL_TO."""
    host = os.environ.get("SMTP_HOST")
    to = [a.strip() for a in os.environ.get("MAIL_TO", "").split(",") if a.strip()]
    if not host or not to:
        print("SMTP_HOST/MAIL_TO er ikke satt – e-post ble ikke sendt.")
        return False
    user = os.environ.get("SMTP_USER")
    sender = os.environ.get("MAIL_FROM") or user
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subj
    msg["From"] = sender
    msg["To"] = ", ".join(to)
    msg.attach(MIMEText(plain_text(result) if result else subj, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    port = int(os.environ.get("SMTP_PORT", "587"))
    if port == 465:
        server = smtplib.SMTP_SSL(host, port, timeout=60)
    else:
        server = smtplib.SMTP(host, port, timeout=60)
        server.starttls()
    with server:
        if user:
            server.login(user, os.environ.get("SMTP_PASSWORD", ""))
        server.sendmail(sender, to, msg.as_string())
    print(f"E-post sendt til {', '.join(to)}")
    return True
