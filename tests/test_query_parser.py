from src.query_parser import parse_question, to_chroma_where

CATEGORIES = {
    "cama_mesa_banho",
    "informatica_acessorios",
    "beleza_saude",
    "relogios_presentes",
    "artigos_de_festas",
    "ferramentas_jardim",
    "desconhecido",
}


def test_broad_complaint_question_goes_to_rag_with_low_score_filter():
  parsed = parse_question("Quais são os principais problemas relatados pelos clientes?", CATEGORIES)
  assert parsed.route == "rag"
  assert parsed.sentiment == "negativa"
  assert parsed.filters == {"score_max": 2}
  assert parsed.semantic_query == "problemas"


def test_praise_question_filters_high_scores():
  parsed = parse_question("Quais aspectos da experiência de compra são mais elogiados?", CATEGORIES)
  assert parsed.route == "rag"
  assert parsed.filters == {"score_min": 4}


def test_unsatisfied_customers_are_negative_not_positive():
  parsed = parse_question("Quais padrões aparecem nas avaliações de clientes insatisfeitos?", CATEGORIES)
  assert parsed.sentiment == "negativa"


def test_category_by_alias_and_by_full_name():
  assert parse_question("problemas com relogio", CATEGORIES).category == "relogios_presentes"
  assert parse_question("o que falam de cama mesa banho", CATEGORIES).category == "cama_mesa_banho"
  assert parse_question("elogios em informática e acessórios", CATEGORIES).category == "informatica_acessorios"


def test_word_inside_another_word_does_not_trigger_category():
  assert parse_question("o produto chegou desmontado", CATEGORIES).category is None


def test_year_and_late_delivery_filters():
  parsed = parse_question("Quais temas aparecem em entregas atrasadas em 2018?", CATEGORIES)
  assert parsed.year == 2018
  assert parsed.late_delivery is True
  assert "2018" not in parsed.semantic_query


def test_ranking_needs_a_subject_not_just_the_word_mais():
  assert parse_question("O que os clientes mais elogiam?", CATEGORIES).route == "rag"
  assert parse_question("Quais categorias têm mais reclamações?", CATEGORIES).route == "ranking"
  assert parse_question("Qual a porcentagem de insatisfeitos por categoria?", CATEGORIES).route == "ranking"


def test_comparison_inside_a_category():
  parsed = parse_question(
      "Sobre informática e acessórios, tem mais gente reclamando ou elogiando?", CATEGORIES
  )
  assert parsed.route == "comparison"
  assert parsed.category == "informatica_acessorios"


def test_forced_category_from_dashboard_click():
  parsed = parse_question("quais são as reclamações", CATEGORIES, forced_category="beleza_saude")
  assert parsed.category == "beleza_saude"
  assert parsed.filters["category"] == "beleza_saude"


def test_where_clause_always_excludes_short_comments():
  assert to_chroma_where({}) == {"is_short": False}
  where = to_chroma_where({"score_max": 2, "category": "beleza_saude", "late_delivery": True})
  assert {"is_short": False} in where["$and"]
  assert {"review_score": {"$lte": 2}} in where["$and"]
  assert {"product_category_name": "beleza_saude"} in where["$and"]
  assert {"delivery_status": {"$in": ["atrasado", "nao_entregue"]}} in where["$and"]


def test_domain_gate_flags_questions_outside_the_shopping_experience():
  assert parse_question("Qual a capital da França?", CATEGORIES).in_domain is False
  assert parse_question("Me passa uma receita de bolo", CATEGORIES).in_domain is False
  assert parse_question("O que dizem sobre a embalagem?", CATEGORIES).in_domain is True
  assert parse_question("E sobre relógios?", CATEGORIES).in_domain is True


def test_score_phrases_are_filters_not_search_text():
  parsed = parse_question("Quais os principais problemas nas avaliações com nota baixa?", CATEGORIES)
  assert parsed.filters == {"score_max": 2}
  assert "nota" not in parsed.semantic_query


def test_sentiment_only_question_is_not_topical():
  assert parse_question("Quais as reclamações sobre cama, mesa e banho em 2018?", CATEGORIES).topical is False
  assert parse_question("O que os clientes relatam sobre a entrega?", CATEGORIES).topical is True
