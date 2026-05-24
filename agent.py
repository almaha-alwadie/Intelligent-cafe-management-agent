from pathlib import Path
from datetime import datetime
import pandas as pd
from groq import Groq
import os
import streamlit as st


# PATHS

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
CSV_DIR = DATA_DIR / "csv"
PDF_DIR = DATA_DIR / "pdfs"
OUTPUTS_DIR = BASE_DIR / "outputs"

INVENTORY_PATH = CSV_DIR / "inventory.csv"
SUPPLIERS_PATH = CSV_DIR / "suppliers.csv"
SALES_PATH = CSV_DIR / "sales.csv"
REVIEWS_PATH = CSV_DIR / "reviews.csv"

MENU_PATH = PDF_DIR / "menu.pdf"
RECIPES_PATH = PDF_DIR / "recipes.pdf"
GUIDE_PATH = PDF_DIR / "employee_guide.pdf"

ALERT_PATH = OUTPUTS_DIR / "stock_alert.txt"
ORDER_PATH = OUTPUTS_DIR / "purchase_order.txt"
REPORT_PATH = OUTPUTS_DIR / "report.txt"
REVIEW_PATH = OUTPUTS_DIR / "review.txt"
HISTORY_PATH = OUTPUTS_DIR / "history.txt"



# GROQ CONFIG (from environment variable or Streamlit secrets)

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


API_KEY = get_groq_api_key()
MODEL_NAME = "llama-3.1-8b-instant"
client = Groq(api_key=API_KEY)


def call_groq(prompt: str, temperature: float = 0.2, max_tokens: int = 700):
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Groq API Error: {e}"



# LOAD CSV

def load_csv(path: Path):
    if not path.exists():
        # إنشاء DataFrame فارغ بشكل مناسب
        if "inventory" in str(path):
            return pd.DataFrame(columns=["item", "initial_stock", "minimum_level", "supplier_id", "lead_time_days"])
        elif "sales" in str(path):
            return pd.DataFrame(columns=["item", "quantity"])
        elif "reviews" in str(path):
            return pd.DataFrame(columns=["review", "rating"])
        elif "suppliers" in str(path):
            return pd.DataFrame(columns=["supplier_id", "supplier_name"])
    return pd.read_csv(path)



# LIVE INVENTORY

def get_current_stock():
    inventory = load_csv(INVENTORY_PATH)
    sales = load_csv(SALES_PATH)
    if inventory.empty or sales.empty:
        return inventory
    total_sold = sales.groupby('item')['quantity'].sum()
    inventory['current_stock'] = inventory['initial_stock'] - inventory['item'].map(total_sold).fillna(0)
    inventory['current_stock'] = inventory['current_stock'].clip(lower=0)
    return inventory


def detect_low_stock(df=None):
    if df is None:
        df = get_current_stock()
    if df.empty or 'minimum_level' not in df.columns:
        return pd.DataFrame()
    return df[df['current_stock'] < df['minimum_level']]


def calculate_reorder(row):
    reorder_quantity = (row["minimum_level"] * row["lead_time_days"]) - row["current_stock"]
    return max(int(reorder_quantity), 0)



# UPDATED inventory_tool WITH LANGUAGE SUPPORT

