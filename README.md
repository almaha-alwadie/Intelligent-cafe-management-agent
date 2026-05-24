# ☕ Intelligent Cafe Management Agent – وكيل إدارة المقهى الذكي


**Intelligent Cafe Management Agent** is a full‑featured web application for cafe management. It combines a conversational RAG assistant, dynamic inventory control with automated purchase orders, a multi‑item ordering system, separate dashboards for staff and manager, full bilingual support (Arabic/English with RTL/LTR), and a dark mode.

**وكيل إدارة المقهى الذكي** هو تطبيق ويب متكامل لإدارة المقهى. يجمع بين مساعد محادثة (RAG)، تحكم ديناميكي في المخزون مع أتمتة أوامر الشراء، نظام طلبات متعدد المنتجات، لوحات تحكم منفصلة للموظف والمدير، دعم كامل للغتين (عربية/إنجليزية مع اتجاه RTL/LTR)، ووضع ليلي.


## Features

- **Multi‑role authentication** – Customer, Staff, and Manager with distinct permissions.
- **RAG‑powered assistant** – Answers questions about the menu, recipes, employee guidelines, and FAQs using ChromaDB and Groq LLM.
- **Dynamic inventory management** – Automatically calculates current stock based on sales history.
- **Inventory automation** – Detects low‑stock items and generates purchase orders for suppliers. Runs automatically on startup (Manager only) and can be triggered manually.
- **Customer ordering system** – Multi‑item shopping cart with quantity selection and payment methods (Cash / Card).
- **Staff order board** – View pending orders and mark them as completed.
- **Manager dashboard** – Low‑stock alerts, a bar chart of top‑selling items, automation logs, and a downloadable inventory report (CSV).
- **Fully bilingual** – English and Arabic with automatic RTL/LTR layout.
- **Dark mode** – User‑preference dark/light theme.
- **Chat history** – Saves all assistant conversations for review.
- **Extensible data layer** – Uses CSV files for products, sales, reviews, suppliers, and customer orders.

---

## Roles & Permissions

| Action                        | Customer     | Staff  | Manager |
|-------------------------------|--------------|------- |--- ------|
| Chat with AI (RAG)            | ✅           | ✅     | ✅      |
| Place a new order             | ✅           | ❌     | ❌      |
| View current inventory        | ❌           | ✅     | ✅      |
| View sales report             | ❌           | ✅     | ✅      |
| View customer reviews         |(ratings only)| ✅     | ✅      |
| Update inventory (automation) | ❌           | ❌     | ✅      |
| Order board                   | ❌           | ✅     | ❌      |
| Advanced dashboard & charts   | ❌           | ❌     | ✅      |
| Download inventory CSV        | ❌           | ❌     | ✅      |

---

## Tech Stack

- **Python** – Core language.
- **Streamlit** – Frontend framework.
- **ChromaDB** – Vector database for RAG.
- **Sentence Transformers** – Embedding model (`intfloat/multilingual-e5-base`).
- **Groq** – LLM (`llama-3.1-8b-instant`) for answer generation.
- **Pandas** – CSV data processing.
- **Plotly** – Interactive sales chart.
- **pdfplumber** – PDF text extraction.
- **Pillow** – Image handling (login banner).

---

## Project Structure

```text
smart_cafe_agent/
│
├── app.py                      # Main Streamlit application
├── agent.py                    # Core agent (routing, inventory, sales, reviews)
├── rag_chatbot.py              # RAG retrieval and answer generation
├── processed_data.py           # PDF chunking script
├── vector_store.py             # ChromaDB index builder
├── requirements.txt
├── README.md
├── .gitignore
│
├── data/
│   ├── csv/
│   │   ├── inventory.csv       # Items, initial stock, min levels, supplier info
│   │   ├── sales.csv           # Item sales quantities
│   │   ├── reviews.csv         # Customer reviews
│   │   ├── suppliers.csv       # Supplier names and IDs
│   │   └── customers_orders.csv# Created automatically; stores customer orders
│   └── pdfs/
│       ├── menu.pdf
│       ├── recipes.pdf
│       ├── employee_guide.pdf
│       └── smart_cafe_faq.pdf  # Frequently asked questions (optional)
│
├── models/                     # Embedding model (downloaded automatically)
│   └── e5-base/
│
├── chroma_db/                  # Vector database (auto‑created)
├── outputs/                    # Logs, alerts, purchase orders, chat history
│
└── login_banner.jpeg           (optional) custom login banner image

Default Credentials
Role	Username	Password
Customer	(none)	–
Staff	staff	staff123
Manager	admin	admin123

Quick Start
1. Install dependencies
bash
pip install -r requirements.txt
2. Prepare data files
Place CSV files (inventory.csv, sales.csv, reviews.csv, suppliers.csv) in data/csv/.

Place PDF files (menu.pdf, recipes.pdf, employee_guide.pdf, smart_cafe_faq.pdf) in data/pdfs/.

3. Build the vector database (first time only)
bash
python processed_data.py   # splits PDFs into semantic chunks
python vector_store.py     # creates ChromaDB index
4. Run the application
bash
streamlit run app.py
Workflow Overview
Customer – Chat with AI, add products to cart, confirm order (Cash/Card).

Staff – View inventory, sales, reviews; see pending orders and mark them as completed.

Manager – All staff tools + dashboard (low‑stock alerts, sales chart, automation logs, inventory CSV download). Inventory automation runs automatically at startup.




Known Limitations
CSV‑based storage is not suitable for high‑concurrency scenarios.

RAG retrieval depends on the quality of PDF text extraction (scanned PDFs not supported).

The embedding model requires downloading ~1.5GB on first run.

Groq API is free but rate‑limited.

Future Improvements
Integrate with a POS system.

Add email/push notifications for new orders.

Order tracking for customers.

Image‑based product display.

Multi‑tenant support.

Portfolio Value
This project demonstrates:

Full‑stack AI integration (RAG, LLM, vector databases).

Role‑based access control in a web application.

End‑to‑end automation (inventory, ordering, reporting).

Bilingual UI with RTL support.

Document processing and chunking for RAG.

Real‑time data handling with CSV and Streamlit.

Production‑ready documentation.

License
This project was developed for educational purposes and presented in a portfolio. You may use, modify and distribute it freely with reference to the source.
© 2026 – Intelligent Cafe Management Agent (Blue Cafe AI)
Built with ☕ and Streamlit.
