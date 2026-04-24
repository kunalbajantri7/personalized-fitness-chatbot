import requests

ACCESS_TOKEN = "EAALEejxob64BRS9yHxumT3dgwzWUs5KFzS94zE8Sx6xV3qLZAv1t1LUTbO2caBjAe5CTZC3OUpd4YS8mpoSZAt1ZCZBdG0hpHwMolWnDt1JE822C78FkScImaY9x37h7iZCyY2CayqlesjVtjJd8UaIZBFGAfyJQlFAFZBKppoFW37mdp38JavA6mgZAYHjXBz6eurX3WP5vw5IqO3Q6nczNh9IrxwShd4lzG2d8AqVBSqTxpNoGhyRJe5CjQX8plsG20YDRZAPzLMWZAIrRkvgQzxR9m9s"
PHONE_NUMBER_ID = "941939392346477"

def send_whatsapp_interactive(to, text, buttons=None, list_options=None):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    if buttons:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": text},
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {"id": b, "title": b.replace("_", " ").title()}
                        } for b in buttons
                    ]
                }
            }
        }

    elif list_options:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {"text": text},
                "action": {
                    "button": "Select",
                    "sections": [
                        {
                            "title": "Options",
                            "rows": [
                                {
                                    "id": opt,
                                    "title": opt.replace("_", " ").title()
                                } for opt in list_options
                            ]
                        }
                    ]
                }
            }
        }

    else:
        return

    requests.post(url, headers=headers, json=payload)