from __future__ import annotations

from foursouls.model.refs import CardId

# Base-game character card IDs.
# In this implementation all characters share the same activated ability:
# tap -> gain one extra loot play this turn.

ISAAC     = CardId("ISAAC")      # 4 HP
MAGDALENE = CardId("MAGDALENE")  # 6 HP
CAIN      = CardId("CAIN")       # 4 HP
EVE       = CardId("EVE")        # 2 HP
