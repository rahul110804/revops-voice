import json
import sqlite3
from datetime import date, timedelta

DB = "crm.db"
MAX_ROWS = 5000

INSERT_SQL = (
    "INSERT INTO deals(company,contact,stage,value,last_activity,extra,source) "
    "VALUES(?,?,?,?,?,?,?)"
)


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def _seed_sample(c):
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
        INSERT_SQL,
        [(a, b, s, v, d.isoformat(), "{}", "sample") for a, b, s, v, d in rows],
    )


def init():
    c = conn()
    c.executescript(
        """
    CREATE TABLE IF NOT EXISTS deals(
        id INTEGER PRIMARY KEY, company TEXT, contact TEXT,
        stage TEXT, value INTEGER, last_activity TEXT);
    CREATE TABLE IF NOT EXISTS activities(
        id INTEGER PRIMARY KEY, deal_id INTEGER, note TEXT, on_date TEXT);
    CREATE TABLE IF NOT EXISTS imports(
        id INTEGER PRIMARY KEY, filename TEXT, mode TEXT, imported_at TEXT,
        rows_added INTEGER, rows_skipped INTEGER);
    """
    )
    cols = [r["name"] for r in c.execute("PRAGMA table_info(deals)").fetchall()]
    if "extra" not in cols:
        c.execute("ALTER TABLE deals ADD COLUMN extra TEXT DEFAULT '{}'")
    if "source" not in cols:
        c.execute("ALTER TABLE deals ADD COLUMN source TEXT DEFAULT 'sample'")
    if c.execute("SELECT COUNT(*) FROM deals").fetchone()[0] == 0:
        _seed_sample(c)
    c.commit()
    c.close()


def _clean_row(raw):
    company = str(raw.get("company") or "").strip()
    if not company:
        return None, "missing company"
    stage = str(raw.get("stage") or "").strip() or "Unknown"
    contact = str(raw.get("contact") or "").strip()
    try:
        value = int(round(float(raw.get("value") or 0)))
    except (TypeError, ValueError):
        return None, f"bad value for {company}"
    if value < 0:
        return None, f"negative value for {company}"
    last = str(raw.get("last_activity") or "").strip()
    try:
        last = date.fromisoformat(last[:10]).isoformat()
    except ValueError:
        last = date.today().isoformat()
    extra = raw.get("extra") if isinstance(raw.get("extra"), dict) else {}
    return {
        "company": company,
        "contact": contact,
        "stage": stage,
        "value": value,
        "last_activity": last,
        "extra": extra,
    }, None


def import_rows(rows, mode="replace", filename="upload.csv"):
    if mode not in ("replace", "append"):
        raise ValueError("mode must be 'replace' or 'append'")
    if len(rows) > MAX_ROWS:
        raise ValueError(f"too many rows (limit {MAX_ROWS})")
    clean, errors = [], []
    for i, raw in enumerate(rows, start=1):
        if not isinstance(raw, dict):
            errors.append(f"row {i}: not an object")
            continue
        row, err = _clean_row(raw)
        if row:
            clean.append(row)
        else:
            errors.append(f"row {i}: {err}")
    if not clean:
        return {"added": 0, "skipped": len(errors), "errors": errors[:5]}
    c = conn()
    if mode == "replace":
        c.execute("DELETE FROM activities")
        c.execute("DELETE FROM deals")
    c.executemany(
        INSERT_SQL,
        [
            (
                r["company"],
                r["contact"],
                r["stage"],
                r["value"],
                r["last_activity"],
                json.dumps(r["extra"]),
                "upload",
            )
            for r in clean
        ],
    )
    c.execute(
        "INSERT INTO imports(filename,mode,imported_at,rows_added,rows_skipped) "
        "VALUES(?,?,?,?,?)",
        (filename, mode, date.today().isoformat(), len(clean), len(errors)),
    )
    c.commit()
    c.close()
    return {"added": len(clean), "skipped": len(errors), "errors": errors[:5]}


def reset_to_sample():
    c = conn()
    c.execute("DELETE FROM activities")
    c.execute("DELETE FROM deals")
    _seed_sample(c)
    c.commit()
    c.close()


if __name__ == "__main__":
    init()
    c = conn()
    n = c.execute("SELECT COUNT(*) FROM deals").fetchone()[0]
    c.close()
    print(f"Database ready with {n} deals")