import pandas as pd

from src.analytics import ReviewAnalytics


def make_analytics():
  df = pd.DataFrame({
      "review_score": [1, 2, 5, 4, 3, 1],
      "product_category_name": ["a", "a", "a", "b", "b", "b"],
      "purchase_month": ["2018-01", "2018-01", "2018-01", "2018-02", "2018-02", "2018-02"],
      "delivery_status": ["atrasado", "no_prazo", "no_prazo", "no_prazo", "nao_entregue", "nao_entregue"],
  })
  return ReviewAnalytics(df)


def test_counts_and_ranking_rate():
  analytics = make_analytics()
  counts = analytics.counts("a")
  assert (counts.total, counts.negative, counts.positive, counts.neutral) == (3, 2, 1, 0)
  ranking = analytics.ranking("negativa").set_index("category")
  assert ranking.loc["a", "reviews"] == 2
  assert round(ranking.loc["a", "rate_in_category"], 3) == 0.667


def test_monthly_rates_skip_small_months():
  rates = make_analytics().monthly_rates(min_reviews=3).set_index("purchase_month")
  assert round(rates.loc["2018-01", "negative_rate"], 3) == 0.667
  assert make_analytics().monthly_rates(min_reviews=4).empty


def test_late_delivery_share_by_sentiment():
  analytics = make_analytics()
  assert analytics.late_delivery_share("negativa") == 2 / 3
  assert analytics.late_delivery_share("positiva") == 0.0
