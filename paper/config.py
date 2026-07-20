"""Shared configuration for paper-oriented scripts."""

# Set this once for all research questions.
SNAPSHOT = "2026-06-30"

# Title font sizes shared by every paper figure (matplotlib's implicit
# default is 12, so these keep existing figures unchanged while making the
# sizes explicit). The combined differential network figure keeps its own
# smaller subplot titles on purpose.
FIGURE_TITLE_FONT_SIZE = 12.0
SUBPLOT_TITLE_FONT_SIZE = 12.0

# Shared legend font size; individual figures may still opt for something
# smaller when a legend has many entries and space is tight.
LEGEND_FONT_SIZE = 9.5
