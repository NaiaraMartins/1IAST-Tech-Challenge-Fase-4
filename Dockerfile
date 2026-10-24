FROM python:3.12-slim

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    HF_HOME=/home/user/.cache/huggingface \
    PYTHONUNBUFFERED=1
WORKDIR /home/user/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"

COPY --chown=user . .
RUN python -m src.vector_store

EXPOSE 7860
CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0", "--server.headless=true"]
