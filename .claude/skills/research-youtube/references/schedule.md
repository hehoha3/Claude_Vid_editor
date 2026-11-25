# research-youtube: scheduling, approval, canary, rollback

## Scheduled scans (Windows Task Scheduler, Python only, no Claude)

Twice a day keeps snapshots ~12 h apart (useful only once metrics are approved; before that a scan just keeps the
cache fresh so reports cost 0 requests). The user runs this once in PowerShell (one task per watchlist):

```powershell
$repo = "C:\Users\ADMIN\Claude_editor"
$act  = New-ScheduledTaskAction -Execute "$repo\.venv\Scripts\python.exe" `
        -Argument "-m dvr_cowork.youtube_research competitors --watchlist africa --quiet" -WorkingDirectory $repo
$trg  = @((New-ScheduledTaskTrigger -Daily -At 07:30), (New-ScheduledTaskTrigger -Daily -At 19:30))
Register-ScheduledTask -TaskName "yt-research-africa" -Action $act -Trigger $trg
# remove: Unregister-ScheduledTask -TaskName "yt-research-africa" -Confirm:$false
```

Cost: ~1 channels.list per 50 channels (cached 7 days) + 1 playlistItems.list per channel + 1 videos.list per 50 new
or stale videos. 20 channels ≈ 22 standard requests per scan, 0 search requests.

## Metrics approval (views/day, VPH, growth, outlier ratio)

YouTube API Developer Policies III.E.4.h forbid metrics derived from API Data unless Google accepts an analytics use
case: https://support.google.com/youtube/contact/yt_api_form -> "Section 5: Use Cases, API Integration, and Feature
Implementation" -> "Analytics & Reporting". Only after a written acceptance: `config/research_youtube.toml [policy]`
`metrics_permission = "approved"`, `approval_ref = "<case id>"`, `review_by = "YYYY-MM-DD"`. Statistics may then stay
36 months; titles / names / tags still refresh or go after 30 days (the engine purges by itself).

## Canary (real API, only with the user's yes; costs quota)

1. `$R doctor`, then `$R rising --preset africa-wildlife --dry-run` (shows the requests).
2. Put 2–3 known channels in `[watchlists] africa`, `$R competitors --watchlist africa` (first snapshot only).
3. ~12 h later the same command: compare as_of, requests (fresh cache = 0), duplicates; check 5 links by hand.
4. Then grow the watchlist to 10 -> 20 channels.

## Rollback

Data: `.work/youtube_research/` (delete the folder = empty cache; migrations leave `research.v<N>.bak`).
Code: the user restores the files from git (`dvr_cowork/youtube_research/`, `dvr_cowork/seo.py`,
`dvr_cowork/fullai/seo.py`, `.claude/skills/research-youtube/`, `config/research_youtube.toml`).
