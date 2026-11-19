"""Larkspur disruption agent. This is the file you build.

It runs right now, and it is wrong in four places. The trace shows each one
before the code does, so read the trace first:

    python3 run.py K7PQ2M --trace

Where you edit:   grep -n '✏' agent.py   (six marks, one per place)
Steps and gates:  https://anthropicpartnerbasecamp.bts.com/
"""
from __future__ import annotations
from typing import Any, Dict, List
from support import (MODEL, SYSTEM_PROMPT, call_local, execute_tool, mcp_client,
                     new_session, next_available_day, record_tool_result,
                     runtime_preamble)

MAX_TOOL_CALLS = 8  # Larkspur's own build capped the loop here; then a human takes over.

TONE_ADDENDUM = ""                       # ✏️ Build 4, step 4.1, intelligence goal


# ── Build 2: the ten tools we add. Read-only, answered from Larkspur's own files. ──
import json as _json
import re as _re
from datetime import timedelta as _td
from support import mock_backend as _be


def _pnr_context(pnr):
    try:
        booking = _be.get_booking_raw(pnr)
    except _be.NotFound as exc:
        return None, None, {"error": str(exc)}
    return booking, _be.get_disrupted_segment(booking), None


def _handbook_sections():
    text = (_be.DATA_DIR / "fare_rules_excerpt.md").read_text(encoding="utf-8")
    parts = _re.split(r"(?m)^(?=### )", text)
    return {p.split("\n", 1)[0].strip("# ").strip(): p.strip() for p in parts if p.startswith("### ")}


def _section(number):
    for title, body in _handbook_sections().items():
        if title.startswith(str(number) + "."):
            return body
    return None


def _cabin_key(cabin):
    return "seats_left_J" if str(cabin).upper() == "J" else "seats_left_Y"


def next_available_day_tool(pnr):
    booking, seg, err = _pnr_context(pnr)
    if err:
        return err
    party = len(booking["passengers"])
    day = _be.earliest_alternative_date(seg["origin"], seg["dest"], seg["date"], seg["cabin"], party)
    return {"pnr": pnr, "origin": seg["origin"], "dest": seg["dest"], "cabin": seg["cabin"],
            "party_size": party, "first_day_with_room_for_whole_party": day,
            "note": None if day else "No open seat for the whole party inside the data horizon.",
            "source": "flights.csv / alternatives search"}


def seats_left(flight_no, date, cabin, party_size=1):
    rows = [r for r in _be.load_flights() if r["flight_no"] == flight_no and r["date"] == date]
    if not rows:
        return {"error": "No flight %s on %s in the data." % (flight_no, date)}
    left = rows[0][_cabin_key(cabin)]
    return {"flight_no": flight_no, "date": date, "cabin": str(cabin).upper(), "seats_left": left,
            "party_size": party_size, "fits": left >= int(party_size), "status": rows[0]["status"],
            "source": "flights.csv"}


def departures_in_window(airport, date, from_time, to_time):
    rows = [r for r in _be.load_flights()
            if r["origin"] == airport.upper() and r["date"] == date
            and from_time <= r["sched_dep_local"] <= to_time]
    rows.sort(key=lambda r: r["sched_dep_local"])
    return {"airport": airport.upper(), "date": date, "window": [from_time, to_time],
            "departures": [{"flight_no": r["flight_no"], "dest": r["dest"], "sched_dep": r["sched_dep_local"],
                            "status": r["status"], "delay_min": r["delay_min"],
                            "seats_left_Y": r["seats_left_Y"], "seats_left_J": r["seats_left_J"]}
                           for r in rows],
            "source": "flights.csv"}


