import streamlit as st


# PAGE CONFIG (يجب أن يكون أول أمر Streamlit)

st.set_page_config(
    page_title="Blue Cafe ",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded"
)

from datetime import datetime
import pandas as pd
import plotly.express as px
from pathlib import Path
from agent import run_agent, inventory_tool
from PIL import Image


# SESSION STATE INIT

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "role" not in st.session_state:
    st.session_state.role = None
if "chat" not in st.session_state:
    st.session_state.chat = []
if "processing" not in st.session_state:
    st.session_state.processing = False
if "language" not in st.session_state:
    st.session_state.language = "en"
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False
if "auto_inventory_ran" not in st.session_state:
    st.session_state.auto_inventory_ran = False
if "auto_inventory_result" not in st.session_state:
    st.session_state.auto_inventory_result = None
if "cart" not in st.session_state:
    st.session_state.cart = []
if "next_order_id" not in st.session_state:
    st.session_state.next_order_id = 1

# CREDENTIALS

CREDENTIALS = {
    "manager": {"username": "admin", "password": "admin123"},
    "staff": {"username": "staff", "password": "staff123"}
}

# PATHS & DATA FILES

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CSV_DIR = DATA_DIR / "csv"
CUSTOMERS_ORDERS_PATH = CSV_DIR / "customers_orders.csv"
SALES_PATH = CSV_DIR / "sales.csv"
REVIEWS_PATH = CSV_DIR / "reviews.csv"

CUSTOMERS_ORDERS_PATH.parent.mkdir(parents=True, exist_ok=True)

if not CUSTOMERS_ORDERS_PATH.exists():
    pd.DataFrame(columns=["order_id", "customer_name", "item", "quantity", "price", "payment_method", "status",
                          "timestamp"]).to_csv(
        CUSTOMERS_ORDERS_PATH, index=False)

if not SALES_PATH.exists():
    pd.DataFrame(columns=["item", "quantity"]).to_csv(SALES_PATH, index=False)



#  عرض التقييمات للعميل

def get_product_ratings():
    """تحسب متوسط التقييم لكل منتج من ملف reviews.csv"""
    if not REVIEWS_PATH.exists():
        return {}
    df = pd.read_csv(REVIEWS_PATH)
    if df.empty or "item" not in df.columns or "rating" not in df.columns:
        return {}
    ratings = df.groupby("item")["rating"].agg(["mean", "count"]).round(2)
    return ratings.to_dict(orient="index")


def display_ratings_for_customer():
    """تعرض متوسط التقييمات للعميل مع ترجمة الأسماء حسب اللغة"""
    ratings = get_product_ratings()
    if not ratings:
        st.info(get_text("no_ratings_available"))
        return

    product_label = get_text("product")
    rating_label = get_text("rating_summary")

    data = []
    for product, info in ratings.items():
        avg = info["mean"]
        count = info["count"]
        stars = "⭐" * int(avg)
        if avg % 1 >= 0.5:
            stars += "½"
        if stars == "":
            stars = "☆☆☆☆☆"
        rating_text = f"{stars} {avg:.1f}/5 ({count} {get_text('reviews_count')})"
        # ترجمة اسم المنتج حسب اللغة المختارة
        if st.session_state.language == "ar":
            display_name = PRODUCT_TRANSLATIONS.get(product, product)
        else:
            display_name = product
        data.append({product_label: display_name, rating_label: rating_text})

    df = pd.DataFrame(data)
    st.table(df)


#
# قاموس المنتجات
#
MENU_ITEMS_EN = {
    "Espresso": 2.00, "Americano": 2.50, "Cappuccino": 3.50,
    "Latte": 3.75, "Mocha": 4.00, "Iced Americano": 3.00,
    "Iced Latte": 4.00, "Iced Mocha": 4.50, "Cold Brew": 3.75,
    "Frappuccino": 5.00, "Iced Spanish Latte": 4.75,
    "Chocolate Cake": 3.50, "Cheesecake Slice": 3.75,
    "Croissant": 2.50, "Blueberry Muffin": 2.75,
    "Brownie": 3.00, "Donut": 2.25
}

