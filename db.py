import sqlite3
from datetime import date, timedelta

DB = "crm.db"


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init():
    c = conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS deals(
        id INTEGER PRIMARY KEY, company TEXT, contact TEXT,
        stage TEXT, value INTEGER, last_activity TEXT);
    CREATE TABLE IF NOT EXISTS activities(
        id INTEGER PRIMARY KEY, deal_id INTEGER, note TEXT, on_date TEXT);
    """)
    if c.execute("SELECT COUNT(*) FROM deals").fetchone()[0] == 0:
        t = date.today()
        rows = [
            ("Acme Logistics", "Priya Nair", "Proposal", 1200000, t - timedelta(days=12)),
            ("BrightEd", "Arjun Rao", "Negotiation", 800000, t - timedelta(days=2)),
            ("Nova Retail", "Meera Shah", "Demo", 450000, t - timedelta(days=9)),
            ("Zenith Foods", "Kabir Sen", "Qualified", 300000, t - timedelta(days=1)),
            ("Orbit Health", "Sana Iqbal", "Proposal", 950000, t - timedelta(days=15)),
            ("Lumen Studio", "Dev Patel", "Demo", 200000, t - timedelta(days=4)),
        ]
        c.executemany(
            "INSERT INTO deals(company,contact,stage,value,last_activity) VALUES(?,?,?,?,?)",
            [(a, b, s, v, d.isoformat()) for a, b, s, v, d in rows],
        )
        c.commit()
    c.close()


if __name__ == "__main__":
    init()
    c = conn()
    n = c.execute("SELECT COUNT(*) FROM deals").fetchone()[0]
    c.close()
    print(f"Database ready with {n} deals")