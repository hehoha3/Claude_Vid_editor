---
name: create-doc-mov
description: Write an original full-AI mountain wildlife survival film (8–15 minutes, chosen to fit the story), built on the channel's narrative DNA (rotating archetypes — migration, lost survivor, predator's quest, mother & young, battle for the throne — dual peril, triangle hook, ticking clock, chokepoint, early role reversal), with a 30s dramatic hook, 30s introduction, dense English narration, full Vietnamese translation and four synchronized Markdown files. Use for /create-doc-mov Chann_N (recommend trending concepts for that channel), /create-doc-mov Chann_N <youtube link> (adapt a reference video into a clearly different film, asking about the cast), /create-doc-mov <video-folder> <minutes> <concept>, or any request to create, brainstorm, adapt or revise a wildlife story, concept, hook or script — including when the user just pastes a YouTube wildlife link and wants "something like this". Stop before voice generation; the user generates the numbered MP3s.
---

# Create a mountain survival story

## Cost discipline (why this skill is shaped the way it is)

A run is billed three ways: tokens Claude writes (story.json is ~90% of them), tokens re-read every turn (each extra tool round trip re-reads the whole conversation), and vidIQ credits. So: batch independent calls into one turn, write the story once in compact form, fix with small Edits, and never pull large files into context.

- Read in one parallel batch, once: [narrative-dna.md](references/narrative-dna.md), [storycraft.md](references/storycraft.md), [source-contract.md](references/source-contract.md), plus [sourcing.md](references/sourcing.md) for `Chann_N` modes. Do not open `examples/*.json`, `input/*.md`, sibling `story.json` files or [reference-analysis.md](references/reference-analysis.md); their useful content is already distilled here or returned by `next-video`.
- vidIQ: at most one call per run (trend outliers *or* a reference transcript). No balance checks; on a credit error, fall back to the YouTube API (sourcing.md).
- Don't web-search by default. Narrate observable behavior and story-framed time ("weeks without a kill") rather than statistics; search only for a specific factual claim you decide to keep.
- After build, don't Read the four generated Markdown files: they are compiled from the source you just wrote. Review from the source and the build summary.

## Entry modes

| Invocation | Turn plan |
|---|---|
| `/create-doc-mov Chann_N` | ① parallel: `next-video`, `youtube-trends`, optional 1 vidIQ outliers call, the reference reads ② one AskUserQuestion: concept + cast ③ init + write ④ build/validate, fix ⑤ report |
| `/create-doc-mov Chann_N <youtube_url>` | ① parallel: `next-video`, `youtube-reference`, 1 vidIQ transcript, the reference reads ② short reference summary + one AskUserQuestion: cast (+ runtime) ③–⑤ as above |
| `/create-doc-mov <video-folder> [minutes] [concept]` | Classic: reads, init, write, build, report. No questions unless the concept is missing |

Details for the `Chann_N` modes (fallbacks, adaptation rules, cast question, runtime choice) are in sourcing.md. Don't create the folder before concept and cast are approved; those are the only questions to ask before writing.

## Writing

1. **Folder and runtime.** Use `next_video` from `next-video` (or the user's folder). Runtime 8–15 minutes from how many real turns the story carries; an explicit user number wins; longer than 15 only on request. Runtime includes both opening sections. Run `python -m dvr_cowork init "<video>" --minutes <m> --title "<title>"` once. Keep the default Resolve project name (`vid_DDMMYY_N`, shared by the same-numbered video of every channel). Existing source: revise the source, not generated outputs. Once voice or shots are issued, preserve that version; use a new folder for an incompatible rewrite.
2. **Design before prose.** Record the archetype (from concept/reference, else `next_archetype`). Fix the lead's motive, the dual peril (living threat + natural force that interact), the ticking clock, the chokepoint and the role-reversal moment; if one is missing, the story sags. One central survival question, a clear visual payoff, a cause-and-effect beat outline, cast IDs with exact counts and readable markings, geography/route and consistent light. Hunger/safety motives without invented claims about animal thoughts. Label it an AI dramatization.
3. **Hook and setup.** 00:00–00:30: five 6s unresolved danger placeholders with continuous narration. Complete the triangle hook by ~00:18 (arresting visual, one specific stakes sentence opening the narration, natural sound in the candidate shot's beats); tease the role reversal at 00:24–00:30 without its result. 00:30–01:00 setup establishes place, individuals and route while advancing danger; it doesn't repeat the hook's narration or resolve its promise.
4. **Budget voice per scene before writing it.** Words per scene ≈ scene seconds × wpm/60 × 0.88 (145wpm → ~2.1 words/s: a 60s scene ≈ 125–130 words, a 30s scene ≈ 60–65). Spread them over 2–4 blocks per minute so no pause exceeds 3s. Getting this right first time is the main way to avoid rebuild loops.
5. **Write story.json compactly** (shapes in source-contract.md): put `camera`/`direction`/`characters` on the scene when shots share them; omit `beats` for routine shots (the compiler derives four from `cause`/`action`) and write explicit beats only for hook candidates, the role reversal, the chokepoint and complex motions. Keep each field one short clause. Every scene changes the situation; every shot has one action, cause, start/end state, 6–9s, and every scene's shots cover its duration exactly. Give `hook_role` + `spoiler:false` only to strong unresolved body moments, with at least one candidate each for threat, vulnerability, pursuit, obstacle, unanswered; the hook narration must stay true for any of them. Voice: naturally connected English paragraphs + complete Vietnamese, **one block = one nonblank transcript line = one MP3**. Write the file in one Write; for films over ~11 minutes write the first half, then append the remaining scenes with one Edit, so no single call is huge.
6. **Build and validate in one command:** `python -m dvr_cowork build "<video>" && python -m dvr_cowork validate "<video>"`. The compiler stops at the first error: fix that scene with a targeted Edit (never rewrite the file) and rerun. Then check, from your source, that the hook/setup narration matches visible events and the payoff, and (adaptations) that the outline doesn't follow the reference's beat order. The compiler checks numbers; you judge narrative quality, originality and factual claims.
7. **Report** in Vietnamese: concept; archetype with motive/dual peril/clock/chokepoint/reversal one line each; (adaptation: one line kept vs changed); brief opening/story summary; actual runtime/word/voice-block/shot counts from the build output; links to the four Markdown files; where to save `audios/mp3/1.mp3…N.mp3`. **Stop**: no voice generation, shots or Resolve editing.

When the user returns with voice, route to doc-edit; don't rewrite approved narration to hide a timing problem.
