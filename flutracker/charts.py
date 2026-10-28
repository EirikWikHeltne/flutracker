"""Static "year by year" chart for the e-mail (Outlook cannot show interactive charts).

Each calendar year is one line over ISO weeks 1–53 (January to December), for the
Nordic total of influenza, COVID-19 and RSV.
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

NAVY = "#110B36"
MUTED = "#6B7280"
GRID = "#ECECEC"
# Newest year first; the current year is drawn thickest in navy. Mirrors the dashboard.
YEAR_COLOURS = [NAVY, "#E07B39", "#008A7A", "#9B3F96", "#9F9DB1", "#C9C7D6"]
# ISO week in which each month starts (approximately) – used for the month labels.
MONTH_WEEKS = [1, 5, 9, 14, 18, 22, 27, 31, 36, 40, 44, 49]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
PANELS = [("flu_cases", "Influenza"), ("covid_cases", "COVID-19"), ("rsv_cases", "RSV")]


def year_colours(years):
    """{year: colour}, newest year first in the palette."""
    return {y: YEAR_COLOURS[min(i, len(YEAR_COLOURS) - 1)] for i, y in enumerate(sorted(years, reverse=True))}


def _panel(ax, by_year, colours, title, small):
    weeks = list(range(1, 54))
    newest = max(int(y) for y in by_year)
    for year in sorted(by_year, key=int):
        values = by_year[year]
        if all(v is None for v in values):
            continue
        current = int(year) == newest
        ax.plot(weeks, [float("nan") if v is None else v for v in values], color=colours[int(year)],
                linewidth=2.6 if current else 1.5, zorder=3 if current else 2, label=year)
    ax.set_title(title, loc="left", fontsize=11 if small else 13, color=NAVY, pad=6)
    ax.set_xlim(1, 53)
    ax.set_ylim(bottom=0)
    ax.set_xticks(MONTH_WEEKS[::2] if small else MONTH_WEEKS)
    ax.set_xticklabels(MONTHS[::2] if small else MONTHS)
    ax.tick_params(colors=MUTED, labelsize=8 if small else 9, length=0)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#D9D9D9")


def year_chart(result, path, area="ALL"):
    """Write the Nordic year-by-year chart as PNG; returns the path, or None without data."""
    data = result["yearly"]["areas"].get(area, {})
    if "flu_cases" not in data:
        return None
    colours = year_colours(result["yearly"]["years"])
    plt.rcParams["font.family"] = "DejaVu Serif"
    fig = plt.figure(figsize=(5.5, 5.4), dpi=200)
    grid = fig.add_gridspec(2, 2, height_ratios=[1.35, 1], hspace=0.45, wspace=0.28)
    axes = [fig.add_subplot(grid[0, :]), fig.add_subplot(grid[1, 0]), fig.add_subplot(grid[1, 1])]
    for ax, (key, name) in zip(axes, PANELS):
        if key in data:
            small = ax is not axes[0]
            _panel(ax, data[key], colours, name if small else f"{name} – lab-confirmed cases per week", small)
        else:
            ax.set_visible(False)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles[::-1], labels[::-1], loc="upper center", ncol=len(labels), frameon=False,
               fontsize=9, bbox_to_anchor=(0.5, 1.0), handlelength=1.6, columnspacing=1.2)
    fig.subplots_adjust(left=0.1, right=0.98, top=0.88, bottom=0.07)
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return path
