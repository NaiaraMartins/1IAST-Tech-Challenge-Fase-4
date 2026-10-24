from ui.theme import (
    ACCENT, BG, BORDER, FAINT, MONO, MUTED, NEGATIVE, NEUTRAL, POSITIVE, SURFACE, SURFACE_HIGH, TEXT, WARNING,
)

CSS = f"""
<style>
:root {{
  --bg: {BG}; --surface: {SURFACE}; --surface-high: {SURFACE_HIGH}; --border: {BORDER};
  --text: {TEXT}; --muted: {MUTED}; --faint: {FAINT}; --accent: {ACCENT};
  --negative: {NEGATIVE}; --positive: {POSITIVE}; --neutral: {NEUTRAL}; --warning: {WARNING};
  --mono: {MONO};
}}

[data-testid="stAppDeployButton"], [data-testid="stDecoration"] {{ display: none; }}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ max-width: min(1360px, 92vw); padding-top: 2.6rem; padding-bottom: 7rem; }}
[data-testid="stBottomBlockContainer"] {{ max-width: min(1360px, 92vw); }}
h1, h2, h3, h4 {{ letter-spacing: -0.01em; text-wrap: balance; }}
p, li {{ line-height: 1.6; }}
[data-testid="stExpander"] details {{ border-color: var(--border); background: transparent; }}
[data-testid="stExpander"] summary p {{ font-size: 0.9rem; font-weight: 500; color: var(--muted); }}
[data-testid="stExpander"] summary:hover p {{ color: var(--text); }}
[data-testid="stChatInput"] {{ border-radius: 14px; }}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{ font-size: 0.88rem; }}

.voc-head {{ display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 16px 24px; margin-bottom: 28px; }}
.voc-head-text {{ display: grid; gap: 6px; min-width: 0; max-width: 680px; }}
.voc-eyebrow {{ font-size: 0.72rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--faint); font-weight: 600; }}
.voc-title {{ font-size: 2rem; font-weight: 600; letter-spacing: -0.02em; line-height: 1.15; color: var(--text); margin: 0; }}
.voc-sub {{ color: var(--muted); font-size: 0.98rem; margin: 0; }}

.status {{ display: inline-flex; align-items: center; gap: 8px; padding: 6px 12px; border: 1px solid var(--border);
  border-radius: 999px; font-size: 0.8rem; color: var(--muted); background: var(--surface); white-space: nowrap; }}
.status::before {{ content: ""; width: 7px; height: 7px; border-radius: 50%; background: var(--positive);
  box-shadow: 0 0 0 3px rgba(63, 184, 164, 0.15); }}
.status.off::before {{ background: var(--warning); box-shadow: 0 0 0 3px rgba(224, 164, 59, 0.15); }}
.status b {{ color: var(--text); font-weight: 500; }}

.kpi-grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 36px; }}
.kpi {{ border: 1px solid var(--border); border-radius: 12px; padding: 16px 18px; background: var(--surface); display: grid; gap: 4px; align-content: start; min-width: 0; }}
.kpi-label {{ font-size: 0.8rem; color: var(--muted); }}
.kpi-value {{ font-size: 1.7rem; font-weight: 600; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; color: var(--text); }}
.kpi-value.neg {{ color: var(--negative); }}
.kpi-value.pos {{ color: var(--positive); }}
.kpi-note {{ font-size: 0.78rem; color: var(--faint); line-height: 1.45; }}

.section-title {{ font-size: 1.05rem; font-weight: 600; color: var(--text); margin: 0 0 2px; }}
.section-note {{ font-size: 0.84rem; color: var(--muted); margin: 0 0 10px; }}
.chart-card-title {{ font-size: 0.92rem; font-weight: 500; color: var(--text); margin: 4px 0 0; }}
.chart-card-note {{ font-size: 0.8rem; color: var(--faint); margin: 2px 0 4px; }}
.divider {{ height: 1px; background: var(--border); margin: 28px 0; }}

.turn-user {{ display: flex; justify-content: flex-end; margin: 26px 0 14px; }}
.turn-user div {{ max-width: min(680px, 88%); background: var(--surface-high); border: 1px solid var(--border);
  border-radius: 14px 14px 4px 14px; padding: 10px 14px; color: var(--text); font-size: 0.95rem; overflow-wrap: anywhere; }}
.meta-row {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 2px 0 12px; }}
.chip {{ display: inline-flex; align-items: center; gap: 6px; font-size: 0.75rem; color: var(--muted);
  border: 1px solid var(--border); border-radius: 999px; padding: 2px 10px; background: var(--surface); white-space: nowrap; }}
.chip.accent {{ color: var(--text); border-color: rgba(232, 51, 109, 0.45); }}
.answer {{ font-size: 0.97rem; color: var(--text); }}
.answer ul {{ padding-left: 1.1rem; }}
.answer li {{ margin-bottom: 6px; }}
.cite {{ font-family: var(--mono); font-size: 0.74em; color: var(--accent); background: rgba(232, 51, 109, 0.1);
  border: 1px solid rgba(232, 51, 109, 0.28); border-radius: 6px; padding: 0 5px; white-space: nowrap; }}

.cite-note {{ font-size: 0.8rem; color: var(--faint); margin: 6px 0 12px; }}
.callout {{ border: 1px solid var(--border); border-left: 3px solid var(--warning); border-radius: 10px;
  padding: 14px 16px; background: var(--surface); display: grid; gap: 6px; margin: 4px 0 10px; }}
.callout.info {{ border-left-color: var(--neutral); }}
.callout.error {{ border-left-color: var(--negative); }}
.callout-title {{ font-weight: 600; font-size: 0.92rem; color: var(--text); }}
.callout-body {{ font-size: 0.88rem; color: var(--muted); white-space: pre-line; }}

.evidence {{ border: 1px solid var(--border); border-radius: 10px; padding: 12px 14px; display: grid; gap: 6px; margin-bottom: 8px; background: var(--bg); }}
.evidence.cited {{ border-color: rgba(232, 51, 109, 0.35); }}
.evidence-meta {{ display: flex; flex-wrap: wrap; align-items: center; gap: 4px 12px; font-size: 0.78rem; color: var(--muted); }}
.evidence-ref {{ font-family: var(--mono); font-size: 0.75rem; color: var(--text); border: 1px solid var(--border); border-radius: 6px; padding: 0 6px; }}
.evidence.cited .evidence-ref {{ color: var(--accent); border-color: rgba(232, 51, 109, 0.4); }}
.score {{ display: inline-flex; align-items: center; gap: 5px; font-variant-numeric: tabular-nums; color: var(--text); }}
.score::before {{ content: ""; width: 7px; height: 7px; border-radius: 50%; background: var(--neutral); }}
.score.neg::before {{ background: var(--negative); }}
.score.pos::before {{ background: var(--positive); }}
.evidence-text {{ font-size: 0.92rem; color: var(--text); overflow-wrap: anywhere; }}
.evidence-id {{ font-family: var(--mono); font-size: 0.7rem; color: var(--faint); overflow-wrap: anywhere; }}

.steps {{ display: grid; gap: 10px; margin-bottom: 10px; }}
.step {{ display: grid; grid-template-columns: 26px 1fr; gap: 10px; align-items: start; }}
.step-n {{ font-family: var(--mono); font-size: 0.75rem; color: var(--muted); border: 1px solid var(--border); border-radius: 6px; text-align: center; line-height: 22px; }}
.step-title {{ font-size: 0.86rem; font-weight: 500; color: var(--text); }}
.step-body {{ font-size: 0.84rem; color: var(--muted); overflow-wrap: anywhere; }}
.step-body code {{ font-size: 0.78rem; }}

.stat-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 8px 0 4px; }}

@media (max-width: 960px) {{
  .kpi-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .block-container [data-testid="stHorizontalBlock"] {{ flex-wrap: wrap; row-gap: 1rem; }}
  .block-container [data-testid="stColumn"] {{ flex: 1 1 100% !important; min-width: 100% !important; }}
}}
@media (max-width: 640px) {{
  .block-container {{ padding-top: 1.6rem; padding-left: 1rem; padding-right: 1rem; }}
  .voc-title {{ font-size: 1.55rem; }}
  .kpi {{ padding: 12px 14px; }}
  .kpi-value {{ font-size: 1.35rem; }}
  .stat-grid {{ grid-template-columns: 1fr; }}
  .turn-user div {{ max-width: 100%; }}
}}
</style>
"""
