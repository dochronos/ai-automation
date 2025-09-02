# scripts/add_test_p1.py  (compatible con CSV de 5 columnas)
import csv, uuid, os, datetime as dt

INPUT = os.getenv("LOCAL_INPUT_CSV", "data/sample_tickets.csv")

# Fila “tipo P1” con SOLO las 5 columnas del input
row = {
    "id": str(uuid.uuid4()),
    "created_at": dt.datetime.now().isoformat(timespec="seconds"),
    "channel": "web",
    "subject": "URGENT: production login outage",
    "description": "Users cannot log in. 500 errors on auth callback. Impacting payments."
}

# Confirmamos encabezado actual y escribimos exactamente esas columnas
with open(INPUT, "r", encoding="utf-8") as f:
    reader = csv.reader(f)
    header = next(reader)

with open(INPUT, "a", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=header)
    # no reescribimos header; el archivo ya lo tiene
    writer.writerow({k: row.get(k, "") for k in header})

print(f"Appended P1-like test row to {INPUT}: {row['id']}")
