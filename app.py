import os

import pandas as pd
import streamlit as st
from sentence_transformers import SentenceTransformer

from src import rag_pipeline as rp
from src.analytics import ReviewAnalytics
from src.config import EMBEDDING_MODEL
from src.vector_store import get_collection
from ui import charts
from ui import components as ui
from ui.styles import CSS
from ui.theme import category_name, model_name, month_label, number, percent

MAX_LLM_CALLS_PER_SESSION = int(os.getenv("MAX_LLM_CALLS_PER_SESSION", "20"))
EVIDENCE_PAGE_SIZE = 5
AUTO = "Auto"
SUGGESTIONS = {
    "Principais problemas": "Quais são os principais problemas relatados pelos clientes em suas avaliações?",
    "Problemas de entrega": "O que os clientes relatam sobre problemas relacionados à entrega?",
    "O que mais elogiam": "Quais aspectos da experiência de compra são mais elogiados pelos clientes?",
    "Clientes insatisfeitos": "Quais padrões podem ser identificados nas avaliações de clientes insatisfeitos?",
    "Evidências de atraso": "Quais avaliações sustentam a conclusão de que existem problemas recorrentes relacionados ao prazo de entrega?",
    "Ranking por categoria": "Quais categorias têm mais reclamações?",
    "Pergunta fora do escopo": "Qual a capital da França?",
}
SENTIMENT_LABELS = {"Reclamações": "negativa", "Elogios": "positiva"}

st.set_page_config(page_title="Voz do Cliente Olist", layout="wide", initial_sidebar_state="collapsed")
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_resource(show_spinner="Carregando o modelo de embeddings e a base vetorial...")
def load_engine():
  analytics = ReviewAnalytics()
  pipeline = rp.VoCPipeline.with_configured_llm(
      SentenceTransformer(EMBEDDING_MODEL), get_collection(), analytics.categories
  )
  return analytics, pipeline


analytics, pipeline = load_engine()
llm_enabled = pipeline.generator is not None
categories = [c for c in analytics.categories if c != "desconhecido"]

for key, value in {"messages": [], "pending": None, "llm_calls": 0}.items():
  st.session_state.setdefault(key, value)


def reset_conversation():
  st.session_state.messages = []
  st.session_state.pending = None
  for key in ("bar_negativa", "bar_positiva"):
    st.session_state.pop(key, None)


def queue_question(question: str, category: str | None = None):
  st.session_state.pending = {"question": question, "category": category}


def on_suggestion():
  label = st.session_state.get("suggestion")
  if label:
    queue_question(SUGGESTIONS[label])
  st.session_state.suggestion = None


# --- Barra lateral: filtros da busca ---
with st.sidebar:
  st.markdown("### Filtros da busca")
  st.caption("Somam-se aos filtros que o sistema detecta na própria pergunta.")
  score_filter = st.segmented_control("Nota", [AUTO, "1–2", "3", "4–5"], default=AUTO, key="f_score", width="stretch")
  category_filter = st.selectbox("Categoria", [AUTO, *categories], key="f_category",
                                 format_func=lambda c: "Detectar pela pergunta" if c == AUTO else category_name(c))
  year_filter = st.selectbox("Ano da compra", ["Todos", "2016", "2017", "2018"], key="f_year",
                             format_func=lambda y: "Todos os anos" if y == "Todos" else y)
  late_filter = st.toggle("Só pedidos atrasados ou não entregues", key="f_late")
  st.divider()
  if llm_enabled:
    remaining = max(MAX_LLM_CALLS_PER_SESSION - st.session_state.llm_calls, 0)
    st.caption(f"Modelo: {model_name(pipeline.generator.label)}. Respostas geradas restantes nesta sessão: {remaining}.")
  else:
    st.caption("Sem chave de LLM configurada: o app mostra as avaliações recuperadas, sem a resposta gerada.")
  if st.button("Limpar conversa", width="stretch"):
    reset_conversation()
    st.rerun()


def sidebar_filters() -> dict:
  filters = {}
  if score_filter == "1–2":
    filters["score_max"] = 2
  elif score_filter == "3":
    filters.update(score_min=3, score_max=3)
  elif score_filter == "4–5":
    filters["score_min"] = 4
  if category_filter != AUTO:
    filters["category"] = category_filter
  if year_filter and year_filter != "Todos":
    filters["year"] = int(year_filter)
  if late_filter:
    filters["late_delivery"] = True
  return filters


