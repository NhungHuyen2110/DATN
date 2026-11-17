from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2] / ".env")
import os
from neo4j import GraphDatabase


# =========================================================
# CẤU HÌNH NEO4J
# =========================================================

URI = "neo4j://127.0.0.1:7687"

USERNAME = "neo4j"

PASSWORD = os.environ["NEO4J_PASSWORD"]
# =========================================================
# TẠO DRIVER
# =========================================================

driver = GraphDatabase.driver(
    URI,
    auth=(USERNAME, PASSWORD)
)


# =========================================================
# KIỂM TRA KẾT NỐI
# =========================================================

def test_connection():
    try:
        driver.verify_connectivity()

        print("===================================")
        print("KET NOI NEO4J THANH CONG")
        print("===================================")

    except Exception as e:

        print("===================================")
        print("KET NOI NEO4J THAT BAI")
        print("===================================")

        print("Loi:", e)


# =========================================================
# CHẠY TEST
# =========================================================

if __name__ == "__main__":

    test_connection()

    driver.close()