PRODUCT_TRANSLATIONS = {
    "Espresso": "اسبريسو", "Americano": "امريكانو", "Cappuccino": "كابتشينو",
    "Latte": "لاتيه", "Mocha": "موكا", "Iced Americano": "امريكانو مثلج",
    "Iced Latte": "لاتيه مثلج", "Iced Mocha": "موكا مثلج", "Cold Brew": "كولد برو",
    "Frappuccino": "فرابوتشينو", "Iced Spanish Latte": "لاتيه اسباني مثلج",
    "Chocolate Cake": "كيك شوكولاتة", "Cheesecake Slice": "تشيز كيك",
    "Croissant": "كرواسون", "Blueberry Muffin": "بلوبيري مافن",
    "Brownie": "براوني", "Donut": "دونات"
}


def get_menu_items():
    """إرجاع قائمة المنتجات مع الأسماء المترجمة أو الأصلية حسب اللغة"""
    if st.session_state.language == "ar":
        return {PRODUCT_TRANSLATIONS[k]: v for k, v in MENU_ITEMS_EN.items()}
    else:
        return MENU_ITEMS_EN.copy()


def get_original_item_name(display_name):
    """تحويل الاسم المعروض (مترجم) إلى الاسم الأصلي للتخزين"""
    if st.session_state.language == "ar":
        for en, ar in PRODUCT_TRANSLATIONS.items():
            if ar == display_name:
                return en
        return display_name
    else:
        return display_name


def translate_product_name(name):
    """ترجمة اسم منتج من إنجليزي إلى عربي (إن أمكن)"""
    return PRODUCT_TRANSLATIONS.get(name, name)


def update_sales(item, quantity):
    sales_df = pd.read_csv(SALES_PATH)
    if item in sales_df['item'].values:
        sales_df.loc[sales_df['item'] == item, 'quantity'] += quantity
    else:
        new_row = pd.DataFrame({'item': [item], 'quantity': [quantity]})
        sales_df = pd.concat([sales_df, new_row], ignore_index=True)
    sales_df.to_csv(SALES_PATH, index=False)


def save_order(customer_name, cart_items, payment_method):
    order_id = st.session_state.next_order_id
    st.session_state.next_order_id += 1
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    orders_df = pd.read_csv(CUSTOMERS_ORDERS_PATH)
    new_rows = []
    for item_data in cart_items:
        new_rows.append({
            "order_id": order_id,
            "customer_name": customer_name,
            "item": item_data["item"],
            "quantity": item_data["quantity"],
            "price": item_data["price"],
            "payment_method": payment_method,
            "status": "pending",
            "timestamp": timestamp
        })
        update_sales(item_data["item"], item_data["quantity"])

    new_df = pd.DataFrame(new_rows)
    orders_df = pd.concat([orders_df, new_df], ignore_index=True)
    orders_df.to_csv(CUSTOMERS_ORDERS_PATH, index=False)
    return order_id


def complete_order(order_id):
    orders_df = pd.read_csv(CUSTOMERS_ORDERS_PATH)
    orders_df.loc[orders_df["order_id"] == order_id, "status"] = "completed"
    orders_df.to_csv(CUSTOMERS_ORDERS_PATH, index=False)


def get_sales_data():
    if SALES_PATH.exists():
        return pd.read_csv(SALES_PATH)
    return pd.DataFrame({"item": ["Espresso", "Latte", "Cappuccino"], "quantity": [50, 70, 40]})


try:
    from agent import get_current_stock
except ImportError:
    def get_current_stock():
        return pd.DataFrame(columns=["item", "current_stock", "minimum_level"])


# LOCALIZATION

