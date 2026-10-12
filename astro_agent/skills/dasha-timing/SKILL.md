---
name: dasha-timing
description: How to time life events (marriage, children, career, wealth, property, foreign travel) from Vimshottari dasha periods and transits. Load before answering any "when will…" question.
---
# Dasha Timing

You answer timing questions from tool output only: `get_dasha_periods` (and
`get_transits` when the question is about the present or the next year or two).

## Method
1. Identify the significators for the event. Read
   `references/life-event-significators.md` for the house / lord / karaka table.
2. Call `get_chart_houses` if you need the house lord's name, then call
   `get_dasha_periods` with `planets` set to those significators so their
   antardashas come back expanded.
3. Pick the ONE strongest window: the mahadasha or antardasha of the house lord
   or karaka, preferring windows where both MD and AD planets are significators.
4. Compare the window with the native's current age (from `today` and
   `dateOfBirth` in the tool result) and choose the tense:
   - Window entirely in the past, or the person is past the usual age for a
     one-time event: lead with "this may well have already happened", name the
     window, then give the next window, and ask them to confirm.
   - Window contains today: "this is an active, supportive period right now".
   - Window in the future: give the age range AND years, tied to the dasha.
5. Transits only fine-tune a dasha window. Always say transit data is a
   snapshot as of `computedAt`.

## Hard rules
- Children are never timed earlier than marriage for the same person.
- Quote only years, ages and planet names that appear in tool output. If the
  dasha timeline is missing (`missing` contains `vimshottariDashas`), say the
  timeline isn't available. Do not estimate one.
- Never read out degrees, longitudes, padas or how a period was computed.

## Answer shape
Three to five sentences: the window (age + year + dasha), the single strongest
reason, and one natural follow-up question.
