"""Builds the knowledge base: one document per customer review with written text.

Decisions (justified in the README, section "Preparação da base"):
- Only reviews with a title or a comment are kept: a score without text carries
  no qualitative evidence for the RAG.
- Title and comment are combined into ``review_text``, the only field that is
  embedded. Category, score, dates and delivery data become metadata, so they
  can filter the search without distorting semantic similarity.
- Orders with items from several categories keep the category of the most
  expensive item (the main purchase of the order).
- Duplicated ``review_id`` (the same review attached to more than one order in
  the source) keeps the first occurrence.
- One-word comments ("Ótima", "Péssima", "ok") are kept for counting but
  flagged as ``is_short`` so they never become evidence for the LLM: they match
  almost any short query and carry no explanation of what happened.
"""

import os
import re

import pandas as pd

from src.config import MIN_EVIDENCE_WORDS, PROCESSED_DIR, RAW_DIR, REVIEWS_CSV

WHITESPACE = re.compile(r"\s+")


def normalize_text(value) -> str:
  if pd.isna(value):
    return ""
  return WHITESPACE.sub(" ", str(value)).strip()


def combine_title_and_comment(title: str, comment: str) -> str:
  if title and comment:
    separator = " " if title.endswith((".", "!", "?")) else ". "
    return f"{title}{separator}{comment}"
  return title or comment


def load_raw():
  read = lambda name: pd.read_csv(os.path.join(RAW_DIR, name))
  return (
      read("olist_order_reviews_dataset.csv"),
      read("olist_orders_dataset.csv"),
      read("olist_order_items_dataset.csv"),
      read("olist_products_dataset.csv"),
  )


def main_category_per_order(order_items: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
  items = order_items.merge(
      products[["product_id", "product_category_name"]], on="product_id", how="left"
  )
  items = items.sort_values(["order_id", "price"], ascending=[True, False])
  main = items.drop_duplicates("order_id")[["order_id", "product_category_name", "price"]]
  categories_per_order = items.groupby("order_id")["product_category_name"].nunique()
  main["has_multiple_categories"] = main["order_id"].map(categories_per_order).gt(1)
  return main.rename(columns={"price": "main_item_price"})


def build_knowledge_base() -> pd.DataFrame:
  reviews, orders, order_items, products = load_raw()
  print(f"Avaliações no dataset: {len(reviews)}")

  reviews["review_comment_title"] = reviews["review_comment_title"].map(normalize_text)
  reviews["review_comment_message"] = reviews["review_comment_message"].map(normalize_text)
  reviews["review_text"] = [
      combine_title_and_comment(t, c)
      for t, c in zip(reviews["review_comment_title"], reviews["review_comment_message"])
  ]
  reviews = reviews[reviews["review_text"] != ""]
  print(f"Com título ou comentário: {len(reviews)}")

  reviews = reviews.drop_duplicates("review_id")
  print(f"Após remover review_id duplicado: {len(reviews)}")

  orders = orders.copy()
  for column in (
      "order_purchase_timestamp",
      "order_delivered_customer_date",
      "order_estimated_delivery_date",
  ):
    orders[column] = pd.to_datetime(orders[column], errors="coerce")

  df = reviews.merge(
      orders[[
          "order_id",
          "order_status",
          "order_purchase_timestamp",
          "order_delivered_customer_date",
          "order_estimated_delivery_date",
      ]],
      on="order_id",
      how="inner",
  )
  df = df.merge(main_category_per_order(order_items, products), on="order_id", how="left")
  print(f"Após cruzar com pedidos: {len(df)}")

  df["product_category_name"] = df["product_category_name"].fillna("desconhecido")
  df["has_multiple_categories"] = df["has_multiple_categories"].fillna(False).astype(bool)

  delivered = df["order_delivered_customer_date"]
  estimated = df["order_estimated_delivery_date"]
  df["delivery_delay_days"] = (delivered - estimated).dt.days
  df["delivery_status"] = "nao_entregue"
  df.loc[delivered.notna() & df["delivery_delay_days"].le(0), "delivery_status"] = "no_prazo"
  df.loc[delivered.notna() & df["delivery_delay_days"].gt(0), "delivery_status"] = "atrasado"

  df["purchase_year"] = df["order_purchase_timestamp"].dt.year.astype("Int64")
  df["purchase_month"] = df["order_purchase_timestamp"].dt.strftime("%Y-%m")
  df["is_short"] = df["review_text"].str.split().str.len().lt(MIN_EVIDENCE_WORDS)

  columns = [
      "review_id",
      "order_id",
      "review_score",
      "review_comment_title",
      "review_comment_message",
      "review_text",
      "is_short",
      "product_category_name",
      "has_multiple_categories",
      "main_item_price",
      "order_status",
      "order_purchase_timestamp",
      "purchase_year",
      "purchase_month",
      "delivery_status",
      "delivery_delay_days",
  ]
  df = df[columns].sort_values(["order_purchase_timestamp", "review_id"]).reset_index(drop=True)

  os.makedirs(PROCESSED_DIR, exist_ok=True)
  df.to_csv(REVIEWS_CSV, index=False, encoding="utf-8")

  print(f"Documentos na base de conhecimento: {len(df)}")
  print(f"Comentários de uma palavra (não viram evidência): {int(df['is_short'].sum())}")
  print(f"Pedidos com mais de uma categoria: {int(df['has_multiple_categories'].sum())}")
  print(f"Status de entrega: {df['delivery_status'].value_counts().to_dict()}")
  print(f"Arquivo salvo em: {REVIEWS_CSV}")
  return df


if __name__ == "__main__":
  build_knowledge_base()
