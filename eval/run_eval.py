"""Evaluates retrieval, refusal and (optionally) generation on a fixed question set.

Usage:
  python -m eval.run_eval                # retrieval + refusal + query-strategy ablation
  python -m eval.run_eval --with-llm     # also generates answers with the configured LLM

Outputs:
  eval/results/retrieval.json   per-question retrieval details
  eval/results/ablation.json    query strategy x threshold grid
  eval/results/answers.json     generated answers (only with --with-llm)
  eval/RESULTADOS.md            human-readable summary used by the README

Metric note: precision@5 here is a lexical proxy. A retrieved review counts as
relevant when it contains at least one of the question's expected word stems
(questions.json). It is cheap, reproducible and good for comparing strategies;
it is not a substitute for reading the evidence, which the README examples do.
"""

import argparse
import json
import os
import statistics
import time
from datetime import date

from sentence_transformers import SentenceTransformer

from src import rag_pipeline as rp
from src.analytics import ReviewAnalytics
from src.config import EMBEDDING_MODEL
from src.query_parser import normalize
from src.retriever import DEFAULT_MAX_DISTANCE
from src.vector_store import get_collection

EVAL_DIR = os.path.dirname(__file__)
RESULTS_DIR = os.path.join(EVAL_DIR, "results")
QUERY_MODES = ["original", "semantic", "hybrid"]
THRESHOLDS = [0.35, 0.40, 0.42, 0.45, 0.50]
LAYER1_REFUSALS = {rp.OUT_OF_SCOPE, rp.NO_EVIDENCE}
STATUS_LABELS = {
    rp.RETRIEVAL_ONLY: "evidência suficiente (segue para o LLM)",
    rp.ANSWERED: "respondida",
    rp.OUT_OF_SCOPE: "recusada: fora do escopo",
    rp.NO_EVIDENCE: "recusada: evidência fraca",
    rp.LLM_REFUSED: "recusada pelo LLM",
    rp.LLM_ERROR: "erro do LLM",
}


def load_questions():
  with open(os.path.join(EVAL_DIR, "questions.json"), encoding="utf-8") as f:
    return json.load(f)["questions"]


def precision_at_5(evidences, expected_terms) -> float | None:
  if not evidences or not expected_terms:
    return None
  top = evidences[:5]
  hits = sum(any(term in normalize(e.text) for term in expected_terms) for e in top)
  return hits / len(top)


def run_retrieval(pipeline, questions, query_mode="hybrid", max_distance=DEFAULT_MAX_DISTANCE):
  pipeline.retrieval_params = {"query_mode": query_mode, "max_distance": max_distance}
  rows = []
  for q in questions:
    answer = pipeline.answer(q["question"], use_llm=False)
    evidences = answer.evidences
    rows.append({
        "id": q["id"],
        "group": q["group"],
        "question": q["question"],
        "expect": q["expect"],
        "status": answer.status,
        "filters": answer.parsed.describe_filters(),
        "semantic_query": answer.parsed.semantic_query,
        "evidences": len(evidences),
        "precision_at_5": precision_at_5(evidences, q.get("expected_terms")),
        "mean_distance_top5": round(statistics.mean(e.distance for e in evidences[:5]), 3) if evidences else None,
        "top_evidences": [
            {"review_id": e.review_id, "score": e.metadata.get("review_score"),
             "distance": round(e.distance, 3), "text": e.text[:200]}
            for e in evidences[:5]
        ],
    })
  return rows


def summarize(rows):
  answer_rows = [r for r in rows if r["expect"] == "answer"]
  refuse_rows = [r for r in rows if r["expect"] == "refuse"]
  precisions = [r["precision_at_5"] for r in answer_rows if r["precision_at_5"] is not None]
  return {
      "in_scope_with_evidence": sum(r["status"] not in LAYER1_REFUSALS for r in answer_rows),
      "in_scope_total": len(answer_rows),
      "mean_precision_at_5": round(statistics.mean(precisions), 3) if precisions else 0.0,
      "out_of_scope_blocked_layer1": sum(r["status"] in LAYER1_REFUSALS for r in refuse_rows),
      "out_of_scope_total": len(refuse_rows),
  }


def run_ablation(pipeline, questions):
  grid = []
  for mode in QUERY_MODES:
    for threshold in THRESHOLDS:
      summary = summarize(run_retrieval(pipeline, questions, mode, threshold))
      grid.append({"query_mode": mode, "max_distance": threshold, **summary})
      print(f"  {mode:9s} limiar {threshold:.2f} -> {summary}")
  return grid


def run_generation(pipeline, questions):
  results = []
  for q in questions:
    started = time.time()
    answer = pipeline.answer(q["question"])
    results.append({
        "id": q["id"],
        "question": q["question"],
        "expect": q["expect"],
        "status": answer.status,
        "model": answer.llm_label,
        "seconds": round(time.time() - started, 1),
        "filters": answer.parsed.describe_filters(),
        "answer": answer.text,
        "error": answer.error,
        "cited": answer.cited,
        "evidences": [
            {"ref": f"R{i}", "review_id": e.review_id, "score": e.metadata.get("review_score"),
             "category": e.metadata.get("product_category_name"), "text": e.text}
            for i, e in enumerate(answer.evidences, 1)
        ],
    })
    print(f"  {q['id']}: {answer.status} ({len(answer.cited)} citações)")
  return results


def pct(a, b):
  return f"{a}/{b} ({a / b:.0%})" if b else "-"


