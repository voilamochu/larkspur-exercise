# PITCH.md

Six lines and a lever. Your words. The last two are scored.

Built: A disruption-care chat agent with 19 tools: Larkspur's given tools, eight we wrote ourselves (including seats_left and cause_in_plain_words), and fare_rules over MCP.
Does: It looks up the booking, checks the flight status and the policy, finds the first day with room for the whole party, and explains the cause of the disruption in plain words.
Number: 19,000 to 23,539 tokens in, for one ticket (K7PQ2M), after we added our tools.
Safety check: It never held or confirmed a rebooking on its own. In the K7PQ2M trace it made six lookups and no hold_seat or confirm_rebooking call, and it ended its turn with a message.
Next: Write a tone rule so an abusive message gets a firm, calm boundary or a hand-off to a person, then re-run the five tickets.
Still broken: An abusive message (R8KD3F) gets a calm, normal resolution, as if nothing was said, because the agent has no tone rule yet.
Lever: <cost | speed | intelligence>

## Priya asked

Costs:
Wrong:
Runs it:
Left out:
