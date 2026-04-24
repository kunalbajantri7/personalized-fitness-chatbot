from fastapi import APIRouter, Request
from backend.app import (
    slack_events,
    is_event_processed,
    mark_event_processed,
    set_context,
    get_context,
    ask_next_question,
    send_whatsapp_message,
    stream_plan_paragraph
)
from app_fastapi.services.domain_guard import classify_domain, get_rejection_message
from engines.final_diet_engine import generate_diet
from app_fastapi.core.user_manager import get_user_profile
from engines.calorie_engine import calculate_calories

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])

VERIFY_TOKEN = "my_verify_token"


# ---------------- VERIFY (GET) ----------------
@router.get("/webhook")
async def verify_webhook(request: Request):
    params = dict(request.query_params)

    if params.get("hub.verify_token") == VERIFY_TOKEN:
        return int(params.get("hub.challenge"))

    return {"status": "verification_failed"}


# ---------------- RECEIVE (POST) ----------------
import requests

ACCESS_TOKEN = "EAALEejxob64BRSrQnvT5RHw91ZA00WA0YFnI6R2OKauQI9Mi71I2ZAqupNaFrfBxdiz9b7Gcv6ySAmx6lfZCygnx81HDnuddIdZBvcPRvQl5GiY12bNZA49eIHPagwqJONJVcR5B5dx3kHWRvJ97YzkDsvGRZCgwQwqNyqTOfDDNDL9do7ziiEfzx0UoDuHZBLZCONE1BZAZBZC6NCHfTPZBNvMipoSsmHxWtZBxlre2ZBhcTnmZBZCYkixT0vP0QHSxC0Sqfld9yhRwnEYvDsD6NX1LZCcboDObrIAZDZD"
PHONE_NUMBER_ID = "941939392346477"


from backend.app import (
    get_global_user_id,
    get_profile,
    get_context,
    is_greeting,
    append_chat_history,
    save_vector_memory,
    llm_router,
    is_plan_generated,
    modify_existing_plan,
    general_chat_with_ollama,
    missing_fields,
    ask_next_question,
    stream_plan_paragraph,
    clear_context,
    set_plan_generated,
    get_chat_history
)

from backend.app import (
    parse_height_cm,
    parse_weight_kg,
    parse_age,
    validate_height_cm,
    validate_weight_kg,
    validate_age,
    is_plain_number,
    is_unit_reply,
    update_profile
)

@router.post("/webhook")
async def receive_message(request: Request):
    data = await request.json()


    try:
        value = data["entry"][0]["changes"][0]["value"]

    # FIRST: ignore non-message events
        if "messages" not in value:
            return {"status": "ignored"}

        msg = value["messages"][0]

    #  SECOND: ignore non-text messages
        if "text" not in msg:
            return {"status": "ignored"}
        
        user_text = msg["text"]["body"]
        sender = msg["from"]

