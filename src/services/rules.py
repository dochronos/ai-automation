from __future__ import annotations
from typing import Literal, Dict

Priority = Literal["P1","P2","P3"]


# English-first keywords, with Spanish fallbacks for robustness
TOPIC_KEYWORDS: Dict[str, list[str]] = {
"login": [
"login", "sign in", "password", "credentials", "cannot log in", "can't log in",
"contraseña", "credenciales", "entrar"
],
"billing": [
"billing", "charge", "charged", "invoice", "credit note", "refund",
"facturación", "cobro", "nota de crédito", "reembolso"
],
"mobile": ["app", "mobile", "android", "ios", "móvil"],
"security": [
"security", "suspicious", "unauthorized", "breach", "fraud",
"seguridad", "acceso raro", "fraude"
],
"info": [
"info", "information", "plan", "price", "pricing", "discount",
"información", "precio", "descuento"
],
}


OWNER_SUGGESTIONS = {
"login": "L1 Support",
"billing": "Finance Ops",
"mobile": "Mobile Squad",
"security": "SecOps",
"info": "Sales",
}


def simple_topic(text: str) -> str:
    t = text.lower()
    for topic, kws in TOPIC_KEYWORDS.items():
        if any(k in t for k in kws):
            return topic
    return "other"




def simple_priority(text: str) -> Priority:
    t = text.lower()
    neg_blockers = ["cannot", "can't", "no puedo", "unauthorized", "breach", "fraud", "acceso raro"]
    if any(k in t for k in TOPIC_KEYWORDS["security"]) or any(k in t for k in neg_blockers):
     return "P1"
    if any(k in t for k in TOPIC_KEYWORDS["billing"]) or any(k in t for k in TOPIC_KEYWORDS["mobile"]):
     return "P2"
    return "P3"




def simple_sentiment(text: str) -> str:
    t = text.lower()
    neg = ["cannot", "can't", "error", "crash", "crashes", "overcharged", "fraud", "no puedo", "se cierra", "cobraron de más"]
    pos = ["thanks", "thank you", "excellent", "great", "fast", "gracias", "excelente", "rápido"]
    if any(k in t for k in neg):
        return "neg"
    if any(k in t for k in pos):
        return "pos"
    return "neu"




def owner_for_topic(topic: str) -> str:
    return OWNER_SUGGESTIONS.get(topic, "L1 Support")