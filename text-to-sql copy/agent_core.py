from pathlib import Path
import os
from urllib.parse import parse_qs, quote, urlencode, urlsplit, urlunsplit

import pandas as pd
from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_openai import ChatOpenAI
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

BASE_DIR = Path(__file__).resolve().parent

for env_path in (BASE_DIR / ".env", Path.cwd() / ".env", Path.cwd() / "text-to-sql copy" / ".env"):
    if env_path.exists():
        load_dotenv(env_path)
        break

# RUN ONCE _ Reading data in csv -> database 
# from sqlalchemy import create_engine
# engine = create_engine("mysql+pymysql://root:huongbinh27@localhost:3306/football")
# for file_path in path.glob("*.csv"):
#     table_name = file_path.stem  # Use the filename (e.g., 'game_lineups') as the MySQL table name
    
#     print(f"Reading {file_path.name}...")
#     df = pd.read_csv(file_path, low_memory=False)
    
#     print(f"Pushing {table_name} into MySQL...")
#     # chunksizes help prevent memory issues with massive datasets
#     df.to_sql(
#         name=table_name, 
#         con=engine, 
#         if_exists='append', 
#         index=False,
#         chunksize=10000 
#     )
#     print(f"Successfully processed {table_name}!\n")

USE_HUGGINGFACE = os.getenv("USE_HUGGINGFACE", "true").lower() == "true"
MAX_RESULT_ROWS = int(os.getenv("MAX_RESULT_ROWS", "25"))
MAX_RESULT_COLUMNS = int(os.getenv("MAX_RESULT_COLUMNS", "8"))
DB_SCHEMA = os.getenv("DB_SCHEMA", "public")


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set. Add your Supabase connection string to .env")
    url = url.strip().strip('"').strip("'")

    rest = url
    for prefix in ("prisma+postgres://", "postgresql+psycopg2://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            rest = url[len(prefix):]
            break

    if "@" in rest:
        userinfo, hostpart = rest.rsplit("@", 1)
        user, password = userinfo.split(":", 1)
        rest = f"{user}:{quote(password, safe='')}@{hostpart}"

    return _strip_unsupported_pg_query_params(f"postgresql+psycopg2://{rest}")


def _strip_unsupported_pg_query_params(url: str) -> str:
    """Remove query params that Supabase/Prisma accept but psycopg2 rejects."""
    split = urlsplit(url)
    if not split.query:
        return url

    params = parse_qs(split.query, keep_blank_values=True)
    for key in ("pgbouncer", "api_key", "connection_limit", "pool_timeout"):
        params.pop(key, None)

    query = urlencode(params, doseq=True)
    return urlunsplit((split.scheme, split.netloc, split.path, query, split.fragment))


def create_db_engine():
    url = get_database_url()
    connect_args = {}
    if "supabase" in url:
        connect_args["sslmode"] = "require"
    return create_engine(
        url,
        poolclass=NullPool,
        connect_args=connect_args,
    )


engine = create_db_engine()

SCHEMA_QUERY = text("""
    SELECT
        table_name AS "Table",
        column_name AS "Column",
        data_type AS "Data Type"
    FROM information_schema.columns
    WHERE table_schema = :schema
      AND table_name NOT LIKE 'pg_%'
    ORDER BY table_name, ordinal_position;
""")

SUGGESTED_QUESTIONS = [
    "Give me the names of 10 players",
    "Which club has the highest total transfer fees received?",
    "Who are the top 5 most valuable players?",
    "How many games were played in each competition?",
    "List the 10 most recent transfers with player and club names",
    "Which country has produced the most players?",
]


def run_query(query, params=None):
    if isinstance(query, str):
        query = text(query)
    with engine.connect() as connection:
        return pd.read_sql(query, con=connection, params=params or {})


def cap_sql_rows(sql: str, max_rows: int = MAX_RESULT_ROWS) -> str:
    """Wrap SQL to fetch at most max_rows + 1 rows (extra row detects truncation)."""
    sql = sql.strip().rstrip(";")
    return f"SELECT * FROM ({sql}) AS _safe_limited LIMIT {max_rows + 1}"


def truncate_result(
    df: pd.DataFrame,
    max_rows: int = MAX_RESULT_ROWS,
    max_cols: int = MAX_RESULT_COLUMNS,
) -> tuple[pd.DataFrame, bool, bool]:
    rows_truncated = len(df) > max_rows
    cols_truncated = len(df.columns) > max_cols

    if rows_truncated:
        df = df.head(max_rows)
    if cols_truncated:
        df = df.iloc[:, :max_cols]

    return df, rows_truncated, cols_truncated


def get_schema_markdown() -> str:
    return run_query(SCHEMA_QUERY, {"schema": DB_SCHEMA}).to_markdown(index=False)


def get_llm(load_from_hugging_face: bool = USE_HUGGINGFACE):
    if load_from_hugging_face:
        hf_token = os.getenv("HUGGINGFACEHUB_API_TOKEN")
        llm = HuggingFaceEndpoint(
            repo_id="meta-llama/Llama-3.3-70B-Instruct",
            task="text-generation",
            provider="hyperbolic",
            huggingfacehub_api_token=hf_token,
        )
        return ChatHuggingFace(llm=llm)
    return ChatOpenAI(model="gpt-4", temperature=0.0)


def write_sql_query(llm, schema_markdown: str):
    template = """Based on the table schema below, write a SQL query that would answer the user's question:
    {schema}

    Question: {question}
    SQL Query: """

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "Given an input question, convert it to a PostgreSQL query. No pre-amble. "
            "Please do not return anything else apart from the SQL query, no prefix or suffix quotes, "
            "no sql keyword, nothing please. "
            f"The database dialect is PostgreSQL (Supabase). Tables are in the '{DB_SCHEMA}' schema. "
            f"Always limit results to at most {MAX_RESULT_ROWS} rows using LIMIT unless the user "
            "explicitly asks for fewer. Never return unbounded result sets. "
            f"Select only the columns needed to answer the question (at most {MAX_RESULT_COLUMNS} columns). "
            "Avoid SELECT * unless the question requires many fields. "
            "Use PostgreSQL syntax (e.g. ILIKE for case-insensitive text search).",
        ),
        ("human", template),
    ])

    return (
        RunnablePassthrough.assign(schema=lambda _: schema_markdown)
        | prompt
        | llm
        | StrOutputParser()
    )


def answer_user_query(question: str, llm=None) -> dict:
    llm = llm or get_llm()
    schema_markdown = get_schema_markdown()

    sql_query = write_sql_query(llm, schema_markdown).invoke({"question": question})
    df_result = run_query(cap_sql_rows(sql_query))
    df_result, rows_truncated, cols_truncated = truncate_result(df_result)

    template = """Based on the table below, sql query, and sql response, write a natural language response: {schema}
    Question: {question}
    SQL Query: {query}
    SQL Response: {response}"""

    prompt_response = ChatPromptTemplate.from_messages([
        (
            "system",
            "Given an input question and SQL response, convert it to a natural language answer. No pre-amble.",
        ),
        ("human", template),
    ])

    answer = (
        prompt_response
        | llm
    ).invoke({
        "schema": schema_markdown,
        "question": question,
        "query": sql_query,
        "response": df_result,
    })

    return {
        "question": question,
        "sql_query": sql_query.strip(),
        "answer": answer.content if hasattr(answer, "content") else str(answer),
        "row_count": len(df_result),
        "rows_truncated": rows_truncated,
        "columns_truncated": cols_truncated,
        "columns": list(df_result.columns),
        "rows": df_result.to_dict(orient="records"),
    }
