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


def _panel(ax, by_year, colours, small):
    weeks = list(range(1, 54))
    newest = max(int(y) for y in by_year)
    for year in sorted(by_year, key=int):
        values = by_year[year]
        current = int(year) == newest
        ax.plot(weeks, [float("nan") if v is None else v for v in values], color=colours[int(year)],
                linewidth=2.8 if current else 1.4, alpha=1 if current else 0.9, zorder=3 if current else 2, label=year)
        if current:
            last = max((i for i, v in enumerate(values) if v is not None), default=None)
            if last is not None:
                ax.plot(weeks[last], values[last], "o", color=NAVY, markersize=4 if small else 5, zorder=4)
                near_edge = weeks[last] > (38 if small else 46)
                ax.annotate(f"{values[last]:,.0f}\nweek {weeks[last]}", (weeks[last], values[last]),
                            xytext=(-6 if near_edge else 6, 8), textcoords="offset points",
                            ha="right" if near_edge else "left", fontsize=7 if small else 8.5,
                            color=NAVY, fontweight="bold", zorder=5,
                            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.9))
    ax.set_xlim(1, 53)
    ax.set_ylim(bottom=0)
    ax.set_xticks(MONTH_WEEKS[::2] if small else MONTH_WEEKS)
    ax.set_xticklabels(MONTHS[::2] if small else MONTHS)
    ax.tick_params(colors=MUTED, labelsize=8 if small else 9, length=0)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(4 if small else 5))
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#D9D9D9")


def year_chart(result, path, area="ALL"):
    """Write the Nordic year-by-year chart as PNG; returns the path, or None without data.

    Influenza is the large panel; COVID-19 and RSV sit side by side below. Titles live in
    the e-mail HTML, so the image holds only the year legend and the plots.
    """
    data = result["yearly"]["areas"].get(area, {})
    if "flu_cases" not in data:
        return None
    colours = year_colours(result["yearly"]["years"])
    plt.rcParams["font.family"] = "DejaVu Sans"
    fig = plt.figure(figsize=(5.5, 5.0), dpi=200)
    grid = fig.add_gridspec(2, 2, height_ratios=[1.45, 1], hspace=0.38, wspace=0.22)
    axes = [fig.add_subplot(grid[0, :]), fig.add_subplot(grid[1, 0]), fig.add_subplot(grid[1, 1])]
    for ax, (key, name) in zip(axes, PANELS):
        if key not in data:
            ax.set_visible(False)
            continue
        small = ax is not axes[0]
        _panel(ax, data[key], colours, small)
        ax.text(0, 1.04, name, transform=ax.transAxes, fontsize=10 if small else 11.5, color=NAVY, fontweight="bold")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles[::-1], labels[::-1], loc="upper right", ncol=len(labels), frameon=False,
               fontsize=8.5, bbox_to_anchor=(0.985, 1.0), handlelength=1.5, columnspacing=1.1, handletextpad=0.5)
    fig.subplots_adjust(left=0.1, right=0.98, top=0.9, bottom=0.06)
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return path
