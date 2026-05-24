from pathlib import Path
import chromadb
from sentence_transformers import SentenceTransformer
from processed_data import process_all_pdfs


# PATHS

BASE_DIR = Path(__file__).resolve().parent
CHROMA_DIR = BASE_DIR / "chroma_db"
COLLECTION_NAME = "cafe_knowledge"

# اسم النموذج من Hugging Face (نفس المستخدم في rag_chatbot.py)
MODEL_NAME = "intfloat/multilingual-e5-base"


# LOAD MODEL (سيتحمّل من Hugging Face عند أول تشغيل)

print(f"📥 Loading embedding model '{MODEL_NAME}' from Hugging Face...")
model = SentenceTransformer(MODEL_NAME)


# CHROMA DB

client = chromadb.PersistentClient(path=str(CHROMA_DIR))

# حذف المجموعة القديمة لضمان بناء نظيف
try:
    client.delete_collection(COLLECTION_NAME)
    print(f"🗑️ Deleted existing collection '{COLLECTION_NAME}'")
except:
    pass

collection = client.create_collection(name=COLLECTION_NAME)


# ADD CHUNKS (مع بادئة passage: المطلوبة لنموذج e5)

def add_chunks(chunks, name):
    if not chunks:
        print(f"⚠️ No chunks for {name}")
        return

    # إضافة البادئة "passage: " لكل نص قبل التضمين
    texts_with_prefix = [f"passage: {c['text']}" for c in chunks]

    embeddings = model.encode(
        texts_with_prefix,
        normalize_embeddings=True,
        show_progress_bar=True
    ).tolist()

    ids = []
    documents = []
    metadatas = []

    for c in chunks:
        meta = c["metadata"]
        ids.append(f"{name}_{meta['global_chunk_index']}")
        documents.append(c["text"])
        metadatas.append(meta)

    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas
    )
    print(f"✔ Added {len(chunks)} chunks from {name}")


# SEARCH FUNCTION (للاستخدام لاحقاً في RAG)

def search(query, top_k=3):
    q_emb = model.encode(
        f"query: {query}",
        normalize_embeddings=True
    ).tolist()
    results = collection.query(
        query_embeddings=[q_emb],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )
    return results


# BUILD VECTOR DB

if __name__ == "__main__":
    print("\n☕ Building Vector DB with multilingual-e5-base model...\n")

    # معالجة جميع ملفات PDF والحصول على الأجزاء (chunks)
    all_results = process_all_pdfs(max_words=50, show_raw_once=False)

    menu_chunks = all_results.get("menu.pdf", [])
    recipes_chunks = all_results.get("recipes.pdf", [])
    employee_chunks = all_results.get("employee_guide.pdf", [])
    faq_chunks = all_results.get("smart_cafe_faq.pdf", [])  # إذا كان موجوداً

    print(f"📊 Menu chunks: {len(menu_chunks)}")
    print(f"📊 Recipes chunks: {len(recipes_chunks)}")
    print(f"📊 Employee chunks: {len(employee_chunks)}")
    print(f"📊 FAQ chunks: {len(faq_chunks)}")
    print()

    add_chunks(menu_chunks, "menu")
    add_chunks(recipes_chunks, "recipes")
    add_chunks(employee_chunks, "employee")
    add_chunks(faq_chunks, "faq")

    print("\n✅ Vector DB Ready!")
    print(f"📍 Collection: {COLLECTION_NAME}")
    print(f"📍 Location: {CHROMA_DIR}")