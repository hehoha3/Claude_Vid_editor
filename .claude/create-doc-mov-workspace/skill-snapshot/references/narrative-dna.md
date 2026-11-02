# Narrative DNA: archetypes, dual peril and retention pillars

Distilled from the user's channel strategy (`input/adn_video_wildlife_content.md`) and adapted to this workspace's fixed contract. When the two disagree, the contract in CLAUDE.md wins (30s hook of five 6s slots, 6–9s shots, no gore, verified facts).

**DNA = character motive × dual peril × triangle hook.** A film without all three is a nature walk, not a survival story.

## 1. Pick one archetype

The channel rotates archetypes so consecutive videos don't feel identical. Pick the one the user's concept implies; if the concept is open, look at sibling video folders' `.production/story.json` `archetype` fields and choose the next in the cycle **migration → lost → predator → mother → throne**. Record the choice as `"archetype"` in story.json (the compiler ignores it; it exists for rotation).

| id | Archetype | Motive (what drives the lead) | Dual peril (animal + nature) | Emotional arc |
|---|---|---|---|---|
| `mother` | Mother & vulnerable young | Instinct to protect a newborn/kid that cannot yet keep up | Stalking predator + terrain the young can't cross | Tenderness → threat → sacrifice/clever defense → fragile safety |
| `migration` | Deadly-terrain migration | The group's will to reach the next range; continuity of generations | Broken terrain (gorge, river, rockfall, avalanche) + predator waiting at the chokepoint | Grandeur → chaos → loss → resilience |
| `lost` | Lost survivor | Fear and the drive to rejoin the herd | Exhaustion/disorientation + a predator closing in, often at night or in fog | Confusion → lurking danger → instinct erupts → breathless escape |
| `predator` | Predator's quest (wolf pack, snow leopard) | Winter hunger; feeding the pack/cubs | Blizzard/cold + large prey that fights back with horns | Exhaustion → tactical coordination → calm climax → respect for life |
| `throne` | Battle for the throne | Territory, mating rights, an aging alpha's last stand | Rival male + cliff/ice where one misstep ends the fight | Dominance → challenge → collapse of the old order → new balance |

For `predator`, the audience follows the hunter: its hunger is a legitimate stake, so the prey stays worthy and the ending earns respect rather than cheering a kill. Whatever the outcome, show no blood, gore or wounds; a hunt can end in a failed attempt, a retreat, or an off-screen implication.

## 2. Dual peril

Always pair a living threat with a natural one, and let them interact: the rockfall drives the herd into the wolves' gully; the blizzard hides the leopard's approach; thin ice makes the rams' clash lethal. Introduce both by 00:18 (hook) and keep both active through the body. One peril alone flattens after a few minutes.

## 3. Triangle hook in the first 15s

Within roughly H1–H3 (00:00–00:18) deliver all three corners:

- **Visual hook:** the most arresting unresolved image the body will produce — an animal teetering on a breaking ledge, glowing eyes surrounding a lone kid in fog, a herd fleeing a falling wall of rock.
- **Narrative hook:** one declarative stakes sentence in the first voice block, specific to this film. Pattern: *situation + why it's fatal + the twist that makes it worse.* E.g. "Cut off from the herd by the storm, this young ibex has walked straight into the one place that kills: a slope of loose rock — and something is already watching from above." Write it so it stays true for whichever spoiler-free candidates are later selected.
- **Audio hook:** natural sound that the generated shot itself can carry — rockfall rumble, wind howl, a low growl, hooves skidding on scree. Put it in the hook-candidate shot's beats. Designed sound (heartbeat rising, sub-bass) belongs to the A3 music decision in doc-edit, not to shot prompts, which allow natural sound only.

Archetype-specific hook openers:

- `migration`: high wide of the herd fleeing a rockfall along a cliff path.
- `lost`: close on one animal's frightened eyes in fog; predator eyes appear behind.
- `predator`: close on the lead hunter's shaking paws on ice, breath freezing; huge horned prey ahead.
- `mother`: newborn's unsteady legs at a ledge edge; predator shape above.
- `throne`: two males' horns locked on an ice-glazed ledge, one hoof slipping.

## 4. Three retention pillars

Every film needs all three, set up early and paid off later. They are what keeps the viewer when the archetype changes.

1. **Ticking clock** — a visible deadline: cross before the flood arrives, bring the prey down before the blizzard closes, reach the herd before dark. Show the clock (rising water, approaching storm wall, sinking sun) and re-show it as it shrinks.
2. **Chokepoint** — a place where escape narrows to one option: a one-hoof ledge, a fogbound gully, a snow bridge. Establish it before it matters so the climax is intelligible.
3. **Role reversal (early climax)** — the expected victim turns the tables: prey wheels and horns the predator off-balance; a rockslide separates hunter and hunted; the herd forms a horn wall. Tease it in H4–H5 (00:24–00:30), cut before its result. In the body, the first real clash starts no later than ~01:45 — right after the setup — not saved for minute six.

Role reversal is physical but non-injurious: shoves, deflections, slips, retreats. No added wounds or extra cast.

## 5. Scene-level mini arc

The user's sample scripts show a 60s pattern that works as a scene unit: **unstable situation → sudden failure (ledge cracks, attack) → improvised defense using terrain → decisive leap/stand that changes position**. Reuse the shape, not the events, and let each scene leave the situation changed for the next.

## 6. What not to copy from the strategy document

- Huge exact numbers ("500 goats", "-40°C", "30 days without food") as narrated fact. AI shots cannot keep hundreds of individuals consistent: lock 1–3 key individuals exactly and describe the herd as a background group with a stated, consistent size (prefer 20–40). Temperatures, fasting periods and behaviors must be plausible and checked, or phrased as story ("weeks without a kill"), never invented statistics.
- Prompt tokens like `8k`, `--ar 16:9`, `hyper-realistic`, or brand names (National Geographic). The compiler writes prompts from the locks; put the useful substance — fur blown by wind, breath vapor, fog density, light direction — into `characters[].lock`, `environment` and the beats.
- Its 15s/60s timings as runtime structure. Our hook is 30s, setup 30s, shots 6–9s.
