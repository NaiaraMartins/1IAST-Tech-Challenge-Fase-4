"""Generates the review embeddings once and stores them as a versioned artifact.

The vectors are saved as float16 (.npy, ~33 MB) instead of committing the
ChromaDB folder: the SQLite file of a 42k-document collection goes past
GitHub's 100 MB per-file limit, while loading precomputed vectors into a fresh
collection takes seconds (see src/vector_store.py). Re-running this script is
only needed when the knowledge base changes.
"""

import os

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

from src.config import (
    EMBEDDING_IDS_FILE,
    EMBEDDING_MODEL,
    EMBEDDINGS_FILE,
    INDEX_DIR,
    REVIEWS_CSV,
)


def generate_embeddings(batch_size: int = 128):
  if not os.path.exists(REVIEWS_CSV):
    raise FileNotFoundError(
        f"{REVIEWS_CSV} não encontrado. Rode antes: python -m src.preprocessing"
    )

  df = pd.read_csv(REVIEWS_CSV)
  print(f"Documentos a vetorizar: {len(df)}")

  model = SentenceTransformer(EMBEDDING_MODEL)
  vectors = model.encode(
      df["review_text"].tolist(),
      batch_size=batch_size,
      show_progress_bar=True,
      normalize_embeddings=True,
  )

  os.makedirs(INDEX_DIR, exist_ok=True)
  np.save(EMBEDDINGS_FILE, vectors.astype(np.float16))
  with open(EMBEDDING_IDS_FILE, "w", encoding="utf-8") as f:
    f.write("\n".join(df["review_id"].astype(str)))

  print(f"Embeddings salvos em {EMBEDDINGS_FILE} ({vectors.shape[0]} x {vectors.shape[1]})")


if __name__ == "__main__":
  generate_embeddings()