def get_text(key):
    texts = {
        "en": {
            "app_title": "☕ Blue Cafe ",
            "subtitle": "Intelligent cafe management",
            "welcome_customer": "Customer",
            "welcome_staff": "Staff",
            "welcome_manager": "Manager",
            "ask_assistant": "💬 Ask the Assistant",
            "placeholder_customer": "e.g., do you have latte?, how to make cappuccino?",
            "placeholder_staff": "e.g., check inventory, sales report",
            "placeholder_manager": "e.g., check inventory, sales report, update inventory",
            "send": "🚀 Send",
            "chat_title": "💬 Conversation",
            "sidebar_control": "⚙️ Control Panel",
            "customer_orders": "🛒 New Order",
            "staff_buttons": " Tools",
            "inventory_btn": "📦 Inventory",
            "sales_btn": "📊 Sales",
            "reviews_btn": "⭐ Reviews",
            "update_stock_btn": "🔄 Update Stock",
            "clear_chat": "🧹 Clear Chat",
            "logout": "🚪 Logout",
            "tips_title": "📘 Quick Tips",
            "dark_mode": "🌙 Dark Mode",
            "download_report": "📥 Download Inventory Report",
            "login_title": "☕ Blue Cafe",
            "login_subtitle": "Please select your role and login",
            "welcome_message": "✨ Welcome to Blue Cafe ✨",
            "role_customer": "Customer",
            "role_staff": "Staff",
            "role_manager": "Manager",
            "username": "Username",
            "password": "Password",
            "login_button": "Login",
            "orders_board": "📋 Pending Orders",
            "complete_btn": "✅ Complete",
            "no_orders": "No pending orders.",
            "order_id": "Order ID",
            "customer": "Customer",
            "item": "Item",
            "quantity": "Qty",
            "price": "Price",
            "payment": "Payment",
            "time": "Time",
            "user_label": "You",
            "bot_label": "Assistant",
            "add_to_cart": "➕ Add to Cart",
            "cart_title": "🛒 Your Cart",
            "empty_cart": "Cart is empty. Add items above.",
            "total": "Total",
            "confirm_order": "✅ Confirm the Order",
            "clear_cart": "🗑️ Clear Cart",
            "order_success": "✅ Order #{} placed successfully! Total: ${:.2f}",
            "manager_dashboard": "📊 Manager Dashboard",
            "auto_stock_expander": "📋 Automatic Stock Check & Purchase Orders (run at startup)",
            "low_stock_items": "⚠️ Low stock items:",
            "all_inventory_good": "✅ All inventory levels are good.",
            "top_selling_title": "Top 5 Selling Items",
            "product": "Product",
            "qty_label": "Quantity",
            "chat_initial_msg": "✨ Ask me about the menu or recipes. Example: 'do you have latte?'",
            "inventory_data_unavailable": "Inventory data not available.",
            "automation_completed": "Automation completed. Check the Dashboard expander.",
            "order_completed_success": "Order #{} marked as completed!",
            "fetching": "Fetching...",
            "updating": "Updating stock and generating purchase orders...",
            "re_running": "Re-running stock check and order generation...",
            "thinking": "☕ Thinking...",
            "run_auto_again": "🔄 Run Full Inventory Automation Again",
            "auto_running": "Running automatic inventory check and purchase order generation...",
            "inventory_updating": "Updating stock and generating purchase orders...",
            "re_run_success": "Automation completed. Check the Dashboard expander.",
            "name_required": "Please enter your name.",
            "add_to_cart_success": "Added {} x {} to cart.",
            "your_name": "Your name",
            "rating_summary": "Rating (avg)",
            "reviews_count": "reviews",
            "no_ratings_available": "No ratings available yet."
        },
        "ar": {
            "app_title": "☕ بلو كافيه ",
            "subtitle": "إدارة ذكية للمقهى",
            "welcome_customer": "عميل",
            "welcome_staff": "موظف",
            "welcome_manager": "مدير",
            "ask_assistant": "💬 اسأل المساعد",
            "placeholder_customer": "مثال: هل لديكم لاتيه؟، كيف أحضر كابتشينو؟",
            "placeholder_staff": "مثال: فحص المخزون، تقرير المبيعات",
            "placeholder_manager": "مثال: فحص المخزون، تقرير المبيعات، تحديث المخزون",
            "send": "🚀 إرسال",
            "chat_title": "💬 المحادثة",
            "sidebar_control": "⚙️ لوحة التحكم",
            "customer_orders": "🛒 طلب جديد",
            "staff_buttons": "أدوات ",
            "inventory_btn": "📦 المخزون",
            "sales_btn": "📊 المبيعات",
            "reviews_btn": "⭐ المراجعات",
            "update_stock_btn": "🔄 تحديث المخزون",
            "clear_chat": "🧹 مسح المحادثة",
            "logout": "🚪 تسجيل الخروج",
            "tips_title": "📘 نصائح سريعة",
            "dark_mode": "🌙 الوضع الليلي",
            "download_report": "📥 تحميل تقرير المخزون",
            "login_title": "☕ بلو كافيه",
            "login_subtitle": "يرجى اختيار دورك وتسجيل الدخول",
            "welcome_message": "✨ مرحباً بكم في بلو كافيه ✨",
            "role_customer": "عميل",
            "role_staff": "موظف",
            "role_manager": "مدير",
            "username": "اسم المستخدم",
            "password": "كلمة المرور",
            "login_button": "تسجيل الدخول",
            "orders_board": "📋 الطلبات المعلقة",
            "complete_btn": "✅ تجهيز",
            "no_orders": "لا توجد طلبات معلقة.",
            "order_id": "رقم الطلب",
            "customer": "العميل",
            "item": "المنتج",
            "quantity": "الكمية",
            "price": "السعر",
            "payment": "الدفع",
            "time": "الوقت",
            "user_label": "أنت",
            "bot_label": "المساعد",
            "add_to_cart": "➕ أضف للسلة",
            "cart_title": "🛒 سلتك",
            "empty_cart": "السلة فارغة. أضف منتجات بالأعلى.",
            "total": "الإجمالي",
            "confirm_order": "✅ تأكيد الطلب",
            "clear_cart": "🗑️ إفراغ السلة",
            "order_success": "✅ تم إرسال الطلب رقم #{} بنجاح! الإجمالي: ${:.2f}",
            "manager_dashboard": "📊 لوحة تحكم المدير",
            "auto_stock_expander": "📋 فحص المخزون التلقائي وأوامر الشراء (عند بدء التشغيل)",
            "low_stock_items": "⚠️ الأصناف منخفضة المخزون:",
            "all_inventory_good": "✅ جميع مستويات المخزون جيدة.",
            "top_selling_title": "أفضل 5 منتجات مبيعاً",
            "product": "المنتج",
            "qty_label": "الكمية",
            "chat_initial_msg": "✨ اسألني عن القائمة أو الوصفات. مثال: 'هل لديكم لاتيه؟'",
            "inventory_data_unavailable": "بيانات المخزون غير متوفرة.",
            "automation_completed": "تمت الأتمتة. تحقق من لوحة التحكم.",
            "order_completed_success": "تم تجهيز الطلب رقم #{}!",
            "fetching": "جاري الجلب...",
            "updating": "جاري تحديث المخزون وإنشاء أوامر الشراء...",
            "re_running": "جاري إعادة فحص المخزون وإنشاء الأوامر...",
            "thinking": "☕ جاري التفكير...",
            "run_auto_again": "🔄 أعد تشغيل الأتمتة الكاملة للمخزون",
            "auto_running": "جاري تشغيل فحص المخزون التلقائي وإنشاء أوامر الشراء...",
            "inventory_updating": "جاري تحديث المخزون وإنشاء أوامر الشراء...",
            "re_run_success": "تمت الأتمتة. تحقق من لوحة التحكم.",
            "name_required": "الرجاء إدخال اسمك.",
            "add_to_cart_success": "تمت إضافة {} × {} إلى السلة.",
            "your_name": "اسمك",
            "rating_summary": "التقييم (متوسط)",
            "reviews_count": "مراجعة",
            "no_ratings_available": "لا توجد تقييمات متاحة بعد."
        }
    }
    return texts[st.session_state.language].get(key, key)