def inventory_tool(create_orders=True, lang="en"):
    """
    Checks low stock and returns alerts + orders.
    If lang == 'ar', returns Arabic text.
    """
    inventory_df = get_current_stock()
    suppliers_df = load_csv(SUPPLIERS_PATH)
    low_stock = detect_low_stock(inventory_df)

    # Translation dictionary for product names
    name_translation = {
        "Blueberry Muffin": "بلوبيري مافن",
        "Brownie": "براوني",
        "Cheesecake Slice": "تشيز كيك",
        "Chocolate Cake": "كيك شوكولاتة",
        "Donut": "دونات",
        "Croissant": "كرواسون",
        "Espresso": "اسبريسو",
        "Americano": "امريكانو",
        "Cappuccino": "كابتشينو",
        "Latte": "لاتيه",
        "Mocha": "موكا",
        "Iced Americano": "امريكانو مثلج",
        "Iced Latte": "لاتيه مثلج",
        "Iced Mocha": "موكا مثلج",
        "Cold Brew": "كولد برو",
        "Frappuccino": "فرابوتشينو",
        "Iced Spanish Latte": "لاتيه اسباني مثلج"
    }

    if low_stock.empty:
        if lang == "ar":
            msg = "جميع مستويات المخزون جيدة."
        else:
            msg = "All inventory levels are good."
        if create_orders:
            OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
            ALERT_PATH.write_text(msg, encoding="utf-8")
            ORDER_PATH.write_text("No orders needed.", encoding="utf-8")
        return msg

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    alerts = []
    orders = []

    for _, row in low_stock.iterrows():
        reorder_quantity = calculate_reorder(row)
        supplier = suppliers_df[suppliers_df["supplier_id"] == row["supplier_id"]]
        supplier_name = supplier.iloc[0]["supplier_name"] if not supplier.empty else "Unknown"
        item_name = row['item']

        if lang == "ar":
            item_display = name_translation.get(item_name, item_name)
            alerts.append(
                f"{item_display} مخزون منخفض (الحالي={row['current_stock']:.0f}, الحد الأدنى={row['minimum_level']})"
            )
            orders.append(
                f"طلب شراء: {item_display} | الكمية={reorder_quantity} | المورد={supplier_name}"
            )
        else:
            alerts.append(
                f"{item_name} LOW STOCK (current={row['current_stock']:.0f}, min={row['minimum_level']})"
            )
            orders.append(
                f"ORDER: {item_name} | qty={reorder_quantity} | supplier={supplier_name}"
            )

    if create_orders:
        ALERT_PATH.write_text("\n".join(alerts), encoding="utf-8")
        ORDER_PATH.write_text("\n".join(orders), encoding="utf-8")
        if lang == "ar":
            result = "\n".join(alerts + ["", "أوامر الشراء:"] + orders)
        else:
            result = "\n".join(alerts + ["", "ORDERS:"] + orders)
    else:
        result = "\n".join(alerts)

    return result


def sales_tool():
    df = load_csv(SALES_PATH)
    if df.empty:
        return "No sales data available."
    top_sales = df.groupby("item")["quantity"].sum().sort_values(ascending=False).head(5)
    return "Top 5 Sales:\n" + top_sales.to_string()


def reviews_tool():
    df = load_csv(REVIEWS_PATH)
    if df.empty:
        return "No reviews available."
    return df.head(10).to_string()



# RAG TOOL

try:
    from rag_chatbot import rag_tool as rag_system_tool
except ImportError:
    def rag_system_tool(query):
        return "RAG system not available. Please install rag_chatbot or check your files."


def rag_tool(query: str):
    return rag_system_tool(query)



# ROUTER

def route_query(query: str):
    q = query.lower()
    inventory_keywords = ["stock", "inventory", "reorder", "low stock", "check stock", "مخزون", "المخزون"]
    sales_keywords = ["sales", "revenue", "top selling", "مبيعات", "المبيعات", "أرباح"]
    review_keywords = ["review", "feedback", "customer", "مراجعة", "مراجعات", "تقييم", "آراء"]
    rag_keywords = [
        # English
        "menu", "recipe", "recipes", "coffee", "drink", "guide", "prepare", "how to",
        "latte", "cappuccino", "espresso", "mocha", "americano", "hot chocolate",
        "have", "available", "is there", "do you have", "what is", "how to make",
        "price", "cost", "ingredients",
        # FAQ English
        "policy", "return", "complaint", "delivery", "payment", "hours", "working",
        # Arabic
        "قائمة", "وصفة", "وصفات", "قهوة", "مشروب", "دليل", "جهز", "كيف", "طريقة",
        "لاتيه", "كابتشينو", "اسبريسو", "موكا", "امريكانو", "شوكولاتة ساخنة",
        "هل لديكم", "عندكم", "ماذا تقدم", "ما هي", "كيف أعمل", "السعر", "سعر", "مكونات",
        # FAQ Arabic
        "ساعات العمل", "سياسة", "إرجاع", "شكوى", "توصيل", "دفع", "مواعيد"
    ]
    if "update inventory" in q or "refresh stock" in q or "تحديث المخزون" in q:
        return "update_inventory"
    elif any(word in q for word in inventory_keywords):
        return "inventory"
    elif any(word in q for word in sales_keywords):
        return "sales"
    elif any(word in q for word in review_keywords):
        return "reviews"
    elif any(word in q for word in rag_keywords):
        return "rag"
    else:
        return "rag"



