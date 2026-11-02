# YouTube SEO: title, description, tags

Credentials: `.secrets/youtube/` (ignored) — `client_secret.json`, `tokens/<channel_id>.json`, `channels.json` (`Chann_N` → ID). Never print them. The channel comes from the video folder `D:\Chann_N_*\<video>`; `youtube-channels` lists every token's live name and key.

| Key | Folder | Channel |
|---|---|---|
| Chann_1 | D:\Chann_1_shadowCanopy | Shadow Canopy (UCt14EsPBuUxeFbTeHKK0E6Q) |
| Chann_2 | D:\Chann_2_UntamedEmpire | Untamed Empire (UCtWpq3WyZlVrCWt4m-LR75g) |

## Flow: two commands, one small draft

1. `youtube-seo <video>` prints film facts (premise, payoff, cast, chapters from plan.json) and a trend digest: top titles by views/day, title patterns, view-weighted words and frequent tags. Default queries come from the cast (`<sp1> <sp2>`, `<sp1> wildlife documentary`), ~202 quota units, cached 7 days (0 units on a rerun). If the cast names are too niche and the digest is thin, rerun once with `--query "snow leopard mountain goat" --query "..."` the way creators title the niche. Read only this stdout; don't open other files.
2. Write `.production/seo_draft.json` (the only text you author, ~1k tokens):

```json
{"titles":["<full title 1>","<full title 2>","<full title 3>"],"pick":1,
 "hook":"2–3 sentences: the hook stakes with main keywords; this is what shows above 'more'.",
 "summary":"2–3 sentences of story without the payoff.",
 "tags":["snow leopard vs ibex","snow leopard hunting mountain goat","..."],
 "hashtags":["#wildlife","#snowleopard","#animalsurvival"]}
```

   Optional `"chapters"`: one name per printed chapter, same count and order; omit to use the scene titles.
3. `youtube-seo <video> --write` builds `youtube_meta.json`: each title is checked as `<story line> | <label>` (≤100 chars) and kept as written; description = hook, summary, chapters, the story's AI disclosure, hashtags; tags deduplicated and trimmed to 500 chars. Fix every `FLAG` line (animal not in the cast, <3 chapters, URL) and rerun `--write`.

## Writing the 3 titles

Titles must look like the user's three reference videos, written in full (the code adds nothing):

- `Snow Leopard Hunts a Mother Mountain Goat and Her Baby on a Deadly Cliff | Wildlife Documentary`
- `Snow Leopard vs Mother Ibex and Her Baby on a Deadly Cliff | BBS Earth Explore` (label = that channel's name)
- `A Baby Chamois Is Born as Snow Falls… Can It Make It Through Its First Night? | Wild animals`

Only two story-line shapes, both plain title case, no ALL CAPS, no emoji:

1. **Clash** — `<Predator> Hunts / vs <Mother|Lone|Young> <Prey> [and Her Baby] on a <Deadly Terrain>`: predator first, both species, the vulnerable relationship, the place. A statement, no question.
2. **Vulnerable moment + survival question** — `A <Baby|Young|Lone> <Prey> <situation as it happens>… Can It <survive the concrete test>?`: one present-tense situation, an ellipsis "…", then a yes/no question about a specific test (first night, the crossing, the storm).

Label after ` | `: `Wildlife Documentary`, `Wild Animals`, or the uploading channel's name (`Shadow Canopy` / `Untamed Empire`). Story line ≤ ~80 chars, whole title ≤100. No "The X Who…" character titles, colons or numbers-lists; they aren't the channel's style. Offer 3 titles (both shapes represented), ranked by expected clicks, reusing the words the digest shows earn the most views.

Name both animals with searchable common names first (ibex/markhor/chamois may be called "mountain goat"). Include the vulnerable relationship and the terrain. Every title must be true to the film: no species, kill, fight or "only / first / biggest" claim the film doesn't show, and the payoff stays hidden. Don't copy a competitor's title verbatim. Set `pick` to the best true title by click pull plus fit to the whole film, not by trend order.

## Tags

20–30 lowercase phrases: specific pair tags first, then species, then the broad niche tags from FREQUENT TAGS (`wildlife documentary`, `animal survival`, `predator vs prey`, `mountain wildlife`). Never use other channels' names or animals that aren't in the film; misleading tags break YouTube's spam policy.

## Reply

The 3 titles best first, the one used plus one line on why (the user can switch: edit `pick`, `--write` again), FLAG fixes, quota used. Then the `youtube-upload` preview per SKILL.md. After upload remind: set the thumbnail and "Thông tin tài sản / Altered content" check in Studio; unaudited API projects stay private.