# CSS (RTL/LTR + DARK MODE)

def load_css():
    if st.session_state.dark_mode:
        bg_color = "#1e1e2f"
        text_color = "#ffffff"
        bot_bg = "#3a3a4a"
        user_bg = "#4a6fa5"
        sidebar_bg = "#252536"
    else:
        bg_color = "linear-gradient(135deg, #eef2ff 0%, #d9e4f5 100%)"
        text_color = "#1e293b"
        bot_bg = "#ffffff"
        user_bg = "#3182ce"
        sidebar_bg = "#f8fafc"

    direction = "rtl" if st.session_state.language == "ar" else "ltr"
    align = "right" if st.session_state.language == "ar" else "left"
    user_radius = "24px 24px 8px 24px" if direction == "ltr" else "24px 24px 24px 8px"
    bot_radius = "24px 24px 24px 8px" if direction == "ltr" else "24px 24px 8px 24px"

    st.markdown(f"""
    <style>
    .stApp {{
        background: {bg_color};
        font-family: 'Segoe UI', sans-serif;
        direction: {direction};
    }}
    .stApp::before {{
        content: "";
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-image: url('https://www.transparenttextures.com/patterns/coffee.png');
        background-repeat: repeat;
        opacity: 0.05;
        pointer-events: none;
        z-index: 0;
    }}
    .main > div {{
        position: relative;
        z-index: 2;
    }}
    .title {{
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #1e3c72, #2b4c7c);
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent;
        text-align: {align};
    }}
    .subtitle {{
        font-size: 1rem;
        color: #2c5282;
        text-align: {align};
        margin-bottom: 1rem;
    }}
    section[data-testid="stSidebar"] {{
        background: {sidebar_bg};
    }}
    .user-box {{
        background: {user_bg};
        color: white;
        padding: 10px 16px;
        border-radius: {user_radius};
        margin-bottom: 12px;
        max-width: 75%;
        margin-left: auto;
        text-align: {align};
    }}
    .bot-box {{
        background: {bot_bg};
        color: {text_color};
        padding: 12px 18px;
        border-radius: {bot_radius};
        margin-bottom: 16px;
        max-width: 85%;
        border: 1px solid #ddd;
        text-align: {align};
    }}
    div.stButton > button {{
        background-color: #2c5282;
        color: white;
        border-radius: 40px;
    }}
    </style>
    """, unsafe_allow_html=True)


