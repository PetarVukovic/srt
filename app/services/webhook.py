# app/services/webhook.py
import requests
from app.core.config import Settings

class WebhookService:
    def __init__(self, settings:Settings):
        self.url = settings.n8n_webhook_url

    def send(self, payload: dict):
        r = requests.post(self.url, json=payload, timeout=30)
        r.raise_for_status()
        return r.status_code