def ground_stop_status(airport):
    ap = airport.upper()
    now = _be.FIXTURE_CLOCK
    hits = [r for r in _be.load_flights() if ap in (r["remarks"] or "") and "ground stop" in (r["remarks"] or "")]
    if not hits:
        return {"airport": ap, "ground_stop_on_record": False, "now": now.isoformat(),
                "source": "flights.csv remarks"}
    window = None
    for r in hits:
        m = _re.search(r"ground stop (\d\d:\d\d)-(\d\d:\d\d)", r["remarks"])
        if m:
            window = (m.group(1), m.group(2))
    out = {"airport": ap, "ground_stop_on_record": True, "now": now.isoformat(),
           "evidence": [r["flight_no"] + ": " + r["remarks"] for r in hits[:4]],
           "source": "flights.csv remarks"}
    if window:
        hhmm = now.strftime("%H:%M")
        out.update(window_local=list(window), stopped_now=window[0] <= hhmm < window[1], until=window[1])
    else:
        out["note"] = "A ground stop is mentioned but no end time is on record; do not guess one."
    return out


def hold_time_left(hold_id):
    hold = _be._holds.get(hold_id)
    if not hold:
        return {"error": "No active hold %s. It may have been confirmed, never created or released." % hold_id}
    left = (hold["expires_at"] - _be.FIXTURE_CLOCK) / _td(minutes=1)
    return {"hold_id": hold_id, "minutes_left": max(0, round(left, 1)), "expired": left <= 0,
            "expires_at": hold["expires_at"].isoformat(), "source": "hold store + fixture clock"}


def care_entitlements(pnr):
    booking, seg, err = _pnr_context(pnr)
    if err:
        return err
    return {"pnr": pnr, "fare_family": booking["fare_family"], "loyalty_tier": booking["loyalty"]["tier"],
            "handbook_section_6": _section(6),
            "note": "Rules as written. The amount for THIS disruption comes from check_policy.",
            "source": "fare_rules_excerpt.md section 6"}


def fare_rules(topic):
    key = {"fare_family": "4.", "disruption": "5.", "refund": "5.", "care": "6."}.get(str(topic).lower())
    if not key:
        return {"error": "topic must be one of fare_family, disruption, refund, care."}
    body = next((b for t, b in _handbook_sections().items() if t.startswith(key)), None)
    return {"topic": topic, "handbook_text": body, "source": "fare_rules_excerpt.md"}


def cause_in_plain_words(cause_code, language="en"):
    labels = _be.load_policy()["cause_labels_customer"]
    if cause_code not in labels:
        return {"error": "Unknown cause code %s. Known: %s." % (cause_code, ", ".join(labels))}
    return {"cause_code": cause_code, "label": labels[cause_code].get(language, labels[cause_code]["en"]),
            "source": "disruption_policy.json cause_labels_customer"}


def reopen_stats(intent_label=None):
    with open(_be.DATA_DIR / "transcripts_sample.jsonl", encoding="utf-8") as fh:
        rows = [_json.loads(l) for l in fh if l.strip()]
    if intent_label:
        rows = [r for r in rows if r.get("intent_label") == intent_label]
    if not rows:
        return {"error": "No conversations with that intent_label in the sample."}
    reopened = [r for r in rows if r.get("reopened_within_72h")]
    return {"conversations": len(rows), "reopened_within_72h": len(reopened),
            "by_intent": {r["intent_label"]: bool(r.get("reopened_within_72h")) for r in rows},
            "reopen_reasons": [r.get("reopen_reason") for r in reopened],
            "caveat": "Tiny human-handled sample; indicative only, never quote it as a probability.",
            "source": "transcripts_sample.jsonl"}


def what_automation_will_not_do():
    return {"handbook_section_7": _section(7),
            "next_step": "Explain plainly and hand over with escalate_to_human.",
            "source": "fare_rules_excerpt.md section 7"}


