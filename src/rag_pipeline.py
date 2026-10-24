"""Orchestrates the Voice of Customer RAG pipeline.

question
  -> parse (route, filters, semantic query)          src/query_parser.py
  -> quantitative route: exact counts                 src/analytics.py
  -> no shopping-experience term: out of scope        (no retrieval, no LLM)
  -> qualitative route:
       retrieve with filters + threshold + MMR        src/retriever.py
       refuse when fewer than MIN_EVIDENCES survive   (no LLM call)
       build numbered context                         src/prompts.py
       generate with the configured LLM               src/llm.py
       validate citations, refuse on SEM_EVIDENCIA
"""

import re
from dataclasses import dataclass, field

from src import llm as llm_config
from src.prompts import NO_EVIDENCE_TOKEN, SYSTEM_PROMPT, build_user_prompt
from src.query_parser import ParsedQuery, parse_question
from src.retriever import RetrievalResult, Retriever

MIN_EVIDENCES = 3
# Questions with no topic beyond sentiment ("reclamações sobre beleza em 2018")
# get their relevance from the metadata filters, so the distance threshold is
# lifted (cosine distance never exceeds 2).
FILTER_DEFINED_MAX_DISTANCE = 2.0
CITATION_GROUP_PATTERN = re.compile(r"\[(R\d+(?:\s*[,;]\s*R?\d+)*)\]")

ANSWERED = "answered"
RETRIEVAL_ONLY = "retrieval_only"
NO_EVIDENCE = "no_evidence"
LLM_REFUSED = "llm_refused"
LLM_ERROR = "llm_error"
ANALYTICS = "analytics"
OUT_OF_SCOPE = "out_of_scope"

OUT_OF_SCOPE_MESSAGE = (
    "Essa pergunta está fora do escopo da base de conhecimento. Eu respondo apenas sobre a"
    " experiência de compra relatada nas avaliações de clientes da Olist: produtos, entrega,"
    " atendimento, preço, qualidade e temas parecidos."
)
REFUSAL_MESSAGE = (
    "Não encontrei avaliações suficientes na base para responder a essa pergunta com segurança."
)


@dataclass
class RAGAnswer:
  question: str
  parsed: ParsedQuery
  status: str
  text: str = ""
  retrieval: RetrievalResult | None = None
  cited: list[int] = field(default_factory=list)
  user_prompt: str = ""
  llm_label: str = ""
  error: str = ""

  @property
  def evidences(self):
    return self.retrieval.evidences if self.retrieval else []

  @property
  def has_uncited_answer(self) -> bool:
    return self.status == ANSWERED and not self.cited


def extract_citations(text: str, evidence_count: int) -> list[int]:
  """Accepts [R1], [R1][R3] and grouped forms such as [R1, R3] or [R1, 3]."""
  found = {
      int(n) for group in CITATION_GROUP_PATTERN.findall(text) for n in re.findall(r"\d+", group)
  }
  return sorted(n for n in found if 1 <= n <= evidence_count)


def explain_no_evidence(parsed: ParsedQuery, retrieval: RetrievalResult) -> str:
  reasons = []
  if not retrieval.candidates:
    reasons.append("nenhuma avaliação atende aos filtros aplicados")
  else:
    best = min(c.distance for c in retrieval.candidates)
    relevant = sum(c.distance <= retrieval.max_distance for c in retrieval.candidates)
    reasons.append(
        f"{relevant} avaliação(ões) ficaram dentro do limiar de relevância"
        f" (mínimo exigido: {MIN_EVIDENCES}); a mais próxima tem distância {best:.2f}"
        f" e o limiar é {retrieval.max_distance:.2f}"
    )
  filters = parsed.describe_filters()
  text = REFUSAL_MESSAGE + "\n\nMotivo: " + "; ".join(reasons) + "."
  if filters:
    text += f"\n\nFiltros usados: {', '.join(filters)}. Tente uma pergunta mais ampla ou sem algum desses filtros."
  else:
    text += "\n\nA pergunta pode estar fora do escopo das avaliações de clientes da Olist."
  return text


class VoCPipeline:

  def __init__(self, embedding_model, collection, categories, generator=None, **retrieval_params):
    self.retriever = Retriever(embedding_model, collection)
    self.categories = set(categories)
    self.generator = generator
    self.retrieval_params = retrieval_params

  @classmethod
  def with_configured_llm(cls, embedding_model, collection, categories, **retrieval_params):
    generator = llm_config.LLMGenerator() if llm_config.is_configured() else None
    return cls(embedding_model, collection, categories, generator, **retrieval_params)

  def answer(
      self,
      question: str,
      forced_category: str | None = None,
      extra_filters: dict | None = None,
      use_llm: bool = True,
  ) -> RAGAnswer:
    parsed = parse_question(question, self.categories, forced_category)
    if extra_filters:
      parsed.filters.update(extra_filters)
      parsed.category = parsed.filters.get("category", parsed.category)
      parsed.year = parsed.filters.get("year", parsed.year)
      parsed.late_delivery = parsed.filters.get("late_delivery", parsed.late_delivery)

    if parsed.route != "rag":
      return RAGAnswer(question, parsed, ANALYTICS)

    if not parsed.in_domain:
      return RAGAnswer(question, parsed, OUT_OF_SCOPE, OUT_OF_SCOPE_MESSAGE)

    params = dict(self.retrieval_params)
    if not parsed.topical and parsed.filters:
      params["max_distance"] = FILTER_DEFINED_MAX_DISTANCE
    retrieval = self.retriever.retrieve(question, parsed.semantic_query, parsed.filters, **params)
    if len(retrieval.evidences) < MIN_EVIDENCES:
      return RAGAnswer(question, parsed, NO_EVIDENCE, explain_no_evidence(parsed, retrieval), retrieval)

    user_prompt = build_user_prompt(question, parsed.describe_filters(), retrieval.evidences)
    if self.generator is None or not use_llm:
      return RAGAnswer(question, parsed, RETRIEVAL_ONLY, retrieval=retrieval, user_prompt=user_prompt)

    try:
      text = self.generator.generate(SYSTEM_PROMPT, user_prompt)
    except Exception as exc:
      return RAGAnswer(
          question, parsed, LLM_ERROR, retrieval=retrieval, user_prompt=user_prompt,
          llm_label=self.generator.label, error=str(exc),
      )

    if NO_EVIDENCE_TOKEN in text:
      return RAGAnswer(
          question, parsed, LLM_REFUSED,
          REFUSAL_MESSAGE + "\n\nO modelo leu as avaliações recuperadas e concluiu que elas não respondem à pergunta.",
          retrieval, user_prompt=user_prompt, llm_label=self.generator.label,
      )

    return RAGAnswer(
        question, parsed, ANSWERED, text, retrieval,
        cited=extract_citations(text, len(retrieval.evidences)),
        user_prompt=user_prompt, llm_label=self.generator.label,
    )
