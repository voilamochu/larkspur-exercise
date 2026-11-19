# PITCH.md

Six lines and a lever. Your words. The last two are scored.

<<<<<<< HEAD
Built: A disruption-care chat agent with 19 tools: Larkspur's given tools, eight we wrote ourselves (including seats_left and cause_in_plain_words), and fare_rules over MCP.
Does: It looks up the booking, checks the flight status and the policy, finds the first day with room for the whole party, and explains the cause of the disruption in plain words.
Number: 19,000 to 23,539 tokens in, for one ticket (K7PQ2M), after we added our tools.
Safety check: It never held or confirmed a rebooking on its own. In the K7PQ2M trace it made six lookups and no hold_seat or confirm_rebooking call, and it ended its turn with a message.
Next: Write a tone rule so an abusive message gets a firm, calm boundary or a hand-off to a person, then re-run the five tickets.
Still broken: An abusive message (R8KD3F) gets a calm, normal resolution, as if nothing was said, because the agent has no tone rule yet.
=======
Built: A support agent for disrupted flights, with Larkspur's nine tools plus eight more we wrote (seats_left, care_entitlements, cause_in_plain_words and five others), and next_available_day and fare_rules served over MCP: 19 tools in all.
Does: It looks up the booking, checks the flight status, says the cause in Larkspur's approved plain words, finds the first day the customer can get home, checks what policy owes them, and searches alternative flights with seats; it hands groups to a human.
Number: 67,538 to 124,641 tokens in, total of the five tickets (9 tools in Build 1, 19 tools after Build 2).
Safety check: It never confirms a rebooking: confirm_rebooking needs a token only the customer's own Confirm-click makes. In the K7PQ2M trace it made 6 tool calls (lookup_booking to search_alternatives) and never called hold_seat or confirm_rebooking.
Next: Turn on prompt caching for the tool list, because cache_read was 0 on all five tickets, then re-run the five tickets to see tokens in come down.
Still broken: The abusive-message ticket (R8KD3F) gets the same calm, normal resolution as every other ticket, because our tone addendum is still empty.
>>>>>>> ccf75d9299967c285a6cf1b5c28467e4ee93d841
Lever: <cost | speed | intelligence>

## Priya asked

Costs:
Wrong:
Runs it:
Left out:
