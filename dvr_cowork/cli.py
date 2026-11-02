from __future__ import annotations

import argparse
import json
import sys
from .core import Stop,prod,read_json
from .resolve_conn import ResolveConnectionError


def parser():
    p=argparse.ArgumentParser(prog="dvr",description="Full-AI mountain wildlife production")
    sub=p.add_subparsers(dest="command",required=True)
    q=sub.add_parser("init");q.add_argument("video");q.add_argument("--minutes",type=float,default=8);q.add_argument("--title")
    for cmd in ("build","validate","plan","conform","prompts","ingest","sheets","hook","status","info","check","render-status"):
        q=sub.add_parser(cmd);q.add_argument("video")
    for cmd in ("voice","assemble","done"):
        q=sub.add_parser(cmd);q.add_argument("video");q.add_argument("--apply",action="store_true")
    q=sub.add_parser("music");q.add_argument("video");q.add_argument("file");q.add_argument("--start",type=float,default=0);q.add_argument("--apply",action="store_true")
    sub.add_parser("youtube-login").add_argument("--key");sub.add_parser("youtube-channels")
    sub.add_parser("youtube-remove").add_argument("key")
    q=sub.add_parser("youtube-upload");q.add_argument("video");q.add_argument("--channel")
    q.add_argument("--publish-at");q.add_argument("--apply",action="store_true")
    q=sub.add_parser("youtube-seo");q.add_argument("video");q.add_argument("--query",action="append")
    q.add_argument("--write",action="store_true")
    sub.add_parser("next-video").add_argument("channel")
    q=sub.add_parser("youtube-trends");q.add_argument("channel");q.add_argument("--query",action="append")
    q=sub.add_parser("youtube-reference");q.add_argument("channel");q.add_argument("url")
    return p


def main(argv=None):
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,"reconfigure"): stream.reconfigure(encoding="utf-8")
    args=parser().parse_args(argv)
    try:
        from . import pipeline,story
        cmd=args.command
        if cmd=="init": result=pipeline.initialize(args.video,args.minutes,args.title)
        elif cmd=="next-video": result=pipeline.next_video(args.channel)
        elif cmd=="build":
            with pipeline.lock(prod(args.video)/"files.lock"):
                plan=story.build(args.video)
            result={"status":plan["status"],"runtime_s":plan["runtime_f"]/plan["fps"],
                    "voice_blocks":len(plan["voice"]),"english_words":sum(len(v["en"].split()) for v in plan["voice"]),
                    "voice_occupancy":plan["voice_occupancy"],"shots":len(plan["slots"]),
                    "mp3_mapping":"One nonblank physical transcript line = one numbered MP3; skip blank lines."}
        elif cmd=="validate":
            plan=story.load_plan(args.video)
            story.compile_story(plan["source"],[v["duration_f"]/plan["fps"] for v in plan["voice"]] if plan["status"]=="CONFORMED" else None)
            result={"validated":True,"status":plan["status"],"plan_hash":pipeline.object_hash(plan)}
        elif cmd=="plan":
            plan=story.load_plan(args.video)
            result={"path":str(pipeline.video_path(args.video)/"audios/visual_plan.md"),"status":plan["status"],
                    "runtime_s":plan["runtime_f"]/plan["fps"],"slots":len(plan["slots"]),
                    "generated_shots":sum(bool(s["prompt_id"]) for s in plan["slots"]),"hook_reuse_slots":5}
        elif cmd in ("conform","ingest","sheets","hook"): result=getattr(pipeline,cmd)(args.video)
        elif cmd=="prompts":
            with pipeline.lock(prod(args.video)/"files.lock"): result=pipeline.missing_prompts(args.video)
        elif cmd=="status": result=read_json(prod(args.video)/"state.json")
        elif cmd in ("voice","assemble","done","music","info","check","render-status"):
            from . import resolve_ops as ro
            if cmd in ("voice","assemble","done","music") and not args.apply:
                result={"dry_run":True,"action":cmd,"video":args.video,
                        "scope":"voice=A2 + SRT; assemble=V1/A1; music=A3; done=verify live Edit then start render",
                        "apply":"Add --apply only for the user-authorized phase."}
            elif cmd in ("voice","assemble"): result=ro.apply(args.video,"voice" if cmd=="voice" else "shots")
            elif cmd=="done": result=ro.render_start(args.video)
            elif cmd=="music": result=ro.music(args.video,args.file,args.start)
            else: result=getattr(ro,cmd.replace("-","_"))(args.video)
        elif cmd=="youtube-login":
            from .youtube import login
            result=login(args.key)
        elif cmd=="youtube-remove":
            from .youtube import remove
            result=remove(args.key)
        elif cmd=="youtube-upload":
            from .youtube import upload
            result=upload(args.video,args.channel,args.publish_at,args.apply)
        elif cmd=="youtube-channels":
            from .youtube import channels
            result=channels()
        elif cmd=="youtube-seo":
            from . import seo
            result=seo.assemble(args.video) if args.write else seo.research(args.video,args.query)
        elif cmd=="youtube-trends":
            from . import seo
            result=seo.trends(args.channel,args.query)
        elif cmd=="youtube-reference":
            from . import seo
            result=seo.reference(args.channel,args.url)
        # plain text reports stay plain: escaped JSON costs tokens
        print(result if isinstance(result,str) else json.dumps(result,ensure_ascii=False,indent=2,default=str))
        return 0
    except (Stop,ValueError,KeyError,OSError,ImportError,ResolveConnectionError) as e:
        print(f"STOP: {e}",file=sys.stderr)
        return 2


if __name__=="__main__": raise SystemExit(main())
