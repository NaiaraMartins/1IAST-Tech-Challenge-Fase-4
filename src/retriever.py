"""Semantic retrieval with metadata filters, a relevance threshold and MMR.

Steps, in order:
1. Embed the question twice, as asked and without interrogative framing, and
   use the normalized average. The framed question alone drifts toward reviews
   that mention "clientes" or "avaliação"; the stripped query alone becomes too
   literal ("insatisfeitos" returns the one-word review "insatisfeito"). The
   evaluation in eval/ compares the three options.
2. Query ChromaDB with the metadata filters inside the query (``where``), so the
   nearest neighbours already belong to the requested slice. Filtering after the
   search would leave small categories with almost no evidence.
3. Drop candidates whose cosine distance is above ``max_distance``: they are the
   closest reviews available, not relevant ones.
4. Collapse reviews with identical text ("Atraso na entrega" is written by
   dozens of customers): one copy goes to the context, annotated with how many
   candidates share it, so the remaining slots bring other themes.
5. Re-rank the survivors with Maximal Marginal Relevance so the context covers
   different themes instead of ten paraphrases of the same complaint.
"""

from dataclasses import dataclass, field

import numpy as np

from src.query_parser import normalize, to_chroma_where

DEFAULT_MAX_DISTANCE = 0.40
DEFAULT_CANDIDATES = 40
DEFAULT_TOP_K = 10
DEFAULT_MMR_LAMBDA = 0.7


@dataclass
class Evidence:
  review_id: str
  text: str
  distance: float
  metadata: dict
  same_text_count: int = 1

  @property
  def similarity(self) -> float:
    return 1 - self.distance


@dataclass
class RetrievalResult:
  evidences: list[Evidence]
  candidates: list[Evidence]
  where: dict
  max_distance: float
  duplicate_ids: set = field(default_factory=set)

  @property
  def rejected(self) -> list[Evidence]:
    return [c for c in self.candidates if c.distance > self.max_distance]


def mmr(query_vector, vectors, k: int, lambda_: float) -> list[int]:
  if len(vectors) == 0:
    return []
  vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
  query_vector = query_vector / np.linalg.norm(query_vector)
  relevance = vectors @ query_vector
  selected = [int(np.argmax(relevance))]
  while len(selected) < min(k, len(vectors)):
    redundancy = (vectors @ vectors[selected].T).max(axis=1)
    scores = lambda_ * relevance - (1 - lambda_) * redundancy
    scores[selected] = -np.inf
    selected.append(int(np.argmax(scores)))
  return selected


class Retriever:

  def __init__(self, embedding_model, collection):
    self.model = embedding_model
    self.collection = collection

  def embed(self, question: str, semantic_query: str | None = None, mode: str = "hybrid") -> np.ndarray:
    if mode == "original" or not semantic_query:
      texts = [question]
    elif mode == "semantic":
      texts = [semantic_query]
    else:
      texts = [question, semantic_query]
    vectors = self.model.encode(texts, normalize_embeddings=True)
    combined = np.asarray(vectors).mean(axis=0)
    return combined / np.linalg.norm(combined)

  def retrieve(
      self,
      question: str,
      semantic_query: str,
      filters: dict,
      top_k: int = DEFAULT_TOP_K,
      candidates: int = DEFAULT_CANDIDATES,
      max_distance: float = DEFAULT_MAX_DISTANCE,
      mmr_lambda: float = DEFAULT_MMR_LAMBDA,
      query_mode: str = "hybrid",
  ) -> RetrievalResult:
    query_vector = self.embed(question, semantic_query, query_mode)
    where = to_chroma_where(filters)
    raw = self.collection.query(
        query_embeddings=[query_vector.tolist()],
        n_results=candidates,
        where=where,
        include=["documents", "metadatas", "distances", "embeddings"],
    )

    found = [
        Evidence(
            review_id=meta.get("review_id", doc_id),
            text=doc,
            distance=float(dist),
            metadata=meta,
        )
        for doc_id, doc, meta, dist in zip(
            raw["ids"][0], raw["documents"][0], raw["metadatas"][0], raw["distances"][0]
        )
    ]
    first_by_text, duplicate_ids = {}, set()
    for i, evidence in enumerate(found):
      if evidence.distance > max_distance:
        continue
      key = normalize(evidence.text)
      if key in first_by_text:
        found[first_by_text[key]].same_text_count += 1
        duplicate_ids.add(evidence.review_id)
      else:
        first_by_text[key] = i
    relevant_idx = list(first_by_text.values())
    if not relevant_idx:
      return RetrievalResult([], found, where, max_distance)

    vectors = np.asarray(raw["embeddings"][0], dtype=np.float32)[relevant_idx]
    order = mmr(query_vector, vectors, top_k, mmr_lambda)
    evidences = [found[relevant_idx[i]] for i in order]
    return RetrievalResult(evidences, found, where, max_distance, duplicate_ids)