# BANNER

def show_banner(image_path: Path, default_url: str):
    if image_path.exists():
        try:
            img = Image.open(image_path)
            st.image(img, use_container_width=True)
            return True
        except Exception as e:
            st.warning(f"Local image could not be loaded: {e}. Using online image instead.")
    st.image(default_url, use_container_width=True)
    return False


# LOGIN SCREEN

def login_screen():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        login_banner_path = BASE_DIR / "login_banner.jpeg"
        login_default_url = "https://images.pexels.com/photos/302899/pexels-photo-302899.jpeg?auto=compress&cs=tinysrgb&w=1600"
        show_banner(login_banner_path, login_default_url)
        st.markdown(
            f'<div style="text-align: center; font-size: 1.8rem; font-weight: 500; margin: 1rem 0;">{get_text("welcome_message")}</div>',
            unsafe_allow_html=True)
        st.markdown(f'<div class="title" style="text-align: center;">{get_text("login_title")}</div>',
                    unsafe_allow_html=True)
        st.markdown(f'<div style="text-align: center;">{get_text("login_subtitle")}</div>', unsafe_allow_html=True)

        lang = st.radio("Language / اللغة", ["English", "العربية"], horizontal=True)
        if lang == "العربية":
            st.session_state.language = "ar"
        else:
            st.session_state.language = "en"

        role = st.radio("Select role", [get_text("role_customer"), get_text("role_staff"), get_text("role_manager")],
                        horizontal=True, label_visibility="collapsed")
        role_map = {get_text("role_customer"): "customer", get_text("role_staff"): "staff",
                    get_text("role_manager"): "manager"}
        role_eng = role_map[role]

        username = ""
        password = ""
        if role_eng != "customer":
            username = st.text_input(get_text("username"))
            password = st.text_input(get_text("password"), type="password")

        if st.button(get_text("login_button"), use_container_width=True):
            if role_eng == "customer":
                st.session_state.authenticated = True
                st.session_state.role = "customer"
                st.rerun()
            elif role_eng == "staff":
                if username == CREDENTIALS["staff"]["username"] and password == CREDENTIALS["staff"]["password"]:
                    st.session_state.authenticated = True
                    st.session_state.role = "staff"
                    st.rerun()
                else:
                    st.error("Invalid username or password for Staff.")
            elif role_eng == "manager":
                if username == CREDENTIALS["manager"]["username"] and password == CREDENTIALS["manager"]["password"]:
                    st.session_state.authenticated = True
                    st.session_state.role = "manager"
                    st.rerun()
                else:
                    st.error("Invalid username or password for Manager.")
    st.stop()


