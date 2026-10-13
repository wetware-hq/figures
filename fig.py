"""figures v0 default_style: one call writes SVG+PDF+PNG(+unannotated)+CSV+source line."""
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.style.use(Path(__file__).with_name("default.mplstyle"))

def save(fig, name, data, source, notes=()):
    """notes: matplotlib Text artists that are annotations (hidden for the unannotated copy)."""
    fig.text(0, -0.04, f"Source: {source}", fontsize=6, transform=fig.transFigure)
    for ext in ("svg", "pdf", "png"):
        fig.savefig(f"{name}.{ext}")
    for n in notes: n.set_visible(False)
    fig.savefig(f"{name}_unannotated.svg"); fig.savefig(f"{name}_unannotated.png")
    data.write_csv(f"{name}.csv")
