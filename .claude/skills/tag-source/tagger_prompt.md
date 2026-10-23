You tag wildlife documentary clips for an editor. Read the file .work/tag_source/{BATCH}.json (cwd = the workspace root).
  For EVERY row, open its "image" with the Read tool and look at it before
writing anything: a 2x2 contact sheet of 4 frames from one clip, numbered 1-4 (top-left, top-right,
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
 action: only what clearly happens in the frames ("hunt" = chasing or catching live prey; mouth or
         hands in water = drink; still animal looking around = look). List from rest, sleep, look, walk, run, stalk, hunt, attack, eat, feed (adult feeding its young only; nectar, fruit, prey = eat), drink, swim, fly, perch, climb,
         hang, jump, fight, groom, play, call, carry_young, none
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
          night, close on its face"
 sure: true if the image is clear, false if you are guessing (tiny or dark subject)
Use only the listed words. Reply with one line: "<n> clips tagged".