# MAIN APP

if not st.session_state.authenticated:
    login_screen()

load_css()

st.markdown(f'<div class="title">{get_text("app_title")}</div>', unsafe_allow_html=True)
st.markdown(f'<div class="subtitle">{get_text("subtitle")} | {get_text(f"welcome_{st.session_state.role}")}</div>',
            unsafe_allow_html=True)

# AUTO INVENTORY

if st.session_state.role == "manager" and not st.session_state.auto_inventory_ran:
    with st.spinner(get_text("auto_running")):
        result = inventory_tool(create_orders=True, lang=st.session_state.language)
        st.session_state.auto_inventory_result = result
        st.session_state.auto_inventory_ran = True

# MANAGER DASHBOARD

if st.session_state.role == "manager":
    st.markdown(f"## {get_text('manager_dashboard')}")
    if st.session_state.auto_inventory_result:
        with st.expander(get_text("auto_stock_expander")):
            st.code(st.session_state.auto_inventory_result, language="text")
    try:
        inv_df = get_current_stock()
        if not inv_df.empty and "minimum_level" in inv_df.columns:
            low_stock = inv_df[inv_df["current_stock"] < inv_df["minimum_level"]]
            if not low_stock.empty:
                if st.session_state.language == "ar":
                    low_stock_names = [translate_product_name(name) for name in low_stock['item'].tolist()]
                else:
                    low_stock_names = low_stock['item'].tolist()
                st.warning(f"{get_text('low_stock_items')} {', '.join(low_stock_names)}")
            else:
                st.success(get_text("all_inventory_good"))
    except:
        st.info(get_text("inventory_data_unavailable"))

    sales_df = get_sales_data()
    if not sales_df.empty:
        top_sales = sales_df.groupby("item")["quantity"].sum().reset_index().sort_values("quantity",
                                                                                         ascending=False).head(5)
        if st.session_state.language == "ar":
            top_sales['item'] = top_sales['item'].apply(translate_product_name)
        fig = px.bar(top_sales, x="item", y="quantity", title=get_text("top_selling_title"), color="quantity")
        fig.update_layout(
            xaxis_title=get_text("product"),
            yaxis_title=get_text("qty_label"),
            font=dict(size=12)
        )
        st.plotly_chart(fig, use_container_width=True)

# CHAT INTERFACE

