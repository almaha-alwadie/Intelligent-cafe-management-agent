from pathlib import Path
from datetime import datetime
import os

# تعطيل ميزة التتبع (Telemetry) في ChromaDB لتجنب أخطاء OpenTelemetry
os.environ["CHROMA_TELEMETRY"] = "False"

import chromadb
from sentence_transformers import SentenceTransformer
from groq import Groq
import re
import streamlit as st

# CONFIG

BASE_DIR = Path(__file__).resolve().parent
MODEL_NAME = "intfloat/multilingual-e5-base"
CHROMA_DIR = BASE_DIR / "chroma_db"
OUTPUTS_DIR = BASE_DIR / "outputs"
HISTORY_PATH = OUTPUTS_DIR / "rag_chat_history.txt"

COLLECTION_NAME = "cafe_knowledge"
TOP_K = 3
SIM_THRESHOLD = 0.60


# GROQ API KEY (from environment variable or Streamlit secrets)

def get_groq_api_key():
    # أولاً: محاولة القراءة من st.secrets (عند النشر على Streamlit Cloud)
    try:
        return st.secrets["GROQ_API_KEY"]
    except (KeyError, AttributeError):
        pass

    # ثانياً: محاولة القراءة من متغير البيئة (للتشغيل المحلي عبر setx/export)
    api_key = os.getenv("GROQ_API_KEY")
    if api_key:
        return api_key

    # إذا لم يوجد المفتاح بأي طريقة
    raise ValueError(
        "GROQ_API_KEY not found. Please set it as an environment variable (GROQ_API_KEY) "
        "or add it to Streamlit secrets."
    )


GROQ_API_KEY = get_groq_api_key()
groq_client = Groq(api_key=GROQ_API_KEY)


# LANGUAGE DETECTION

def detect_language(text: str) -> str:
    arabic = sum('\u0600' <= c <= '\u06FF' for c in text)
    return "ar" if arabic > 0 else "en"


MESSAGES = {
    "ar": "❌ هذه المعلومة غير متوفرة ضمن بيانات النظام. حاول سؤالاً آخر.",
    "en": "❌ This information is not available in the system data. Please try another question."
}

# DOMAIN FILTERING (CAFE KEYWORDS)

CAFE_KEYWORDS = [
    "coffee", "espresso", "latte", "cappuccino", "mocha", "americano",
    "cold brew", "frappuccino", "iced coffee", "hot chocolate",
    "croissant", "cake", "brownie", "muffin", "donut",
    "menu", "recipe", "ingredient", "price", "preparation",
    "inventory", "stock", "order", "payment", "customer",
    "barista", "shift", "working hours", "dress code", "hygiene",
    "uniform", "dress", "safety", "employee", "policy",
    "قهوة", "اسبريسو", "لاتيه", "كابتشينو", "موكا", "امريكانو",
    "قائمة", "وصفة", "سعر", "مخزون", "طلب", "عميل", "بارستا",
    "وردية", "ساعات العمل", "زي رسمي", "الزي الرسمي", "زي", "لباس",
    "نظافة", "سلامة", "موظف", "سياسة"
]


def is_cafe_related(items, min_keyword_ratio=0.65):
    if not items:
        return False
    keyword_count = 0
    for item in items:
        text = item["text"].lower()
        if any(kw in text for kw in CAFE_KEYWORDS):
            keyword_count += 1
    ratio = keyword_count / len(items)
    print(f"[DEBUG] Cafe keyword ratio: {ratio:.2f}")
    return ratio >= min_keyword_ratio


# TRANSLATION MAPPING (FOR COMMON PHRASES IN EMPLOYEE GUIDE)