# --- Resposta do assistente ---
def render_evidences(answer: rp.RAGAnswer, index: int):
  evidences = answer.evidences
  if not evidences:
    return
  order = [n for n in range(1, len(evidences) + 1) if n in answer.cited]
  order += [n for n in range(1, len(evidences) + 1) if n not in answer.cited]
  limit_key = f"evidence_limit_{index}"
  limit = st.session_state.get(limit_key, EVIDENCE_PAGE_SIZE)
  label = f"Avaliações usadas como evidência ({len(evidences)})"
  with st.expander(label, expanded=answer.status == rp.RETRIEVAL_ONLY):
    st.markdown("".join(ui.evidence(n, evidences[n - 1], n in answer.cited) for n in order[:limit]),
                unsafe_allow_html=True)
    if limit < len(order):
      if st.button(f"Mostrar mais {min(EVIDENCE_PAGE_SIZE, len(order) - limit)}", key=f"more_{index}"):
        st.session_state[limit_key] = limit + EVIDENCE_PAGE_SIZE
        st.rerun()


def render_trace(answer: rp.RAGAnswer):
  with st.expander("Como a resposta foi construída"):
    st.markdown(ui.steps(answer.parsed, answer.retrieval, answer.llm_label), unsafe_allow_html=True)
    retrieval = answer.retrieval
    if retrieval and retrieval.candidates:
      selected = {e.review_id for e in retrieval.evidences}

      def situation(c):
        if c.review_id in selected:
          return "No contexto"
        if c.distance > retrieval.max_distance:
          return "Pouco relevante"
        if c.review_id in retrieval.duplicate_ids:
          return "Texto repetido"
        return "Redundante (MMR)"

      table = pd.DataFrame([
          {"Similaridade": 1 - c.distance, "Situação": situation(c), "Nota": c.metadata.get("review_score"),
           "Avaliação": c.text}
          for c in retrieval.candidates
      ])
      st.dataframe(
          table, hide_index=True, width="stretch", height=280,
          column_config={
              "Similaridade": st.column_config.ProgressColumn(format="%.2f", min_value=0, max_value=1, width="small"),
              "Situação": st.column_config.TextColumn(width="small"),
              "Nota": st.column_config.NumberColumn(width="small"),
          },
      )
    if answer.user_prompt:
      st.caption("Contexto enviado ao modelo")
      st.code(answer.user_prompt, language=None, wrap_lines=True, height=260)


def render_ranking(answer: rp.RAGAnswer):
  parsed = answer.parsed
  sentiment = parsed.sentiment if parsed.sentiment in ("negativa", "positiva") else "negativa"
  noun = "reclamações" if sentiment == "negativa" else "elogios"
  table = analytics.ranking(sentiment)
  st.markdown(ui.section(f"Categorias com mais {noun}",
                         f"Contagem exata sobre {number(analytics.counts().total)} avaliações com texto, "
                         "feita com pandas e não pelo modelo."), unsafe_allow_html=True)
  if parsed.wants_chart and "pizza" in parsed.normalized:
    st.plotly_chart(charts.share_donut(table, sentiment), config=charts.PLOTLY_CONFIG, width="stretch")
  else:
    st.plotly_chart(charts.category_bars(table, sentiment, top=10), config=charts.PLOTLY_CONFIG, width="stretch")
  view = table.head(15).copy()
  view["Categoria"] = view["category"].map(category_name)
  st.dataframe(
      view[["Categoria", "reviews", "share_of_sentiment", "rate_in_category", "category_total"]],
      hide_index=True, width="stretch",
      column_config={
          "reviews": st.column_config.NumberColumn(noun.capitalize(), format="localized"),
          "share_of_sentiment": st.column_config.NumberColumn(f"% do total de {noun}", format="percent"),
          "rate_in_category": st.column_config.ProgressColumn(
              "Taxa na categoria", format="percent", min_value=0, max_value=float(view["rate_in_category"].max())),
          "category_total": st.column_config.NumberColumn("Avaliações da categoria", format="localized"),
      },
  )
  st.caption("A taxa na categoria compara categorias de tamanhos diferentes: volume alto nem sempre é taxa alta.")