st.markdown(f"### {get_text('ask_assistant')}")
col1, col2 = st.columns([4, 1])
with col1:
    placeholder = get_text(f"placeholder_{st.session_state.role}")
    query = st.text_input("", placeholder=placeholder, key="user_input", disabled=st.session_state.processing,
                          label_visibility="collapsed")
with col2:
    send = st.button(get_text("send"), disabled=st.session_state.processing, use_container_width=True)

if send and query and not st.session_state.processing:
    st.session_state.processing = True
    with st.spinner(get_text("thinking")):
        response = run_agent(query)
        if not response:
            response = "No response from assistant."
        st.session_state.chat.append({
            "time": datetime.now().strftime("%I:%M %p"),
            "user": query,
            "bot": response
        })
        st.session_state.processing = False
        st.rerun()

st.markdown("---")
st.markdown(f"## {get_text('chat_title')}")
if not st.session_state.chat:
    st.info(get_text("chat_initial_msg"))
for msg in reversed(st.session_state.chat):
    st.markdown(f'<div class="user-box">🧑 {get_text("user_label")} · {msg["time"]}<br>{msg["user"]}</div>',
                unsafe_allow_html=True)
    st.markdown(
        f'<div class="bot-box">🤖 {get_text("bot_label")} · {msg["time"]}<br>{msg["bot"].replace(chr(10), "<br>")}</div>',
        unsafe_allow_html=True)

# SIDEBAR

