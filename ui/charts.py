"""Plotly figures with one shared visual language."""

import pandas as pd
import plotly.graph_objects as go

from ui.theme import (
    BAR_MUTED, BORDER, FAINT, FONT, MUTED, NEGATIVE, NEUTRAL, POSITIVE, SURFACE_HIGH, TEXT, category_name, month_label, number,
    percent,
)

PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True}
SENTIMENT_COLOR = {"negativa": NEGATIVE, "positiva": POSITIVE, "neutra": NEUTRAL}


def _rgba(hex_color: str, alpha: float) -> str:
  h = hex_color.lstrip("#")
  r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
  return f"rgba({r}, {g}, {b}, {alpha})"


def _base(fig: go.Figure, height: int, margin=None) -> go.Figure:
  fig.update_layout(
      height=height,
      margin=margin or dict(t=8, b=8, l=0, r=8),
      paper_bgcolor="rgba(0,0,0,0)",
      plot_bgcolor="rgba(0,0,0,0)",
      font=dict(family=FONT, size=12, color=MUTED),
      hoverlabel=dict(bgcolor=SURFACE_HIGH, bordercolor=BORDER, font=dict(family=FONT, size=12, color=TEXT)),
      showlegend=False,
      dragmode=False,
      separators=",.",
  )
  return fig


def category_bars(ranking: pd.DataFrame, sentiment: str, top: int = 8) -> go.Figure:
  data = ranking.head(top).iloc[::-1]
  color = SENTIMENT_COLOR[sentiment]
  names = [category_name(c) for c in data["category"]]
  labels = [f"{number(n)}  ·  {percent(r, 0)}" for n, r in zip(data["reviews"], data["rate_in_category"])]
  fig = go.Figure(go.Bar(
      x=data["reviews"],
      y=names,
      orientation="h",
      marker=dict(color=[BAR_MUTED] * (len(data) - 1) + [color], line=dict(width=0)),
      text=labels,
      textposition="outside",
      textfont=dict(family=FONT, size=12, color=MUTED),
      cliponaxis=False,
      customdata=data["category"],
      hovertemplate="<b>%{y}</b><br>%{x:,} avaliações<extra></extra>",
      width=0.62,
      selected=dict(marker=dict(opacity=1)),
      unselected=dict(marker=dict(opacity=0.35)),
  ))
  fig.update_xaxes(visible=False, range=[0, data["reviews"].max() * 1.6])
  fig.update_yaxes(tickfont=dict(family=FONT, size=12.5, color=TEXT), ticksuffix="   ", showgrid=False)
  return _base(fig, height=40 * len(data) + 20)


def monthly_rate(monthly: pd.DataFrame, sentiment: str) -> go.Figure:
  column = "negative_rate" if sentiment == "negativa" else "positive_rate"
  color = SENTIMENT_COLOR[sentiment]
  x = [month_label(m) for m in monthly["purchase_month"]]
  y = monthly[column]
  fig = go.Figure(go.Scatter(
      x=x, y=y, mode="lines", line=dict(color=color, width=2.2, shape="spline", smoothing=0.6),
      fill="tozeroy", fillcolor=_rgba(color, 0.08),
      customdata=monthly["reviews"],
      hovertemplate="<b>%{x}</b><br>%{y:.1%} das avaliações<br>%{customdata:,} avaliações no mês<extra></extra>",
  ))
  peak = int(y.idxmax()) if sentiment == "negativa" else int(y.idxmin())
  fig.add_trace(go.Scatter(
      x=[x[peak]], y=[y.iloc[peak]], mode="markers+text",
      marker=dict(color=color, size=8, line=dict(color=SURFACE_HIGH, width=2)),
      text=[percent(y.iloc[peak], 0)], textposition="top center",
      textfont=dict(family=FONT, size=12, color=TEXT), hoverinfo="skip",
  ))
  fig.update_xaxes(showgrid=False, tickfont=dict(size=11, color=FAINT), nticks=8, showline=False)
  fig.update_yaxes(
      tickformat=".0%", gridcolor=_rgba("#FFFFFF", 0.05), zeroline=False, tickfont=dict(size=11, color=FAINT),
      range=[0, y.max() * 1.25], nticks=5,
  )
  return _base(fig, height=300, margin=dict(t=18, b=8, l=0, r=12))


def share_donut(ranking: pd.DataFrame, sentiment: str, top: int = 6) -> go.Figure:
  head = ranking.head(top)
  others = ranking.iloc[top:]["reviews"].sum()
  names = [category_name(c) for c in head["category"]] + ["Outras"]
  values = list(head["reviews"]) + [others]
  base = SENTIMENT_COLOR[sentiment]
  colors = [_rgba(base, a) for a in (1, 0.8, 0.64, 0.5, 0.38, 0.28)][:len(head)] + [_rgba("#FFFFFF", 0.1)]
  fig = go.Figure(go.Pie(
      labels=names, values=values, hole=0.62, sort=False, direction="clockwise",
      marker=dict(colors=colors, line=dict(color="rgba(0,0,0,0)", width=0)),
      textinfo="none", hovertemplate="<b>%{label}</b><br>%{value:,} · %{percent}<extra></extra>",
  ))
  fig.update_layout(showlegend=True, legend=dict(font=dict(family=FONT, size=12, color=TEXT), x=1.02, y=0.5))
  _base(fig, height=300)
  fig.update_layout(showlegend=True)
  return fig


def composition(rows: list[tuple[str, int, int, int]]) -> go.Figure:
  """100% stacked bars; each row is (label, negative, neutral, positive)."""
  labels = [r[0] for r in rows][::-1]
  totals = [sum(r[1:]) for r in rows][::-1]
  fig = go.Figure()
  for index, (name, color) in enumerate((("Reclamações", NEGATIVE), ("Neutras", NEUTRAL), ("Elogios", POSITIVE)), 1):
    shares = [r[index] / sum(r[1:]) for r in rows][::-1]
    fig.add_trace(go.Bar(
        y=labels, x=shares, name=name, orientation="h", marker=dict(color=color, line=dict(width=0)),
        text=[percent(s, 0) if s >= 0.06 else "" for s in shares], textposition="inside",
        insidetextanchor="middle", textfont=dict(family=FONT, size=12, color="#0C0D10"),
        customdata=totals, hovertemplate=f"<b>%{{y}}</b><br>{name}: %{{x:.1%}}<extra></extra>", width=0.56,
    ))
  fig.update_layout(barmode="stack", showlegend=True,
                    legend=dict(orientation="h", y=-0.12, x=0, traceorder="normal", font=dict(family=FONT, size=12, color=MUTED)))
  fig.update_xaxes(visible=False, range=[0, 1])
  fig.update_yaxes(tickfont=dict(family=FONT, size=12.5, color=TEXT), ticksuffix="   ")
  _base(fig, height=140, margin=dict(t=4, b=4, l=0, r=0))
  fig.update_layout(showlegend=True)
  return fig
