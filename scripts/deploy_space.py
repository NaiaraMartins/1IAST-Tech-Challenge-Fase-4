"""Publishes the app to a Hugging Face Space (Docker SDK).

Since 2026, Docker and Gradio Spaces on cpu-basic require a Hugging Face PRO
subscription (the API answers 402 otherwise). The free path for this project is
Streamlit Community Cloud (see README); this script stays for teams with PRO.

Usage:
  python -m scripts.deploy_space --space <usuario-hf>/voc-olist

Reads from the environment (or .env):
  HF_TOKEN        Hugging Face token with write permission
  LLM_PROVIDER    copied to the Space as a variable (default gemini)
  LLM_MODEL       optional, copied as a variable
  GOOGLE_API_KEY  copied as a Space secret when set
  GROQ_API_KEY    copied as a Space secret when set

Only the files the app needs are uploaded (no raw CSVs, no ChromaDB folder:
the Docker build recreates the collection from data/index/embeddings.npy).
Secrets are sent through the Hugging Face API and never written to the repo.
"""

import argparse
import os
import shutil
import tempfile

from dotenv import load_dotenv
from huggingface_hub import HfApi

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FILES = ["app.py", "requirements.txt", "Dockerfile"]
FOLDERS = ["src", "ui", ".streamlit", "data/processed", "data/index"]
SPACE_README = """---
title: Voice of Customer Olist
emoji: 🛍️
colorFrom: pink
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
short_description: RAG sobre avaliações de clientes da Olist (FIAP Fase 4)
---

Voice of Customer Intelligence com RAG sobre as avaliações da Olist.
Código, arquitetura e instruções: {github}
"""


def stage_files(target: str, github_url: str):
  for name in FILES:
    shutil.copy2(os.path.join(ROOT, name), os.path.join(target, name))
  for folder in FOLDERS:
    shutil.copytree(
        os.path.join(ROOT, folder), os.path.join(target, folder),
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".gitkeep"),
    )
  with open(os.path.join(target, "README.md"), "w", encoding="utf-8") as f:
    f.write(SPACE_README.format(github=github_url))


def main():
  load_dotenv(os.path.join(ROOT, ".env"))
  parser = argparse.ArgumentParser()
  parser.add_argument("--space", required=True, help="usuario/nome-do-space")
  parser.add_argument(
      "--github", default="https://github.com/NaiaraMartins/1IAST-Tech-Challenge-Fase-4"
  )
  args = parser.parse_args()

  token = os.getenv("HF_TOKEN")
  if not token:
    raise SystemExit("Defina HF_TOKEN (token de escrita do Hugging Face) no ambiente ou no .env.")

  api = HfApi(token=token)
  api.create_repo(args.space, repo_type="space", space_sdk="docker", exist_ok=True)

  api.add_space_variable(args.space, "LLM_PROVIDER", os.getenv("LLM_PROVIDER", "gemini"))
  if os.getenv("LLM_MODEL"):
    api.add_space_variable(args.space, "LLM_MODEL", os.getenv("LLM_MODEL"))
  for secret in ("GOOGLE_API_KEY", "GROQ_API_KEY"):
    if os.getenv(secret):
      api.add_space_secret(args.space, secret, os.getenv(secret))
      print(f"Secret {secret} cadastrado no Space.")

  with tempfile.TemporaryDirectory() as staging:
    stage_files(staging, args.github)
    api.upload_folder(
        folder_path=staging, repo_id=args.space, repo_type="space",
        commit_message="Deploy from GitHub repository",
        delete_patterns=["*"],
    )
  print(f"Publicado: https://huggingface.co/spaces/{args.space}")
  print("O primeiro build leva alguns minutos (instala PyTorch e monta o índice).")


if __name__ == "__main__":
  main()
