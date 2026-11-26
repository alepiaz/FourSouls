# Effect inventory

This snapshot covers the Sprint 14 interactions and selected architecture probes. Base Game V2 is the initial corpus for the full audit. Rows describe simulator support, not authoritative printed wording.

| Card or probe | Trigger / cost | Chooser and target | Effect and duration | Support | Coverage |
|---|---|---|---|---|---|
| Butter Bean | Play loot / loot allowance | Acting player, live stack item | Remove the target from the stack | Loot-specific path | `tests/acceptance/test_sprint14_acceptance.py` |
| Soul Heart | Play loot / loot allowance | Acting player, player or monster slot | Grant a damage shield until consumed or cleared | Loot-specific path | `tests/acceptance/test_sprint14_acceptance.py` |
| Bomb! | Play loot / loot allowance | Acting player, player or monster slot | Deal damage, consuming applicable shields first | Loot-specific path | `tests/acceptance/test_sprint14_acceptance.py` |
| Carrion Queen | Incoming combat damage on 4 or 5 | Automatic, self | Prevent the damage | Shared replacement pipeline | `tests/acceptance/test_sprint13_completion.py` |
| Headless Horseman | Would die, once per turn | Automatic, self | Prevent death, heal, and modify stats until end of turn | Shared replacement pipeline | `tests/acceptance/test_sprint13_completion.py` |
| Wizoob probe | Simulated death trigger | Choose player, then that player chooses a soul | Destroy the chosen soul | Shared primitives verified in isolation | `tests/unit/test_trigger_pipeline.py` |
| Cursed Gaper | Resolved roll | Automatic group targeting | Temporary group stat modifier | Universal roll event and group application pending | Pending |
| Death’s Head | Static and linked death behavior | Automatic | Attack restriction and linked removal | Static legality and death linkage pending | Pending |

For each new row, record the card source and variant, event, conditions, cost, target and chooser, atomic effects, duration, usage limit, support status, and regression test. Mark support as shared, card-specific, isolated probe, or pending. Verify card wording against its source before treating the row as an implementation specification.
