---
name: kundali-compatibility
description: How to explain Ashtakoota (36-guna) kundali matching results, doshas such as Nadi, Bhakoot and Manglik, and overall compatibility. Load before answering any matching or relationship-compatibility question.
---
# Kundali Compatibility

## Getting the data
1. Both people need a saved kundali. Use `list_my_kundalis` to find them. If
   only one exists, ask the user to create the partner's kundali in the app.
   Don't guess the partner's chart.
2. Call `match_kundali` with `boy_kundali_id` and `girl_kundali_id`.

## Interpreting the result
- Report the total as "X out of 36" using `match.score` / `match.totalPoints`
  exactly as returned.
- Rough bands, said in words rather than as a table:
  - Below 18: weak; needs care.
  - 18 to 24: average; workable.
  - 25 to 32: good.
  - Above 32: excellent.
- Gunas carrying the most weight: Nadi (8), Bhakoot (7), Gana (6) and Graha
  Maitri (5). A zero in Nadi or Bhakoot matters more than the total.
- Doshas: mention only those in `match.doshas`, with their status. A
  cancelled dosha must be described as cancelled.
- Close with the single most important strength and the single most important
  challenge from `match.strengths` and `match.challenges`.

## Hard rules
- Never invent guna scores or recompute them.
- Compatibility is a guide, not a verdict on whether two people should marry.
  Never discourage or encourage a marriage outright.
