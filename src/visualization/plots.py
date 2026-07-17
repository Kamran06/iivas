"""
Section 8 — publication-quality visualisations.

Generates static (matplotlib/seaborn) figures for a paper/README and an
interactive Plotly bundle for exploration. All figures are written to
reports/figures/. Functions are individually callable so a notebook can pull
just one chart.

Charts:
  bar           -> IIVAS composite ranking by investor
  heatmap       -> support rate (investor x category)
  corr_matrix   -> correlation of sub-scores across investor-years
  radar         -> sub-score profile per investor (plotly)
  trend         -> yearly support-rate lines
  sankey        -> proposal-category -> vote-outcome flow (plotly)
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")  # headless backend for reproducible file output
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns

from src.io_utils import read_df, write_df
from src.config_loader import path

sns.set_theme(style="whitegrid", context="talk")
PALETTE = {"Vanguard": "#C8102E", "BlackRock": "#1A1A1A", "State Street": "#00833C"}


def _read(name: str) -> pd.DataFrame:
    return pd.read_csv(path("processed") / name)


def bar_iivas_ranking() -> None:
    df = _read("iivas_overall.csv").sort_values("iivas_composite")
    fig, ax = plt.subplots(figsize=(9, 5))
    colors = [PALETTE.get(f, "#666") for f in df["filer"]]
    ax.barh(df["filer"], df["iivas_composite"], color=colors)
    ax.set_xlabel("IIVAS composite (0-100, higher = more management-aligned)")
    ax.set_title("Institutional Investor Voting Alignment Score")
    for y, v in enumerate(df["iivas_composite"]):
        ax.text(v + 0.5, y, f"{v:.1f}", va="center")
    fig.tight_layout()
    fig.savefig(path("figures") / "bar_iivas_ranking.png", dpi=200)
    plt.close(fig)


def heatmap_support_by_category() -> None:
    df = _read("eda_support_by_category.csv")
    pivot = df.pivot_table(index="filer", columns="category",
                           values="support_rate", aggfunc="mean")
    fig, ax = plt.subplots(figsize=(10, 4))
    sns.heatmap(pivot, annot=True, fmt=".2f", cmap="RdYlGn", vmin=0, vmax=1, ax=ax)
    ax.set_title("Management-support rate by investor and proposal category")
    fig.tight_layout()
    fig.savefig(path("figures") / "heatmap_support_category.png", dpi=200)
    plt.close(fig)


def correlation_matrix() -> None:
    df = _read("iivas_by_year.csv")
    cols = ["governance_score", "compensation_score", "esg_score",
            "management_alignment_score", "iivas_composite"]
    corr = df[cols].corr()
    fig, ax = plt.subplots(figsize=(7, 6))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", center=0, ax=ax)
    ax.set_title("Correlation of IIVAS sub-scores (investor-years)")
    fig.tight_layout()
    fig.savefig(path("figures") / "corr_subscores.png", dpi=200)
    plt.close(fig)


def radar_profiles() -> None:
    df = _read("iivas_overall.csv")
    cats = ["governance_score", "compensation_score", "esg_score",
            "management_alignment_score"]
    labels = ["Governance", "Compensation", "ESG", "Mgmt Alignment"]
    fig = go.Figure()
    for _, r in df.iterrows():
        fig.add_trace(go.Scatterpolar(
            r=[r[c] for c in cats] + [r[cats[0]]],
            theta=labels + [labels[0]],
            name=r["filer"], fill="toself",
            line=dict(color=PALETTE.get(r["filer"]))))
    fig.update_layout(title="IIVAS sub-score profiles",
                      polar=dict(radialaxis=dict(range=[0, 100])))
    fig.write_html(path("figures") / "radar_profiles.html")


def trend_lines() -> None:
    df = _read("eda_support_by_year.csv")
    fig, ax = plt.subplots(figsize=(10, 5))
    for filer, g in df.groupby("filer"):
        g = g.sort_values("filing_year")
        ax.plot(g["filing_year"], g["support_rate"], marker="o",
                label=filer, color=PALETTE.get(filer))
    ax.set_ylabel("Management-support rate")
    ax.set_xlabel("Year")
    ax.set_title("Management-support rate over time (RQ6)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path("figures") / "trend_support.png", dpi=200)
    plt.close(fig)


def sankey_category_outcome() -> None:
    df = read_df(path("interim") / "votes_classified.parquet")
    d = df.dropna(subset=["vote_cast"])
    flow = d.groupby(["category", "vote_cast"]).size().reset_index(name="n")
    cats = list(flow["category"].unique())
    outs = list(flow["vote_cast"].unique())
    nodes = cats + outs
    idx = {n: i for i, n in enumerate(nodes)}
    fig = go.Figure(go.Sankey(
        node=dict(label=nodes, pad=15, thickness=18),
        link=dict(source=[idx[c] for c in flow["category"]],
                  target=[idx[o] for o in flow["vote_cast"]],
                  value=flow["n"])))
    fig.update_layout(title_text="Proposal category -> vote outcome", font_size=12)
    fig.write_html(path("figures") / "sankey_category_outcome.html")


def run() -> None:
    for fn in (bar_iivas_ranking, heatmap_support_by_category, correlation_matrix,
               radar_profiles, trend_lines, sankey_category_outcome):
        try:
            fn()
            print(f"  ok: {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            print(f"  skip {fn.__name__}: {exc}")
    print(f"Figures -> {path('figures')}")


if __name__ == "__main__":
    run()