EXTRA_TOOLS: List[Dict[str, Any]] = [      # ✏️ Build 2, step 2.1: schemas for the tools you add
    {"name": "seats_left",
     "description": ("Free seats in one cabin of one named flight on one date, and whether a party of a given "
                     "size fits. Call it when the customer asks if there is room on a specific flight for "
                     "their group. Not for finding flights (use search_alternatives)."),
     "input_schema": {"type": "object", "properties": {
         "flight_no": {"type": "string", "description": "Flight number, e.g. LK105"},
         "date": {"type": "string", "description": "Local date, YYYY-MM-DD"},
         "cabin": {"type": "string", "enum": ["Y", "J"], "description": "Y = main cabin, J = first/business"},
         "party_size": {"type": "integer", "description": "Number of passengers who need seats"}},
         "required": ["flight_no", "date", "cabin", "party_size"]}},
    {"name": "departures_in_window",
     "description": ("List flights still scheduled to leave one airport within a local time window on a date, "
                     "with live status, delay and seats left. Call it for 'what is still leaving Denver this "
                     "afternoon'. Lists all flights, not alternatives tailored to a booking."),
     "input_schema": {"type": "object", "properties": {
         "airport": {"type": "string", "description": "3-letter IATA code, e.g. DEN"},
         "date": {"type": "string", "description": "Local date, YYYY-MM-DD"},
         "from_time": {"type": "string", "description": "Window start, 24-hour HH:MM local, e.g. 14:00"},
         "to_time": {"type": "string", "description": "Window end, 24-hour HH:MM local, e.g. 20:00"}},
         "required": ["airport", "date", "from_time", "to_time"]}},
    {"name": "ground_stop_status",
     "description": ("Whether an airport is under an air-traffic ground stop right now and until what time, "
                     "from OpsFeed remarks. Call it when the customer asks if an airport is still stopped or "
                     "when it reopens. If no end time is on record it says so; never invent one."),
     "input_schema": {"type": "object", "properties": {
         "airport": {"type": "string", "description": "3-letter IATA code, e.g. DEN"}},
         "required": ["airport"]}},
    {"name": "hold_time_left",
     "description": ("Minutes remaining before a held seat is released. Call it when the customer asks how "
                     "long they have to decide, using the hold_id returned by hold_seat. Read-only."),
     "input_schema": {"type": "object", "properties": {
         "hold_id": {"type": "string", "description": "Hold id from hold_seat, e.g. HOLD-1A2B3C"}},
         "required": ["hold_id"]}},
    {"name": "care_entitlements",
     "description": ("Larkspur's written rules on meals, ground transport and hotel while waiting (Handbook "
                     "section 6), with this booking's fare and tier. Call it to EXPLAIN what care exists. It "
                     "does not decide this customer's amounts or approve anything: use check_policy for that."),
     "input_schema": {"type": "object", "properties": {
         "pnr": {"type": "string", "description": "Six-character confirmation code"}},
         "required": ["pnr"]}},
    {"name": "cause_in_plain_words",
     "description": ("Customer-safe wording for a disruption cause code. Call it before telling a customer "
                     "why a flight was cancelled or delayed, with the cause code from get_flight_status. "
                     "Use its label only; do not elaborate or assign blame."),
     "input_schema": {"type": "object", "properties": {
         "cause_code": {"type": "string", "enum": ["WX", "ATC", "MX", "CREW", "SEC"],
                        "description": "Cause code from get_flight_status"},
         "language": {"type": "string", "enum": ["en", "es"], "description": "Customer's language"}},
         "required": ["cause_code"]}},
    {"name": "reopen_stats",
     "description": ("How often this kind of problem came back within 72 hours in a small sample of human-"
                     "handled chats. Call it when the customer asks if the problem will recur, or to judge "
                     "follow-up risk. Tiny sample: say 'in our sample', never give a probability."),
     "input_schema": {"type": "object", "properties": {
         "intent_label": {"type": "string",
                          "description": "Optional problem type, e.g. rebook_after_cancellation, refund_vs_credit. Omit for all."}},
         "required": []}},
    {"name": "what_automation_will_not_do",
     "description": ("Handbook section 7: what this chat may not do (refunds, cancelling the trip, hotel "
                     "approval, groups of 10+, minors, partner flights, and more). Call it when the customer "
                     "asks for any of these, then hand over with escalate_to_human."),
     "input_schema": {"type": "object", "properties": {}, "required": []}},
]
LOCAL_TOOLS: Dict[str, Any] = {            # ✏️ Build 2, step 2.1: the functions behind them
    "seats_left": seats_left,
    "departures_in_window": departures_in_window, "ground_stop_status": ground_stop_status,
    "hold_time_left": hold_time_left, "care_entitlements": care_entitlements,
    "cause_in_plain_words": cause_in_plain_words, "reopen_stats": reopen_stats,
    "what_automation_will_not_do": what_automation_will_not_do,
}


