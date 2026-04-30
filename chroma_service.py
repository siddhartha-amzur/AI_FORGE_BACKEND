import chromadb
from chromadb.config import Settings
from openai import OpenAI
import os
from dotenv import load_dotenv

# Load env
load_dotenv()

LITELLM_URL = os.getenv("LITELLM_PROXY_URL")
LITELLM_KEY = os.getenv("LITELLM_VIRTUAL_KEY")

# LiteLLM client
client = OpenAI(
    api_key=LITELLM_KEY,
    base_url=LITELLM_URL
)

# ChromaDB client
chroma = chromadb.Client(
    Settings(persist_directory="./chroma_db")
)

collection = chroma.get_or_create_collection(name="docs")

# Add document
def add_doc(text, doc_id):
    embedding = client.embeddings.create(
        model="text-embedding-3-large",
        input=text
    ).data[0].embedding

    collection.add(
        documents=[text],
        embeddings=[embedding],
        ids=[doc_id]
    )

# Search document
def search(query):
    query_embedding = client.embeddings.create(
        model="text-embedding-3-large",
        input=query
    ).data[0].embedding

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=1
    )

    return results