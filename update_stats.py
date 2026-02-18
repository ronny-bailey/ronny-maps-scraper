#!/usr/bin/env python3
"""Update stats.json with live CRM data for GitHub README badges."""
import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.expanduser("~/leads/ronny_crm.db")
STATS_PATH = os.path.join(os.path.dirname(__file__), "stats.json")

def update():
    conn = sqlite3.connect(DB_PATH)
    leads = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    emails_sent = conn.execute("SELECT COUNT(*) FROM emails WHERE status='sent'").fetchone()[0]
    replies = conn.execute("SELECT COUNT(*) FROM emails WHERE status IN ('replied','interested','meeting')").fetchone()[0]
    reply_rate = round((replies / emails_sent * 100), 1) if emails_sent > 0 else 0
    today = conn.execute("SELECT COUNT(*) FROM emails WHERE status='sent' AND date(sent_at)=date('now')").fetchone()[0]
    conn.close()

    stats = {
        "schemaVersion": 1,
        "leads": leads,
        "emails_sent": emails_sent,
        "reply_rate": f"{reply_rate}%",
        "sent_today": today,
        "last_updated": datetime.now().strftime("%Y-%m-%d")
    }

    with open(STATS_PATH, "w") as f:
        json.dump(stats, f, indent=2)
    print(f"Updated stats.json: {leads} leads, {emails_sent} sent, {reply_rate}% reply rate")

if __name__ == "__main__":
    update()
