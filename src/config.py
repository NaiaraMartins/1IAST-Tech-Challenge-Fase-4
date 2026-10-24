import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW_DIR = os.path.join(ROOT_DIR, "data", "raw")
PROCESSED_DIR = os.path.join(ROOT_DIR, "data", "processed")
INDEX_DIR = os.path.join(ROOT_DIR, "data", "index")
CHROMA_DIR = os.path.join(ROOT_DIR, "data", "chroma_db")

REVIEWS_CSV = os.path.join(PROCESSED_DIR, "reviews_clean.csv")
EMBEDDINGS_FILE = os.path.join(INDEX_DIR, "embeddings.npy")
EMBEDDING_IDS_FILE = os.path.join(INDEX_DIR, "embedding_ids.txt")

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
COLLECTION_NAME = "olist_reviews_voc"

MIN_EVIDENCE_WORDS = 2

NEGATIVE_MAX_SCORE = 2
POSITIVE_MIN_SCORE = 4
