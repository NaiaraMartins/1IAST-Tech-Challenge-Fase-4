"""Turns a manager's question into a retrieval plan.

This is the "transformação da pergunta" step of the pipeline. It is rule based
on purpose: every decision is deterministic and shown in the interface, so the
reader can see exactly why a filter was applied.

Output:
- ``route``: ``rag`` (qualitative question, answered by the LLM over retrieved
  reviews), ``ranking`` or ``comparison`` (quantitative questions, answered by
  exact counts over the whole base, never by the LLM).
- ``filters``: metadata constraints pushed into the ChromaDB query.
- ``semantic_query``: the question without interrogative framing. It is
  embedded together with the original question (see src/retriever.py).
- ``topical``: whether the semantic query says anything beyond sentiment
  ("reclamações sobre cama mesa banho" -> only "reclamacoes" is left). When it
  does not, the metadata filters alone define the relevant slice, so the
  distance threshold is not applied (see src/rag_pipeline.py).
- ``in_domain``: whether the question mentions anything about the shopping
  experience. Questions with no such term are refused before retrieval, because
  a small embedding model always finds some "closest" review, even for "qual a
  capital da França?".
"""

import re
import unicodedata
from dataclasses import dataclass, field

from src.config import NEGATIVE_MAX_SCORE, POSITIVE_MIN_SCORE

NEGATIVE_PATTERN = re.compile(
    r"\b(reclam|problem|ruim|ruins|pior|piores|defeit|atras|falh|negativ|critic"
    r"|erro|insatisf|quebr|danific|avari|nao chegou|nunca chegou|decepcion|nota baixa"
    r"|notas baixas|mal atendid|pessim)\w*"
)
POSITIVE_PATTERN = re.compile(
    r"\b(elogi|gost|excelent|perfeit|otim|satisfeit|satisfac|recomend|melhor|melhores"
    r"|positiv|bom|boa|bons|boas|valoriz|amam|amaram|adora|nota alta|notas altas)\w*"
)
LATE_DELIVERY_PATTERN = re.compile(
    r"\b(entregas? (atrasad|insatisfat|ruim|ruins|problematic)\w*"
    r"|pedidos? atrasad\w*|atrasos? (na|de) entrega|entregues? com atraso|fora do prazo"
    r"|nao entregues?|nao recebid\w*)"
)
DOMAIN_PATTERN = re.compile(
    r"\b(produt|entreg|compr|pedid|client|consumidor|comprador|avalia|coment|loja|vend"
    r"|atend|prazo|qualidad|preco|precos|frete|embal|devol|troc|reembols|estorn|garant"
    r"|defeit|problem|reclam|elogi|insatisf|satisf|nota|notas|experienc|servic|suporte"
    r"|correio|transport|receb|cheg|anunci|olist|categori|item|itens|mercadori|pagament"
    r"|cancel|atras|recomend|marketplace|ecommerce|e commerce|demor|quebr|danific|avari"
    r"|gost|ruim|pessim|otim|excelent)\w*"
)
SCORE_PHRASE_PATTERN = re.compile(r"\bnotas? (baixa|baixas|alta|altas|ruim|ruins|boa|boas)\b")
YEAR_PATTERN = re.compile(r"\b(2016|2017|2018)\b")
RANKING_SUBJECT = re.compile(r"\b(categoria|categorias|produto|produtos|setor|setores)\b")
RANKING_WORDS = re.compile(
    r"\b(mais|menos|maior|maiores|menor|ranking|top|piores|melhores|lider\w*)\b"
)
PERCENTAGE_PATTERN = re.compile(r"\b(porcentagem|percentual|proporcao|por cento)\b|%")
CHART_PATTERN = re.compile(r"\b(grafico|pizza|barras?|plot\w*)\b")
COMPARISON_PATTERN = re.compile(
    r"\b(compar\w*|versus|vs)\b|\b(reclam\w*|elogi\w*|positiv\w*|negativ\w*) ou "
)

FRAMING_WORDS = {
    "quais", "qual", "que", "o", "a", "os", "as", "sao", "e", "de", "da", "do", "das",
    "dos", "em", "no", "na", "nos", "nas", "por", "para", "pelos", "pelas", "pelo",
    "pela", "com", "sobre", "existem", "existe", "ha", "principais", "principal",
    "clientes", "cliente", "consumidores", "consumidor", "relatam", "relatados",
    "relatadas", "relatado", "relatos", "avaliacoes", "avaliacao", "comentarios",
    "aparecem", "podem", "pode", "ser", "identificados", "padroes", "recorrentes",
    "mais", "frequencia", "frequentes", "um", "uma", "se", "seus", "suas", "sua",
    "seu", "lhes", "eles", "elas", "aspectos", "experiencia", "experiencias",
    "sustentam", "conclusao", "determinadas", "determinada", "relacionados",
    "relacionadas", "relacionado", "relacionada", "tem", "teve", "tiveram",
    "maior", "maiores", "temas", "tema", "falam", "dizem", "acham", "foi", "sobre",
    "quais", "quanto", "muito", "muitos", "gente", "pessoas",
}