def text_of(response) -> str:
    """Given. The last non-empty text block, never content[0]."""
    texts = [b.text for b in response.content if getattr(b, "type", None) == "text" and b.text]
    return texts[-1] if texts else ""


def tool_results(response) -> List[Dict[str, Any]]:
    """Given. Runs every tool_use block and packages the results the way the
    API expects them back. A tool can live in three places: the MCP server,
    LOCAL_TOOLS, or support/tools.py."""
    # three branches, no try/except in this file: mcp_client.call_remote() and
    # support.call_local() answer with an error dict instead of raising, and both
    # record what came back on the trace
    results = []
    for block in response.content:
        if getattr(block, "type", None) != "tool_use":
            continue
        if block.name in mcp_client.tool_names:
            output = mcp_client.call_remote(block.name, block.input)
        elif block.name in LOCAL_TOOLS:
            output = call_local(LOCAL_TOOLS[block.name], block.name, block.input)
        else:
            output = execute_tool(block.name, block.input)
        results.append({
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": str(output),
        })
    return results


def run_agent(pnr: str, last_name: str, message: str) -> str:            # ✏️ Build 1, step 1.2
    """Run the tool loop until Claude stops asking for tools. Return its final text."""
    client, tracer = new_session()
    tools = tool_list()
    messages = [
        {"role": "user", "content": f"PNR {pnr}, last name {last_name}. {message}"},
    ]

    response = client.messages.create(
        model=MODEL, max_tokens=4096, system=runtime_preamble() + SYSTEM_PROMPT + TONE_ADDENDUM,
        thinking={"type": "adaptive"}, tools=tools, messages=messages,
    )

    turns = 1
    while response.stop_reason == "tool_use" and turns < MAX_TOOL_CALLS:
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results(response)})
        response = client.messages.create(
            model=MODEL, max_tokens=4096, system=runtime_preamble() + SYSTEM_PROMPT + TONE_ADDENDUM,
            thinking={"type": "adaptive"}, tools=tools, messages=messages,
        )
        turns += 1

    return text_of(response)


def tool_list() -> List[Dict[str, Any]]:                   # ✏️ Build 2, step 2.2
    """Given. Exactly what Claude is offered on every turn; run.py --show-tools
    prints this list."""
    return build_tools() + EXTRA_TOOLS + mcp_client.tools()


