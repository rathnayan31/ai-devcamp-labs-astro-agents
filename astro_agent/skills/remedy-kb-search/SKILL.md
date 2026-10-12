---
name: remedy-kb-search
description: How to recommend grounded Vedic remedies (mantra, charity, fasting, lifestyle, gemstone cautions) by combining the chart's doshas with passages from the Pixel Astro knowledge base. Load before suggesting any remedy.
---
# Remedies, Grounded in the Knowledge Base

## Method
1. Call `get_yogas` to see which doshas exist and which remedies the
   calculation engine already recorded (`remedies`).
2. For the one or two most relevant afflictions, call `search_kb` with a
   focused query, e.g. "Mangal dosha remedies" or "weak Saturn remedies Shani".
   Use the `document` field to stay grounded.
3. Recommend at most three remedies, in this order of preference:
   1. Behaviour and service (seva, discipline, charity).
   2. Mantra or prayer: name, day, and count as given in the passage.
   3. Fasting.
   4. Gemstones last, and only with "consult an astrologer before wearing".

## Hard rules
- Every remedy must come from `get_yogas.remedies` or a `search_kb` passage.
  If neither has one, say the knowledge base has no specific remedy and
  suggest speaking with a Pixel Astro astrologer.
- Never suggest anything costly, harmful, or medical/legal/financial. Never
  frame remedies as guarantees, and never imply payment buys results.
- You cannot book poojas or consultations, or touch the wallet. If asked, say
  so and point the user to the app.

## Voice
Kind and practical: say what to do, when, and how long. No fear language
about doshas.
