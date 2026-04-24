import psycopg2

try:
    conn = psycopg2.connect(
        dbname="fitness_chatbot",
        user="postgres",
        password="kunal@123",
        host="localhost",
        port="5432"
    )

    print("✅ Connected to PostgreSQL")

    cur = conn.cursor()
    cur.execute("SELECT version();")

    print("DB Version:", cur.fetchone())

    conn.close()

except Exception as e:
    print("❌ Connection failed:", e)