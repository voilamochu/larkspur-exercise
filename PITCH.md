# PITCH.md

Built: A support agent for disrupted flights, with Larkspur's nine tools plus eight more we wrote (seats_left, care_entitlements, cause_in_plain_words and five others), and next_available_day and fare_rules served over MCP: 19 tools in all.
Does: It looks up the booking, checks the flight status, says the cause in Larkspur's approved plain words, finds the first day the customer can get home, checks what policy owes them, and searches alternative flights with seats; it hands groups to a human.
Number: 67,538 to 124,641 tokens in, total of the five tickets (9 tools in Build 1, 19 tools after Build 2).
Safety check: It never confirms a rebooking: confirm_rebooking needs a token only the customer's own Confirm-click makes. In the K7PQ2M trace it made 6 tool calls (lookup_booking to search_alternatives) and never called hold_seat or confirm_rebooking.
Next: Turn on prompt caching for the tool list, because cache_read was 0 on all five tickets, then re-run the five tickets to see tokens in come down.
Still broken: The abusive-message ticket (R8KD3F) gets the same calm, normal resolution as every other ticket, because our tone addendum is still empty.
Lever: cost

## Priya asked

Costs:
Wrong:
Runs it:
Left out:
