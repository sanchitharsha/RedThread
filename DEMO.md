# Redthread demo kit (about 4 minutes)

**Disclosure to state out loud:** the shop is a sandbox we built and control. It is labelled as such on every page and in the UI. We do not claim real retailers, global coverage, or "AI-verified". Official data is real (CPSC recall 26419, Fisher & Paykel gas ranges).

**Recorded run rule:** a replay always shows the "Recorded run" badge and is always called a replay. Never present it as live. If a live run stalls past 60 seconds, say so and switch.

## Script

| Time | Screen | Say | Who |
|------|--------|-----|-----|
| 0:00 | Slide: one recall notice | "A recall notice describes one product. The people who must act need to know which listings it touches, and how sure we are. Today that is hours of manual searching." | M4 |
| 0:25 | Start screen. Recall 26419, sandbox shop. Point at the Sandbox shop badge, press Investigate | "We start from a real CPSC recall. The shop is a sandbox we control, and it says so. Real shops block automation and have terms we respect." | M4 |
| 0:50 | Live view: official record, browser opens the notice | "Official data first. Then the browser agent opens the notice itself, because the model numbers are in the notice text, not in the API fields." | M1 |
| 1:30 | Agent searches the shop and opens listings; graph grows | "Nobody scripted these clicks. The agent chooses which results to open and how to reach the spec tab. It has a domain allowlist and a step budget." | M1 |
| 2:15 | Extraction tab: ticks and crosses, verdict chips appear | "The AI reads pages but cannot decide. Every field needs a quote that code finds in the page. Verdicts come from rules." | M2 |
| 2:45 | A look-alike marked Related (e.g. the sibling model); open the reason | "Same brand, near-identical model. We do not call it recalled. It is Related, and here is why." | M2 |
| 3:10 | The bot-check listing marked Unresolved | "This page blocked us. We report Unresolved. We do not try to get around it, and we do not guess." | M2 |
| 3:35 | Click a graph line: evidence drawer. Then View exposure report | "Every link opens its source, quote and time. The report ends with what we did not check." | M3 |
| 4:05 | Slide: limits and next steps | "US CPSC data, one sandbox shop. We never say a product is safe. Next: more authorities and monitoring." | M4 |

Optional, only if rehearsed: show the listing with hidden instructions and the agent ignoring it; turn off Wi-Fi and run the replay (badge: Recorded run).

## Judge Q&A

- **Why a browser agent when CPSC has an API?** The API gives the official record. The model numbers, date codes and listings only exist on web pages, so the agent reads those.
- **How do you stop false matches?** Identifiers decide, never name similarity. Both sides need a verified quote, the brand must agree, scope is checked, and the LLM never sets a verdict. A golden test with zero false Confirmed gates the build.
- **Is the shop real?** No. It is a labelled sandbox. The official data is real.
- **What does "No match found in checked sources" mean?** Only that nothing matched in the sources listed in the coverage panel. It is never a statement about safety.
- **Can a page trick the agent?** Page text is treated as data, the tool list and domain allowlist are the defence, and the sandbox contains a planted instruction we test against.
- **Is the verdict a probability?** No. It is a tier with reason codes.
- **Other countries / Amazon?** Not tested and not claimed.

## T-minus-60 checklist

- [ ] Pull latest main, run `make smoke`, run `make test`
- [ ] Both the Live run and Recorded run badges display; Sandbox shop badge always visible
- [ ] Run once live and once as a replay; backup video plays
- [ ] API key and quota checked, spare key loaded, CPSC fixture present (`OFFLINE=1` works)
- [ ] `python sandbox/build.py` re-run after any change to `fixtures/cpsc_sample.json`
- [ ] Two people have independently checked every Confirmed result against the official notice
- [ ] Notifications off, browser zoom and window size set, everyone knows who speaks when

## Open items before the demo (verify, do not assume)

- The API record for 26419 has no model numbers and no parsed scope; they come from the notice text. Check that `enrich_recall` fills them, or no listing can reach Confirmed.
- The API brand is a long manufacturer string; the shop shows "Fisher & Paykel". Check that the brand match accepts it.
- The recall is limited by date code (May 25 to Jan 26). The sandbox uses "August 2025" (inside) and "March 2024" (outside). Check that the date parser reads them.
- The product is a gas range with a burn hazard. Confirm the team is comfortable showing it live.