# ANALYSIS & REVIEW

def analyze(query, outputs):
    combined = ""
    for name, result in outputs:
        combined += f"\n[{name}]\n{result}\n"
    prompt = f"""
You are Smart Cafe Agent.
User request: {query}
Tool results: {combined}
Generate:
1. Findings
2. Problems
3. Recommendations
4. Actions
"""
    return call_groq(prompt, max_tokens=900)


def review(report):
    prompt = f"Review this report:\n{report}\nCheck correctness, clarity, usefulness."
    return call_groq(prompt, max_tokens=400)


def save(query, plan, report, review_text):
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    REVIEW_PATH.write_text(review_text, encoding="utf-8")
    with open(HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write("\n" + "=" * 70 + "\n")
        f.write(f"Time: {datetime.now()}\nQuery: {query}\nPlan: {plan}\nReport:\n{report}\nReview:\n{review_text}\n")



# MAIN AGENT (تعيد نصًا للواجهة)

def run_agent(query: str) -> str:
    """
    تعيد النتيجة النهائية كسلسلة نصية لعرضها في Streamlit.
    """
    try:
        tool_type = route_query(query)

        # إذا كان السؤال من نوع RAG (قائمة، وصفات، وجود منتج...)، نعيد إجابة RAG مباشرة
        if tool_type == "rag":
            return rag_tool(query)

        # باقي الأدوات: inventory, sales, reviews, update_inventory
        outputs = []

        if tool_type == "update_inventory":
            result = inventory_tool(create_orders=True)
            outputs.append(("inventory_auto", result))

        elif tool_type == "inventory":
            if "create order" in query.lower() or "purchase order" in query.lower():
                result = inventory_tool(create_orders=True)
            else:
                result = inventory_tool(create_orders=False)
            outputs.append(("inventory", result))

        elif tool_type == "sales":
            result = sales_tool()
            outputs.append(("sales", result))

        elif tool_type == "reviews":
            result = reviews_tool()
            outputs.append(("reviews", result))

        else:  # unknown
            return (
                "I cannot answer this request.\n"
                "Available knowledge:\n"
                "- inventory.csv\n- sales.csv\n- reviews.csv\n"
                "- menu.pdf\n- recipes.pdf\n- employee_guide.pdf"
            )

        # إذا كان لدينا مخرجات من أدوات، نقوم بتحليلها باستخدام Groq
        if outputs:
            report = analyze(query, outputs)
            review_text = review(report)
            save(query, ["routed"], report, review_text)
            return f"{report}\n\n[Review]\n{review_text}"
        else:
            return "No output generated."

    except Exception as e:
        return f"Error in agent: {str(e)}"



# تشغيل تلقائي عند بدء السكريبت (للوضع التفاعلي)

if __name__ == "__main__":
    print("Smart Cafe Agent Started - Interactive Mode")
    # تشغيل فحص المخزون أول مرة
    print("\n[SYSTEM] Running inventory check...")
    print(inventory_tool(create_orders=True))
    print("[SYSTEM] Ready.\n")
    while True:
        q = input("Ask: ").strip()
        if q.lower() in ["exit", "quit"]:
            print("Goodbye")
            break
        if not q:
            continue
        response = run_agent(q)
        print("\n" + response + "\n")