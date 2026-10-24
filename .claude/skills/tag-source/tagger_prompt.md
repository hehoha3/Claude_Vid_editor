You tag wildlife documentary clips for an editor. Read the file .work/tag_source/{BATCH}.json (cwd = the workspace root).
  For EVERY row, open its "image" with the Read tool and look at it before
writing anything (open all images of the batch in ONE message: parallel Read calls, not one per turn): a 2x2 contact sheet of 4 frames from one clip, numbered 1-4 (top-left, top-right,
bottom-left, bottom-right) in time order. Tag only what you SEE. "folder" is the user's sorting (usually
the main animal) - use it to name the species when the image agrees; never tag from title_hint or the
file name alone.

Write .work/tag_source/{BATCH}_result.json: {"<id>": {...}, ...} with exactly these keys:
 species: list of common names, lowercase singular ("jaguar", "capybara", "howler monkey", "lion", "wildebeest",
          "hippo", "rhino"); [] if none. "folder" null = no hint, name what you see. Species names only, no
          sex/age words ("lion", not "lioness"/"cub"; "elephant", not "calf"; put those in the caption).
          The main animal = the folder name (singular, e.g. folder "Eagle" -> "eagle") unless the image
          clearly shows a different kind of animal (folder jaguar, image a monkey). Do not narrow it to a
          sub-species from a silhouette. Folders landscape, bird(s), insects are not a species: name what you
          see (birds: e.g. "toucan", "parrot", "kingfisher"). Add other animals you see (prey, background).
 count: none|one|two|few|many   (animals in frame)
 action: only what clearly happens in the frames (mouth or hands in water = drink; still animal looking around =
         look). List from rest, sleep, look, walk, run, stalk (moving slowly, low, toward prey), hide (body low or
         behind cover, still, watching: an ambush, not a nap), chase (predator pursuing prey at speed), catch
         (predator grabs, holds or brings down live prey), attack, eat, feed (adult feeding its young only; nectar,
         fruit, prey = eat), drink, swim, fly, perch, climb, hang, jump, fight, groom, play, call, carry_young, none.
         Lying with the head down or eyes closed = rest / sleep, never hide.
 phase: list of 4 actions, the main subject's action in frame 1, 2, 3, 4 (same words as action), e.g.
        ["hide", "hide", "chase", "chase"]
 sex: female|male|mixed|unknown   (the adults of the main animal: "lioness" female, a mane = male; mixed = adult
      females and males in frame; young of unseen sex do not count (lioness + cubs = female); unknown when the
      frames do not show it - never guess from the species)
 age: adult|young|mixed|unknown   (young = calf, cub, foal, juvenile clearly smaller than the adults; mixed =
      adults with young)
 outcome: none|miss|catch|kill|unknown   (predation only: catch = predator holds / brings down live prey, kill =
          prey visibly dead or a carcass, miss = the attack visibly fails, prey escapes; unknown = the end is not in
          the frames; none = no predation in the clip)
 shot_size: extreme_close|close_up|medium|wide|aerial   (size of the main subject; landscape -> wide/aerial)
 angle: eye|low|high|top_down   (camera looks up at the subject, sky behind it = low)
 camera: static|moving   (background shifts between frames = moving)
 light: day|golden|dusk|night|moon
 setting: list from canopy, forest, forest_floor, undergrowth, river, riverbank, lake, swamp, waterfall,
          underwater, grassland, rock, cave, sky, moon, mountain, village, savanna (open African grass/bush with
          scattered trees, acacia), waterhole, desert
 weather: clear|mist|rain|storm|none
 mood: calm|tense|dramatic|playful|majestic|eerie
 direction: left|right|toward|away|none   (way the main subject moves or, if still, faces on screen)
 good: frame numbers (1-4) usable in an edit: subject clear, sharp, no AI deformation, no logo/text
 issues: list from logo, text, morph (only when "source" is "ai": melted limbs, extra legs, warped faces;
         real camera footage never morphs - motion blur there is "blur"), unnatural (anything a real wildlife
         camera would never film: butcher-cut meat, plastic-looking food, impossible pose or situation, wrong
         anatomy for the species), blur, dark,
         watermark, frame_cut (subject cut by the frame edge)
 caption: one plain sentence an editor can search, e.g. "Jaguar stalks through dense undergrowth at
          night, close on its face"; name sex / age when visible ("lioness", "male lion", "wildebeest calf")
 sure: true if the image is clear, false if you are guessing (tiny or dark subject)
Retag rows: a row with "fields" (e.g. ["sex", "age", "phase"]) was tagged before; open and look at its image all
the same, then write ONLY those keys for it. "old_caption" is the earlier tagger's sentence: context, the image decides.
Use only the listed words. Reply with one line: "<n> clips tagged".