# ──────────────────────────────────────────────────────────────────────────────
# Below this line: what Claude is told about each tool. Step 1.3.
# The functions these describe are written and correct, in support/tools.py.
# ──────────────────────────────────────────────────────────────────────────────
def build_tools() -> List[Dict[str, Any]]:                 # ✏️ Build 1, step 1.3
    """Anthropic-shaped schemas: name, description, input_schema. What Claude is
    told about each of the nine tools, and all it is ever told."""
    return [
        {
            "name": "lookup_booking",
            "description": (
                "Retrieve a Larkspur reservation from Altura by confirmation code (PNR) "
                "and the passenger's last name. Both are required to prevent a lookup on "
                "a guessed PNR. Returns fare family, loyalty tier, the segment that needs "
                "attention, and any group/partner/minor/SSR flags relevant to scope."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"pnr": {"type": "string"}, "last_name": {"type": "string"}},
                "required": ["pnr", "last_name"],
            },
        },
        {
            "name": "get_flight_status",
            "description": (
                "Look up a Larkspur or Larkspur Link flight's current OpsFeed status for "
                "one local date: status, delay minutes, and cause. Use this before telling "
                "a customer anything about a flight's timing; never state it from memory."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "flight_no": {"type": "string"},
                    "date": {"type": "string", "description": "Local flight date in YYYY-MM-DD format, e.g. 2025-05-08"},
                },
                "required": ["flight_no", "date"],
            },
        },
        {
            "name": "search_alternatives",
            "description": (
                "Search for alternative flights to rebook a customer whose flight is "
                "cancelled, diverted, or badly delayed. Call it after get_flight_status "
                "confirms a disruption and the customer wants to be rebooked. Returns a "
                "list of options, each with an option_id; pass the option_id the customer "
                "picks to hold_seat and check_policy. Searching changes nothing on the booking."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "pnr": {
                        "type": "string",
                        "description": "The 6-character confirmation code, as already used in lookup_booking.",
                    }
                },
                "required": ["pnr"],
            },
        },
        {
            "name": "check_policy",
            "description": (
                "Resolve what Larkspur owes this customer for the disruption: rebooking "
                "waiver, refund path, meal/hotel/ground care, goodwill eligibility and cap, "
                "and any escalation triggers. cause_code, delay_minutes and status describe "
                "what get_flight_status told you; fare_family, loyalty_tier and whether this "
                "is overnight are looked up from the booking, not asked of you. Every "
                "response carries a policy_row_id. Cite it if you reference this decision "
                "again."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "pnr": {"type": "string"},
                    "cause_code": {"type": "string", "enum": ["WX", "ATC", "MX", "CREW", "SEC"]},
                    "delay_minutes": {"type": "integer"},
                    "status": {"type": "string", "enum": ["ON_TIME", "DELAYED", "CANCELLED", "DIVERTED"]},
                    "wait_minutes_for_alternative": {"type": "integer"},
                    "chosen_option_id": {"type": "string"},
                },
                "required": ["pnr", "cause_code", "delay_minutes", "status"],
            },
        },
        {
            "name": "hold_seat",
            "description": (
                "Place a 15-minute hold on one alternative the customer has chosen. Call it "
                "only after search_alternatives has returned options and the customer has "
                "picked one; never guess an option_id. Reversible: the hold simply expires. "
                "Returns a hold_id, which confirm_rebooking needs, but the customer must "
                "still click Confirm themselves."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "option_id": {
                        "type": "string",
                        "description": "An option_id returned by search_alternatives, for the option the customer picked.",
                    },
                    "pnr": {"type": "string", "description": "The booking's confirmation code."},
                },
                "required": ["option_id", "pnr"],
            },
        },
        {
            "name": "confirm_rebooking",
            "description": (
                "Finalize a held seat. Irreversible. Requires a confirmation_token that "
                "only the customer's own Confirm-click can produce. You cannot supply it "
                "yourself, and 'the customer said yes' in chat does not substitute for it."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"hold_id": {"type": "string"}, "confirmation_token": {"type": "string"}},
                "required": ["hold_id", "confirmation_token"],
            },
        },
        {
            "name": "issue_voucher",
            "description": (
                "Issue a meal, ground, hotel, or goodwill voucher. Auto-approves within the "
                "policy's threshold for that type; above it, returns a pending status for a "
                "human. It does not fail. Always pass the policy_row_id that made it eligible."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "voucher_type": {"type": "string", "enum": ["meal", "ground", "hotel", "goodwill"]},
                    "amount_usd": {"type": "number"},
                    "pnr": {"type": "string"},
                    "policy_row_id": {"type": "string"},
                },
                "required": ["voucher_type", "amount_usd", "pnr", "policy_row_id"],
            },
        },
        {
            "name": "escalate_to_human",
            "description": (
                "Hand this conversation to a human, with your reasoning attached. Use for "
                "groups, partner segments, unaccompanied minors, refunds, or anything else "
                "out of scope. This is the correct outcome for those cases, not a failure."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "pnr": {"type": "string"}, "reason": {"type": "string"},
                    "summary_for_human": {"type": "string"}, "queue": {"type": "string"},
                },
                "required": ["pnr", "reason", "summary_for_human"],
            },
        },
        {
            "name": "send_confirmation",
            "description": "Send the customer a written confirmation of what was just done. Benign.",
            "input_schema": {
                "type": "object",
                "properties": {"pnr": {"type": "string"}, "message": {"type": "string"}},
                "required": ["pnr", "message"],
            },
        },
    ]