def render_comparison(answer: rp.RAGAnswer):
  category = answer.parsed.category
  c, base = analytics.counts(category), analytics.counts()
  st.markdown(ui.section(f"Reclamações e elogios em {category_name(category).lower()}",
                         f"{number(c.total)} avaliações com texto na categoria. Contagem exata, sem o modelo."),
              unsafe_allow_html=True)
  st.markdown(ui.stat_cards([
      ("Reclamações (1–2)", number(c.negative), f"{percent(c.negative / c.total)} da categoria", "neg"),
      ("Neutras (3)", number(c.neutral), f"{percent(c.neutral / c.total)} da categoria", ""),
      ("Elogios (4–5)", number(c.positive), f"{percent(c.positive / c.total)} da categoria", "pos"),
  ]), unsafe_allow_html=True)
  st.plotly_chart(charts.composition([
      (category_name(category), c.negative, c.neutral, c.positive),
      ("Base inteira", base.negative, base.neutral, base.positive),
  ]), config=charts.PLOTLY_CONFIG, width="stretch")
  more = "mais elogios do que reclamações" if c.positive > c.negative else "mais reclamações do que elogios"
  st.markdown(f"A categoria tem **{more}**. A taxa de reclamação é **{percent(c.negative / c.total)}**, "
              f"contra **{percent(base.negative / base.total)}** na base inteira.")


REFUSAL_TITLES = {
    rp.OUT_OF_SCOPE: "Fora do escopo",
    rp.NO_EVIDENCE: "Sem evidência suficiente",
    rp.LLM_REFUSED: "As avaliações não sustentam uma resposta",
}


def render_answer(answer: rp.RAGAnswer, index: int):
  status = answer.status
  if status == rp.ANALYTICS:
    if answer.parsed.route == "comparison":
      render_comparison(answer)
    else:
      render_ranking(answer)
    return

  filters = answer.parsed.describe_filters()
  if status == rp.ANSWERED:
    st.markdown(ui.chips([model_name(answer.llm_label), f"{len(answer.evidences)} avaliações no contexto",
                          f"{len(answer.cited)} citadas", *filters], accent_first=True), unsafe_allow_html=True)
    st.markdown(ui.answer(answer.text), unsafe_allow_html=True)
    st.markdown(ui.citation_note(len(answer.cited), len(answer.evidences)), unsafe_allow_html=True)
    if answer.has_uncited_answer:
      st.markdown(ui.callout("Resposta sem citações",
                             "O modelo não citou nenhuma avaliação. Confira as evidências antes de usar.", "error"),
                  unsafe_allow_html=True)
  elif status in REFUSAL_TITLES:
    st.markdown(ui.callout(REFUSAL_TITLES[status], answer.text), unsafe_allow_html=True)
  elif status == rp.RETRIEVAL_ONLY:
    reason = ("o limite de respostas geradas desta sessão foi atingido" if llm_enabled
              else "não há chave de LLM configurada")
    st.markdown(ui.callout("Modo só busca", f"Sem resposta gerada porque {reason}. Abaixo estão as avaliações "
                                            "que seriam enviadas ao modelo.", "info"), unsafe_allow_html=True)
  elif status == rp.LLM_ERROR:
    st.markdown(ui.callout("O modelo de linguagem não respondeu", answer.error[:300], "error"),
                unsafe_allow_html=True)

  render_evidences(answer, index)
  render_trace(answer)


def run_question(question: str, category: str | None) -> rp.RAGAnswer:
  use_llm = llm_enabled and st.session_state.llm_calls < MAX_LLM_CALLS_PER_SESSION
  with st.spinner("Buscando avaliações e escrevendo a resposta..."):
    answer = pipeline.answer(question, category, sidebar_filters(), use_llm=use_llm)
  if answer.status in (rp.ANSWERED, rp.LLM_REFUSED, rp.LLM_ERROR):
    st.session_state.llm_calls += 1
  return answer


