from fastapi import FastAPI, Request
import requests
import time
import re
import json
import os
import chromadb
from chromadb.utils import embedding_functions
import threading
from app_fastapi.core.user_manager import get_user_profile
import psycopg2
from app_fastapi.services.whatsapp_utils import send_whatsapp_interactive

db_lock = threading.Lock()


ACCESS_TOKEN = "EAALEejxob64BRS9yHxumT3dgwzWUs5KFzS94zE8Sx6xV3qLZAv1t1LUTbO2caBjAe5CTZC3OUpd4YS8mpoSZAt1ZCZBdG0hpHwMolWnDt1JE822C78FkScImaY9x37h7iZCyY2CayqlesjVtjJd8UaIZBFGAfyJQlFAFZBKppoFW37mdp38JavA6mgZAYHjXBz6eurX3WP5vw5IqO3Q6nczNh9IrxwShd4lzG2d8AqVBSqTxpNoGhyRJe5CjQX8plsG20YDRZAPzLMWZAIrRkvgQzxR9m9s"
PHONE_NUMBER_ID = "941939392346477"

def send_whatsapp_message(to, text):
    import requests

    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }

    response = requests.post(url, headers=headers, json=payload)
    print("📤 WhatsApp SEND:", response.status_code, response.text)


app = FastAPI()

# -------------------- CONFIG --------------------
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "chatbot_global.db")

DM_ONLY_MODE = False 

# -------------------- VECTOR DB (Phase-3) --------------------
chroma_client = chromadb.Client()

embedding_func = embedding_functions.OllamaEmbeddingFunction(
    url="http://localhost:11434",
    model_name="nomic-embed-text",
)

memory_collection = chroma_client.get_or_create_collection(
    name="chat_memory_vectors",
    embedding_function=embedding_func,
)



# -------------------- DB --------------------
def init_db():
    conn = db()
    cur = conn.cursor()

    # ---------------- USER PROFILE ----------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_profile (
        global_user_id TEXT PRIMARY KEY,
        height_cm FLOAT,
        weight_kg FLOAT,
        age INT,
        gender TEXT,
        activity_level TEXT,
        goal TEXT,
        diet_type TEXT,
        updated_at BIGINT
    )
    """)

    # ---------------- PROCESSED EVENTS ----------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS processed_events (
        event_id TEXT PRIMARY KEY,
        created_at BIGINT
    )
    """)

    # ---------------- CONTEXT ----------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS conversation_context (
        global_user_id TEXT PRIMARY KEY,
        last_question_type TEXT,
        last_question_text TEXT,
        pending_field TEXT,
        pending_value TEXT,
        updated_at BIGINT
    )
    """)

    # ---------------- CHAT MEMORY ----------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS chat_memory (
        global_user_id TEXT PRIMARY KEY,
        history TEXT,
        updated_at BIGINT
    )
    """)

    # ---------------- PLAN STATE ----------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS plan_state (
        global_user_id TEXT PRIMARY KEY,
        generated INT,
        updated_at BIGINT
    )
    """)

    # ---------------- ARTIFACTS ----------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS conversation_artifacts (
        id SERIAL PRIMARY KEY,
        global_user_id TEXT,
        type TEXT,
        content TEXT,
        created_at BIGINT
    )
    """)

    conn.commit()
    conn.close()

    print("✅ PostgreSQL tables initialized")


DB_CONFIG = {
    "dbname": "fitness_chatbot",
    "user": "postgres",
    "password": "kunal@123",   # <-- same as test file
    "host": "localhost",
    "port": "5432"
}

def db():
    return psycopg2.connect(**DB_CONFIG)


# -------------------- EVENT DEDUP --------------------
def is_event_processed(event_id: str) -> bool:
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM processed_events WHERE event_id = %s", (event_id,))
    row = cur.fetchone()
    conn.close()
    return row is not None


