from matplotlib.colors import to_rgba

PLOT_COLOR_ALPHA = 1.0

# ORDERED_PLOT_PALETTE entries are the commented base colors blended ~20%
# towards white; tint() reproduces that so ad-hoc colors match the family.
PLOT_TINT_FRACTION = 0.2


def with_plot_alpha(color, alpha: float | None = None):
    return to_rgba(color, PLOT_COLOR_ALPHA if alpha is None else alpha)


def tint(color, fraction: float = PLOT_TINT_FRACTION):
    red, green, blue, alpha = to_rgba(color)
    return (
        red + (1.0 - red) * fraction,
        green + (1.0 - green) * fraction,
        blue + (1.0 - blue) * fraction,
        alpha,
    )


ORDERED_PLOT_PALETTE = (
    "#7195BC",  # "#4e79a7",
    "#E77476",  # "#e15759",
    "#7BBA73",  # "#59a14f",
    "#e396cd",  # "#59a14f",
    "#f28e2b",
    "#b07aa1",
    "#76b7b2",
    "#9c755f",
    "#edc948",
    "#ff9da7",
    "#bab0ab",
)

REACT_CLASSIFICATION_PALETTE = (
    "#4e79a7",
    "#f28e2c",
    "#e15759",
    "#76b7b2",
    "#59a14f",
    "#edc949",
    "#af7aa1",
    "#ff9da7",
    "#9c755f",
    "#bab0ab",
    "#66c2a5",
    "#fc8d62",
    "#8da0cb",
    "#e78ac3",
    "#a6d854",
    "#ffd92f",
    "#e5c494",
    "#b3b3b3",
    "#8dd3c7",
    "#ffffb3",
    "#bebada",
    "#fb8072",
    "#80b1d3",
    "#fdb462",
    "#b3de69",
    "#fccde5",
    "#d9d9d9",
    "#bc80bd",
    "#ccebc5",
    "#ffed6f",
)

NEUTRAL_PLOT_COLOR = "#868e96"

BIP_TYPE_ORDER = [
    "Specification",
    "Informational",
    "Process",
    "Unknown Type",
]

# Keep both mappings here so switching the paper plots back is a one-line change.
REACT_CONSISTENT_BIP_TYPE_COLORS = {
    "Specification": REACT_CLASSIFICATION_PALETTE[0],
    "Informational": REACT_CLASSIFICATION_PALETTE[1],
    "Process": REACT_CLASSIFICATION_PALETTE[2],
    "Unknown Type": NEUTRAL_PLOT_COLOR,
}

OKABE_ITO_BIP_TYPE_COLORS = {
    "Specification": "#0072B2",
    "Informational": "#E69F00",
    "Process": "#CC79A7",
    "Unknown Type": NEUTRAL_PLOT_COLOR,
}

TRIPTYCH_BIP_TYPE_COLORS = {
    "Specification": ORDERED_PLOT_PALETTE[0],
    "Informational": ORDERED_PLOT_PALETTE[1],
    "Process": ORDERED_PLOT_PALETTE[2],
    "Unknown Type": NEUTRAL_PLOT_COLOR,
}

BIP_TYPE_COLORS = TRIPTYCH_BIP_TYPE_COLORS

# Quartet panel colors: (a) top authors red, (b) clusters green,
# (c) authors per BIP blue, (d) BIPs per author orange.
TOP_AUTHORS_COLOR = ORDERED_PLOT_PALETTE[1]
COLLABORATION_COMPONENT_COLOR = ORDERED_PLOT_PALETTE[2]
AUTHORS_PER_BIP_COLOR = ORDERED_PLOT_PALETTE[0]
AUTHORSHIP_DISTRIBUTION_COLOR = ORDERED_PLOT_PALETTE[4]
COAUTHOR_DEGREE_COLOR = ORDERED_PLOT_PALETTE[0]
