"""Static "year by year" chart for the e-mail (Outlook cannot show interactive charts).

Each calendar year is one line over ISO weeks 1–53 (January to December), for the
Nordic total of influenza, COVID-19 and RSV.
"""

import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

# The e-mail is set in Georgia, which may not be redistributed. Gelasio is an open font
# drawn to the same proportions, bundled here so the chart looks the same wherever it is built.
FONT = "Gelasio"
for _ttf in sorted((pathlib.Path(__file__).parent / "fonts").glob("*.ttf")):
    font_manager.fontManager.addfont(str(_ttf))

NAVY = "#110B36"
MUTED = "#6B7280"
GRID = "#ECECEC"
# Newest year first; the current year is drawn thickest in navy. Mirrors the dashboard.
YEAR_COLOURS = [NAVY, "#E07B39", "#008A7A", "#9B3F96", "#9F9DB1", "#C9C7D6"]
# ISO week in which each month starts (approximately) – used for the month labels.
MONTH_WEEKS = [1, 5, 9, 14, 18, 22, 27, 31, 36, 40, 44, 49]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
# Size of the chart in the e-mail, in CSS pixels (the PNG holds twice as many).
EMAIL_SIZE = (550, 860)
PANELS = [("flu_cases", "Influenza"), ("covid_cases", "COVID-19"), ("rsv_cases", "RSV")]


def year_colours(years):
    """{year: colour}, newest year first in the palette."""
    return {y: YEAR_COLOURS[min(i, len(YEAR_COLOURS) - 1)] for i, y in enumerate(sorted(years, reverse=True))}


def _panel(ax, by_year, colours, name):
    weeks = list(range(1, 54))
    newest = max(int(y) for y in by_year)
    latest = None
    for year in sorted(by_year, key=int):
        values = by_year[year]
        current = int(year) == newest
        ax.plot(weeks, [float("nan") if v is None else v for v in values], color=colours[int(year)],
                linewidth=3.2 if current else 1.7, zorder=3 if current else 2, label=year,
                solid_capstyle="round", solid_joinstyle="round")
        if current:
            last = max((i for i, v in enumerate(values) if v is not None), default=None)
            if last is not None:
                latest = (weeks[last], values[last])
    # Panel title, with this year's latest figure beside it instead of a label inside the
    # plot (a label there hides the other years' lines right where they are compared).
    ax.text(0, 1.06, name, transform=ax.transAxes, fontsize=13.5, color=NAVY, fontweight="bold")
    if latest:
        week, value = latest
        ax.axvline(week, color="#C9C7D6", linewidth=0.9, linestyle=(0, (2, 2.5)), zorder=1)
        ax.plot(week, value, "o", color=NAVY, markersize=8, markeredgecolor="white", markeredgewidth=1.6,
                zorder=4, clip_on=False)
        ax.text(1, 1.06, f"{value:,.0f} in week {week}", transform=ax.transAxes, ha="right",
                fontsize=11, color=NAVY, fontweight="bold")
    ax.set_xlim(1, 53)
    ax.set_ylim(bottom=0)
    ax.margins(y=0.08)
    # Short ticks where each month starts, the month name centred in between.
    ax.set_xticks(MONTH_WEEKS)
    ax.set_xticklabels([])
    ax.set_xticks([(a + b) / 2 for a, b in zip(MONTH_WEEKS, MONTH_WEEKS[1:] + [53])], minor=True)
    ax.set_xticklabels(MONTHS, minor=True)
    ax.tick_params(axis="x", which="major", length=4, color="#D9D9D9")
    ax.tick_params(axis="x", which="minor", length=0, pad=6)
    ax.tick_params(axis="y", length=0, pad=6)
    ax.tick_params(which="both", labelcolor=MUTED, labelsize=10.5)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(4))
    ax.grid(axis="y", color=GRID, linewidth=0.9)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#D9D9D9")


def year_chart(result, path, area="ALL"):
    """Write the Nordic year-by-year chart as PNG; returns the path, or None without data.

    The three viruses are stacked full width, so the text stays readable when a phone
    scales the image down to the width of the screen. The image is drawn at twice
    EMAIL_SIZE, which keeps it sharp on high-resolution screens.
    """
    data = result["yearly"]["areas"].get(area, {})
    if "flu_cases" not in data:
        return None
    colours = year_colours(result["yearly"]["years"])
    plt.rcParams["font.family"] = [FONT, "DejaVu Serif"]
    fig = plt.figure(figsize=(EMAIL_SIZE[0] / 100, EMAIL_SIZE[1] / 100), dpi=200)
    grid = fig.add_gridspec(3, 1, height_ratios=[1.3, 1, 1], hspace=0.42)
    axes = [fig.add_subplot(grid[i, 0]) for i in range(3)]
    for ax, (key, name) in zip(axes, PANELS):
        if key not in data:
            ax.set_visible(False)
            continue
        _panel(ax, data[key], colours, name)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles[::-1], labels[::-1], loc="upper left", ncol=len(labels), frameon=False,
               fontsize=11, bbox_to_anchor=(0.1, 1.0), handlelength=1.3, columnspacing=1.3,
               handletextpad=0.5, borderaxespad=0.2, labelcolor=NAVY)
    fig.subplots_adjust(left=0.115, right=0.985, top=0.915, bottom=0.04)
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return path
