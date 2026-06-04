from pathlib import Path
import os

import pandas as pd
from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_openai import ChatOpenAI
from sqlalchemy import create_engine, text

for env_path in (Path.cwd() / ".env", Path.cwd() / "text-to-sql" / ".env"):
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

# print("All 12 datasets have been created and populated in MySQL!")


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:huongbinh27@localhost:3306/football",
)
USE_HUGGINGFACE = os.getenv("USE_HUGGINGFACE", "true").lower() == "true"
MAX_RESULT_ROWS = int(os.getenv("MAX_RESULT_ROWS", "25"))
MAX_RESULT_COLUMNS = int(os.getenv("MAX_RESULT_COLUMNS", "8"))

engine = create_engine(DATABASE_URL)

SCHEMA_QUERY = text("""
    SELECT
        TABLE_NAME AS `Table`,
        COLUMN_NAME AS `Column`,
        DATA_TYPE AS `Data Type`
    FROM information_schema.columns
    WHERE table_schema = 'football'
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


def run_query(query):
    if isinstance(query, str):
        query = text(query)
    with engine.connect() as connection:
        return pd.read_sql(query, con=connection)


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
    return run_query(SCHEMA_QUERY).to_markdown(index=False)


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
            "Given an input question, convert it to a SQL query. No pre-amble. "
            "Please do not return anything else apart from the SQL query, no prefix or suffix quotes, "
            "no sql keyword, nothing please. "
            f"Always limit results to at most {MAX_RESULT_ROWS} rows using LIMIT unless the user "
            "explicitly asks for fewer. Never return unbounded result sets. "
            f"Select only the columns needed to answer the question (at most {MAX_RESULT_COLUMNS} columns). "
            "Avoid SELECT * unless the question requires many fields.",
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
