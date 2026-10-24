"""Small HTML building blocks. Every piece of user or model text is escaped."""

import html
import json

from src.rag_pipeline import CITATION_GROUP_PATTERN
from ui.theme import category_name, model_name, month_label, number

esc = html.escape


def header(llm_label: str | None, total_reviews: int) -> str:
  status = (
      f'<span class="status">Modelo ativo <b>{esc(model_name(llm_label))}</b></span>' if llm_label
      else '<span class="status off">Modo só busca <b>sem chave de LLM</b></span>'
  )
  return f"""
  <div class="voc-head">
    <div class="voc-head-text">
      <span class="voc-eyebrow">FIAP Pós Tech · IA Science · Fase 4</span>
      <h1 class="voc-title">Voz do Cliente Olist</h1>
      <p class="voc-sub">Pergunte em linguagem natural sobre {number(total_reviews)} avaliações escritas por clientes.
      Cada resposta cita as avaliações que a sustentam.</p>
    </div>
    {status}
  </div>"""


def kpi_grid(items: list[tuple[str, str, str, str]]) -> str:
  """items: (label, value, note, tone) with tone in {"", "neg", "pos"}."""
  cards = "".join(
      f'<div class="kpi"><span class="kpi-label">{esc(label)}</span>'
      f'<span class="kpi-value {tone}">{esc(value)}</span><span class="kpi-note">{esc(note)}</span></div>'
      for label, value, note, tone in items
  )
  return f'<div class="kpi-grid">{cards}</div>'


def section(title: str, note: str = "") -> str:
  note_html = f'<p class="section-note">{esc(note)}</p>' if note else ""
  return f'<p class="section-title">{esc(title)}</p>{note_html}'


def chart_title(title: str, note: str = "") -> str:
  note_html = f'<p class="chart-card-note">{esc(note)}</p>' if note else ""
  return f'<p class="chart-card-title">{esc(title)}</p>{note_html}'


def user_turn(text: str) -> str:
  return f'<div class="turn-user"><div>{esc(text)}</div></div>'


def chips(items: list[str], accent_first: bool = False) -> str:
  body = "".join(
      f'<span class="chip{" accent" if accent_first and i == 0 else ""}">{esc(item)}</span>'
      for i, item in enumerate(items) if item
  )
  return f'<div class="meta-row">{body}</div>'


def answer(text: str) -> str:
  safe = esc(text, quote=False)
  return CITATION_GROUP_PATTERN.sub(lambda m: f'<span class="cite">{m.group(0)}</span>', safe)


def citation_note(cited: int, total: int) -> str:
  return (f'<p class="cite-note">Os códigos <span class="cite">[R1]</span>, <span class="cite">[R2]</span>… são '
          f'referências: cada um aponta para a avaliação de mesmo número na lista abaixo. '
          f'{cited} de {total} avaliações recuperadas foram citadas.</p>')


def callout(title: str, body: str, kind: str = "") -> str:
  return (f'<div class="callout {kind}"><span class="callout-title">{esc(title)}</span>'
          f'<span class="callout-body">{esc(body)}</span></div>')


def _score_class(score) -> str:
  try:
    value = int(score)
  except (TypeError, ValueError):
    return ""
  return "neg" if value <= 2 else ("pos" if value >= 4 else "")


def _delivery(meta: dict) -> str:
  status = meta.get("delivery_status")
  if status == "atrasado":
    delay = meta.get("delivery_delay_days")
    return f"entrega atrasou {delay} dia(s)" if delay is not None else "entrega atrasada"
  if status == "nao_entregue":
    return "pedido não entregue"
  if status == "no_prazo":
    return "entregue no prazo"
  return ""


def evidence(ref: int, item, cited: bool) -> str:
  meta = item.metadata
  parts = [
      f'<span class="evidence-ref">R{ref}</span>',
      f'<span class="score {_score_class(meta.get("review_score"))}">nota {esc(str(meta.get("review_score")))}</span>',
      f"<span>{esc(category_name(meta.get('product_category_name', '')))}</span>",
      f"<span>{esc(month_label(meta.get('purchase_month', '')))}</span>",
      f"<span>{esc(_delivery(meta))}</span>",
      f"<span>similaridade {item.similarity:.2f}</span>".replace(".", ","),
  ]
  if getattr(item, "same_text_count", 1) > 1:
    parts.append(f"<span>mesmo texto em {item.same_text_count} avaliações</span>")
  if cited:
    parts.append('<span style="color: var(--accent)">citada na resposta</span>')
  return (
      f'<div class="evidence{" cited" if cited else ""}"><div class="evidence-meta">{"".join(parts)}</div>'
      f'<div class="evidence-text">{esc(item.text)}</div>'
      f'<div class="evidence-id">review_id {esc(item.review_id)}</div></div>'
  )


def steps(parsed, retrieval, llm_label: str) -> str:
  filters = ", ".join(parsed.describe_filters()) or "nenhum"
  route = {"rag": "busca semântica + geração", "ranking": "contagem exata", "comparison": "contagem exata"}
  items = [
      ("Interpretação da pergunta",
       f"Rota: {route.get(parsed.route, parsed.route)}. Sentimento: {parsed.sentiment}. "
       f"Consulta semântica: <code>{esc(parsed.semantic_query)}</code>."),
      ("Filtros de metadados", esc(filters)),
  ]
  if retrieval is not None:
    selected = len(retrieval.evidences)
    items += [
        ("Busca no ChromaDB",
         f"<code>{esc(json.dumps(retrieval.where, ensure_ascii=False))}</code> · "
         f"{len(retrieval.candidates)} candidatas mais próximas."),
        ("Seleção das evidências",
         f"{len(retrieval.rejected)} acima do limiar de distância {str(retrieval.max_distance).replace('.', ',')}; "
         f"{len(retrieval.duplicate_ids)} com texto repetido agrupadas; {selected} escolhidas por MMR para o contexto."),
    ]
  if llm_label:
    items.append(("Geração", f"{esc(model_name(llm_label))} (<code>{esc(llm_label.partition(" · ")[2] or llm_label)}</code>) com o contexto numerado abaixo."))
  body = "".join(
      f'<div class="step"><span class="step-n">{i}</span><div><div class="step-title">{esc(title)}</div>'
      f'<div class="step-body">{text}</div></div></div>'
      for i, (title, text) in enumerate(items, 1)
  )
  return f'<div class="steps">{body}</div>'


def stat_cards(items: list[tuple[str, str, str, str]]) -> str:
  cards = "".join(
      f'<div class="kpi"><span class="kpi-label">{esc(label)}</span>'
      f'<span class="kpi-value {tone}">{esc(value)}</span><span class="kpi-note">{esc(note)}</span></div>'
      for label, value, note, tone in items
  )
  return f'<div class="stat-grid">{cards}</div>'

