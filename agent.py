"""Larkspur disruption agent. This is the file you build.

It runs right now, and it is wrong in four places. The trace shows each one
before the code does, so read the trace first:

    python3 run.py K7PQ2M --trace

Where you edit:   grep -n '✏' agent.py   (six marks, one per place)
Steps and gates:  https://anthropicpartnerbasecamp.bts.com/
"""
from __future__ import annotations
import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List
from support import mock_backend as backend
from support import (MODEL, SYSTEM_PROMPT, call_local, execute_tool, mcp_client,
                     new_session, next_available_day, record_tool_result,
                     runtime_preamble)

MAX_TOOL_CALLS = 8  # Larkspur's own build capped the loop here; then a human takes over.

TONE_ADDENDUM = ""                       # ✏️ Build 4, step 4.1, intelligence goal
# EXTRA_TOOLS and LOCAL_TOOLS (Build 2, step 2.1) live at the bottom of the file,
# after the functions they point at.


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

    answer = ""
    turns = 1
    while response.stop_reason == "tool_use" and turns < MAX_TOOL_CALLS:
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results(response)})
        answer = text_of(response)
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
                    "date": {"type": "string", "description": "YYYY-MM-DD, the segment's local departure date as returned by lookup_booking"},
                },
                "required": ["flight_no", "date"],
            },
        },
        {
            "name": "search_alternatives",
            "description": (
                "Find rebooking options for a disrupted booking: other Larkspur flights "
                "with seats, ranked, each with an option_id that hold_seat accepts. Call "
                "it only after lookup_booking and get_flight_status have shown the segment "
                "is cancelled, delayed, or misconnected and the customer needs a new "
                "flight. It does not book or hold anything."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"pnr": {"type": "string"}},
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
                    "wait_minutes_for_alternative": {
                        "type": "integer",
                        "description": "Once an alternative is chosen or held: minutes from the original "
                                       "departure to the new one. Call check_policy again with it, since "
                                       "meal credit on cancellations depends on it."},
                    "chosen_option_id": {"type": "string", "description": "The option_id the customer chose or you held"},
                },
                "required": ["pnr", "cause_code", "delay_minutes", "status"],
            },
        },
        {
            "name": "hold_seat",
            "description": "Place a 15-minute hold on one alternative. Reversible. It simply expires.",
            "input_schema": {
                "type": "object",
                "properties": {"option_id": {"type": "string"}, "pnr": {"type": "string"}},
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


# ──────────────────────────────────────────────────────────────────────────────
# Build 2: the tools the team added. Each one answers from a file in
# data/americas/ or from the backend's own state, and says so when the answer
# is not there rather than filling the gap.
# ──────────────────────────────────────────────────────────────────────────────
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HHMM = re.compile(r"^\d{2}:\d{2}$")
DATA_DATE = ("YYYY-MM-DD in the data's own calendar: the segment date lookup_booking returned, "
             "e.g. 2025-05-08. 'Today' or 'tonight' means that date, never the Current time line.")
HORIZON = ("flights.csv covers %s to %s only, and the data's now is bookings.json's fixture_clock."
           % (backend.DATA_HORIZON_START, backend.DATA_HORIZON_END))


def _now() -> datetime:
    """The moment the sample data treats as now: bookings.json's fixture_clock."""
    return datetime.fromisoformat(backend.load_bookings()["fixture_clock"])


def _plus_minutes(hhmm: str, minutes: int) -> str:
    return (datetime.strptime(hhmm, "%H:%M") + timedelta(minutes=minutes)).strftime("%H:%M")


def _handbook() -> Dict[str, Dict[str, str]]:
    """fare_rules_excerpt.md split on its ### headings, keyed by section number."""
    text = (backend.DATA_DIR / "fare_rules_excerpt.md").read_text(encoding="utf-8")
    sections = {}
    for chunk in re.split(r"^### ", text, flags=re.M)[1:]:
        heading, _, body = chunk.partition("\n")
        sections[heading.split(".", 1)[0].strip()] = {"heading": heading.strip(), "text": body.strip()}
    return sections


def _flight_row(flight_no: str, date: str):
    return next((r for r in backend.load_flights()
                 if r["flight_no"] == flight_no and r["date"] == date), None)


def reopen_stats(intent_label: str = None) -> Dict[str, Any]:
    with open(backend.DATA_DIR / "transcripts_sample.jsonl", encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    by_intent: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        entry = by_intent.setdefault(r["intent_label"], {"conversations": 0, "reopened_within_72h": 0,
                                                         "reopen_reasons": []})
        entry["conversations"] += 1
        if r.get("reopened_within_72h"):
            entry["reopened_within_72h"] += 1
            if r.get("reopen_reason"):
                entry["reopen_reasons"].append(r["reopen_reason"])
    result = {"source": "transcripts_sample.jsonl", "sample_size": len(rows),
              "caveat": "Eight human-handled conversations, mostly one per kind of problem. "
                        "A count here is one conversation, not a rate to quote as a statistic.",
              "reopened_overall": sum(e["reopened_within_72h"] for e in by_intent.values())}
    if intent_label:
        if intent_label not in by_intent:
            result.update({"found": False, "known_intent_labels": sorted(by_intent),
                           "note": "No conversation of that kind in the sample."})
            return result
        result["by_intent"] = {intent_label: by_intent[intent_label]}
    else:
        result["by_intent"] = by_intent
    return result


def care_entitlements(cause_code: str, status: str, delay_minutes: int = 0) -> Dict[str, Any]:
    policy = backend.load_policy()
    if cause_code not in policy["cause_classes"]:
        return {"error": "unknown cause_code %s; one of %s" % (cause_code, sorted(policy["cause_classes"]))}
    cause_class = policy["cause_classes"][cause_code]
    if status == "CANCELLED":
        band = "CXL"
    elif status == "DIVERTED":
        band = "DIV"
    else:
        band = next((b["band"] for b in policy["delay_bands"] if b["band"] not in ("CXL", "DIV")
                     and b["min_minutes"] <= delay_minutes
                     and (b["max_minutes"] is None or delay_minutes <= b["max_minutes"])), None)
    row = next((r for r in policy["rows"] if r["cause_class"] == cause_class and r["band"] == band), None)
    if row is None:
        return {"found": False, "note": "disruption_policy.json has no row for %s / %s." % (cause_class, band)}
    bonuses = {tier: {k: v for k, v in rules.items() if k.startswith("meal_bonus")}
               for tier, rules in policy["loyalty_rules"].items() if rules.get("meal_bonus_usd")}
    return {"table_row": row["policy_row_id"], "cause_class": cause_class, "band": band,
            "care_per_passenger": row["care"], "loyalty_meal_bonus": bonuses,
            "handbook_section_6": _handbook().get("6", {}).get("text"),
            "note": "The general table, not this customer's decision. Never cite table_row to the "
                    "customer as theirs and never pass it to issue_voucher; check_policy gives the "
                    "policy_row_id of record."}


def cause_in_plain_words(cause_code: str, language: str = "en") -> Dict[str, Any]:
    policy = backend.load_policy()
    labels = policy["cause_labels_customer"].get(cause_code)
    if labels is None:
        return {"error": "unknown cause_code %s; one of %s" % (cause_code, sorted(policy["cause_labels_customer"]))}
    if language not in labels:
        return {"found": False, "cause_code": cause_code, "languages_available": sorted(labels),
                "note": "No customer wording in that language. Hand off rather than translate."}
    in_control = policy["cause_classes"][cause_code] == "controllable"
    return {"cause_code": cause_code, "say": labels[language],
            "control": "within our control" if in_control else "outside our control",
            "rule": policy["customer_wording"]["cause_attribution"]}


def departures_in_window(airport: str, date: str, from_time: str = "00:00",
                         to_time: str = "23:59") -> Dict[str, Any]:
    if not ISO_DATE.match(str(date)):
        return {"error": "date must be YYYY-MM-DD, got %s" % date}
    if not (HHMM.match(from_time) and HHMM.match(to_time)):
        return {"error": "from_time and to_time must be HH:MM, 24-hour"}
    now = _now()
    departures = []
    for r in backend.load_flights():
        if r["origin"] != airport or r["date"] != date:
            continue
        est = _plus_minutes(r["sched_dep_local"], r["delay_min"])
        if not from_time <= est <= to_time:
            continue
        departures.append({"flight_no": r["flight_no"], "dest": r["dest"],
                           "sched_dep_local": r["sched_dep_local"], "est_dep_local": est,
                           "status": r["status"], "delay_min": r["delay_min"],
                           "gone_before_now": date < now.strftime("%Y-%m-%d") or (
                               date == now.strftime("%Y-%m-%d") and est < now.strftime("%H:%M"))})
    departures.sort(key=lambda d: d["est_dep_local"])
    result = {"airport": airport, "date": date, "window": [from_time, to_time],
              "now": now.isoformat(), "source": "flights.csv", "departures": departures}
    if not departures:
        result["note"] = "flights.csv has no departure from %s in that window. %s" % (airport, HORIZON)
    return result


def seats_left(flight_no: str, date: str, party_size: int = None) -> Dict[str, Any]:
    if not ISO_DATE.match(str(date)):
        return {"error": "date must be YYYY-MM-DD, got %s" % date}
    row = _flight_row(flight_no, date)
    if row is None:
        return {"found": False, "flight_no": flight_no, "date": date,
                "note": "flights.csv has no record of that flight on that date. " + HORIZON}
    result = {"flight_no": flight_no, "date": date, "status": row["status"],
              "seats_left_main": row["seats_left_Y"], "seats_left_first": row["seats_left_J"],
              "source": "flights.csv"}
    if party_size:
        result["party_size"] = party_size
        result["fits_in_main"] = row["seats_left_Y"] >= party_size
        result["fits_in_first"] = row["seats_left_J"] >= party_size
    if row["status"] == "CANCELLED":
        result["note"] = "This flight is cancelled; it has no seats to sell."
    return result


def ground_stop_status(airport: str) -> Dict[str, Any]:
    now = _now()
    mentions, window = [], None
    for r in backend.load_flights():
        remark = r["remarks"] or ""
        if airport not in remark and airport not in (r["origin"], r["dest"]):
            continue
        if "ground stop" not in remark.lower() and "metering" not in remark.lower():
            continue
        mentions.append({"flight_no": r["flight_no"], "date": r["date"], "remark": remark})
        found = re.search(r"ground stop (\d{2}:\d{2})-(\d{2}:\d{2})", remark)
        if found and window is None:
            window = {"start_local": found.group(1), "end_local": found.group(2), "date": r["date"]}
    if not mentions:
        return {"found": False, "airport": airport, "now": now.isoformat(),
                "note": "flights.csv records no ground stop or metering at %s." % airport}
    result = {"airport": airport, "now": now.isoformat(), "source": "flights.csv remarks",
              "remarks": mentions}
    if window:
        same_day = window["date"] == now.strftime("%Y-%m-%d")
        hhmm = now.strftime("%H:%M")
        result["ground_stop"] = window
        result["in_effect_now"] = same_day and window["start_local"] <= hhmm < window["end_local"]
        result["note"] = ("The end time is the planned end in an OpsFeed remark, not a promise. "
                          "Remarks mentioning metering show delays continuing after it.")
    else:
        result["ground_stop"] = None
        result["note"] = "The remarks mention a ground stop but give no times. Do not state an end time."
    return result


def hold_time_left(hold_id: str) -> Dict[str, Any]:
    now = _now()
    hold = backend._holds.get(hold_id)
    if hold is None:
        if hold_id in backend._confirmed:
            return {"hold_id": hold_id, "status": "confirmed", "note": "Already confirmed, no longer a hold."}
        return {"found": False, "hold_id": hold_id,
                "note": "No hold with that id in this session. Do not guess a time."}
    seconds = (hold["expires_at"] - now).total_seconds()
    return {"hold_id": hold_id, "option_id": hold["option_id"], "now": now.isoformat(),
            "expires_at": hold["expires_at"].isoformat(),
            "minutes_left": max(0, int(seconds // 60)), "expired": seconds <= 0}


def what_automation_will_not_do() -> Dict[str, Any]:
    section = _handbook().get("7")
    if section is None:
        return {"found": False, "note": "Section 7 is missing from fare_rules_excerpt.md."}
    return {"source": "Handbook v14.3, fare_rules_excerpt.md", "section": section["heading"],
            "text": section["text"]}


EXTRA_TOOLS: List[Dict[str, Any]] = [        # ✏️ Build 2, step 2.1: schemas for the tools you add
    # next_available_day and fare_rules are served by the MCP server now
    # (support/mcp_server.py) and reach Claude through tool_list().
    {
        "name": "reopen_stats",
        "description": (
            "How often each kind of problem came back within 72 hours, from eight "
            "conversations human agents handled. Use when the customer asks whether this "
            "is likely to come back or be sorted for good, or when weighing what to warn "
            "them about. Returns counts and reopen reasons per intent, with a sample-size "
            "caveat that must be passed on."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "intent_label": {
                    "type": "string",
                    "description": "Optional. One kind of problem, e.g. rebook_after_cancellation, "
                                   "refund_vs_credit, missed_connection. Omit to get all of them.",
                },
            },
        },
    },
    {
        "name": "care_entitlements",
        "description": (
            "Look up the general care table (meal, hotel and ground transport per passenger) "
            "for a cause and a delay, with Handbook section 6 behind it. Use only for a "
            "hypothetical or general question, such as what Larkspur gives for a maintenance "
            "cancellation, not for this customer's own flight. For what this customer is "
            "owed, call check_policy instead: it applies their fare, tier and overnight "
            "status. Its table_row is never the customer's decision and never goes to "
            "issue_voucher."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cause_code": {"type": "string", "enum": ["WX", "ATC", "MX", "CREW", "SEC"]},
                "status": {"type": "string", "enum": ["ON_TIME", "DELAYED", "CANCELLED", "DIVERTED"]},
                "delay_minutes": {"type": "integer", "description": "From get_flight_status; 0 when cancelled"},
            },
            "required": ["cause_code", "status"],
        },
    },
    {
        "name": "cause_in_plain_words",
        "description": (
            "Turn a cause_code from get_flight_status into the only words Larkspur lets you "
            "use for it with a customer, in English or Spanish, plus whether it was within "
            "our control. Call it once per conversation, before you first name the cause, "
            "in the booking's language. Returns the phrase to say."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cause_code": {"type": "string", "enum": ["WX", "ATC", "MX", "CREW", "SEC"]},
                "language": {"type": "string", "enum": ["en", "es"], "description": "The booking's language. Defaults to en."},
            },
            "required": ["cause_code"],
        },
    },
    {
        "name": "departures_in_window",
        "description": (
            "List every Larkspur departure from one airport on one date between two local "
            "times, with status, delay and estimated departure, and whether it has already "
            "gone by now. Use when the customer asks what is still leaving an airport in a "
            "time window, any destination. Returns the departures, or a note that there are "
            "none."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "airport": {"type": "string", "description": "IATA code of the departure airport, e.g. DEN"},
                "date": {"type": "string", "description": DATA_DATE},
                "from_time": {"type": "string", "description": "Window start, local HH:MM 24-hour. Defaults to 00:00."},
                "to_time": {"type": "string", "description": "Window end, local HH:MM 24-hour. Defaults to 23:59."},
            },
            "required": ["airport", "date"],
        },
    },
    {
        "name": "seats_left",
        "description": (
            "Say whether a party of a given size fits on one flight, in Main and First. Use "
            "when the customer asks if there is room on a specific flight for them or their "
            "group, instead of get_flight_status: you do not need both on the same flight, "
            "and get_flight_status already carries seats_left_Y/J if you have called it. "
            "Returns seat counts and fits_in_main / fits_in_first, or found=false."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "flight_no": {"type": "string", "description": "e.g. LK417"},
                "date": {"type": "string", "description": DATA_DATE},
                "party_size": {"type": "integer", "description": "How many people need seats. Use passenger_count from lookup_booking."},
            },
            "required": ["flight_no", "date"],
        },
    },
    {
        "name": "ground_stop_status",
        "description": (
            "Check whether an airport is under a ground stop right now and its planned end "
            "time, from the OpsFeed remarks, measured against the data's own clock. Use when "
            "the customer asks if an airport is still stopped, or until when. Returns the "
            "stop window, in_effect_now and the remarks it came from, or found=false."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"airport": {"type": "string", "description": "IATA code, e.g. DEN"}},
            "required": ["airport"],
        },
    },
    {
        "name": "hold_time_left",
        "description": (
            "Say how many minutes remain on an existing seat hold. Not right after hold_seat: "
            "its own result already says expires_in_minutes. Use on a later turn, when the "
            "customer comes back and asks how long is left. Needs the hold_id hold_seat "
            "returned. Returns minutes_left and expires_at, or found=false."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"hold_id": {"type": "string", "description": "From hold_seat, e.g. HOLD-3F9A1C"}},
            "required": ["hold_id"],
        },
    },
    {
        "name": "what_automation_will_not_do",
        "description": (
            "Read Handbook section 7: the list of things this chat is not allowed to do "
            "(refunds, hotel approval, other airlines, groups of 10 or more, minors, partner "
            "flights, pets, medical, baggage). Use when the customer asks you to do something "
            "outside rebooking, holds and vouchers, to check it is allowed before you try, or "
            "to explain why a person has to do it. If it is on the list, escalate_to_human "
            "next. Returns the section verbatim."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
]

LOCAL_TOOLS: Dict[str, Any] = {               # ✏️ Build 2, step 2.1: the functions behind them
    "reopen_stats": reopen_stats,
    "care_entitlements": care_entitlements,
    "cause_in_plain_words": cause_in_plain_words,
    "departures_in_window": departures_in_window,
    "seats_left": seats_left,
    "ground_stop_status": ground_stop_status,
    "hold_time_left": hold_time_left,
    "what_automation_will_not_do": what_automation_will_not_do,
}