EN_AR_TRANSLATIONS = {
    "dress code": "قواعد اللباس",
    "wear clean cafe uniform at all times": "ارتدِ الزي الرسمي للمقهى النظيف في جميع الأوقات",
    "maintain personal hygiene and neat appearance": "حافظ على النظافة الشخصية والمظهر الأنيق",
    "closed shoes are required for safety": "الأحذية المغلقة مطلوبة لأسباب السلامة",
    "working hours": "ساعات العمل",
    "morning shift": "الفترة الصباحية",
    "evening shift": "الفترة المسائية",
    "employees must arrive 10 minutes before shift starts": "يجب على الموظفين الوصول قبل 10 دقائق من بدء الوردية",
    "customer service": "خدمة العملاء",
    "greet every customer politely within 10 seconds": "رحِّب بكل عميل بلطف خلال 10 ثوانٍ",
    "take orders accurately and confirm them": "استلم الطلبات بدقة وأكدها",
    "handle complaints calmly and professionally": "تعامل مع الشكاوى بهدوء واحترافية",
    "barista responsibilities": "مسؤوليات الباريستا",
    "prepare drinks according to cafe recipes": "حضّر المشروبات وفقاً لوصفات المقهى",
    "cashier responsibilities": "مسؤوليات الصراف",
    "process customer orders and payments accurately": "معالجة طلبات العملاء والمدفوعات بدقة",
    "cleaning & hygiene": "التنظيف والنظافة",
    "clean tables after each customer leaves": "نظِّف الطاولات بعد مغادرة كل عميل",
    "sanitize work surfaces regularly": "عقم أسطح العمل بانتظام",
    "inventory management": "إدارة المخزون",
    "safety procedures": "إجراءات السلامة",
    "general rules": "القواعد العامة",
    "no personal phone is used during busy hours": "لا يُسمح باستخدام الهاتف الشخصي خلال ساعات الذروة",
    "cappuccino": "كابتشينو",
    "latte": "لاتيه",
    "espresso": "اسبريسو",
    "mocha": "موكا",
    "americano": "امريكانو"
}


def translate_context(text: str) -> str:
    lower_text = text.lower()
    for en, ar in EN_AR_TRANSLATIONS.items():
        if en in lower_text:
            pattern = r'\b' + re.escape(en) + r'\b'
            text = re.sub(pattern, ar, text, flags=re.IGNORECASE)
    return text


# SYSTEM PROMPT (STRICT)

SYSTEM_MESSAGE = """
You are a professional coffee shop assistant.

RULES:
- Answer ONLY using the provided context. DO NOT add any information from your own knowledge.
- NEVER suggest ordering, requesting, or any action outside the context (e.g., do NOT say "you can order now").
- Respond in the SAME LANGUAGE as the user (Arabic or English).
- Keep answers VERY short (1 sentence maximum).
- If the user asks in Arabic, you MUST write your answer in Arabic.
- When the context is in English and you are asked in Arabic, translate the answer accurately without adding any extra words (like "يعتبر", "ممتاز", "يمكنك الطلب الآن").
- DO NOT list all items unless user explicitly asks.
- If the context does NOT contain the answer, say exactly: "I don't have this information." (in the user's language).
"""


# LOAD MODELS & CHROMA (WITH STREAMLIT CACHING + AUTO-BUILD)

@st.cache_resource
def load_resources():
    print(f"📥 Loading embedding model '{MODEL_NAME}' from Hugging Face...")
    model = SentenceTransformer(MODEL_NAME)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    try:
        collection = client.get_collection(COLLECTION_NAME)
        print("✅ Collection found.")
    except Exception:
        print("⚠️ Collection not found. Building vector database from scratch (this may take a few minutes)...")
        st.warning("⚠️ جاري بناء قاعدة المعرفة لأول مرة. قد يستغرق هذا بضع دقائق.")

        # استيراد دوال معالجة PDFs
        from processed_data import process_all_pdfs

        # 1. معالجة جميع ملفات PDF إلى أجزاء (chunks)
        all_results = process_all_pdfs(max_words=50, show_raw_once=False)

        # 2. إنشاء مجموعة جديدة
        collection = client.create_collection(name=COLLECTION_NAME)

        # 3. إضافة الأجزاء إلى قاعدة المتجهات
        for name, chunks in [
            ("menu", all_results.get("menu.pdf", [])),
            ("recipes", all_results.get("recipes.pdf", [])),
            ("employee", all_results.get("employee_guide.pdf", [])),
            ("faq", all_results.get("smart_cafe_faq.pdf", []))
        ]:
            if chunks:
                # إضافة البادئة "passage: " لكل نص قبل التضمين (مطلوب لنموذج e5)
                texts_with_prefix = [f"passage: {c['text']}" for c in chunks]
                embeddings = model.encode(texts_with_prefix, normalize_embeddings=True).tolist()
                ids = [f"{name}_{c['metadata']['global_chunk_index']}" for c in chunks]
                documents = [c["text"] for c in chunks]
                metadatas = [c["metadata"] for c in chunks]
                collection.upsert(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)
                print(f"✔ Added {len(chunks)} chunks from {name}")

        print("✅ Vector database built successfully.")
        st.success("✅ تم بناء قاعدة المعرفة بنجاح.")

    print("✅ Resources loaded (model cached).")
    return model, collection


