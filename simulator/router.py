import re

TONES = ("friendly", "formal", "urgent", "casual", "professional", "polite", "short")

LOG_WORDS = ("log ", "record ", "add a note", "note that", "i just spoke",
             "i just called", "i called", "i spoke", "i met")
DRAFT_WORDS = ("draft", "write", "compose", "follow up", "follow-up", "followup", "email")
BOARD_WORDS = ("show the pipeline", "show me the pipeline", "show pipeline",
               "pipeline board", "board", "visual", "kanban",
               "see the pipeline", "view the pipeline")
STALL_WORDS = ("stall", "stuck", "going cold", "gone cold", "idle", "no activity",
               "neglected", "slipping", "inactive")
LIST_WORDS = ("what deals do i have", "list deals", "list my deals", "all deals",
              "my deals", "show deals", "show me deals")
SUMMARY_WORDS = ("pipeline", "summary", "overview", "how are we doing", "status")


def parse_companies(text: str) -> list[str]:
    """Read company names out of the list_deals sentence."""
    if ":" not in text:
        return []
    body = text.split(":", 1)[1]
    names = []
    for part in body.split(";"):
        name = part.split(",")[0].strip()
        if name:
            names.append(name)
    return names


def find_company(text_lower: str, companies: list[str]):
    """Return (name, end_index). A shared first word (e.g. 'Acme') is passed on as typed so the server can ask which deal is meant."""
    best = None
    for company in companies:
        name = company.lower()
        first = name.split()[0]
        for key, is_full in ((name, True), (first, False)):
            idx = text_lower.find(key)
            if idx != -1 and len(key) >= 3:
                if best is None or len(key) > best[2]:
                    best = (company, idx + len(key), len(key), key, is_full)
                break
    if not best:
        return None
    company, end, _, key, is_full = best
    if not is_full:
        shared = [c for c in companies if c.lower().split()[0] == key]
        if len(shared) > 1:
            return key.title(), end
    return company, end


def extract_note(text: str, end: int) -> str:
    rest = text[end:].strip(" :,-.")
    rest = re.sub(r"^(?:saying|says|that|and|because|about)\s+", "", rest, flags=re.I)
    return rest if len(rest) >= 3 else text.strip()


def extract_days(text_lower: str) -> int:
    m = re.search(r"(\d+)\s*(?:day|days)", text_lower)
    if m:
        return int(m.group(1))
    if "week" in text_lower:
        return 7
    return 7


def extract_tone(text_lower: str) -> str:
    for tone in TONES:
        if tone in text_lower:
            return tone
    return "friendly"


def route(text: str, companies: list[str]):
    """Turn a sentence into (tool_name, arguments), or None if it isn't understood."""
    t = text.lower().strip()
    if not t:
        return None
    match = find_company(t, companies)

    if match and any(w in t for w in LOG_WORDS):
        return "log_activity", {"company": match[0], "note": extract_note(text, match[1])}
    if match and any(w in t for w in DRAFT_WORDS):
        return "draft_followup", {"company": match[0], "tone": extract_tone(t)}
    if any(w in t for w in BOARD_WORDS):
        return "show_pipeline", {}
    if any(w in t for w in STALL_WORDS):
        return "stalled_deals", {"days": extract_days(t)}
    if any(w in t for w in LIST_WORDS):
        return "list_deals", {}
    if any(w in t for w in SUMMARY_WORDS):
        return "pipeline_summary", {}
    return None