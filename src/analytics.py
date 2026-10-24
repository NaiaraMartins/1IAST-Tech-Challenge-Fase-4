"""Exact counts over the whole knowledge base.

Rankings, percentages and comparisons are computed here with pandas, never by the
LLM: a language model reading 10 reviews cannot count 42 thousand, and numbers
must be reproducible.
"""

from dataclasses import dataclass

import pandas as pd

from src.config import NEGATIVE_MAX_SCORE, POSITIVE_MIN_SCORE, REVIEWS_CSV


@dataclass
class CategoryCounts:
  total: int
  negative: int
  positive: int
  neutral: int


class ReviewAnalytics:

  def __init__(self, df: pd.DataFrame | None = None):
    self.df = df if df is not None else pd.read_csv(REVIEWS_CSV)
    self.df["sentiment"] = "neutra"
    self.df.loc[self.df["review_score"] <= NEGATIVE_MAX_SCORE, "sentiment"] = "negativa"
    self.df.loc[self.df["review_score"] >= POSITIVE_MIN_SCORE, "sentiment"] = "positiva"

  @property
  def categories(self) -> list[str]:
    return sorted(self.df["product_category_name"].unique())

  def counts(self, category: str | None = None) -> CategoryCounts:
    df = self.df if category is None else self.df[self.df["product_category_name"] == category]
    by_sentiment = df["sentiment"].value_counts()
    return CategoryCounts(
        total=len(df),
        negative=int(by_sentiment.get("negativa", 0)),
        positive=int(by_sentiment.get("positiva", 0)),
        neutral=int(by_sentiment.get("neutra", 0)),
    )

  def ranking(self, sentiment: str = "negativa") -> pd.DataFrame:
    """Categories ordered by number of reviews with the given sentiment.

    ``share_of_sentiment``: the category's share of all reviews with that sentiment.
    ``rate_in_category``: share of the category's own reviews with that sentiment,
    which is the fair comparison between categories of different sizes.
    """
    df = self.df[self.df["product_category_name"] != "desconhecido"]
    totals = df.groupby("product_category_name").size()
    if sentiment == "neutra":
      selected = totals
    else:
      selected = df[df["sentiment"] == sentiment].groupby("product_category_name").size()
    table = pd.DataFrame({"reviews": selected, "category_total": totals}).fillna(0)
    table["share_of_sentiment"] = table["reviews"] / table["reviews"].sum()
    table["rate_in_category"] = table["reviews"] / table["category_total"]
    return (
        table.sort_values("reviews", ascending=False)
        .reset_index(names="category")
        .astype({"reviews": int, "category_total": int})
    )

  def delivery_breakdown(self, category: str | None = None) -> pd.Series:
    df = self.df if category is None else self.df[self.df["product_category_name"] == category]
    return df.groupby("delivery_status")["review_score"].agg(["count", "mean"])

  def monthly_rates(self, min_reviews: int = 300) -> pd.DataFrame:
    """Share of complaints and praise per purchase month.

    Months with fewer than ``min_reviews`` written reviews (the start of 2016
    and the tail of 2018 in this dataset) are left out: a rate over a handful
    of reviews swings too much to read as a trend.
    """
    grouped = self.df.groupby("purchase_month")["sentiment"]
    table = pd.DataFrame({
        "reviews": grouped.size(),
        "negative_rate": grouped.apply(lambda s: (s == "negativa").mean()),
        "positive_rate": grouped.apply(lambda s: (s == "positiva").mean()),
    })
    return table[table["reviews"] >= min_reviews].reset_index()

  def late_delivery_share(self, sentiment: str) -> float:
    """Share of reviews with the given sentiment whose order was late or never delivered."""
    subset = self.df[self.df["sentiment"] == sentiment]
    if subset.empty:
      return 0.0
    return float(subset["delivery_status"].isin(["atrasado", "nao_entregue"]).mean())
