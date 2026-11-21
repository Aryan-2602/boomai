# Boom Advisor Digest — POC (v0)

## Goal
Turn `data/boom_test_students_50.csv` into a ranked, per-advisor digest. Each flagged student shows
(1) WHY they're flagged, citing the actual field values, and (2) a suggested message that fits their
primary blocker. Advisors review and send messages themselves; nothing is sent automatically.

## v0 scope (keep it boring)
- Pure Python 3.11+, standard library + pandas only. No LLM, no web app, no database yet.
- Rules-based detection → simple scoring → template messages → Markdown output.
- One command: `python -m boom.digest --csv data/boom_test_students_50.csv --as-of 2026-11-19 --out out/`
- Output: `out/<advisor_slug>.md` per advisor + `out/summary.md` (counts by barrier and tier).

## Layout
```
src/boom/
  load.py       # read CSV, parse dates, keep blank LMS fields as None (NOT 0)
  barriers.py   # one small function per detector -> list[Barrier]
  rank.py       # tier + score + sort
  messages.py   # template per primary barrier + channel suggestion
  render.py     # markdown per advisor
  digest.py     # CLI entrypoint
tests/
  test_barriers.py
```

## Data model
```python
@dataclass
class Barrier:
    code: str        # e.g. "REG_HOLD"
    label: str       # human-readable, e.g. "Registration hold"
    weight: int      # contribution to score
    evidence: str    # built from real field values, e.g. "Unpaid balance hold since 2026-10-12 (38 days)"
```

## Detectors (v0)
| Code | Rule | Weight |
|---|---|---|
| REG_HOLD | `registration_hold == "Y"`; evidence includes `aid_hold_type` + days since `aid_hold_since` | 40 |
| NOT_REGISTERED | `registered_for_spring == "N"` AND no registration hold | 20 |
| ACADEMIC | `lowest_current_grade in {D, F}` OR `missing_assignments >= 3` | 20 |
| DISENGAGED | `lms_logins_last_14_days <= 3` AND ACADEMIC is true (low logins alone is NOT a flag) | 15 |
| DATA_GAP | LMS login fields blank → "Can't assess engagement; check Canvas sync" | 0 (separate section) |
| OUTREACH_NO_REPLY | `outreach_response == "No reply"` → suggest a different channel | 10 |
| OUTREACH_REPLIED | `outreach_response == "Replied"` → next step is "follow up on their reply" | 0 |
| STALE_CONTACT | `last_advisor_contact` more than 60 days before as-of date | 10 |

## Ranking
- Tier 1: blocks spring registration (REG_HOLD or NOT_REGISTERED).
- Tier 2: ACADEMIC / DISENGAGED without a registration blocker.
- Data gaps: listed in their own section, not ranked.
- Within a tier: sort by score (sum of weights), then by hold age in days.

## Messages
- One template per primary barrier (highest-weight barrier). Fill slots only from the row:
  first name, advisor name, one concrete next step.
- Supportive tone ("want to make sure nothing's in your way for spring"), never "at risk".
- Privacy: NO GPA, grades, or hold dollar amounts/types in SMS text. Email may say "an item on your
  account" but nothing more specific.
- Channel: if last outreach got no reply, suggest a different channel (email → SMS → phone call).
- If the student replied, the suggested action is "follow up on their reply", not a new cold message.

## Acceptance checks (must pass; these were checked by hand against the CSV)
- 12 students have REG_HOLD. Six of them also have ACADEMIC + DISENGAGED + no reply:
  S100100, S100101, S100102, S100103, S100104, S100105 → they make up the top of Tier 1.
- Hold only (fine academically): S100106–S100111.
- NOT_REGISTERED without a hold: S100124, S100125, S100126, S100127, S100128.
- ACADEMIC with no registration blocker: S100112–S100119 (S100119 is ACADEMIC but not DISENGAGED: 4 logins).
- Replied → follow-up action: S100114, S100118.
- DATA_GAP: S100129, S100130, S100131.
- Must NOT be flagged (low logins but doing fine): S100120, S100121, S100122, S100123.
- 22 students total have no flags.

## Not in v0 (later iterations)
LLM tone pass + fact-check guard, HTML digest, configurable thresholds, approve/edit queue, outcome tracking.