CATEGORY_ALIASES = {
    "relogio": "relogios_presentes", "relogios": "relogios_presentes",
    "informatica": "informatica_acessorios",
    "cama": "cama_mesa_banho", "banho": "cama_mesa_banho",
    "beleza": "beleza_saude", "saude": "beleza_saude",
    "esporte": "esporte_lazer", "esportes": "esporte_lazer", "lazer": "esporte_lazer",
    "moveis": "moveis_decoracao", "decoracao": "moveis_decoracao",
    "festa": "artigos_de_festas", "festas": "artigos_de_festas",
    "brinquedo": "brinquedos", "brinquedos": "brinquedos",
    "bebe": "bebes", "bebes": "bebes",
    "ferramenta": "ferramentas_jardim", "ferramentas": "ferramentas_jardim",
    "jardim": "ferramentas_jardim",
    "pet": "pet_shop", "petshop": "pet_shop",
    "celular": "telefonia", "celulares": "telefonia", "telefone": "telefonia",
    "automotivo": "automotivo", "carro": "automotivo",
    "perfume": "perfumaria", "perfumes": "perfumaria", "perfumaria": "perfumaria",
    "eletronicos": "eletronicos", "eletronico": "eletronicos",
    "utilidades": "utilidades_domesticas", "cozinha": "utilidades_domesticas",
}


def normalize(text: str) -> str:
  if not text:
    return ""
  text = "".join(
      c for c in unicodedata.normalize("NFD", str(text)) if unicodedata.category(c) != "Mn"
  )
  text = re.sub(r"[^\w\s%]", " ", text.lower())
  return re.sub(r"\s+", " ", text).strip()


@dataclass
class ParsedQuery:
  original: str
  normalized: str
  semantic_query: str
  sentiment: str
  route: str
  category: str | None = None
  year: int | None = None
  late_delivery: bool = False
  in_domain: bool = True
  topical: bool = True
  wants_percentage: bool = False
  wants_chart: bool = False
  filters: dict = field(default_factory=dict)

  def describe_filters(self) -> list[str]:
    labels = []
    if "score_max" in self.filters:
      labels.append(f"nota ≤ {self.filters['score_max']}")
    if "score_min" in self.filters:
      labels.append(f"nota ≥ {self.filters['score_min']}")
    if self.category:
      labels.append(f"categoria = {self.category}")
    if self.year:
      labels.append(f"ano da compra = {self.year}")
    if self.late_delivery:
      labels.append("entrega atrasada ou não entregue")
    return labels


def detect_sentiment(normalized: str) -> str:
  if NEGATIVE_PATTERN.search(normalized):
    return "negativa"
  if POSITIVE_PATTERN.search(normalized):
    return "positiva"
  return "neutra"


def detect_category(normalized: str, categories) -> str | None:
  padded = f" {normalized} "
  for category in sorted(categories, key=len, reverse=True):
    if category == "desconhecido":
      continue
    spoken = category.replace("_", " ")
    if f" {category} " in padded or (len(spoken) > 3 and f" {spoken} " in padded):
      return category
  for token in normalized.split():
    if token in CATEGORY_ALIASES and CATEGORY_ALIASES[token] in categories:
      return CATEGORY_ALIASES[token]
  return None


def build_semantic_query(normalized: str, category: str | None) -> str:
  removable = set(FRAMING_WORDS)
  if category:
    removable.update(category.split("_"))
    removable.update(k for k, v in CATEGORY_ALIASES.items() if v == category)
  text = SCORE_PHRASE_PATTERN.sub(" ", normalized)
  tokens = [t for t in text.split() if t not in removable and not YEAR_PATTERN.fullmatch(t)]
  return " ".join(tokens) if tokens else normalized


def is_topical(semantic_query: str) -> bool:
  return any(
      not (NEGATIVE_PATTERN.match(token) or POSITIVE_PATTERN.match(token))
      for token in semantic_query.split()
  )


def parse_question(question: str, categories, forced_category: str | None = None) -> ParsedQuery:
  normalized = normalize(question)
  sentiment = detect_sentiment(normalized)
  category = forced_category or detect_category(normalized, categories)
  year_match = YEAR_PATTERN.search(normalized)
  wants_percentage = bool(PERCENTAGE_PATTERN.search(normalized))
  wants_chart = bool(CHART_PATTERN.search(normalized))

  if category and COMPARISON_PATTERN.search(normalized):
    route = "comparison"
  elif not category and (
      wants_percentage
      or wants_chart
      or (RANKING_SUBJECT.search(normalized) and RANKING_WORDS.search(normalized))
  ):
    route = "ranking"
  else:
    route = "rag"

  semantic_query = build_semantic_query(normalized, category)
  parsed = ParsedQuery(
      original=question,
      normalized=normalized,
      semantic_query=semantic_query,
      sentiment=sentiment,
      route=route,
      category=category,
      year=int(year_match.group(1)) if year_match else None,
      late_delivery=bool(LATE_DELIVERY_PATTERN.search(normalized)),
      in_domain=bool(category or DOMAIN_PATTERN.search(normalized)),
      topical=is_topical(semantic_query),
      wants_percentage=wants_percentage,
      wants_chart=wants_chart,
  )
  if sentiment == "negativa":
    parsed.filters["score_max"] = NEGATIVE_MAX_SCORE
  elif sentiment == "positiva":
    parsed.filters["score_min"] = POSITIVE_MIN_SCORE
  if category:
    parsed.filters["category"] = category
  if parsed.year:
    parsed.filters["year"] = parsed.year
  if parsed.late_delivery:
    parsed.filters["late_delivery"] = True
  return parsed


def to_chroma_where(filters: dict) -> dict:
  clauses = [{"is_short": False}]
  if "score_max" in filters:
    clauses.append({"review_score": {"$lte": filters["score_max"]}})
  if "score_min" in filters:
    clauses.append({"review_score": {"$gte": filters["score_min"]}})
  if "category" in filters:
    clauses.append({"product_category_name": filters["category"]})
  if "year" in filters:
    clauses.append({"purchase_year": filters["year"]})
  if filters.get("late_delivery"):
    clauses.append({"delivery_status": {"$in": ["atrasado", "nao_entregue"]}})
  return clauses[0] if len(clauses) == 1 else {"$and": clauses}
