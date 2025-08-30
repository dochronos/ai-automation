from __future__ import annotations
import csv
import random
from datetime import datetime, timedelta
from argparse import ArgumentParser
from pathlib import Path

CHANNELS = ["web", "email", "whatsapp", "app", "phone"]
SUBJECTS = {
    "login": ["Login issue", "Can't sign in", "Password reset doesn't work"],
    "billing": ["Billing question", "Charged twice", "Refund request"],
    "mobile": ["Mobile app bug", "App crashes on payment", "Android login freeze"],
    "security": ["Security alert", "Suspicious access", "Account breach suspected"],
    "info": ["Product information", "Pricing plan", "Annual discount?"],
}

DESCRIPTIONS = {
    "login": [
        "I can't log in with my email; says invalid credentials.",
        "Password reset link expired; still can't access my account.",
    ],
    "billing": [
        "I was overcharged this month, need a credit note.",
        "Invoice total seems wrong compared to my plan.",
    ],
    "mobile": [
        "The app crashes when I try to pay.",
        "Android app freezes on the login screen.",
    ],
    "security": [
        "I noticed an unfamiliar login from another country.",
        "Got an alert about a suspicious access to my account.",
    ],
    "info": [
        "Do you offer an annual plan with a discount?",
        "Can you share pricing for the team plan?",
    ],
}

TOPICS = list(SUBJECTS.keys())

def _random_date(days_back: int = 21) -> str:
    base = datetime.now() - timedelta(days=random.randint(0, days_back))
    return base.strftime("%Y-%m-%d")

def generate_rows(n: int) -> list[dict]:
    rows = []
    for i in range(1, n + 1):
        topic = random.choices(
            TOPICS,
            weights=[28, 22, 20, 15, 15],  # bias toward login/billing/mobile
            k=1,
        )[0]
        subject = random.choice(SUBJECTS[topic])
        description = random.choice(DESCRIPTIONS[topic])
        # small chance to add a tone token
        tone = random.choice(["", " thanks!", " please help", " urgent", " asap"]) if random.random() < 0.4 else ""
        rows.append(
            {
                "id": i,
                "created_at": _random_date(),
                "channel": random.choice(CHANNELS),
                "subject": subject,
                "description": description + tone,
            }
        )
    return rows

def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["id", "created_at", "channel", "subject", "description"],
        )
        writer.writeheader()
        writer.writerows(rows)

def main() -> None:
    ap = ArgumentParser()
    ap.add_argument("--rows", type=int, default=120)
    ap.add_argument("--out", type=str, default="data/sample_tickets.csv")
    args = ap.parse_args()

    rows = generate_rows(args.rows)
    write_csv(rows, Path(args.out))
    print(f"Wrote {len(rows)} rows to {args.out}")

if __name__ == "__main__":
    main()
