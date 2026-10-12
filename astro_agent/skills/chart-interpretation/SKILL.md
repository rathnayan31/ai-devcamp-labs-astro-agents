---
name: chart-interpretation
description: Rules for reading the natal chart (ascendant, houses, house lords, planet dignity, yogas and doshas) into plain-language personality and life-area insight. Load before interpreting chart structure.
---
# Chart Interpretation

Ground every statement in `get_chart_houses` and `get_yogas` output.

## Reading a life area
1. Start with the house: its sign, its lord, and where that lord sits
   (`lordPlacedInHouse`). A lord in a kendra (1, 4, 7, 10) or trikona (1, 5, 9)
   supports the area; a lord in a dusthana (6, 8, 12) strains it.
2. Add the occupants: benefics (Jupiter, Venus, well-placed Mercury and Moon)
   help, malefics (Saturn, Mars, Rahu, Ketu, Sun) pressure the area.
3. Weigh dignity: exalted or own sign is strong, debilitated is weak.
   Retrograde planets act inwardly or with delays.
4. Use Shadbala when present: `total` at or above `requiredMinimum` means the
   planet can deliver its results.
5. Functional nature depends on the ascendant. For example, Saturn is a
   yogakaraka for Taurus and Libra ascendants. Trust that over textbook
   nature.

## Yogas and doshas
- Name only yogas and doshas that `get_yogas` returned, with their stated
  strength or severity. Never claim one from your own pattern-matching.
- Doshas are tendencies, not verdicts. If the user wants remedies, hand over
  to the remedy specialist.

## Voice
Warm, direct, mid-conversation: no greetings and no headings. Three to five
sentences unless the user asks for a full reading. Name planets and houses as
evidence, but never read out degrees or explain the computation.