def write_markdown(rows, grid, answers):
  summary = summarize(rows)
  lines = [
      "# Resultados da avaliação",
      "",
      f"Gerado por `python -m eval.run_eval` em {date.today().isoformat()}. "
      f"Configuração: consulta híbrida, limiar de distância {DEFAULT_MAX_DISTANCE}, mínimo de "
      f"{rp.MIN_EVIDENCES} evidências, MMR λ=0,7, top 10.",
      "",
      "## Resumo",
      "",
      f"- Perguntas do escopo que chegaram ao modelo com evidência suficiente: "
      f"{pct(summary['in_scope_with_evidence'], summary['in_scope_total'])}",
      f"- Precisão@5 média (proxy lexical): {summary['mean_precision_at_5']:.2f}",
      f"- Perguntas fora do escopo barradas antes do LLM (camada 1): "
      f"{pct(summary['out_of_scope_blocked_layer1'], summary['out_of_scope_total'])}. "
      "As demais chegam ao modelo, que deve responder SEM_EVIDENCIA (camada 2).",
      "",
  ]
  if answers:
    in_scope = [a for a in answers if a["expect"] == "answer"]
    out_scope = [a for a in answers if a["expect"] == "refuse"]
    refused = {rp.OUT_OF_SCOPE, rp.NO_EVIDENCE, rp.LLM_REFUSED}
    times = [a["seconds"] for a in answers if a["status"] in (rp.ANSWERED, rp.LLM_REFUSED)]
    lines += [
        f"Com o LLM (`{next((a['model'] for a in answers if a['model']), '-')}`):",
        "",
        f"- Perguntas do escopo respondidas com pelo menos uma citação: "
        f"{pct(sum(a['status'] == rp.ANSWERED and bool(a['cited']) for a in in_scope), len(in_scope))}",
        f"- Perguntas fora do escopo recusadas no total (camadas 1 e 2): "
        f"{pct(sum(a['status'] in refused for a in out_scope), len(out_scope))}",
        f"- Tempo médio das chamadas ao modelo: {statistics.mean(times):.1f} s" if times else "",
        "",
    ]
  lines += [
      "## Por pergunta",
      "",
      "| Pergunta | Esperado | Resultado | Filtros | Evidências | Precisão@5 | Distância média top 5 |",
      "|---|---|---|---|---|---|---|",
  ]
  for r in rows:
    p5 = f"{r['precision_at_5']:.2f}" if r["precision_at_5"] is not None else "-"
    dist = f"{r['mean_distance_top5']:.3f}" if r["mean_distance_top5"] is not None else "-"
    lines.append(
        f"| {r['question']} | {'responder' if r['expect'] == 'answer' else 'recusar'} | {STATUS_LABELS[r['status']]} | "
        f"{', '.join(r['filters']) or '-'} | {r['evidences']} | {p5} | {dist} |"
    )
  lines += [
      "",
      "## Estratégia de consulta x limiar",
      "",
      "Cada linha roda as 22 perguntas. \"Escopo com evidência\" deve ser alto; \"fora barradas\" também.",
      "",
      "| Consulta | Limiar | Escopo com evidência | Precisão@5 | Fora do escopo barradas (camada 1) |",
      "|---|---|---|---|---|",
  ]
  for g in grid:
    lines.append(
        f"| {g['query_mode']} | {g['max_distance']:.2f} | {pct(g['in_scope_with_evidence'], g['in_scope_total'])} | "
        f"{g['mean_precision_at_5']:.2f} | {pct(g['out_of_scope_blocked_layer1'], g['out_of_scope_total'])} |"
    )
  if answers:
    lines += ["", "## Respostas geradas", ""]
    for a in answers:
      lines += [f"### {a['question']}", "", f"Resultado: {STATUS_LABELS[a['status']]} · modelo: `{a['model']}` · "
                f"filtros: {', '.join(a['filters']) or 'nenhum'}", ""]
      if a["answer"]:
        lines += [a["answer"], ""]
      cited = [e for i, e in enumerate(a["evidences"], 1) if i in a["cited"]]
      if cited:
        lines.append("Avaliações citadas:")
        lines += [f"- **{e['ref']}** (nota {e['score']}, {e['category']}, `{e['review_id']}`): {e['text']}" for e in cited]
        lines.append("")
  with open(os.path.join(EVAL_DIR, "RESULTADOS.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")


def save(name, data):
  os.makedirs(RESULTS_DIR, exist_ok=True)
  with open(os.path.join(RESULTS_DIR, name), "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)


def load_saved(name):
  path = os.path.join(RESULTS_DIR, name)
  if not os.path.exists(path):
    return []
  with open(path, encoding="utf-8") as f:
    return json.load(f)


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument("--with-llm", action="store_true", help="gera respostas com o LLM configurado")
  args = parser.parse_args()

  questions = load_questions()
  analytics = ReviewAnalytics()
  model = SentenceTransformer(EMBEDDING_MODEL)
  collection = get_collection()

  pipeline = rp.VoCPipeline.with_configured_llm(model, collection, analytics.categories)
  print("Recuperação com a configuração padrão...")
  rows = run_retrieval(pipeline, questions)
  save("retrieval.json", rows)
  print("Ablação: estratégia de consulta x limiar...")
  grid = run_ablation(pipeline, questions)
  save("ablation.json", grid)
  pipeline.retrieval_params = {}

  answers = load_saved("answers.json")
  if args.with_llm:
    if pipeline.generator is None:
      raise SystemExit("Nenhum LLM configurado. Preencha o .env (veja .env.example).")
    print(f"Gerando respostas com {pipeline.generator.label}...")
    answers = run_generation(pipeline, questions)
    save("answers.json", answers)

  write_markdown(rows, grid, answers)
  print(f"Resumo: {summarize(rows)}")
  print("Relatório salvo em eval/RESULTADOS.md")


if __name__ == "__main__":
  main()
