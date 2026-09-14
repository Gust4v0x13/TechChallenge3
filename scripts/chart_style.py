"""
Shared chart style for visualization/chart_generation.ipynb and
scripts/generate_charts.py — the validated default palette from the
dataviz skill (references/palette.md), applied unchanged (no custom hue
ordering introduced here, so no re-validation is required — see that
file's "swap in your own ramps" caveat, which does not apply to this
unmodified reference instance).

Charts here are static PNGs for the executive deck (presentation/), not
interactive HTML, so the hover/tooltip layer from the dataviz skill does
not apply — everything else does: fixed categorical hue order, one hue
sequential ramps for magnitude, the blue<->red diverging pair for
positive/negative change, muted gridlines/axes, and direct labels instead
of a legend wherever there is only one series per chart.

Plotting itself is done with matplotlib + seaborn: seaborn draws the marks
(sns.barplot / sns.lineplot) onto axes we create and size ourselves, so we
keep full control over figure size, saving, and the caption/label fixes
below — seaborn only replaces the manual x-position/width bookkeeping that
grouped bars needed before.
"""
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import seaborn as sns

# --- light-mode surface & ink (charts are exported for a white-background deck) ---
SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"

# --- categorical palette, FIXED order — never re-cycled, never reordered per chart ---
CATEGORICAL = [
    "#2a78d6",  # 1 blue
    "#eb6834",  # 2 orange
    "#1baf7a",  # 3 aqua
    "#eda100",  # 4 yellow
    "#e87ba4",  # 5 magenta
    "#008300",  # 6 green
    "#4a3aa7",  # 7 violet
    "#e34948",  # 8 red
]

# --- sequential (single hue, light -> dark), used for pure magnitude ranking ---
SEQUENTIAL_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

# --- diverging pair: blue (negative) <-> red (positive), gray midpoint ---
DIVERGING_NEGATIVE = "#2a78d6"
DIVERGING_POSITIVE = "#e34948"
DIVERGING_MIDPOINT = "#f0efec"

# --- status (reserved — only for genuine state, never reused as a series color) ---
STATUS_GOOD = "#0ca30c"
STATUS_WARNING = "#fab219"
STATUS_SERIOUS = "#ec835a"
STATUS_CRITICAL = "#d03b3b"

FONT_STACK = ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"]


def apply_style():
    """Sets the seaborn theme (rc dict shared with matplotlib) and pins
    seaborn's default categorical palette to our fixed hue order, so any
    sns.barplot/lineplot that doesn't pass an explicit `palette=` still
    never falls back to seaborn's own default cycle."""
    rc = {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.family": FONT_STACK,
        "font.size": 11,
        "text.color": INK_PRIMARY,
        "axes.edgecolor": BASELINE,
        "axes.labelcolor": INK_SECONDARY,
        "axes.titlecolor": INK_PRIMARY,
        "axes.titleweight": "bold",
        "axes.titlesize": 13,
        "axes.grid": True,
        "grid.color": GRIDLINE,
        "grid.linewidth": 0.8,
        "xtick.color": INK_MUTED,
        "ytick.color": INK_MUTED,
        "xtick.labelsize": 9.5,
        "ytick.labelsize": 9.5,
        "legend.frameon": False,
        "legend.fontsize": 9.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.spines.bottom": True,
    }
    sns.set_theme(style="whitegrid", rc=rc)
    sns.set_palette(CATEGORICAL)


def style_horizontal_bar_axes(ax):
    """Recessive gridlines on the value axis only, no left spine (labels sit
    directly beside the bars — the category axis is not a measured axis)."""
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.spines["bottom"].set_color(BASELINE)


def style_vertical_bar_axes(ax):
    ax.grid(axis="x", visible=False)
    ax.grid(axis="y", visible=True)
    ax.spines["bottom"].set_color(BASELINE)


def add_source_caption(fig, text):
    fig.text(0.01, 0.01, text, fontsize=8, color=INK_MUTED, ha="left", va="bottom")


def savefig(fig, path, add_caption_text=None):
    if add_caption_text:
        add_source_caption(fig, add_caption_text)
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor=SURFACE)
    print(f"  -> saved {path}")


def label_bars(ax, fmt, padding=3, fontsize=8.5, color=INK_SECONDARY, min_value=None):
    """Adds a value label above/beside every bar in every container on `ax`
    (one container per seaborn hue level for grouped bars), via
    matplotlib's built-in Axes.bar_label — replaces the old per-chart
    manual `for b, v in zip(bars, values): ax.text(...)` loops.

    `fmt` is a callable float -> str (e.g. lambda v: f"{v*100:.0f}%").
    NaN bars (missing year/category combos) get an empty label instead of
    "nan" — seaborn still leaves a zero-width gap for them.

    `min_value`, when set, suppresses the label on bars smaller than it in
    magnitude — use this (not an exact `== 0` check) for shares that are
    truthfully nonzero but round to a misleading "0%" at the chosen
    decimal precision (e.g. a 0.3% slice on a chart labeled to 0 decimals);
    an exact-zero check would still mislabel those as "0%".
    """
    import math
    for container in ax.containers:
        labels = []
        for v in container.datavalues:
            if v is None or (isinstance(v, float) and math.isnan(v)):
                labels.append("")
            elif min_value is not None and abs(v) < min_value:
                labels.append("")
            else:
                labels.append(fmt(v))
        ax.bar_label(container, labels=labels, padding=padding, fontsize=fontsize, color=color)
