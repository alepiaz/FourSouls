# Base Game V2 audit

Coverage checkpoint: 7 of 340 official catalog entries have a source-reviewed ability breakdown below. Engine support is assessed against the Sprint 14 branch. Complete coverage requires a reconciled catalog, a disposition for each entry (including cards without an ability), and an engine/test reference for each supported ability.

[Official set index](https://foursouls.com/cards/) · [Set filter](https://foursouls.com/card-search/?origin=b2)

| Card | Timing / cost | Target | Effect | Engine assessment |
|---|---|---|---|---|
| [Wizoob](https://foursouls.com/cards/b2-wizoob/) | Own death | Active player chooses player; chosen player selects own soul | Destroy selected soul | Shared selector and effect verified by isolated probe; card flow pending |
| [Portal](https://foursouls.com/cards/b2-portal/) | Own death | Active player | Require an additional attack | Review unrestricted attack obligation; existing forced effects bind the attack to the deck or a slot |
| [Box!](https://foursouls.com/cards/b2-box/) | Tap; must successfully destroy itself | Self and controller | Unlock unlimited additional loot plays through end of turn | Pending conditional self-destruction and unlimited allowance |
| [The Curse](https://foursouls.com/cards/b2-the_curse/) | Controller turn start | Top of a deck | Move to discard | Compare existing turn-start hook and verify deck choice |
| The Curse | Tap | Top of a discard pile | Return to corresponding deck top | Pile selection and movement require verification |
| [Secret Room!](https://foursouls.com/cards/b2-secret_room/) | Event roll | Resolving player | Branch into self-damage, loot discard, coin gain or treasure gain | Existing branch runner is synchronous; verify discard choice and treasure resolution |
| [Book of Belial](https://foursouls.com/cards/b2-book_of_belial/) | Activate in response to a roll | Pending roll | Modify result by either +1 or −1 | Sprint 15 roll targeting and modifier choice |
| Book of Belial | Controller turn end | Self | Recharge | Verify item configuration against end-of-turn recharge mechanism |
| [The Bone](https://foursouls.com/cards/b2-the_bone/) | Tap | Self | Add a counter | Verify existing counter support against an activated effect |
| The Bone | Spend one counter | Pending roll | Add one to result | Pending counter costs and roll control |
| The Bone | Spend two counters | Player or monster | Deal one damage | Existing damage paths; counter cost and shared monster targeting need verification |
| The Bone | Spend five counters | Self | Convert item to soul and remove abilities | Pending zone conversion and ability cleanup |
