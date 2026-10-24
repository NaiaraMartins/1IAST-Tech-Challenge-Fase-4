"""Design tokens shared by the CSS, the HTML components and the Plotly charts."""

BG = "#0C0D10"
SURFACE = "#15171B"
SURFACE_HIGH = "#1C1F24"
BORDER = "#262930"
BAR_MUTED = "#3A3E46"
TEXT = "#E6E8EB"
MUTED = "#8B919B"
FAINT = "#5C626C"

ACCENT = "#E8336D"
NEGATIVE = "#E8336D"
POSITIVE = "#3FB8A4"
NEUTRAL = "#6E7581"
WARNING = "#E0A43B"

FONT = "IBM Plex Sans, system-ui, -apple-system, Segoe UI, sans-serif"
MONO = "IBM Plex Mono, ui-monospace, SFMono-Regular, Consolas, monospace"

CATEGORY_NAMES = {
    "cama_mesa_banho": "Cama, mesa e banho",
    "beleza_saude": "Beleza e saúde",
    "esporte_lazer": "Esporte e lazer",
    "informatica_acessorios": "Informática e acessórios",
    "moveis_decoracao": "Móveis e decoração",
    "utilidades_domesticas": "Utilidades domésticas",
    "relogios_presentes": "Relógios e presentes",
    "telefonia": "Telefonia",
    "telefonia_fixa": "Telefonia fixa",
    "automotivo": "Automotivo",
    "brinquedos": "Brinquedos",
    "cool_stuff": "Cool stuff",
    "ferramentas_jardim": "Ferramentas e jardim",
    "perfumaria": "Perfumaria",
    "bebes": "Bebês",
    "eletronicos": "Eletrônicos",
    "papelaria": "Papelaria",
    "fashion_bolsas_e_acessorios": "Bolsas e acessórios",
    "pet_shop": "Pet shop",
    "moveis_escritorio": "Móveis de escritório",
    "consoles_games": "Consoles e games",
    "malas_acessorios": "Malas e acessórios",
    "construcao_ferramentas_construcao": "Construção",
    "eletrodomesticos": "Eletrodomésticos",
    "eletroportateis": "Eletroportáteis",
    "instrumentos_musicais": "Instrumentos musicais",
    "livros_interesse_geral": "Livros",
    "alimentos": "Alimentos",
    "bebidas": "Bebidas",
    "climatizacao": "Climatização",
    "artigos_de_festas": "Artigos de festa",
    "desconhecido": "Sem categoria",
}

MONTHS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def model_name(label: str) -> str:
  """'gemini · gemini-flash-lite-latest' -> 'Gemini Flash-Lite'."""
  if not label:
    return ""
  provider, _, model = label.partition(" · ")
  pretty = {
      "gemini-flash-lite-latest": "Gemini Flash-Lite",
      "gemini-flash-latest": "Gemini Flash",
      "openai/gpt-oss-120b": "GPT-OSS 120B via Groq",
  }
  return pretty.get(model, f"{provider.capitalize()} {model}".strip())


def category_name(category: str) -> str:
  if not category:
    return ""
  return CATEGORY_NAMES.get(category, category.replace("_", " ").capitalize())


def month_label(year_month: str) -> str:
  try:
    year, month = str(year_month).split("-")[:2]
    return f"{MONTHS[int(month) - 1]}/{year}"
  except (ValueError, IndexError):
    return str(year_month)


def number(value: int) -> str:
  return f"{value:,}".replace(",", ".")


def percent(value: float, digits: int = 1) -> str:
  return f"{value * 100:.{digits}f}%".replace(".", ",")