# --- Página inicial ---
def render_home():
  counts = analytics.counts()
  st.markdown(ui.kpi_grid([
      ("Avaliações com texto", number(counts.total), "Pedidos de set/2016 a ago/2018", ""),
      ("Taxa de reclamação", percent(counts.negative / counts.total), "Avaliações com nota 1 ou 2", "neg"),
      ("Taxa de elogio", percent(counts.positive / counts.total), "Avaliações com nota 4 ou 5", "pos"),
      ("Reclamações ligadas à entrega", percent(analytics.late_delivery_share("negativa")),
       f"Pedido atrasado ou não entregue. Entre os elogios: {percent(analytics.late_delivery_share('positiva'))}", ""),
  ]), unsafe_allow_html=True)

  head, toggle = st.columns([3, 1], vertical_alignment="bottom")
  head.markdown(ui.section("Onde os clientes reclamam e o que elogiam",
                           "Números exatos sobre a base inteira. Clique numa categoria para investigar os motivos."),
                unsafe_allow_html=True)
  choice = toggle.segmented_control("Visão", list(SENTIMENT_LABELS), default="Reclamações", key="home_sentiment",
                                    label_visibility="collapsed", width="stretch")
  sentiment = SENTIMENT_LABELS.get(choice or "Reclamações")
  noun = "reclamações" if sentiment == "negativa" else "elogios"

  left, right = st.columns([1.1, 1], gap="large")
  with left:
    ranking = analytics.ranking(sentiment)
    st.markdown(ui.chart_title(f"Categorias com mais {noun}", "Volume · taxa dentro da categoria"),
                unsafe_allow_html=True)
    event = st.plotly_chart(charts.category_bars(ranking, sentiment), config=charts.PLOTLY_CONFIG, width="stretch",
                            on_select="rerun", selection_mode="points", key=f"bar_{sentiment}")
    points = (event or {}).get("selection", {}).get("points", [])
    if points:
      names = {category_name(c): c for c in ranking["category"].head(8)}
      category = names.get(points[0].get("y"))
      if category:
        template = ("Quais são as principais reclamações sobre {}?" if sentiment == "negativa"
                    else "O que os clientes mais elogiam em {}?")
        queue_question(template.format(category_name(category).lower()), category)
        st.rerun()
  with right:
    monthly = analytics.monthly_rates()
    column = "negative_rate" if sentiment == "negativa" else "positive_rate"
    peak = monthly.loc[monthly[column].idxmax() if sentiment == "negativa" else monthly[column].idxmin()]
    peak_note = (f"Pico em {month_label(peak['purchase_month'])}: {percent(peak[column], 0)}" if sentiment == "negativa"
                 else f"Menor taxa em {month_label(peak['purchase_month'])}: {percent(peak[column], 0)}")
    st.markdown(ui.chart_title(f"Taxa de {noun} por mês da compra", f"Meses com 300+ avaliações · {peak_note}"),
                unsafe_allow_html=True)
    st.plotly_chart(charts.monthly_rate(monthly, sentiment), config=charts.PLOTLY_CONFIG, width="stretch")

  st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
  st.markdown(ui.section("Comece por uma pergunta",
                         "Ou escreva a sua no campo abaixo. Filtros avançados ficam na barra lateral."),
              unsafe_allow_html=True)
  st.pills("Sugestões", list(SUGGESTIONS), key="suggestion", on_change=on_suggestion, label_visibility="collapsed")


# --- Layout principal ---
st.markdown(ui.header(pipeline.generator.label if llm_enabled else None, analytics.counts().total),
            unsafe_allow_html=True)

if not st.session_state.messages and not st.session_state.pending:
  render_home()
else:
  bar_left, bar_right = st.columns([4, 1], vertical_alignment="center")
  bar_left.caption("Conversa")
  if bar_right.button("Nova conversa", width="stretch"):
    reset_conversation()
    st.rerun()
  for index, message in enumerate(st.session_state.messages):
    if message["role"] == "user":
      st.markdown(ui.user_turn(message["content"]), unsafe_allow_html=True)
    else:
      render_answer(message["answer"], index)

if st.session_state.pending:
  pending = st.session_state.pending
  st.session_state.pending = None
  st.session_state.messages.append({"role": "user", "content": pending["question"]})
  st.markdown(ui.user_turn(pending["question"]), unsafe_allow_html=True)
  answer = run_question(pending["question"], pending["category"])
  st.session_state.messages.append({"role": "assistant", "answer": answer})
  render_answer(answer, len(st.session_state.messages) - 1)

if question := st.chat_input("Pergunte sobre as avaliações. Ex.: o que os clientes falam sobre a embalagem?"):
  queue_question(question)
  st.rerun()