with st.sidebar:
    st.markdown(f"### {get_text('sidebar_control')}")

    if st.button(get_text("dark_mode"), use_container_width=True):
        st.session_state.dark_mode = not st.session_state.dark_mode
        st.rerun()
    st.markdown("---")

    # CUSTOMER (مع عرض متوسط التقييمات بدلاً من المراجعات الكاملة)
    if st.session_state.role == "customer":
        st.subheader(get_text("customer_orders"))
        customer_name = st.text_input(get_text("your_name"), key="cust_name")
        menu_items = get_menu_items()
        col1, col2 = st.columns([3, 1])
        with col1:
            selected_item_display = st.selectbox(get_text("item"), list(menu_items.keys()), key="select_item")
        with col2:
            quantity = st.number_input(get_text("quantity"), min_value=1, max_value=10, value=1, step=1, key="qty")
        original_item = get_original_item_name(selected_item_display)
        price = MENU_ITEMS_EN[original_item]
        if st.button(get_text("add_to_cart"), use_container_width=True):
            st.session_state.cart.append({
                "item": original_item,
                "quantity": quantity,
                "price": price
            })
            st.success(get_text("add_to_cart_success").format(quantity, selected_item_display))
            st.rerun()

        st.markdown("---")
        st.markdown(f"### {get_text('cart_title')}")
        if not st.session_state.cart:
            st.info(get_text("empty_cart"))
        else:
            cart_display = []
            for item in st.session_state.cart:
                display_name = translate_product_name(item["item"]) if st.session_state.language == "ar" else item[
                    "item"]
                cart_display.append({
                    get_text("item"): display_name,
                    get_text("quantity"): item["quantity"],
                    get_text("price"): f"{item['price']:.2f}",
                    get_text("total"): f"{item['quantity'] * item['price']:.2f}"
                })
            cart_df = pd.DataFrame(cart_display)
            st.table(cart_df)
            total_amount = sum(item["quantity"] * item["price"] for item in st.session_state.cart)
            st.write(f"**{get_text('total')}: ${total_amount:.2f}**")
            payment_method = st.radio(get_text("payment"), ["Cash", "Card"], horizontal=True)
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button(get_text("confirm_order"), use_container_width=True):
                    if customer_name:
                        order_id = save_order(customer_name, st.session_state.cart, payment_method.lower())
                        st.success(get_text("order_success").format(order_id, total_amount))
                        st.session_state.cart = []
                        st.rerun()
                    else:
                        st.error(get_text("name_required"))
            with col_btn2:
                if st.button(get_text("clear_cart"), use_container_width=True):
                    st.session_state.cart = []
                    st.rerun()

        st.markdown("---")
        st.markdown(f"### {get_text('reviews_btn')}")
        display_ratings_for_customer()

    # STAFF (يرى المراجعات الكاملة)
    elif st.session_state.role == "staff":
        st.markdown(f"### {get_text('staff_buttons')}")
        if st.button(get_text("inventory_btn"), use_container_width=True):
            with st.spinner(get_text("fetching")):
                res = run_agent("check inventory")
                st.code(res, language="text")
        if st.button(get_text("sales_btn"), use_container_width=True):
            with st.spinner(get_text("fetching")):
                res = run_agent("sales report")
                st.code(res, language="text")
        if st.button(get_text("reviews_btn"), use_container_width=True):
            with st.spinner(get_text("fetching")):
                res = run_agent("show reviews")
                st.code(res, language="text")
        st.markdown("---")
        st.markdown(f"### {get_text('orders_board')}")
        orders_df = pd.read_csv(CUSTOMERS_ORDERS_PATH)
        pending = orders_df[orders_df["status"] == "pending"]
        if pending.empty:
            st.info(get_text("no_orders"))
        else:
            grouped = pending.groupby("order_id")
            for order_id, group in grouped:
                customer = group.iloc[0]["customer_name"]
                if st.session_state.language == "ar":
                    items_summary = ", ".join(
                        [f"{translate_product_name(row['item'])} x{row['quantity']}" for _, row in group.iterrows()])
                else:
                    items_summary = ", ".join([f"{row['item']} x{row['quantity']}" for _, row in group.iterrows()])
                total_price = (group["quantity"] * group["price"]).sum()
                st.write(f"**#{order_id}** - {customer} - {items_summary} - ${total_price:.2f}")
                if st.button(get_text("complete_btn"), key=f"complete_{order_id}"):
                    complete_order(order_id)
                    st.success(get_text("order_completed_success").format(order_id))
                    st.rerun()

    # MANAGER (يرى المراجعات الكاملة)
    else:
        st.markdown(f"### {get_text('staff_buttons')}")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button(get_text("inventory_btn"), use_container_width=True):
                with st.spinner(get_text("fetching")):
                    res = run_agent("check inventory")
                    st.code(res, language="text")
        with col_b:
            if st.button(get_text("sales_btn"), use_container_width=True):
                with st.spinner(get_text("fetching")):
                    res = run_agent("sales report")
                    st.code(res, language="text")
        if st.button(get_text("reviews_btn"), use_container_width=True):
            with st.spinner(get_text("fetching")):
                res = run_agent("show reviews")
                st.code(res, language="text")
        if st.button(get_text("update_stock_btn"), use_container_width=True):
            with st.spinner(get_text("inventory_updating")):
                res = run_agent("update inventory")
                st.code(res, language="text")
        st.markdown("---")
        if st.button(get_text("run_auto_again"), use_container_width=True):
            with st.spinner(get_text("re_running")):
                new_result = inventory_tool(create_orders=True, lang=st.session_state.language)
                st.session_state.auto_inventory_result = new_result
                st.success(get_text("re_run_success"))
        try:
            inv_df = get_current_stock()
            if not inv_df.empty:
                csv = inv_df.to_csv(index=False).encode('utf-8')
                st.download_button(get_text("download_report"), data=csv, file_name="inventory_report.csv",
                                   mime="text/csv")
        except:
            st.info(get_text("inventory_data_unavailable"))

    # COMMON BUTTONS
    st.markdown("---")
    if st.button(get_text("clear_chat"), use_container_width=True):
        st.session_state.chat = []
        st.rerun()
    if st.button(get_text("logout"), use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.role = None
        st.session_state.chat = []
        st.session_state.auto_inventory_ran = False
        st.session_state.auto_inventory_result = None
        st.session_state.cart = []
        st.rerun()

    st.markdown("---")
    st.caption(get_text("tips_title"))
    st.caption("© Blue Cafe ")