from __future__ import annotations

import argparse
import json
import sys
from .core import Stop,prod,read_json
from ..resolve_conn import ResolveConnectionError


def parser():
    p=argparse.ArgumentParser(prog="dvr_cowork ai",description="full-AI 8-15p (any region): voice -> prompts -> shots -> review -> done")
    sub=p.add_subparsers(dest="command",required=True)
    q=sub.add_parser("init");q.add_argument("video");q.add_argument("--minutes",type=float,help="default: the profile's")
    q.add_argument("--title");q.add_argument("--region",help="himalaya | amazon | africa (default: himalaya)")
    q.add_argument("--type",default="full_ai_mountain",help="profile or alias (full-AI)")
    q=sub.add_parser("voice-ready",help="conform -> A2 + SRT -> prompts in one call");q.add_argument("video")
    q.add_argument("--apply",action="store_true")
    q=sub.add_parser("shots-ready",help="ingest -> body on V1/A1 -> hook contact sheets");q.add_argument("video")
    q.add_argument("--apply",action="store_true")
    q=sub.add_parser("finish",help="hook -> intro -> song + beds + birds -> check");q.add_argument("video");q.add_argument("song")
    q.add_argument("--wind");q.add_argument("--beds");q.add_argument("--birds");q.add_argument("--apply",action="store_true")
    for cmd in ("build","validate","plan","conform","ingest","sheets","hook","status","info","check","render-status"):
        q=sub.add_parser(cmd);q.add_argument("video")
    q=sub.add_parser("prompts");q.add_argument("video");q.add_argument("--reissue",action="store_true")
    q.add_argument("--only",type=lambda s:[int(x) for x in s.split(",")],help="redo list: shot IDs, e.g. 3,7,12")
    for cmd in ("voice","assemble","done"):
        q=sub.add_parser(cmd);q.add_argument("video");q.add_argument("--apply",action="store_true")
    sub.choices["assemble"].add_argument("--rehook",action="store_true",help="replace this engine's old intro items (backup first)")
    q=sub.add_parser("music");q.add_argument("video");q.add_argument("file")
    q.add_argument("--wind");q.add_argument("--beds",help="JSON {scene id: licensed bed file}; default .production/beds.json")
    q.add_argument("--birds",help="JSON {prompt id: licensed bird file}; default .production/birds.json")
    q.add_argument("--replace",action="store_true");q.add_argument("--apply",action="store_true")
    q=sub.add_parser("next-video");q.add_argument("channel");q.add_argument("--region",default="himalaya")
    return p


def main(argv=None):
    args=parser().parse_args(argv)
    try:
        from . import pipeline,story
        cmd=args.command
        if cmd=="init": result=pipeline.initialize(args.video,args.minutes,args.title,args.region,args.type)
        elif cmd=="next-video": result=pipeline.next_video(args.channel,args.region)
        elif cmd=="build":
            with pipeline.lock(prod(args.video)/"files.lock"):
                plan=story.build(args.video)
            result={"status":plan["status"],"runtime_s":plan["runtime_f"]/plan["fps"],
                    "voice_blocks":len(plan["voice"]),"english_words":sum(len(v["en"].split()) for v in plan["voice"]),
                    "voice_occupancy":plan["voice_occupancy"],"shots":len(plan["slots"]),
                    "mp3_mapping":"One nonblank physical transcript line = one numbered MP3; skip blank lines."}
        elif cmd=="validate":
            plan=story.load_plan(args.video)
            story.compile_story(plan["source"],[v["duration_f"]/plan["fps"] for v in plan["voice"]] if plan["status"]=="CONFORMED" else None,
                                story.pinned_profile(args.video))
            result={"validated":True,"status":plan["status"],"plan_hash":pipeline.object_hash(plan)}
        elif cmd=="plan":
            plan=story.load_plan(args.video)
            result={"path":str(pipeline.video_path(args.video)/"audios/visual_plan.md"),"status":plan["status"],
                    "runtime_s":plan["runtime_f"]/plan["fps"],"slots":len(plan["slots"]),
                    "generated_shots":sum(bool(s["prompt_id"]) for s in plan["slots"]),
                    "intro":(plan.get("rules") or {}).get("intro",{}).get("mode","five_roles_6s")}
        elif cmd in ("conform","ingest","sheets","hook"): result=getattr(pipeline,cmd)(args.video)
        elif cmd=="prompts":
            with pipeline.lock(prod(args.video)/"files.lock"): result=pipeline.missing_prompts(args.video,args.reissue,args.only)
        elif cmd=="status": result=read_json(prod(args.video)/"state.json")
        else:
            from . import resolve_ops as ro
            if cmd=="voice-ready": result=ro.voice_ready(args.video,args.apply)
            elif cmd=="shots-ready": result=ro.shots_ready(args.video,args.apply)
            elif cmd=="finish": result=ro.finish(args.video,args.song,args.apply,wind=args.wind,beds=args.beds,birds=args.birds)
            elif cmd in ("voice","assemble","done","music") and not args.apply:
                result={"dry_run":True,"action":cmd,"video":args.video,
                        "scope":"voice=A2 + SRT; assemble=V1/A1; music=A7 intro music + A3/A4 scene beds; done=verify live Edit then start render",
                        "apply":"Add --apply only for the user-authorized phase."}
            elif cmd=="voice": result=ro.apply(args.video,"voice")
            elif cmd=="assemble": result=ro.apply(args.video,"shots",rehook=args.rehook)
            elif cmd=="done": result=ro.render_start(args.video)
            elif cmd=="music": result=ro.music(args.video,args.file,args.wind,args.replace,beds=args.beds,birds=args.birds)
            else: result=getattr(ro,cmd.replace("-","_"))(args.video)
        # plain text reports stay plain: escaped JSON costs tokens
        print(result if isinstance(result,str) else json.dumps(result,ensure_ascii=False,indent=2,default=str))
        return 0
    except (Stop,ValueError,KeyError,OSError,ImportError,ResolveConnectionError) as e:
        print(f"STOP: {e}",file=sys.stderr)
        return 2
