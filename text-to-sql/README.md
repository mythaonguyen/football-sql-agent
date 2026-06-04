# ⚽ Football SQL Agent

> Ask questions about professional football in plain English — get SQL-backed answers instantly.

An **AI-powered text-to-SQL web app** that turns natural language questions into MySQL queries, runs them against a football database, and returns readable answers with the generated SQL and result table.

---

## ✨ What it does

Football data is spread across **12 related tables** (players, clubs, games, transfers, appearances, and more). Most people can't write SQL to explore it — this app handles that for you.

**Example questions you can ask:**

- 🧑‍🤝‍🧑 *"Give me the names of 10 players"*
- 💰 *"Who are the top 5 most valuable players?"*
- 🔄 *"List the 10 most recent transfers with player and club names"*
- 🌍 *"Which country has produced the most players?"*

---

## 🏗️ How it works

```mermaid
flowchart LR
    A[🌐 Browser UI] -->|POST /api/query| B[⚡ FastAPI]
    B --> C[🤖 LangChain Agent]
    C -->|1. Generate SQL| D[(🗄️ MySQL<br/>football schema)]
    D -->|2. Query results| C
    C -->|3. Summarize| E[🧠 LLM]
    E --> C
    C --> B
    B --> A
```

**Pipeline in 3 steps:**

1. 📝 **Text → SQL** — The LLM reads the database schema and writes a SQL query for your question.
2. ▶️ **Run query** — SQLAlchemy executes the query against MySQL.
3. 💬 **SQL → Answer** — The LLM summarizes the results in natural language.

Results are capped at **25 rows** and **8 columns** by default to keep responses fast and stable.

---

## 🖥️ Web UI

The frontend includes:

| Feature | Description |
|---------|-------------|
| 💡 **Suggested questions** | Clickable chips to try example queries |
| ✍️ **Question input** | Type any football question and press **Ask** |
| 📂 **Accordion history** | Past questions stay on the page — expand/collapse each one |
| 📊 **Results panel** | Natural language answer, generated SQL, and data table |

---

## 📁 Project structure

```
text-to-sql/
├── agent_core.py      # 🤖 LLM + SQL logic (LangChain)
├── app.py             # ⚡ FastAPI server & API routes
├── agent.ipynb        # 📓 Original notebook prototype
├── requirements.txt   # 📦 Python dependencies
├── .env               # 🔐 Secrets (not committed)
└── static/
    ├── index.html     # 🌐 Page layout
    ├── style.css      # 🎨 Styling
    └── app.js         # ⚙️ Frontend logic & accordion UI
```

---

## 🗄️ Data layer

| | |
|---|---|
| **📥 Source** | [Kaggle — davidcariboo/player-scores](https://www.kaggle.com/datasets/davidcariboo/player-scores) |
| **📊 Tables** | 12 CSVs → `players`, `clubs`, `games`, `transfers`, `appearances`, `competitions`, `countries`, and more |
| **💾 Storage** | MySQL database/schema named `football` |
| **🔧 Setup** | One-time load from CSV → MySQL (see `agent_core.py` — uncomment the setup block and configure your connection) |

---

## 🤖 AI / backend layer

| Setting | Default |
|---------|---------|
| **LLM** | HuggingFace — Llama 3.3 70B (via Hyperbolic) |
| **Alternative** | OpenAI GPT-4 (`USE_HUGGINGFACE=false`) |
| **Framework** | LangChain (prompt templates + chains) |
| **DB access** | SQLAlchemy + PyMySQL |

**What each query returns:**

- ✅ Natural language **answer**
- 📝 Generated **SQL query** (for transparency)
- 📋 **Result table** (up to 25 rows × 8 columns)

---

## 🚀 Getting started

### Prerequisites

- 🐍 Python 3.10+
- 🗄️ MySQL with the `football` schema populated
- 🔑 HuggingFace API token (or OpenAI API key)

### 1. Install dependencies

```bash
cd text-to-sql
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

Create a `.env` file in `text-to-sql/`:

```env
# Database (local or cloud, e.g. Railway)
DATABASE_URL=mysql+pymysql://USER:PASSWORD@HOST:PORT/football

# LLM — pick one
HUGGINGFACEHUB_API_TOKEN=your_hf_token
USE_HUGGINGFACE=true

# Optional: OpenAI instead of HuggingFace
# USE_HUGGINGFACE=false
# OPENAI_API_KEY=your_openai_key

# Optional: tune result limits
# MAX_RESULT_ROWS=25
# MAX_RESULT_COLUMNS=8
```

### 3. Run the app

```bash
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000** in your browser. 🎉

---

## 🔌 API endpoints

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/` | Serve the web UI |
| `GET` | `/api/suggestions` | List example questions |
| `POST` | `/api/query` | Run a natural language query |


---

## 🛠️ Tech stack

| Layer | Tools |
|-------|-------|
| **Frontend** | HTML, CSS, JavaScript |
| **Backend** | FastAPI, Uvicorn |
| **AI** | LangChain, HuggingFace / OpenAI |
| **Database** | MySQL, SQLAlchemy, PyMySQL |
| **Data** | Pandas, Kaggle dataset |


---

## 📜 License

Personal / portfolio project. Dataset credit: [davidcariboo/player-scores on Kaggle](https://www.kaggle.com/datasets/davidcariboo/player-scores).
