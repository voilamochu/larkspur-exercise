# Client review: Larkspur disruption-care agent

**To:** Room 17  
**From:** Larkspur client review agent, on behalf of Priya Raghavan  
**Re:** the disruption-care agent you walked us through in our last session  
**Generated:** 2026-11-19 03:43

## Priya's note

> Our vendor says we should just be using your best model.
>
> Why aren't we?
>
> Priya Raghavan, Larkspur Airlines

She sent that before this session opened. She means it. A vendor told her to buy
the biggest model, and she has a number to defend upstairs. Her four questions from
day one are still open. Naming a model answers none of them.

## Still open from day one

| Her question | What she means by it |
| --- | --- |
| **What it costs** | Per resolved contact, against the $6.90 a human contact costs us. |
| **When it is wrong** | The first untrue thing it says, and what happens after that. |
| **Who runs it** | In June, after you have left. |
| **What you left out** | The scope you cut, and why. |

## What the review agent found

Larkspur pointed a review agent at your repository. It read the
code. It did not run your agent, and the only file it changed is this one. Each
item below names the file and the line it is about.

**1. agent.py search_alternatives: the 6-character description "search" is now a 327-character description, and hold_seat is still 73.**

Your diff rewrote search_alternatives to say it runs only after lookup_booking and get_flight_status show a cancelled, delayed or misconnected segment, and that it does not book or hold anything. hold_seat still reads "Place a 15-minute hold on one alternative. Reversible. It simply expires." at 73 characters, and send_confirmation is 71. Nothing in the repository shows whether the search_alternatives rewrite changed which tool the model picks.

Run python3 run.py --all --trace and paste the totals footer, then run python3 verify.py 1.3 and paste its result.

**2. agent.py run_agent: the loop now returns text_of(response), but MAX_TOOL_CALLS = 8 is untested against a booking that needs more turns.**

The diff changes the assistant message to response.content and the return to text_of(response), so tool_use blocks round-trip and the last turn's text comes back. The while loop exits when turns reaches 8, and at that point response.stop_reason may still be tool_use, so text_of(response) can return an empty string. Your only committed wire run in readout-trace.json used 4 API turns and 6 tool calls, so the cap has not been hit in any run you banked.

Run python3 run.py --all --trace and paste, for the booking with the most tool calls, the turn count and what the final answer string was.

**3. agent.py tool_list(): you offer 17 tool schemas (the pack ships 9), and your only committed wire run called 6 of them.**

Eight EXTRA_TOOLS (reopen_stats through what_automation_will_not_do) plus the MCP tools sit alongside the nine from build_tools(), all sent on every turn. The readout-trace.json run shows 26340 tokens in for 4 turns and 1101 out. Of the six tools called, only next_available_day and cause_in_plain_words are additions, and none of the other six added executors appears in that run. Nobody has measured what the extra schemas cost per turn or whether they change which tool gets picked.

Run python3 run.py --tool-tax and paste its output next to the 26340 tokens in figure from readout-trace.json.

**4. agent.py: cache_control appears nowhere and readout-trace.json shows 0 cache read, 0 written, hit ratio None.**

Every call in run_agent resends runtime_preamble() + SYSTEM_PROMPT + TONE_ADDENDUM and the full 17-schema tool list. That prefix is identical across the 4 turns in your trace and across bookings, and none of it is cached. The 26340 input tokens in a 12.8s run are the number Priya's model question has to be argued against, and a different model would not change a hit ratio of None.

Run python3 bench.py --label before --stage 1 --runs 3 and paste the output, so the token and latency baseline exists before anything is changed.

**5. Repository: no evals/cases.json, PITCH.md blank apart from its template labels, and banked gates stop at 2.2.**

readout.html banks 1.2, 1.3, 1.4, 2.1, 2.2, and the scan lists nothing for 3.1 or 4.1. TONE_ADDENDUM is 0 characters. The repository contains no eval case, so no sentence about how often the agent is right can be backed by a file today. Several given files also differ from the shipped pack, including verify.py, eval_harness.py and bench.py, which changes what any number from them means.

Run python3 eval_harness.py and paste the full output, and run python3 verify.py 3.1 and paste its result.

## Your four answers

The four lines under `## Priya asked` in your PITCH.md are still empty. They
are one line each and they are not a coding job: cost, what happens when it is
wrong, who runs it in June, and what you left out. Whoever on your side is not
editing agent.py is the right person to write them, and they are the four
things I will ask about first.

## Before our next meeting

> Before our next meeting, tell me: which model should we be on, and how will you prove it is the right call?
>
> Priya Raghavan, Larkspur Airlines

Bring two things. A recommendation, and the measurement behind it. If the model is
not the problem, say so, and bring the number that shows it.

## What this review read

- `agent.py (597 lines)`
- `PITCH.md`
- `TEAM.md`
- `readout-trace.json`
- `readout.html (evidence block)`
- given files that differ from the shipped pack: `verify.py`, `eval_harness.py`, `bench.py`, `readout.py`, `setup.py`, `pod_sync.py`, `run.py`, `review.py`, `support/__init__.py`, `support/client.py`, `support/data.py`, `support/models.py`, `support/tools.py`, `support/trace.py`, `support/offline.py`, `support/mock_backend.py`, `support/mcp_client.py`, `support/mcp_server.py`, `support/mcp_selftest.py`, `support/access.py`, `support/keyscan.py`, `support/review.py`

Reviewer: `claude-sonnet-5-5`. Static read only: nothing in this repository was executed, and nothing was modified except this file. Larkspur Airlines is a fictional training scenario. Confidential, do not distribute.