def mark_event_processed(event_id: str):
    with db_lock:
        conn = db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO processed_events(event_id, created_at)
            VALUES (%s, %s)
            ON CONFLICT (event_id) DO NOTHING
        """, (event_id, int(time.time())))
        conn.commit()
        conn.close()


# -------------------- CONTEXT MEMORY --------------------
def get_context(global_user_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT last_question_type, last_question_text, pending_field, pending_value
        FROM conversation_context WHERE global_user_id=%s
    """, (global_user_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return {
            "last_question_type": None,
            "last_question_text": None,
            "pending_field": None,
            "pending_value": None
        }

    return {
        "last_question_type": row[0],
        "last_question_text": row[1],
        "pending_field": row[2],
        "pending_value": row[3]
    }


def set_context(global_user_id, q_type, q_text, pending_field=None, pending_value=None):
    with db_lock:
        conn = db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO conversation_context(global_user_id, last_question_type, last_question_text, pending_field, pending_value, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (global_user_id) DO UPDATE SET
                last_question_type = EXCLUDED.last_question_type,
                last_question_text = EXCLUDED.last_question_text,
                pending_field = EXCLUDED.pending_field,
                pending_value = EXCLUDED.pending_value,
                updated_at = EXCLUDED.updated_at
        """, (global_user_id, q_type, q_text, pending_field, pending_value, int(time.time())))
        conn.commit()
        conn.close()


def clear_context(global_user_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("DELETE FROM conversation_context WHERE global_user_id=%s", (global_user_id,))
    conn.commit()
    conn.close()

def set_plan_generated(global_user_id, value: bool):
    with db_lock:
        conn = db()
        cur = conn.cursor()


        cur.execute("""
            INSERT INTO plan_state(global_user_id, generated, updated_at)
            VALUES (%s, %s, %s)
            ON CONFLICT(global_user_id) DO UPDATE SET
                generated=EXCLUDED.generated,
                updated_at = EXCLUDED.updated_at  
        """, (global_user_id, 1 if value else 0, int(time.time())))

        conn.commit()
        conn.close()

def save_artifact(global_user_id, type_, content):
    with db_lock:
        conn = db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO conversation_artifacts(global_user_id, type, content, created_at)
            VALUES (%s, %s, %s, %s)
        """, (global_user_id, type_, content, int(time.time())))
        conn.commit()
        conn.close()

def save_vector_memory(global_user_id, text, type_="chat"):
    """
    Stores semantic memory into ChromaDB.
    """

    memory_collection.add(
        documents=[text],
        metadatas=[{"user": global_user_id, "type": type_}],
        ids=[f"{global_user_id}_{int(time.time()*1000)}"],
    )



def get_recent_artifacts(global_user_id, limit=3):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT type, content FROM conversation_artifacts
        WHERE global_user_id=%s
        ORDER BY created_at DESC
        LIMIT %s
    """, (global_user_id, limit))
    rows = cur.fetchall()
    conn.close()

    return "\n\n".join([f"{t.upper()}:\n{c}" for t, c in rows])

# -------------------- RAG CORE --------------------
def build_rag_context(global_user_id, query=None):
    """
    Combines:
    - user profile
    - recent artifacts
    - semantic vector memory search
    """

    artifacts = get_recent_artifacts(global_user_id)
    profile = get_profile(global_user_id)

    vector_memory = ""
    if query:
        vector_memory = search_vector_memory(global_user_id, query)

    profile_text = f"""
PROFILE:
Height: {profile['height_cm']}
Weight: {profile['weight_kg']}
Age: {profile['age']}
Goal: {profile['goal']}
Activity: {profile['activity_level']}
Diet: {profile['diet_type']}
"""

    return profile_text + "\n\nRECENT ARTIFACTS:\n" + artifacts + "\n\nSEMANTIC MEMORY:\n" + vector_memory


def search_vector_memory(global_user_id, query, k=3):
    """
    Finds most relevant past memories using vector similarity.
    """

    results = memory_collection.query(
        query_texts=[query],
        n_results=k,
        where={"user": global_user_id},
    )

    if not results or not results.get("documents"):
        return ""

    docs = results["documents"][0]
    return "\n\n".join(docs)


# -------------------- VECTOR RAG (PHASE 2) --------------------
import chromadb
from chromadb.utils import embedding_functions







def is_plan_generated(global_user_id) -> bool:
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT generated FROM plan_state WHERE global_user_id=%s
    """, (global_user_id,))

    row = cur.fetchone()
    conn.close()

    return bool(row[0]) if row else False