# ---------------- GUARDRAIL (TOP PRIORITY) ----------------
        context = get_context(get_global_user_id("whatsapp", sender))

        # ✅ allow if inside questionnaire
        if context.get("last_question_type"):
            pass
        elif not is_greeting(user_text):
            domain = classify_domain(user_text)

            if domain == "non_fitness":
                send_whatsapp_message(sender, get_rejection_message())
                return {"status": "guardrail_blocked"}

    #  THIRD: dedup (NOW msg exists safely)
        message_id = msg.get("id")

        if not message_id:
            return {"status": "no_id"}

        if is_event_processed(message_id):
            print("⚠️ Duplicate skipped:", message_id)
            return {"status": "duplicate"}

        mark_event_processed(message_id)

        print("📩 WhatsApp:", user_text)

        #  SAME AS SLACK
        global_user_id = get_global_user_id("whatsapp", sender)

        print("📱 USER:", sender)
        print("🌍 GLOBAL USER ID:", global_user_id)

        append_chat_history(global_user_id, "user", user_text)
        save_vector_memory(global_user_id, user_text, "user")

        profile = get_profile(global_user_id)
        context = get_context(global_user_id)

        # ---------------- EDIT FLOW FIX ----------------
        if context.get("last_question_type") == "edit_field":
    
            field = user_text.lower().strip()

            if field == "height":
                q = "Enter correct height (e.g., 180 cm or 6 ft)."
                set_context(global_user_id, "height", q)
                send_whatsapp_message(sender, q)
                return {"status": "ok"}

            elif field == "weight":
                q = "Enter correct weight (e.g., 75 kg)."
                set_context(global_user_id, "weight", q)
                send_whatsapp_message(sender, q)
                return {"status": "ok"}

            elif field == "age":
                q = "Enter correct age."
                set_context(global_user_id, "age", q)
                send_whatsapp_message(sender, q)
                return {"status": "ok"}

            elif field == "goal":
                ask_next_question({"goal": None}, global_user_id, sender)
                return {"status": "ok"}

            elif field == "activity":
                ask_next_question({"activity_level": None}, global_user_id, sender)
                return {"status": "ok"}

            elif field == "diet":
                ask_next_question({"diet_type": None}, global_user_id, sender)
                return {"status": "ok"}

            else:
                send_whatsapp_message(sender, "Invalid field. Choose: height / weight / age / goal / activity / diet")
                return {"status": "ok"}

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
                    profile = get_profile(global_user_id)
                    ask_next_question(profile, global_user_id, sender)
                    return {"status": "ok"}

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
                    profile = get_profile(global_user_id)
                    ask_next_question(profile, global_user_id, sender)
                    return {"status": "ok"}
                
        # -------- typed answer handling --------
        updates = {}
        last_q_type = context.get("last_question_type")

        if last_q_type == "height":
            h = parse_height_cm(user_text)
            if h and validate_height_cm(h):
                updates["height_cm"] = h
            elif is_plain_number(user_text):
                msg = f"You entered {user_text}. Is that in ft or cm?"
                send_whatsapp_message(sender, msg)
                return {"status": "ok"}

        elif last_q_type == "weight":
            w = parse_weight_kg(user_text)
            if w and validate_weight_kg(w):
                updates["weight_kg"] = w
            elif is_plain_number(user_text):
                msg = f"You entered {user_text}. Is that in kg or lbs?"
                send_whatsapp_message(sender, msg)
                return {"status": "ok"}

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
            profile = get_profile(global_user_id)
            ask_next_question(profile, global_user_id, sender)
            return {"status": "ok"}
        
        # ---- manual button handling (WhatsApp) ----
        text = user_text.lower().strip()

        if text in ["fat loss", "muscle gain", "fitness"]:
            update_profile(global_user_id, goal=text.replace(" ", "_"))
            profile = get_profile(global_user_id)
            ask_next_question(profile, global_user_id, sender)
            return {"status": "ok"}

        if text in ["sedentary", "light", "moderate", "active"]:
            update_profile(global_user_id, activity_level=text)
            profile = get_profile(global_user_id)
            ask_next_question(profile, global_user_id, sender)
            return {"status": "ok"}

        if text in ["vegetarian", "non veg", "non-veg", "mixed", "vegan", "eggetarian"]:
            val = text.replace(" ", "_").replace("-", "_")
            update_profile(global_user_id, diet_type=val)
            profile = get_profile(global_user_id)
            ask_next_question(profile, global_user_id, sender)
            return {"status": "ok"}
        
        import asyncio

        if text == "confirm":
            profile = get_profile(global_user_id)

            print("🧠 PROFILE DEBUG:", profile)

            # Step 1: Show thinking message
            send_whatsapp_message(sender, "Generating your personalized fitness plan...")

            # Step 2: Add delay (simulate thinking)
            await asyncio.sleep(2)

            if not profile:
                send_whatsapp_message(sender, "❌ Error: Profile not found")
                return {"status": "error"}

            try:
                stream_plan_paragraph(profile, sender, global_user_id)
            except Exception as e:
                print("❌ Plan Error:", str(e))
                send_whatsapp_message(sender, "❌ Error generating plan")

            set_plan_generated(global_user_id, True)
            clear_context(global_user_id)

            return {"status": "ok"}

        if text == "edit":
            set_context(global_user_id, "edit_field", "editing")
            send_whatsapp_message(sender, "Type which field: height / weight / age / goal / activity / diet")
            return {"status": "ok"}

        # ---- GREETING ----
        if is_greeting(user_text):
            send_whatsapp_message(
                sender,
                "Hey! I’m your AI Fitness & Diet Coach.\n\n"
                "You can ask me anything about:\n"
                "• fat loss\n"
                "• muscle gain\n"
                "• diet planning\n"
                "• workouts\n\n"
                "Any Queries about Fitness and Diet"
            )
            return {"status": "ok"}
        

        # ---- ROUTER ----
        history = get_chat_history(global_user_id)
        action = llm_router(user_text, context, history)

        plan_exists = is_plan_generated(global_user_id)

        if plan_exists and action == "continue_plan":
            action = "chat"

        if plan_exists and action == "start_plan":
            action = "modify_plan"


        # ---- MODIFY PLAN ----
        if action == "modify_plan":
            modify_existing_plan(user_text, sender, global_user_id)
            return {"status": "ok"}

        # ---- CHAT ----
        if action == "chat":
            general_chat_with_ollama(user_text, sender, global_user_id)
            return {"status": "ok"}

        # ---- START PLAN ----
        if action == "start_plan":
            # 🚨 HARD GUARDRAIL (CRITICAL)
            if classify_domain(user_text) == "non_fitness":
                send_whatsapp_message(sender, get_rejection_message())
                return {"status": "guardrail_blocked"}
            miss = missing_fields(profile)

            if miss:
                send_whatsapp_message(sender, "Let’s build your plan 💪")
                ask_next_question(profile, global_user_id, sender)
                return {"status": "ok"}

            stream_plan_paragraph(profile, sender, global_user_id)
            set_plan_generated(global_user_id, True)
            clear_context(global_user_id)
            return {"status": "ok"}

        # ---- CONTINUE PLAN ----
        if action == "continue_plan":
            ask_next_question(profile, global_user_id, sender)
            return {"status": "ok"}

    except Exception as e:
        print("❌ WhatsApp Error:", e)
        print("RAW:", data)

    return {"status": "received"}

    


def send_whatsapp_message(to, text):
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



