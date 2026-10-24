import numpy as np

from src import rag_pipeline as rp
from src.prompts import NO_EVIDENCE_TOKEN, build_context
from src.retriever import Evidence, mmr

CATEGORIES = {"beleza_saude", "cama_mesa_banho"}


class FakeEmbedder:

  def encode(self, texts, normalize_embeddings=True):
    return np.array([[1.0, 0.0, 0.0]])


class FakeCollection:

  def __init__(self, distances):
    self.distances = distances
    self.last_where = None

  def query(self, query_embeddings, n_results, where, include):
    self.last_where = where
    n = len(self.distances)
    rng = np.random.default_rng(0)
    return {
        "ids": [[f"id{i}" for i in range(n)]],
        "documents": [[f"texto da avaliação {i}" for i in range(n)]],
        "metadatas": [[{"review_id": f"id{i}", "review_score": 1, "product_category_name": "beleza_saude",
                        "purchase_month": "2018-01", "delivery_status": "atrasado", "delivery_delay_days": 3}
                       for i in range(n)]],
        "distances": [self.distances],
        "embeddings": [rng.normal(size=(n, 3)).tolist()],
    }


class FakeGenerator:
  label = "fake · test"

  def __init__(self, reply):
    self.reply = reply
    self.calls = 0

  def generate(self, system_prompt, user_prompt):
    self.calls += 1
    return self.reply


def make_pipeline(distances, reply=None):
  generator = FakeGenerator(reply) if reply is not None else None
  return rp.VoCPipeline(FakeEmbedder(), FakeCollection(distances), CATEGORIES, generator)


def test_out_of_scope_question_is_refused_before_retrieval():
  pipeline = make_pipeline([0.1, 0.1, 0.1], reply="não deveria ser chamado")
  answer = pipeline.answer("Qual a capital da França?")
  assert answer.status == rp.OUT_OF_SCOPE
  assert pipeline.retriever.collection.last_where is None
  assert pipeline.generator.calls == 0


def test_refuses_without_calling_llm_when_evidence_is_weak():
  pipeline = make_pipeline([0.5, 0.55, 0.6], reply="não deveria ser chamado")
  answer = pipeline.answer("qual o preço do bitcoin hoje?")
  assert answer.status == rp.NO_EVIDENCE
  assert pipeline.generator.calls == 0
  assert "limiar" in answer.text


def test_refuses_when_filters_return_nothing():
  answer = make_pipeline([]).answer("reclamações de beleza em 2016")
  assert answer.status == rp.NO_EVIDENCE
  assert "nenhuma avaliação atende aos filtros" in answer.text


def test_retrieval_only_mode_without_llm():
  answer = make_pipeline([0.2, 0.3, 0.35, 0.4, 0.5]).answer("quais os problemas de entrega?")
  assert answer.status == rp.RETRIEVAL_ONLY
  assert len(answer.evidences) == 4
  assert "[R1]" in answer.user_prompt


def test_answer_keeps_only_valid_citations():
  answer = make_pipeline([0.2, 0.3, 0.4], reply="Atrasos [R1][R3] e embalagem [R9].").answer(
      "quais os problemas de entrega?"
  )
  assert answer.status == rp.ANSWERED
  assert answer.cited == [1, 3]


def test_llm_saying_no_evidence_becomes_refusal():
  answer = make_pipeline([0.2, 0.3, 0.4], reply=NO_EVIDENCE_TOKEN).answer("quais os problemas?")
  assert answer.status == rp.LLM_REFUSED


def test_quantitative_question_skips_retrieval_and_llm():
  pipeline = make_pipeline([0.2, 0.3, 0.4], reply="x")
  answer = pipeline.answer("Quais categorias têm mais reclamações?")
  assert answer.status == rp.ANALYTICS
  assert pipeline.generator.calls == 0


def test_filters_reach_the_vector_store_query():
  pipeline = make_pipeline([0.2, 0.3, 0.4])
  pipeline.answer("reclamações de beleza")
  where = pipeline.retriever.collection.last_where
  assert {"product_category_name": "beleza_saude"} in where["$and"]
  assert {"review_score": {"$lte": 2}} in where["$and"]


def test_context_numbers_evidences_with_metadata():
  evidences = [Evidence("a", "Chegou quebrado", 0.2, {"review_score": 1, "product_category_name": "x",
                                                       "purchase_month": "2018-02", "delivery_status": "atrasado",
                                                       "delivery_delay_days": 4})]
  context = build_context(evidences)
  assert context.startswith("[R1] nota 1/5 | categoria: x | compra: 2018-02 | entrega: atrasado 4 dia(s)")
  assert context.endswith("Chegou quebrado")


def test_mmr_prefers_diverse_results():
  query = np.array([1.0, 0.0])
  vectors = np.array([[1.0, 0.0], [0.99, 0.01], [0.8, 0.6]])
  assert mmr(query, vectors, k=2, lambda_=0.3) == [0, 2]


def test_filter_defined_question_lifts_the_distance_threshold():
  answer = make_pipeline([0.6, 0.7, 0.8]).answer("reclamações sobre beleza")
  assert answer.status == rp.RETRIEVAL_ONLY
  assert answer.retrieval.max_distance == rp.FILTER_DEFINED_MAX_DISTANCE


def test_grouped_citations_are_recognized():
  text = "Atrasos [R1, R3, R6] e itens faltando [R2][R5]; ver também [R4; 7] e [R99]."
  assert rp.extract_citations(text, 10) == [1, 2, 3, 4, 5, 6, 7]


def test_identical_texts_are_grouped_into_one_evidence():
  class SameText(FakeCollection):
    def query(self, **kwargs):
      raw = super().query(**kwargs)
      raw["documents"][0] = ["Atraso na entrega", "atraso na entrega!", "Atraso na entrega", "Veio quebrado", "Cor errada"]
      return raw
  pipeline = rp.VoCPipeline(FakeEmbedder(), SameText([0.1, 0.11, 0.12, 0.2, 0.3]), CATEGORIES)
  answer = pipeline.answer("quais os problemas de entrega?")
  texts = [e.text for e in answer.evidences]
  assert len(answer.evidences) == 3
  assert texts.count("Atraso na entrega") == 1
  assert next(e for e in answer.evidences if e.text == "Atraso na entrega").same_text_count == 3
  assert answer.retrieval.duplicate_ids == {"id1", "id2"}
  assert "mesmo texto em 3 avaliações" in answer.user_prompt