def get_chat_history(global_user_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT history FROM chat_memory WHERE global_user_id=%s", (global_user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else ""


def append_chat_history(global_user_id, role, text):
    history = get_chat_history(global_user_id)

    # Convert to list
    lines = history.split("\n") if history else []

    # Add new message
    lines.append(f"{role}: {text}")

    # Keep ONLY last 6 messages (3 user + 3 bot)
    lines = lines[-6:]

    new_history = "\n".join(lines)


    with db_lock:
        conn = db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO chat_memory(global_user_id, history, updated_at)
            VALUES (%s, %s, %s)
            ON CONFLICT(global_user_id) DO UPDATE SET
                history=excluded.history,
                updated_at=excluded.updated_at
        """, (global_user_id, new_history, int(time.time())))
        conn.commit()
        conn.close()



# -------------------- IDENTITY --------------------
def get_global_user_id(channel: str, channel_user_id: str) -> str:
    return f"{channel}:{channel_user_id}"


# -------------------- PROFILE --------------------
def profile_exists(global_user_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM user_profile WHERE global_user_id=%s", (global_user_id,))
    row = cur.fetchone()
    conn.close()
    return row is not None


def get_profile(global_user_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT height_cm, weight_kg, age, gender, activity_level, goal, diet_type
        FROM user_profile WHERE global_user_id=%s
    """, (global_user_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return {
            "height_cm": None,
            "weight_kg": None,
            "age": None,
            "gender": None,
            "activity_level": None,
            "goal": None,
            "diet_type": None
        }

    return {
    "height_cm": row[0],
    "weight_kg": row[1],
    "age": row[2],
    "gender": row[3],
    "activity_level": row[4],
    "goal": row[5],
    "diet_type": row[6]
}


def update_profile(global_user_id, **kwargs):
    existing = get_profile(global_user_id)

    height_cm = kwargs.get("height_cm", existing["height_cm"])
    weight_kg = kwargs.get("weight_kg", existing["weight_kg"])
    age = kwargs.get("age", existing["age"])
    gender = kwargs.get("gender", existing.get("gender"))
    activity_level = kwargs.get("activity_level", existing["activity_level"])
    goal = kwargs.get("goal", existing["goal"])
    diet_type = kwargs.get("diet_type", existing["diet_type"])

    with db_lock:
        conn = db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO user_profile(global_user_id, height_cm, weight_kg, age, gender, activity_level, goal, diet_type, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT(global_user_id) DO UPDATE SET
                height_cm=excluded.height_cm,
                weight_kg=excluded.weight_kg,
                age=excluded.age,
                gender = excluded.gender,
                activity_level=excluded.activity_level,
                goal=excluded.goal,
                diet_type=excluded.diet_type,
                updated_at=excluded.updated_at
            """, (global_user_id, height_cm, weight_kg, age, gender, activity_level, goal, diet_type, int(time.time())))
        conn.commit()
        conn.close()


# -------------------- SLACK SEND --------------------
def send_slack_message(channel_id, text):

    # 👉 WHATSAPP MODE
    if is_whatsapp(channel_id):  # phone number
        send_whatsapp_message(channel_id, text)
        return

    # 👉 SLACK MODE
    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "channel": channel_id,
        "text": text
    }

    r = requests.post("https://slack.com/api/chat.postMessage", headers=headers, json=payload)
    print("Slack send:", r.status_code, r.text)
    


def update_slack_message(channel, ts, text):
    requests.post(
        "https://slack.com/api/chat.update",
        headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "channel": channel,
            "ts": ts,
            "text": text,
        },
        timeout=5
    )


#  FIXED: Unique action_id per button using action_prefix + value
def send_buttons(channel_id, text, buttons, action_prefix):
    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json"
    }

    elements = []
    for b in buttons:
        elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": b["text"]},
            "value": b["value"],
            "action_id": f"{action_prefix}_{b['value']}"
        })

    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": text}},
        {"type": "actions", "elements": elements}
    ]

    payload = {"channel": channel_id, "text": text, "blocks": blocks}
    r = requests.post(url, headers=headers, json=payload)

    try:
        data = r.json()
    except:
        print(" Buttons send failed: non-json response")
        print(r.text)
        return False

    if not data.get("ok"):
        print(" Slack Block send error:", data.get("error"))
        print("Full Slack response:", data)
        return False

    return True

def send_long_message(channel, text, chunk_size=2500):
    """
    Sends long text to Slack in multiple chunks.
    Prevents 3000-char truncation.
    """
    parts = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

    for part in parts:
        send_slack_message(channel, part)
        time.sleep(0.3)  # small delay to avoid Slack rate limit


# -------------------- HELPERS --------------------
def is_greeting(text):
    t = text.lower().strip()
    greetings = ["hi", "hello", "hey", "hii", "hlo", "good morning", "good afternoon", "good evening"]
    return any(t == g or t.startswith(g + " ") for g in greetings)

def is_whatsapp(channel_id):
    return str(channel_id).isdigit()

def detect_plan_section(user_text):
    t = user_text.lower()

    if any(w in t for w in ["workout", "exercise", "training", "knee", "injury"]):
        return "workout"

    if any(w in t for w in ["diet", "food", "calorie", "meal", "nutrition"]):
        return "diet"

    return "full"


def is_plain_number(text):
    t = text.strip().lower()
    return re.fullmatch(r"\d{1,3}(\.\d{1,2})?", t) is not None


def is_unit_reply(text):
    t = text.strip().lower()
    return t in ["kg", "kgs", "lb", "lbs", "g", "cm", "m", "ft", "feet"]


def parse_age(text):
    t = text.strip().lower()
    if re.fullmatch(r"\d{1,2}", t):
        a = int(t)
        if 5 <= a <= 100:
            return a
    return None


def parse_height_cm(text):
    t = text.lower().strip()

    # 5 ft 7 in
    m = re.search(r"(\d+)\s*ft\s*(\d+)\s*in", t)
    if m:
        feet = int(m.group(1))
        inches = int(m.group(2))
        return round(feet * 30.48 + inches * 2.54, 2)

    # 5.7 ft (treat decimal as feet only)
    m = re.search(r"(\d+(?:\.\d+)?)\s*(ft|feet)", t)
    if m:
        return round(float(m.group(1)) * 30.48, 2)

    # cm
    m = re.search(r"(\d{2,3}(?:\.\d+)?)\s*cm", t)
    if m:
        return float(m.group(1))

    # meters
    m = re.search(r"(\d(?:\.\d+)?)\s*m", t)
    if m:
        return float(m.group(1)) * 100

    return None




def parse_weight_kg(text: str):
    t = text.lower().strip()

    # --- kilograms ---
    m = re.search(r'(\d{1,3}(?:\.\d+)?)\s*(kg|kgs|kilogram|kilograms)\b', t)
    if m:
        return float(m.group(1))

    # --- grams ---
    m = re.search(r'(\d{3,6}(?:\.\d+)?)\s*(g|gram|grams)\b', t)
    if m:
        return float(m.group(1)) / 1000

    # --- pounds ---
    m = re.search(r'(\d{2,3}(?:\.\d+)?)\s*(lb|lbs|pound|pounds)\b', t)
    if m:
        return float(m.group(1)) * 0.453592

    # --- stone + pounds (UK format) ---
    m = re.search(r'(\d{1,2})\s*(st|stone)\s*(\d{1,2})?\s*(lb|lbs)?', t)
    if m:
        stone = int(m.group(1))
        pounds = int(m.group(3)) if m.group(3) else 0
        total_pounds = stone * 14 + pounds
        return total_pounds * 0.453592

    return None



def validate_height_cm(h): return h is not None and 80 <= h <= 250

def validate_weight_kg(w): return w is not None and 20 <= w <= 300

def validate_age(a): return a is not None and 5 <= a <= 100


# -------------------- FLOW --------------------
def missing_fields(profile):
    missing = []
    if profile.get("height_cm") is None:
        missing.append("height")
    if profile.get("weight_kg") is None:
        missing.append("weight")
    if profile.get("age") is None:
        missing.append("age")
    if profile.get("gender") is None:
        missing.append("gender")
    if profile.get("goal") is None:
        missing.append("goal")
    if profile.get("activity_level") is None:
        missing.append("activity")
    if profile.get("diet_type") is None:
        missing.append("diet_type")
    return missing


def send_profile_summary(profile, channel_id, global_user_id):
    summary = (
        "Please verify your details:\n\n"
        f"Height: {profile['height_cm']} cm\n"
        f"Weight: {profile['weight_kg']} kg\n"
        f"Age: {profile['age']}\n"
        f"Gender: {profile.get('gender', 'Not set')}\n"
        f"Goal: {profile['goal']}\n"
        f"Activity Level: {profile['activity_level']}\n"
        f"Diet Type: {profile['diet_type']}\n\n"
    )

    if is_whatsapp(channel_id):
        send_whatsapp_interactive(
            channel_id,
            summary + "\n\nAre these details correct?",
            buttons=["confirm", "edit"]
        )
    else:
        send_buttons(...)

    set_context(global_user_id, "verify", summary)



def ask_next_question(profile, global_user_id, channel_id):
    missing = missing_fields(profile)

    if not missing:
        send_profile_summary(profile, channel_id, global_user_id)
        return


    field = missing[0]

    if field == "height":
        q = "What's your height? (e.g., 6 ft / 180 cm)"
        set_context(global_user_id, "height", q)
        send_slack_message(channel_id, q)

    elif field == "weight":
        q = "Got it  What's your weight? (e.g., 85 kg)"
        set_context(global_user_id, "weight", q)
        send_slack_message(channel_id, q)

    elif field == "age":
        q = "Nice  What's your age?"
        set_context(global_user_id, "age", q)
        send_slack_message(channel_id, q)

    elif field == "gender":
        q = "Select your gender:"
        set_context(global_user_id, "gender", q)

        if is_whatsapp(channel_id):
            send_whatsapp_interactive(
                channel_id,
                "Select your gender:",
                buttons=["male", "female"]
            )
        else:
            send_buttons(channel_id, q, [
                {"text": "Male", "value": "male"},
                {"text": "Female", "value": "female"}
            ], action_prefix="gender")

    elif field == "goal":
        q = "Select your goal:"
        set_context(global_user_id, "goal", q)

        if is_whatsapp(channel_id):
            send_whatsapp_interactive(
                channel_id,
                "Select your goal:",
                buttons=["fat_loss", "muscle_gain", "fitness"]
            )
        else:
            send_buttons(channel_id, q, [
                {"text": "Fat Loss", "value": "fat_loss"},
                {"text": "Muscle Gain", "value": "muscle_gain"},
                {"text": "Fitness", "value": "fitness"},
            ], action_prefix="goal")

    elif field == "activity":
        q = "Select your activity level:"
        set_context(global_user_id, "activity", q)

        if is_whatsapp(channel_id):
            send_whatsapp_interactive(
                channel_id,
                "Select activity level:",
                list_options=["sedentary", "light", "moderate", "active"]
            )
        else:
            send_buttons(channel_id, q, [
                {"text": "Sedentary", "value": "sedentary"},
                {"text": "Light", "value": "light"},
                {"text": "Moderate", "value": "moderate"},
                {"text": "Active", "value": "active"},
            ], action_prefix="activity")

    elif field == "diet_type":
        q = "Select your diet type:"
        set_context(global_user_id, "diet_type", q)

        if is_whatsapp(channel_id):
            send_whatsapp_interactive(
                channel_id,
                "Select your diet:",
                list_options=["vegetarian", "non_veg", "mixed", "vegan", "eggetarian"]
            )
        else:
            send_buttons(channel_id, q, [
                {"text": "Vegetarian", "value": "vegetarian"},
                {"text": "Non Veg", "value": "non_veg"},
                {"text": "Mixed", "value": "mixed"},
                {"text": "Vegan", "value": "vegan"},
                {"text": "Eggetarian", "value": "eggetarian"},
            ], action_prefix="diet")


# -------------------- PLAN GENERATOR --------------------
def stream_plan_paragraph(profile, channel, global_user_id):

    from engines.calorie_engine import calculate_calories
    from engines.diet_engine import generate_diet
    from engines.workout_engine import generate_workout
    from engines.clinical_engine import generate_clinical_plan

    # ---------------- REQUIRED FIELD FIX ----------------
    if "gender" not in profile or not profile["gender"]:
        profile["gender"] = "male"  # fallback (or ask user later)

    # ---------------- CALCULATIONS ----------------
    cal = calculate_calories(profile)

    # ---------------- DIET ----------------
    diet = generate_diet(profile, cal["target_calories"])

    # ---------------- WORKOUT ----------------
    workout = generate_workout(profile)

    # ---------------- CLINICAL ----------------
    clinical = generate_clinical_plan(profile)

    # ---------------- RESPONSE ----------------
    text = f"""
🔥 YOUR PERSONALIZED FITNESS PLAN

📊 BMR: {cal['bmr']} kcal
🔥 Maintenance Calories: {cal['tdee']} kcal
🎯 Target Calories: {cal['target_calories']} kcal/day

🥗 DIET PLAN
{diet['breakfast']}
{diet['lunch']}
{diet['snacks']}
{diet['dinner']}

🏋️ WORKOUT PLAN
"""

    for day, ex in workout.items():
        text += f"\n{day}: {', '.join(ex)}"

    text += "\n\n💡 CLINICAL ADVICE\n"
    for tip in clinical:
        text += f"- {tip}\n"

    send_slack_message(channel, text)

    save_artifact(global_user_id, "plan", text)
    save_vector_memory(global_user_id, text, "plan")
    set_plan_generated(global_user_id, True)


def stream_chat_paragraph(prompt, channel):
    """
    Streams normal conversational AI reply (NOT a fitness plan).
    """

    r = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": "qwen2.5:7b", "prompt": prompt, "stream": True},
        stream=True,
        timeout=120
    )

    full_text = ""

    for line in r.iter_lines():
        if not line:
            continue

        data = json.loads(line.decode())
        token = data.get("response", "")
        full_text += token

        if data.get("done"):
            break

    # ✅ FINAL SEND (WhatsApp via override)
    send_slack_message(channel, full_text)

    return full_text


def detect_intent_llm(user_text):
    """
    Uses Ollama to classify user intent.
    Returns one of:
    greeting | plan | chat | answer_profile | update_profile
    """

    prompt = f"""
Classify the user message into ONE label only:

Labels:
- greeting → saying hi/hello
- plan → asking to create/generate diet or workout plan
- answer_profile → answering height/weight/age/activity/diet questions
- update_profile → changing existing profile info
- chat → general conversation or explanation

Reply with ONLY the label word.

User message:
{user_text}
"""

    try:
        r = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "qwen2.5:7b", "prompt": prompt, "stream": False},
            timeout=20
        )

        label = r.json().get("response", "").strip().lower()

        valid = {"greeting", "plan", "chat", "answer_profile", "update_profile"}
        return label if label in valid else "chat"

    except Exception as e:
        print("Intent detection error:", e)
        return "chat"
    
def llm_router(user_text, context, history):
    """
    Conversational intent router with memory awareness.
    """

    prompt = f"""
You are the decision brain of an AI fitness coach.

Conversation so far:
{history}

Latest user message:
{user_text}

Current state:
- In profile questionnaire: {context.get("last_question_type") is not None}

Choose ONE action:

chat → normal talk or explanation
start_plan → create new plan from scratch
continue_plan → answering profile questions
update_profile → changing height/weight/age/etc
modify_plan → user wants to adjust existing fitness plan



Reply with ONLY the action word.
"""

    try:
        r = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "qwen2.5:7b", "prompt": prompt, "stream": False},
            timeout=20,
        )

        action = r.json().get("response", "").strip().lower()
        valid = {"chat", "start_plan", "continue_plan", "update_profile", "modify_plan"}


        return action if action in valid else "chat"

    except Exception:
        return "chat"


def general_chat_with_ollama(user_text, channel, global_user_id):
    history = get_chat_history(global_user_id)
    artifacts = get_recent_artifacts(global_user_id)
    rag_context = build_rag_context(global_user_id, user_text)
    


    prompt = f"""
    You are a friendly AI fitness assistant like ChatGPT.

    Conversation so far:
    {history}

    Relevant stored context:
    {rag_context}

    

    User: {user_text}

    Reply naturally and context-aware.
    Use ONLY English language.
    Never switch to any other language.
    Do NOT ask for height/weight unless user asks to create a plan.
    """
    reply = stream_chat_paragraph(prompt, channel)
    save_artifact(global_user_id, "chat", reply)
    save_vector_memory(global_user_id, reply, "chat")
    append_chat_history(global_user_id, "assistant", reply)

def modify_existing_plan(user_text, channel, global_user_id):
    """
    Section-aware intelligent plan modification
    with human-like coaching intro.
    """

    section = detect_plan_section(user_text)
    rag_context = build_rag_context(global_user_id)

    # -------- Human coaching intro --------
    if section == "workout":
        intro = "Got it — let’s modify your workout to keep you safe and progressing.\n\n"
        instruction = "Return ONLY the updated WORKOUT PLAN section."

    elif section == "diet":
        intro = "Great — let’s adjust your diet to better match your goal and lifestyle.\n\n"
        instruction = "Return ONLY the updated DIET / CALORIE section."

    else:
        intro = "Perfect — I’ll rebuild your full fitness plan based on your new request.\n\n"
        instruction = "Return the FULL updated plan."

    # -------- LLM prompt --------
    prompt = f"""
You are a professional AI fitness coach.

IMPORTANT RULES:
- Modify the EXISTING plan only.
- Do NOT regenerate unrelated sections.
- {instruction}
- Reply in clear, simple English.

Existing plan:
{rag_context}

User request:
{user_text}
"""

    # -------- Get LLM reply --------
    reply = stream_chat_paragraph(prompt, channel)

    # -------- Send intro + reply together --------
    send_slack_message(channel, intro + reply)

    # -------- Save memory --------
    save_artifact(global_user_id, "plan_update", reply)
    append_chat_history(global_user_id, "assistant", reply)


# -------------------- ROUTES --------------------
@app.get("/")
async def home():
    return "Slack chatbot running "


@app.post("/slack/interactive")
async def slack_interactive(request: Request):
    form = await request.form()
    payload = form.get("payload")
    if not payload:
        return "No payload", 400

    data = json.loads(payload)
    slack_user_id = data.get("user", {}).get("id")
    channel_id = data.get("channel", {}).get("id")
    global_user_id = get_global_user_id("slack", slack_user_id)

    actions = data.get("actions", [])
    if not actions:
        return "OK", 200

    action = actions[0]
    action_id = action.get("action_id")
    value = action.get("value")

    # ---- VERIFY BUTTONS ----
    if action_id.startswith("verify_"):

        if value == "confirm":
            profile = get_profile(global_user_id)
            stream_plan_paragraph(profile, channel_id, global_user_id)
            set_plan_generated(global_user_id, True)
            clear_context(global_user_id)
            return "", 200

        elif value == "edit":
            send_buttons(
                channel_id,
                "Which field would you like to correct?",
                [
                    {"text": "Height", "value": "height"},
                    {"text": "Weight", "value": "weight"},
                    {"text": "Age", "value": "age"},
                    {"text": "Goal", "value": "goal"},
                    {"text": "Activity", "value": "activity"},
                    {"text": "Diet Type", "value": "diet_type"},
                ],
                action_prefix="edit"
            )
            set_context(global_user_id, "edit_field", "editing")
            return "", 200
        
    # ---- EDIT FIELD BUTTON ----
    if action_id.startswith("edit_"):
        field = value

        if field == "height":
            q = "Enter correct height (e.g., 180 cm or 6 ft)."
        elif field == "weight":
            q = "Enter correct weight (e.g., 75 kg)."
        elif field == "age":
            q = "Enter correct age."
        elif field == "goal":
            ask_next_question({"goal": None}, global_user_id, channel_id)
            return "", 200
        elif field == "activity":
            ask_next_question({"activity_level": None}, global_user_id, channel_id)
            return "", 200
        elif field == "diet_type":
            ask_next_question({"diet_type": None}, global_user_id, channel_id)
            return "", 200
        else:
            return "", 200

        set_context(global_user_id, field, q)
        send_slack_message(channel_id, q)
        return "", 200



    #  Goal buttons
    if action_id.startswith("goal_"):
        update_profile(global_user_id, goal=value)

    #  Activity buttons
    elif action_id.startswith("activity_"):
        update_profile(global_user_id, activity_level=value)

    #  Diet buttons
    elif action_id.startswith("diet_"):
        update_profile(global_user_id, diet_type=value)

    profile = get_profile(global_user_id)
    ask_next_question(profile, global_user_id, channel_id)
    return "", 200


@app.post("/slack/events")
async def slack_events(request: Request):
    if request.headers.get("X-Slack-Retry-Num"):
        return "OK", 200

    data = await request.json()

    if data and data.get("type") == "url_verification":
        return data.get("challenge"), 200

    if data and data.get("type") == "event_callback":
        event_id = data.get("event_id")
        event = data.get("event", {})

        if event_id and is_event_processed(event_id):
            return "OK", 200
        if event_id:
            mark_event_processed(event_id)

        if event.get("type") != "message" or "subtype" in event or "bot_id" in event:
            return "OK", 200

        user_text = event.get("text", "").strip()
        
        channel_id = event.get("channel")
        slack_user_id = event.get("user")

        

        global_user_id = get_global_user_id("slack", slack_user_id)
        append_chat_history(global_user_id, "user", user_text)
        save_vector_memory(global_user_id, user_text, "user")

        if DM_ONLY_MODE and channel_id.startswith("C"):
            if is_greeting(user_text):
                send_slack_message(channel_id, "Hey  I’m your Fitness & Diet Assistant.\n Please DM me to generate your personal plan.")
            else:
                send_slack_message(channel_id, " Please DM me to generate your personal plan ")
            return "OK", 200

        profile = get_profile(global_user_id)
        db_profile = get_profile(global_user_id)

        # merge DB into memory
        for key in db_profile:
            if profile.get(key) is None:
                profile[key] = db_profile[key]
        
        context = get_context(global_user_id)

        #  Greeting fix: new user vs continue user
        if is_greeting(user_text):
            send_slack_message(
                channel_id,
                "Hey! I’m your AI Fitness & Diet Coach.\n\n"
                "You can ask me anything about:\n"
                "• fat loss\n"
                "• muscle gain\n"
                "• diet planning\n"
                "• workouts\n\n"
                "Any Queries about Fitness and Diet",
            )
            return "OK", 200
        

        # -------- TRUE LLM ROUTING --------
        history = get_chat_history(global_user_id)
        action = llm_router(user_text, context, history)
        
        plan_exists = is_plan_generated(global_user_id)

        if plan_exists and action == "start_plan":
            action = "modify_plan"

        if plan_exists and action == "continue_plan":
            action = "chat"

        # --- If plan already generated, prevent questionnaire loop ---
        if is_plan_generated(global_user_id) and action == "continue_plan":
            action = "chat"

        # ---- MODIFY EXISTING PLAN ----
        if action == "modify_plan":
            modify_existing_plan(user_text, channel_id, global_user_id)
            return "OK", 200


        # ---- CHAT ----
        if action == "chat":
            general_chat_with_ollama(user_text, channel_id, global_user_id)
            return "OK", 200

        # ---- START PLAN ----
        if action == "start_plan":
            miss = missing_fields(profile)

            if miss:
                send_slack_message(channel_id, "Great — let’s build your personalized plan.")
                ask_next_question(profile, global_user_id, channel_id)
                return "OK", 200

            stream_plan_paragraph(profile, channel_id, global_user_id)
            set_plan_generated(global_user_id, True)
            clear_context(global_user_id)
            return "OK", 200

        # ---- CONTINUE PLAN ----
        if action == "continue_plan":
            pass  # existing questionnaire logic below will handle



        # -------- unit clarification first --------
        pending_field = context.get("pending_field")
        pending_value = context.get("pending_value")

        if pending_field and pending_value and is_unit_reply(user_text):
            unit = user_text.strip().lower()
            val = float(pending_value)

            if pending_field == "weight":
                if unit in ["kg", "kgs"]:
                    w = val
                elif unit in ["lb", "lbs"]:
                    w = val * 0.453592
                elif unit == "g":
                    w = val / 1000
                else:
                    w = None

                if w and validate_weight_kg(w):
                    update_profile(global_user_id, weight_kg=w)
                    set_context(
                        global_user_id,
                        "weight",
                        context.get("last_question_text"),
                        pending_field=None,
                        pending_value=None
                    )
                    profile = get_profile(global_user_id)
                    ask_next_question(profile, global_user_id, channel_id)
                    return "OK", 200

            if pending_field == "height":
                if unit == "cm":
                    h = val
                elif unit == "m":
                    h = val * 100
                elif unit in ["ft", "feet"]:
                    h = val * 30.48
                else:
                    h = None

                if h and validate_height_cm(h):
                    update_profile(global_user_id, height_cm=h)
                    set_context(
                        global_user_id,
                        "height",
                        context.get("last_question_text"),
                        pending_field=None,
                        pending_value=None
                    )
                    profile = get_profile(global_user_id)
                    ask_next_question(profile, global_user_id, channel_id)
                    return "OK", 200

        # -------- typed answer handling --------
        updates = {}
        last_q_type = context.get("last_question_type")

        if last_q_type == "height":
            h = parse_height_cm(user_text)
            if h and validate_height_cm(h):
                updates["height_cm"] = h
            elif is_plain_number(user_text):
                msg = f"You entered {user_text} \nIs that in ft or cm?"
                set_context(global_user_id, "height", msg, pending_field="height", pending_value=user_text)
                send_slack_message(channel_id, msg)
                return "OK", 200

        elif last_q_type == "weight":
            w = parse_weight_kg(user_text)
            if w and validate_weight_kg(w):
                updates["weight_kg"] = w
            elif is_plain_number(user_text):
                msg = f"You entered {user_text} \nIs that in kg or lbs?"
                set_context(global_user_id, "weight", msg, pending_field="weight", pending_value=user_text)
                send_slack_message(channel_id, msg)
                return "OK", 200

        elif last_q_type == "age":
            a = parse_age(user_text)
            if a and validate_age(a):
                updates["age"] = a

        elif last_q_type == "gender":
            g = user_text.strip().lower()
            if g in ["male", "female"]:
                updates["gender"] = g

        if updates:
            update_profile(global_user_id, **updates)
            mem_profile = get_user_profile(global_user_id)
            mem_profile.update(updates)
            profile = get_profile(global_user_id)

        ask_next_question(profile, global_user_id, channel_id)
        return "OK", 200

    return "OK", 200


init_db()