embedding_model, collection = load_resources()


# RETRIEVAL FUNCTIONS

def retrieve(query: str):
    final_query = "query: " + query
    q_emb = embedding_model.encode(final_query, normalize_embeddings=True).tolist()
    results = collection.query(
        query_embeddings=[q_emb],
        n_results=TOP_K,
        include=["documents", "metadatas", "distances"]
    )
    items = []
    if results["documents"] and results["documents"][0]:
        for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
        ):
            items.append({
                "text": doc,
                "meta": meta,
                "distance": dist
            })
    return items


def is_relevant(items):
    if not items:
        return False
    best = min(i["distance"] for i in items)
    print(f"[DEBUG] Best distance: {best:.4f} (threshold: {SIM_THRESHOLD})")
    return best < SIM_THRESHOLD


def build_context(items, lang):
    parts = []
    for i, item in enumerate(items):
        text = item["text"]
        if lang == "ar":
            text = translate_context(text)
        parts.append(f"{i + 1}. {text}")
    return "\n\n".join(parts)


def clean_answer(answer: str) -> str:
    unwanted = [
        r'يعتبر', r'ممتاز', r'يمكنك الطلب الآن', r'يمكنك طلبها الآن',
        r'يعتبر كابتشينو مثالي', r'يعتبر المشروب مثالياً'
    ]
    for pattern in unwanted:
        answer = re.sub(pattern, '', answer, flags=re.IGNORECASE)
    answer = re.sub(r'\s+', ' ', answer).strip()
    answer = re.sub(r'\s+\.$', '.', answer)
    return answer


def build_prompt(user_query, context, lang):
    if lang == "ar":
        instruction = f"""
استخدم السياق التالي للإجابة على سؤال المستخدم. اجب بالعربية فقط.

السياق:
{context}

السؤال:
{user_query}

تعليمات صارمة جداً:
- أجب بجملة واحدة قصيرة فقط (لا تزيد عن 10 كلمات).
- اذكر الإجابة مباشرة دون أي كلمات إضافية مثل "يعتبر" أو "ممتاز" أو "يمكنك الطلب الآن".
- إذا كان السياق يؤكد وجود المنتج، اكتب فقط "نعم، لدينا [المنتج].".
- إذا كان السياق يصف المنتج، اكتب الوصف المختصر كما هو دون تحسين.
- إذا لم توجد الإجابة في السياق، اكتب فقط "لا أعرف".
- لا تترجم بشكل فضفاض؛ التزم بالنص الأصلي قدر الإمكان.

الإجابة:
"""
    else:
        instruction = f"""
Use the following context to answer the user's question. Answer in English only.

Context:
{context}

User question:
{user_query}

Strict rules:
- Answer in one short sentence (max 10 words).
- Answer directly without any extra words like "you can order now" or "it's great".
- If the context confirms the item exists, write exactly "Yes, we have [item]."
- If the context describes the item, quote the short description.
- If no answer, write "I don't know".

Answer:
"""
    return instruction


def ask_llm(prompt):
    res = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_tokens=60
    )
    raw = res.choices[0].message.content.strip()
    return clean_answer(raw)


def save_history(query, answer):
    OUTPUTS_DIR.mkdir(exist_ok=True)
    with open(HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write("=" * 50 + "\n")
        f.write(f"Q: {query}\n")
        f.write(f"A: {answer}\n\n")


# MAIN RAG TOOL

def rag_tool(query: str) -> str:
    try:
        lang = detect_language(query)
        items = retrieve(query)

        if not is_relevant(items) or not is_cafe_related(items):
            answer = MESSAGES[lang]
            save_history(query, answer)
            return answer

        context = build_context(items, lang)
        prompt = build_prompt(query, context, lang)
        answer = ask_llm(prompt)
        save_history(query, answer)
        return answer
    except Exception as e:
        error_msg = f"⚠️ RAG error: {str(e)}"
        save_history(query, error_msg)
        return error_msg


# INTERACTIVE LOOP (for testing only)

if __name__ == "__main__":
    print("\n☕ Smart Cafe RAG (Testing Mode)\n")
    while True:
        q = input("You: ").strip()
        if q.lower() in ("exit", "quit"):
            break
        if not q:
            continue
        answer = rag_tool(q)
        print("\nAnswer:\n", answer, "\n")