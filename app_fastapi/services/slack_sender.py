import os
import requests

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")


def send_slack_message(channel: str, text: str):
    url = "https://slack.com/api/chat.postMessage"

    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "channel": channel,
        "text": text
    }

    response = requests.post(url, headers=headers, json=payload)

    return response.json()