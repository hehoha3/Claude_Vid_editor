---
name: hide-logo
description: Detect and remove broadcast logos (BBC, Discovery, etc.) from video using Object Removal or zoom/pan. Use this when videos have logos in corners that need to be hidden. Provide timeline name or use current. Skill will detect logo presence, add markers at visible range, report for approval, then apply Object Removal (Studio) or fallback to zoom/pan technique to hide logo while preserving frame content.
compatibility: DaVinci Resolve 21.1 Studio (Object Removal), ffmpeg, Fusion API
---

# Hide Logo Skill

Automatically detects and removes broadcast logos from video using DaVinci Resolve Object Removal or zoom/pan technique.

## What is a Logo?

A broadcast logo is typically:
- **Network badge** (BBC, Discovery, Animal Planet, etc.)
- **Located in corners** — usually top-left, sometimes top-right
- **Semi-transparent** or opaque
- **Small but visible** — occupies ~2-5% of frame

Examples: BBC logo, Discovery Channel logo, Animal Planet logo in video corners

## Workflow

When you invoke this skill:

1. **Detection phase** — Scans frames for logo patterns (small rectangular region with network branding)
2. **Marking phase** — Adds markers at:
   - `[LOGO-START]` — first frame where logo is visible
   - `[LOGO-END]` — last frame where logo is visible
3. **Review phase** — Shows you frame captures highlighting logo location, reports detection confidence
4. **Execute phase** (after your approval) — Applies one of two techniques:
   - **Object Removal (Studio)** — AI-powered inpainting to remove logo
   - **Fallback zoom/pan** — Zoom X 1.070-1.096 + adjust position Y to hide logo off-screen

## Using This Skill

### Basic usage (scan current timeline)

```
/hide-logo
```

Scans all clips in timeline "Edit" track V1 for logos.

### Scan specific timeline

```
/hide-logo --timeline "MyTimeline"
```

### Execute with specific removal method

**Object Removal (Studio):**
```
/hide-logo --execute
```
or
```
/hide-logo --execute object-removal
```

**Zoom-Pan (auto-optimized):**
```
/hide-logo --execute zoom-pan
```

When using zoom-pan, the skill automatically calculates:
- **Zoom factor**: 1.083 (within your tested range 1.070-1.096)
- **Position Y shift**: Based on detected logo corner (top/bottom)

If result isn't perfect, skill suggests fine-tuning values.

## What Happens

### Detection phase:
- Reads frames from V1 track
- Detects logo pattern (corner badge with specific color/shape characteristics)
- Identifies visible range (LOGO-START to LOGO-END)

### Marking phase:
- Places `[LOGO-START]` marker at first logo frame
- Places `[LOGO-END]` marker at last logo frame
- Exports sample frames highlighting detected logo region for your review

### Review & Execute:
- You see frame captures with logo highlighted + detection confidence
- Markers visible in Resolve timeline
- Approve markers, then invoke with `--execute` flag

### Removal phase (two options):

**Option A: Object Removal (Studio)**
- Uses Fusion API to create Object Removal effect
- AI removes logo while preserving background
- Applied to both V1 and A1 (video/audio remain synced)
- Result: Logo disappears, background filled naturally

**Option B: Zoom-Pan (fallback)**
- Zooms clip by factor 1.070-1.096 (adjustable)
- Shifts position Y to hide logo off-frame
- Preserves all video content, just reframed
- Applied to both V1 and A1 (they scale together)
- Result: Logo pushed off-screen, more of center content visible

## Output

After detection:
- Markers visible in Resolve: `[LOGO-START]`, `[LOGO-END]`
- Frame exports: `.work/hide_logo/<clipname>/logo_detected.jpg`, `logo_location.jpg`
- Report: detection confidence, logo location (corner), method selected

After execution:
- Logo removed or hidden
- Report: method used, clips affected, result preview

## Possible Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| "No logo detected" | Video doesn't have visible logo, or pattern differs | Manually check video, use Resolve marker tool if needed |
| "Logo not fully removed" | Object Removal incomplete, or logo partially visible | Try zoom-pan fallback, or manually tweak Object Removal mask |
| "Content cut off after zoom" | Zoom factor too high | Review with `--method zoom-pan` and bạn can adjust zoom in preview |
| "Object Removal not available" | Not using DaVinci Resolve Studio | Automatically falls back to zoom-pan technique |
| "Gaps created" | Audio/video mismatch | Skill handles sync automatically |

## Technical Details

- **Logo detection** — Corner badge recognition + color analysis + shape heuristics
- **Object Removal** — Uses TimelineItem.AddFusionComp() with Fusion Object Removal effect
- **Zoom-Pan** — Uses TimelineItem.SetZoom() + SetPosition() (requires Studio or proper API support)
- **Frame-accurate** — Markers placed at exact frame boundaries
- **Synced trim** — Both V1 and A1 modified together to maintain sync

## When to Use This Skill

✅ Videos have broadcast logos in corners (BBC, Discovery, etc.)
✅ You want automatic detection + manual approval before removal
✅ You want AI-powered removal (Object Removal) or simple reframing (zoom-pan)
✅ Logos appear intermittently (beginning/end, or specific segments)

❌ Don't use for watermark removal (different technique)
❌ Don't use for logos that are central to the shot (they should stay visible)
❌ Don't use if you want to keep the logo (use this to remove it)

## Workflow Best Practices

1. **Scan first** — Run skill without `--execute` to preview markers
2. **Review in Resolve** — Open timeline, play around marked frames
3. **Check method** — If Object Removal applied, review quality (may need mask adjustment)
4. **Fallback if needed** — If Object Removal unsatisfactory, try zoom-pan (`--method zoom-pan --execute`)
5. **Verify result** — Play affected clips in Resolve to confirm logo gone and content still good

## Advanced Options

### Custom zoom factor (override auto-calculated)

```
/hide-logo --execute zoom-pan --zoom 1.085
```

Skill auto-calculates zoom (1.083 default, within your range 1.070-1.096). Use `--zoom` to override if needed.

### Manually specify logo corner

```
/hide-logo --corner top-left --execute zoom-pan
```

If auto-detection misses corner, hint which corner logo is in. Helps optimize Y shift calculation.

### Preview without executing

```
/hide-logo --preview
```

Shows detection results and suggested zoom/pan values without applying them.
