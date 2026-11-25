from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from dvr_cowork.fullai import core,intro_music,pipeline,resolve_ops,story,youtube
from dvr_cowork.fullai.tests.fixtures import install,source
from dvr_cowork.fullai.tests.fake_resolve import Clip,Item,Resolve
from dvr_cowork.videokey import timeline_name

# A 120 BPM "tense song": quiet opening, loud 20-70 s climax, own ending decaying from 70 s to silence.
TENSE_SONG=("aevalsrc=exprs=(0.2+0.8*between(t\\,20\\,70))*if(gt(t\\,70)\\,exp(-(t-70)*0.8)\\,1)"
            "*sin(2*PI*110*t)*exp(-20*mod(t\\,0.5)):s=22050")
# 120 BPM kicks: quiet 0-20 s, a LOUD sustained 60 Hz pad without hits 20-45 s, strong kicks 45-70 s, decay from 70 s.
_KICK="sin(2*PI*60*t)*exp(-15*mod(t\\,0.5))"
PAD_VS_KICKS=(f"aevalsrc=exprs=(0.2*{_KICK}*(1-between(t\\,20\\,70))+0.95*between(t\\,20\\,45)*sin(2*PI*60*t)"
              f"+0.8*between(t\\,45\\,70)*{_KICK})*if(gt(t\\,70)\\,exp(-(t-70)*0.8)\\,1):s=22050")


class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.video=self.root/"Chann_1"/"snow_story"
        # The fixture film is a v2 one (6-9 s shots, four beats); v3 (3-7 s, 1-2 beats) has its own test below.
        from dvr_cowork import profile as prof
        real=prof.load
        self.v2=patch.object(prof,"load",lambda name,version=None,allow_disabled=False:real("full_ai_mountain" if prof.profile_id(name) in ("full_ai","full_ai_mountain") else name,version or 2,allow_disabled))
        self.v2.start()
    def tearDown(self): self.v2.stop();self.temp.cleanup()

    def test_v3_short_shots_and_beats_by_length(self):
        # user 2026-11-09: v3 shots 3-7 s, clip = slot + 1 s, one beat under a 5 s clip, else up to two, even ticks
        from dvr_cowork import profile as prof
        p3=prof.load("full_ai_mountain",3)
        self.assertEqual((story.max_beats(p3,3),story.max_beats(p3,4),story.max_beats(p3,7)),(1,2,2))
        self.assertIsNone(story.max_beats(prof.load("full_ai_mountain",2),8))
        s=source();sc=s["scenes"][2];old=sc["shots"][0]
        half=dict(old,duration_s=old["duration_s"]/2,beats=old["beats"][:2])
        sc["shots"]=[half,dict(half,title=old["title"]+" (b)",beats=old["beats"][2:])]+sc["shots"][1:]
        with self.assertRaisesRegex(core.Stop,"every shot must be 6"):story.compile_story(copy.deepcopy(s))
        with self.assertRaisesRegex(core.Stop,"action beat"):story.compile_story(copy.deepcopy(s),profile=p3)

    def test_eight_and_eleven_minute_contract(self):
        for minutes in (8,11):
            p=story.compile_story(source(minutes));d=story.documents(p)
            self.assertEqual(p["runtime_f"],minutes*60*24)
            self.assertEqual(sum(s["end_f"]-s["start_f"] for s in p["slots"]),p["runtime_f"])
            self.assertTrue(.85<p["voice_occupancy"]<.93)
            self.assertEqual(len(p["slots"]),62 if minutes==8 else 86)
            lines=[x for x in d["transcript.md"].splitlines() if x]
            self.assertEqual(lines,[v["en"] for v in p["voice"]])
            self.assertEqual(d["timestamp.md"].count("["),2*len(lines))
            self.assertTrue(all(6<=(s["end_f"]-s["start_f"])/24<=9 for s in p["slots"] if s["id"]!="HOOK"))

    def test_spanish_narrator(self):
        s=source();s["lang"]="es"
        for sc in s["scenes"]:
            for v in sc["voice"]: v["es"]=v.pop("en")
        p=story.compile_story(s);d=story.documents(p)
        self.assertIn("## Spanish",d["timestamp.md"]);self.assertNotIn("## English",d["timestamp.md"])
        self.assertEqual([x for x in d["transcript.md"].splitlines() if x],[v["en"] for v in p["voice"]])
        s["lang"]="fr"
        with self.assertRaisesRegex(core.Stop,"lang must be en or es"): story.compile_story(s)

    def test_dense_narration_overflow_and_sparse_script(self):
        s=source();s["scenes"][2]["voice"][0]["en"]="word "*200
        with self.assertRaisesRegex(core.Stop,"exceeds picture window"): story.compile_story(s)
        s=source();s["scenes"][2]["voice"]=[{"en":"Too little narration.","vi":"Quá ít lời dẫn."}]
        with self.assertRaisesRegex(core.Stop,"narrator gap"): story.compile_story(s)

    def test_next_video_numbers_per_channel_and_skips_pushed(self):
        from datetime import datetime
        today=datetime.now().strftime("%d%m%y");ch=self.root/"Chann_4_test"
        for name in (f"vid_{today}_1",f"_done/vid_{today}_2",f"_pushed/vid_{today}_7","africa_old"):(ch/name).mkdir(parents=True)
        (self.root/"Chann_1_other"/f"africa_{today}_5").mkdir(parents=True)  # another channel's films never count
        install(ch/f"vid_{today}_1")
        s=core.read_json(core.prod(ch/f"vid_{today}_1")/"story.json");s["archetype"]="mother"
        core.write_json(core.prod(ch/f"vid_{today}_1")/"story.json",s)
        r=pipeline.next_video("Chann_4","himalaya",str(self.root)+"/")  # old region name = frozen, type prefix a_
        self.assertTrue(r["next_video"].endswith(f"a_en_frozen_{today}_3"));self.assertEqual(r["next_archetype"],"throne")
        self.assertEqual(r["recent"][0]["cast"],["ibex","ibex"])
        with self.assertRaisesRegex(core.Stop,"Expected one"):pipeline.next_video("Chann_5","himalaya",str(self.root)+"/")

    def test_compact_shots_inherit_scene_defaults_and_require_energetic_beats(self):
        s=source();sc=s["scenes"][3]
        sc.update(camera="low telephoto",direction="east to west",characters=["M"])
        for sh in sc["shots"]:
            for k in ("direction","characters"): sh.pop(k)
        sc["shots"][0]["camera"]="close detail";sc["shots"][1].pop("camera")
        sc["location"]="A narrow shelf under a gray wall"
        p=story.compile_story(s)
        slots=[x for x in p["slots"] if x["scene"]==sc["id"]]
        self.assertEqual(slots[0]["camera"],"close detail");self.assertEqual(slots[1]["camera"],"low telephoto")
        self.assertTrue(all(x["direction"]=="east to west" and x["characters"]==["M"] and len(x["beats"])==4 for x in slots))
        text=story.prompt_text(p,slots[1])
        self.assertIn("0-2s: "+slots[1]["beats"][0]+". 2-5s:",text);self.assertIn("7-10s: "+slots[1]["beats"][3]+".",text)
        self.assertIn("10-second 16:9",text)  # 9 s slot -> 10 s clip (slot + 1 s, user 2026-11-09)
        self.assertIn("never silently staring at each other",text)  # shared tail (prompt_rules)
        self.assertIn("East to west".lower(),text.lower());self.assertTrue(text.startswith("Real-time footage at true natural speed"))
        self.assertIn("ONE SINGLE CONTINUOUS TAKE",text);self.assertIn("Location: A narrow shelf",text)
        self.assertIn("no standing still",text);self.assertNotIn("holding the final state",text)
        self.assertIn(", The video must not have a blue tint - 10-second",text)
        self.assertIn("no slow motion",text);self.assertIn("no blue, cyan or teal tint",text)
        sc["location"]="A narrow shelf at blue dusk"
        with self.assertRaisesRegex(core.Stop,"blue grade; use neutral daylight or warm low sun instead of: blue, dusk"):story.compile_story(s)
        sc["location"]="A narrow shelf under a gray wall"
        self.assertNotIn(s["geography"],text)
        sc["shots"][1]["beats"][2]="She waits carefully on the shelf"
        with self.assertRaisesRegex(core.Stop,"fast, continuous action; rewrite without: carefully, waits"):story.compile_story(s)
        sc["location"]="A narrow shelf at dusk"  # one build lists every word problem, not only the first
        with self.assertRaisesRegex(core.Stop,"(?s)instead of: dusk.*rewrite without: carefully, waits"):story.compile_story(s)
        sc["location"]="A narrow shelf under a gray wall"
        sc["shots"][1]["beats"][2]="She bounds past the frozen spring";story.compile_story(s)
        sc["shots"][1].pop("beats")
        with self.assertRaisesRegex(core.Stop,"requires beats"):story.compile_story(s)
        sc["shots"][1]["beats"]=["a","b","c","d"]
        sc["shots"][2]["camera"]="low telephoto"
        with self.assertRaisesRegex(core.Stop,"share one camera"):story.compile_story(s)

    def test_prompt_cast_lists_and_absent_character_leaks(self):
        s=source();sc=s["scenes"][3];sc["characters"]=["M"]
        for sh in sc["shots"]: sh.pop("characters")
        p=story.compile_story(s)
        text=story.prompt_text(p,next(x for x in p["slots"] if x["scene"]==sc["id"]))
        self.assertIn("of exactly 1 animal for the whole take",text);self.assertIn("NOT IN FRAME: ibex —",text)
        self.assertNotIn("small cream-colored kid",text)
        s["scenes"][3]["shots"][2]["end_state"]="The kid waits above"
        s["geography"]="One cliff where the kids wait."
        with self.assertRaises(core.Stop) as e: story.compile_story(s)
        self.assertIn("geography: 'kids' names K",str(e.exception));self.assertIn("(B3): 'kid' names K (not in frame) in end_state",str(e.exception))
        s=source();s["characters"][1]["terms"]=["Mother"]
        with self.assertRaisesRegex(core.Stop,"two characters"): story.compile_story(s)

    def test_fractional_fps_does_not_accumulate_boundary_drift(self):
        s=source(11);s["fps"]=24000/1001
        p=story.compile_story(s)
        self.assertLessEqual(abs(p["runtime_f"]/p["fps"]-660),1/p["fps"])
        self.assertTrue(all(6-1/p["fps"]<=(x["end_f"]-x["start_f"])/p["fps"]<=9+1/p["fps"] for x in p["slots"] if x["id"]!="HOOK"))

    def test_short_shot_and_missing_translation_rejected(self):
        s=source();s["scenes"][2]["shots"][0]["duration_s"]=5
        with self.assertRaisesRegex(core.Stop,"6–9"): story.compile_story(s)
        s=source();s["scenes"][3]["voice"][0]["vi"]=""
        with self.assertRaisesRegex(core.Stop,"translation"): story.compile_story(s)

    def test_numeric_identity_and_alias(self):
        self.root.joinpath("1.mp4").touch();self.root.joinpath("3.mp4").touch()
        with self.assertRaisesRegex(core.Stop,"missing.*2.*extra.*3"):core.numbered(self.root,".mp4",2)
        for n in range(2,12):self.root.joinpath(f"{n}.mp4").touch()
        self.assertEqual(list(core.numbered(self.root,".mp4",11)),list(range(1,12)))
        self.root.joinpath("01.mp4").touch()  # trailing number = index (user 2026-11-06): 01 = 1 -> duplicate
        with self.assertRaisesRegex(core.Stop,"Duplicate"):core.numbered(self.root,".mp4",11)
        for p in self.root.glob("*.mp4"): p.unlink()
        for n,name in enumerate(("shot_001","shot-002","S03","4"),1): self.root.joinpath(f"{name}.mp4").touch()
        self.assertEqual({n:p.name for n,p in core.numbered(self.root,".mp4",4).items()},
                         {1:"shot_001.mp4",2:"shot-002.mp4",3:"S03.mp4",4:"4.mp4"})
        self.root.joinpath("shot_000.mp4").touch()
        with self.assertRaisesRegex(core.Stop,"trailing index"):core.numbered(self.root,".mp4",4)

    def test_output_tampering_and_frozen_prompt_ids(self):
        p=self.prepare_voice()
        resolve_ops.apply(self.video,"voice",Resolve(self.video.name))
        first=pipeline.missing_prompts(self.video)
        self.assertEqual(first["prompts"],61)
        self.assertEqual(pipeline.missing_prompts(self.video),first)
        self.assertFalse((self.video/"lock-assets.md").exists())  # user 2026-11-24: prompts carry the locks
        from dvr_cowork.prompt_rules import prompt_rows
        rows=prompt_rows(self.video)
        self.assertEqual(len(rows),61)
        self.assertEqual((rows[0]["shot_id"],rows[0]["dur_s"]),("c1v1_1","7.0"))  # 6 s slot + 1 s
        self.assertEqual(rows[6]["dur_s"],"10.0")
        self.assertIn("(ABSOLUTE: Notch on the RIGHT ear only.)",rows[0]["generation_prompt"])
        self.assertIn("7-second 16:9",rows[0]["generation_prompt"]);self.assertIn("5-7s: Moment",rows[0]["generation_prompt"])
        self.assertFalse((self.video/"missing-prompt.md").exists())
        (self.video/"audios/transcript.md").write_text("Changed",encoding="utf-8")
        with self.assertRaisesRegex(core.Stop,"canonical"):story.load_plan(self.video)

    def test_same_name_channels_are_independent(self):
        a=self.root/"Chann_1/same";b=self.root/"Chann_2/same"
        install(a);install(b)
        core.event(a,"WAITING_FOR_VOICE");core.event(b,"WAITING_FOR_SHOTS")
        self.assertNotEqual(core.read_json(core.prod(a)/"state.json"),core.read_json(core.prod(b)/"state.json"))

    def test_lock_released_after_exception(self):
        lock=self.root/"lock"
        try:
            with core.lock(lock):
                with self.assertRaises(core.Stop):
                    with core.lock(lock): pass
                raise ValueError("crash")
        except ValueError:pass
        with core.lock(lock):pass

    def prepare_voice(self,minutes=8):
        plan=install(self.video,minutes,conformed=True)
        folder=self.video/"voice";folder.mkdir()
        data={}
        for v in plan["voice"]:
            p=folder/f"{v['id']}.mp3";p.write_bytes(f"test voice {v['id']}".encode())
            data[str(v["id"])]={"path":str(p),"sha256":core.digest(p),"duration":v["duration_f"]/24}
        core.write_json(core.prod(self.video)/"voice_media.json",data)
        return plan

    def prepare_shots(self,minutes=8):
        plan=self.prepare_voice(minutes)
        resolve_ops.apply(self.video,"voice",Resolve(self.video.name))
        pipeline.missing_prompts(self.video)
        folder=self.video/"shots";folder.mkdir()
        evidence=core.prod(self.video)/"review/evidence.jpg";evidence.parent.mkdir();evidence.write_bytes(b"fake evidence")
        media={};qc={"plan_hash":core.object_hash(plan),"shots":{}}
        manifest=core.read_json(core.prod(self.video)/"manifest.json")
        for row in manifest["rows"]:
            i=str(row["prompt_id"]);path=folder/f"{i}.mp4";path.write_bytes(f"test shot {i}".encode())
            m={"path":str(path),"sha256":core.digest(path),"duration":row["duration_s"],"fps":24,
               "prompt_sha256":row["prompt_sha256"],"audio":True,"video":True}
            media[i]=m;qc["shots"][i]={"sha256":m["sha256"],"prompt_sha256":m["prompt_sha256"],
                "approved":True,"reviewer":"Test double, not a production approval","notes":"Artificial fixture verified",
                "hook_ok":True,"hook_start_s":0,"evidence":[str(evidence)]}
        core.write_json(core.prod(self.video)/"shot_media.json",media);core.write_json(core.prod(self.video)/"shot_qc.json",qc)
        pipeline.hook(self.video)
        return plan

    def test_voice_additive_resume_and_foreign_collision(self):
        plan=self.prepare_voice();r=Resolve(self.video.name)
        first=resolve_ops.apply(self.video,"voice",r)
        self.assertEqual(first["placed"],len(plan["voice"]))
        self.assertIn("unsupported",first["subtitles"])
        self.assertEqual(resolve_ops.apply(self.video,"voice",r)["placed"],0)
        tl=next(t for t in r.project.timelines if t.name==timeline_name(self.video))
        tl.items["audio",2][0].clip=Clip(str(self.root/"manual.wav"))
        n=len(tl.items["audio",2])
        with self.assertRaisesRegex(core.Stop,"Manual/foreign"):resolve_ops.apply(self.video,"voice",r)
        self.assertEqual(len(tl.items["audio",2]),n)

    def test_one_project_holds_one_timeline_per_video(self):
        # The day-project template: an empty channN_vid1 (V1-V2, A1-A9) in each Chann_N/6. Timeline is reused.
        from dvr_cowork.fullai.tests.fake_resolve import Timeline
        r=Resolve("vid_021126_1");mp=r.project.mp;template=[]
        for ch in ("Chann_1","Chann_2"):
            t=Timeline(r.project,f"{ch.lower().replace('_','')}_vid1");t.tracks.update(video=2,audio=9);r.project.timelines.append(t)
            t.names["audio",3]="My bed"  # a name the user set is kept
            resolve_ops.ensure_bin(mp,f"{ch}/6. Timeline").clips.append(t.clip);template.append(t)
        for ch in ("Chann_1_shadowCanopy","Chann_2_UntamedEmpire"):
            self.video=self.root/ch/"vid_021126_1";plan=self.prepare_voice()
            self.assertEqual(resolve_ops.apply(self.video,"voice",r)["placed"],len(plan["voice"]))
        edits=[t for t in r.project.timelines if t.name in ("chann1_vid1","chann2_vid1")]
        self.assertEqual(edits,template)
        for ch,tl in zip(("Chann_1","Chann_2"),edits):
            self.assertEqual(tl.tracks["audio"],9)
            self.assertEqual((tl.GetTrackName("audio",3),tl.GetTrackName("audio",7)),("My bed","Music"))
            self.assertTrue(all(ch.lower() in str(i.clip.path).lower() for i in tl.items["audio",2]))
            narr=resolve_ops.ensure_bin(mp,f"{ch}/4. Audio/Narrator",create=False)
            self.assertEqual(len(narr.clips),len(plan["voice"]))
        self.assertEqual(resolve_ops.apply(self.video,"voice",r)["placed"],0)
        self.assertEqual([f.name for f in mp.root.subs],["Chann_1","Chann_2"])

    def test_missing_video_timeline_is_created_in_its_channel_bin(self):
        r=Resolve("vid_021126_1")
        for ch,name in (("Chann_1_shadowCanopy","chann1_vid1"),("Chann_2_UntamedEmpire","chann2_vid1")):
            self.video=self.root/ch/"vid_021126_1";self.prepare_voice()
            resolve_ops.apply(self.video,"voice",r)
            tl=next(t for t in r.project.timelines if t.name==name)
            self.assertIn(tl.clip,resolve_ops.ensure_bin(r.project.mp,f"{ch[:7]}/6. Timeline",create=False).clips)
            self.assertEqual(tl.tracks["audio"],9)

    def test_whole_eleven_minute_v1_a1_link_and_manual_review(self):
        plan=self.prepare_shots(11);r=Resolve(self.video.name)
        resolve_ops.apply(self.video,"voice",r);result=resolve_ops.apply(self.video,"shots",r)
        tl=next(t for t in r.project.timelines if t.name==timeline_name(self.video))
        clips=len(core.read_json(core.prod(self.video)/"hook.json")["cuts"])+sum(bool(s["prompt_id"]) for s in plan["slots"])
        self.assertEqual(result["verified"],clips*2)  # 1x intro cuts keep A1
        self.assertEqual(len(tl.linked),clips)
        self.assertTrue(any(t.start>86400+480*24 for t in tl.items["audio",1]))
        # the 1h black fades: in at 0:00, out on the last intro cut, in on the first story shot, out at the end
        v=sorted(tl.items["video",1],key=lambda i:i.start);cut=86400+pipeline.hook_window(plan)[1]
        k=next(j for j,i in enumerate(v) if i.start==cut)
        self.assertEqual(result["black_fades"],"black fades: 8 checked, 8 set")  # 4 on V1 + their A1 (user 2026-11-06)
        want=[{"FadeIn":24,"FadeOut":0},{"FadeIn":0,"FadeOut":36},{"FadeIn":60,"FadeOut":0},{"FadeIn":0,"FadeOut":72}]
        self.assertEqual([v[0].GetFades(),v[k-1].GetFades(),v[k].GetFades(),v[-1].GetFades()],want)
        a1={(i.start,i.end):i for i in tl.items["audio",1]}
        self.assertEqual([a1[x.start,x.end].GetFades() for x in (v[0],v[k-1],v[k],v[-1])],want)
        v[k].fades={};v[-1].fades={"FadeIn":0,"FadeOut":96}  # a lost fade comes back; the user's longer fade stays
        again=resolve_ops.apply(self.video,"shots",r)
        self.assertEqual((again["placed"],again["black_fades"],v[k].GetFades()["FadeIn"],v[-1].GetFades()["FadeOut"]),
                         (0,"black fades: 8 checked, 1 set",60,96))
        self.assertEqual(resolve_ops.check(self.video,r)["runtime_s"],660)
        tl.items["video",1][-1].properties["ZoomX"]=1.03
        self.assertEqual(resolve_ops.check(self.video,r)["runtime_s"],660)
        tl.items["audio",1][-1].offset+=10
        with self.assertRaisesRegex(core.Stop,"A1 no longer matches"):resolve_ops.check(self.video,r)

    def test_source_changed_invalidates_qc(self):
        self.prepare_shots();(self.video/"shots/2.mp4").write_bytes(b"regenerated")
        with self.assertRaisesRegex(core.Stop,"changed since ingest"):pipeline.hook(self.video)
        with self.assertRaisesRegex(core.Stop,"changed since ingest"):resolve_ops.shot_operations(self.video)

    def test_rehook_replaces_only_this_engines_intro(self):
        plan=self.prepare_shots();r=Resolve(self.video.name)
        resolve_ops.apply(self.video,"voice",r);resolve_ops.apply(self.video,"shots",r)
        tl=next(t for t in r.project.timelines if t.name==timeline_name(self.video));end=pipeline.hook_window(plan)[1]
        old=[(i.start,i.end) for i in tl.items["video",1] if i.start<86400+end]
        q=core.read_json(core.prod(self.video)/"shot_qc.json")
        for x in q["shots"].values():x["hook_start_s"]=1.0  # a new hook: other source ranges
        core.write_json(core.prod(self.video)/"shot_qc.json",q);pipeline.hook(self.video)
        with self.assertRaisesRegex(core.Stop,"Manual/foreign"):resolve_ops.apply(self.video,"shots",r)
        res=resolve_ops.apply(self.video,"shots",r,rehook=True)
        self.assertTrue(res["backup"])
        intro=[i for i in tl.items["video",1] if i.start<86400+end]
        self.assertEqual([(i.start,i.end) for i in intro],old)  # same cut grid, new source offsets
        self.assertTrue(all(i.offset==24 for i in intro))
        self.assertEqual(resolve_ops.check(self.video,r)["runtime_s"],480)
        intro[0].clip=Clip(str(self.root/"manual.mp4"))  # a hand-placed clip in the intro is never removed
        q=core.read_json(core.prod(self.video)/"shot_qc.json")
        for x in q["shots"].values():x["hook_start_s"]=0.5
        core.write_json(core.prod(self.video)/"shot_qc.json",q);pipeline.hook(self.video)
        with self.assertRaisesRegex(core.Stop,"Foreign / manual item in the intro"):resolve_ops.apply(self.video,"shots",r,rehook=True)

    def test_assemble_body_without_hook_then_done_blocked(self):
        # User 2026-11-05: assemble right after ingest (user reviews on the timeline), intro added later by `hook`.
        plan=self.prepare_shots();(core.prod(self.video)/"hook.json").unlink()
        q=core.read_json(core.prod(self.video)/"shot_qc.json")
        for x in q["shots"].values():x.update(approved=False,reviewer="",notes="",evidence=[])
        core.write_json(core.prod(self.video)/"shot_qc.json",q)
        r=Resolve(self.video.name);resolve_ops.apply(self.video,"voice",r)
        result=resolve_ops.apply(self.video,"shots",r)
        body=sum(bool(s["prompt_id"]) and s["phase"]!="hook" for s in plan["slots"])
        self.assertEqual(result["verified"],body*2)
        self.assertTrue(resolve_ops.ensure_bin(r.project.mp,"Chann_1/1. Other_roll",create=False).clips
                        or resolve_ops.ensure_bin(r.project.mp,"1. Other_roll",create=False).clips)
        with self.assertRaisesRegex(core.Stop,"V1 gap/overlap at frame 0"):resolve_ops.check(self.video,r)

    def test_redo_prompts_only_listed_ids(self):
        self.prepare_shots()
        out=pipeline.missing_prompts(self.video,only=[3,7])
        self.assertEqual(out["prompts"],2)
        text=(self.video/"missing-prompt.txt").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("c1v1_3 |"));self.assertIn("\n\nc1v1_7 |",text)
        self.assertNotIn("c1v1_4 |",text)
        with self.assertRaisesRegex(core.Stop,"No prompt with ID"):pipeline.missing_prompts(self.video,only=[999])

    def test_mixed_source_fps_conforms_to_exact_timeline_frames(self):
        self.prepare_shots();r=Resolve(self.video.name)
        media=core.read_json(core.prod(self.video)/"shot_media.json")
        for m in media.values():
            m["fps"]=30;r.project.fps_by_path[m["path"]]=30
        core.write_json(core.prod(self.video)/"shot_media.json",media)
        resolve_ops.apply(self.video,"voice",r)
        resolve_ops.apply(self.video,"shots",r)
        self.assertEqual(resolve_ops.check(self.video,r)["runtime_s"],480)

    def test_technical_ingest_never_grants_visual_approval(self):
        p=self.prepare_voice();resolve_ops.apply(self.video,"voice",Resolve(self.video.name));pipeline.missing_prompts(self.video)
        folder=self.video/"shots";folder.mkdir()
        for i in range(1,62):(folder/f"{i}.mp4").write_bytes(f"file {i}".encode())
        def metadata(path,decode=False):
            return {"duration":9,"fps":24,"video":True,"audio":True,"width":320,"height":180,"size":12,"sha256":core.digest(path)}
        with patch.object(pipeline,"probe",side_effect=metadata): result=pipeline.ingest(self.video)
        self.assertEqual(result["technical_pass"],61)
        self.assertTrue(all(not x["approved"] for x in core.read_json(core.prod(self.video)/"shot_qc.json")["shots"].values()))
        with self.assertRaisesRegex(core.Stop,"Intro needs 8\+ reviewed"):pipeline.hook(self.video)

    def test_corrupt_and_short_shots_are_aggregated(self):
        self.prepare_voice();resolve_ops.apply(self.video,"voice",Resolve(self.video.name));pipeline.missing_prompts(self.video)
        folder=self.video/"shots";folder.mkdir()
        for i in range(1,62):(folder/f"{i}.mp4").write_bytes(f"file {i}".encode())
        def metadata(path,decode=False):
            if Path(path).stem=="1":raise core.Stop("broken stream")
            return {"duration":1,"fps":24,"video":True,"audio":True,"width":320,"height":180,"sha256":core.digest(path)}
        with patch.object(pipeline,"probe",side_effect=metadata):
            with self.assertRaises(core.Stop) as exc:pipeline.ingest(self.video)
        self.assertIn("1.mp4",str(exc.exception));self.assertIn("61.mp4",str(exc.exception))
        self.assertFalse((core.prod(self.video)/"shot_media.json").exists())

    def test_prompts_require_verified_narrator_placement(self):
        install(self.video,conformed=True)
        with self.assertRaisesRegex(core.Stop,"verify narrator A2"):pipeline.missing_prompts(self.video)

    def test_hook_requires_all_roles_and_withholds_payoff(self):
        self.prepare_shots();q=core.read_json(core.prod(self.video)/"shot_qc.json")
        for entry in q["shots"].values():entry["hook_ok"]=False
        core.write_json(core.prod(self.video)/"shot_qc.json",q)
        with self.assertRaisesRegex(core.Stop,"Intro needs 8\+ reviewed, spoiler-free"):pipeline.hook(self.video)

    def test_wrong_project_and_endpoint_mismatch(self):
        self.prepare_voice()
        with self.assertRaisesRegex(core.Stop,"Open Resolve project"):resolve_ops.apply(self.video,"voice",Resolve("other"))
        r=Resolve(self.video.name,"inclusive")
        with self.assertRaisesRegex(core.Stop,"frame convention"):resolve_ops.apply(self.video,"voice",r)
        self.assertTrue(any(t.name.startswith(timeline_name(self.video)+"_bak_") for t in r.project.timelines))
        with patch.object(resolve_ops,"config",return_value={"resolve":{"source_end":"inclusive"}}):
            r=Resolve(self.video.name,"inclusive")
            self.assertGreater(resolve_ops.apply(self.video,"voice",r)["placed"],0)

    def test_backup_failure_prevents_any_clip_append(self):
        self.prepare_voice();r=Resolve(self.video.name);r.project.fail_backup=True
        with self.assertRaisesRegex(core.Stop,"Backup failed"):resolve_ops.apply(self.video,"voice",r)
        self.assertTrue(all(not t.items for t in r.project.timelines))

    def test_changed_voice_cannot_overwrite_a2(self):
        self.prepare_voice();r=Resolve(self.video.name);resolve_ops.apply(self.video,"voice",r)
        (self.video/"voice/1.mp3").write_bytes(b"changed")
        with self.assertRaisesRegex(core.Stop,"Voice changed"):resolve_ops.apply(self.video,"voice",r)

    def test_youtube_private_ai_disclosure_and_aware_schedule(self):
        meta={"title":"Test","description":"AI dramatization","tags":["wildlife"]}
        body=youtube.upload_body(meta)
        self.assertEqual(body["status"]["privacyStatus"],"private")
        self.assertTrue(body["status"]["containsSyntheticMedia"])
        with self.assertRaisesRegex(core.Stop,"time-zone"):youtube.upload_body(meta,"2099-01-01T18:00:00")
        with self.assertRaisesRegex(core.Stop,"past"):youtube.upload_body(meta,"2001-01-01T18:00:00+07:00")
        self.assertEqual(youtube.upload_body(meta,"2099-01-01T18:00:00+07:00")["status"]["publishAt"],"2099-01-01T11:00:00Z")

    def test_seo_digest_title_tags_and_meta_assembly(self):
        from dvr_cowork.fullai import seo
        vids=[{"title":"Snow Leopard vs Ibex | Wildlife Documentary","channel":"A","views":900000,"days":30,"tags":["Snow Leopard","ibex"]},
              {"title":"Can the Kid Survive?","channel":"B","views":50000,"days":10,"tags":["snow leopard"]},
              {"title":"Snow Leopard vs Ibex | Wildlife Documentary","channel":"A","views":900000,"days":30,"tags":[]}]
        d=seo.trend_digest(vids,per_day=True)
        self.assertTrue(d.startswith("TOP 2") and "30000 | 900000 | Snow Leopard vs Ibex" in d,d)
        self.assertIn("TOP 2 BY VIEWS (views | title | channel):\n900000 | Snow Leopard",seo.trend_digest(vids,per_day=False))
        self.assertIn("question 1/2",d);self.assertTrue(d.split("TAGS: ")[1].startswith("snow leopard"))
        self.assertEqual(seo.trend_digest([]),"NO TREND DATA")
        self.assertEqual(seo.tag_budget(["A b","a b","x"*495,"c"]),["a b"])
        self.assertEqual(seo.full_title("Mother Ibex on a Cliff  |  Wild animals"),"Mother Ibex on a Cliff | Wild animals")
        with self.assertRaisesRegex(core.Stop,"exactly"): seo.full_title("Mother Ibex on a Cliff")
        with self.assertRaisesRegex(core.Stop,"100 chars"): seo.full_title("x"*90+" | Wildlife Documentary")
        install(self.video)
        draft={"titles":["Snow Leopard Hunts a Mother Ibex | Wildlife Documentary",
                         "The Mountain Goat Who Would Not Fall | Wildlife Documentary","Wolves at the Ledge | Shadow Canopy"],
               "hook":"H.","summary":"S.","tags":["snow leopard","ibex"],"hashtags":["#Wildlife","bad tag"],"pick":2}
        out=seo.assemble(self.video,draft)
        meta=core.read_json(core.prod(self.video)/"youtube_meta.json")
        self.assertEqual(meta["title"],"The Mountain Goat Who Would Not Fall | Wildlife Documentary")
        self.assertIn("Chapters\n00:00 Opening\n01:00 Fixture 2",meta["description"])
        self.assertTrue(meta["description"].endswith("not actual event footage.\n\n#Wildlife"))
        flags=[x for x in out.splitlines() if "FLAG" in x]
        self.assertEqual(len(flags),2,out)  # wolf + leopard are not in the ibex-only fixture cast; goat is fine
        self.assertEqual(youtube.upload_body(meta)["snippet"]["defaultAudioLanguage"],"en")
        st=core.read_json(core.prod(self.video)/"story.json");st["lang"]="es"
        core.write_json(core.prod(self.video)/"story.json",st)
        with self.assertRaisesRegex(core.Stop,"chapter names in Spanish"): seo.assemble(self.video,draft)
        seo.assemble(self.video,dict(draft,chapters=[f"Capítulo {i}" for i in range(len(seo.film(self.video)[2]))]))
        meta=core.read_json(core.prod(self.video)/"youtube_meta.json")
        self.assertIn("Capítulos\n00:00 Capítulo 0",meta["description"]);self.assertIn("generada con IA",meta["description"])
        self.assertEqual(youtube.upload_body(meta)["snippet"]["defaultLanguage"],"es")
        self.assertEqual(youtube.channel_of(self.root/"Chann_9_x"/"v"),None)

    def test_youtube_remove_forgets_key_and_unshared_token(self):
        a,b="UC"+"a"*22,"UC"+"b"*22
        from dvr_cowork import youtube as shared  # login / remove / channels live in the shared module
        with patch.object(shared,"CHANNELS",self.root/"channels.json"),patch.object(shared,"TOKENS",self.root/"tokens"):
            (self.root/"tokens").mkdir()
            for c in (a,b): (self.root/"tokens"/f"{c}.json").write_text("{}")
            core.write_json(shared.CHANNELS,{"Chann_1":a,"Chann_2":b,"Chann_3":b})
            self.assertEqual(shared.channel_of(r"D:\Chann_2_UntamedEmpire\v1"),b)
            shared.remove("Chann_1");shared.remove("Chann_2")
            self.assertEqual(core.read_json(shared.CHANNELS),{"Chann_3":b})
            self.assertFalse((self.root/"tokens"/f"{a}.json").exists())
            self.assertTrue((self.root/"tokens"/f"{b}.json").exists())  # still used by Chann_3
            with self.assertRaisesRegex(core.Stop,"not in"): shared.remove("Chann_1")

    def test_render_job_is_verified_before_completion_and_never_overwrites(self):
        self.prepare_shots();r=Resolve(self.video.name)
        resolve_ops.apply(self.video,"voice",r);resolve_ops.apply(self.video,"shots",r)
        result=resolve_ops.render_start(self.video,r)
        self.assertEqual(result["status"],"RUNNING")
        self.assertNotEqual(resolve_ops.render_status(self.video,r)["status"],"VERIFIED")
        r.project.render_running=False;r.project.jobs[result["job"]]={"JobStatus":"Complete"}
        with self.assertRaises(core.Stop):resolve_ops.render_status(self.video,r)
        Path(result["path"]).write_bytes(b"fake completed render")
        with patch.object(resolve_ops,"probe",return_value={"video":True,"audio":True,"duration":480,"sha256":"mock output hash"}):
            completed=resolve_ops.render_status(self.video,r)
        self.assertEqual(completed["status"],"VERIFIED")
        self.assertEqual(core.read_json(core.prod(self.video)/"state.json")["stage"],"RENDERED")
        again=resolve_ops.render_start(self.video,r)
        self.assertTrue(again["path"].endswith("_v2.mp4"))
        self.assertEqual(Path(result["path"]).read_bytes(),b"fake completed render")

    def test_unknown_upload_blocks_retry_and_completed_upload_is_idempotent(self):
        install(self.video,conformed=True)
        p=self.video/"Done_snow_story.mp4";p.write_bytes(b"mock render")
        core.write_json(core.prod(self.video)/"render.json",{"status":"VERIFIED","path":str(p),"sha256":core.digest(p)})
        meta={"title":"Test","description":"AI dramatization","tags":["mountains"]}
        core.write_json(core.prod(self.video)/"youtube_meta.json",meta)
        channel="UC"+"a"*22
        preview=youtube.upload(self.video,channel)
        meta["approved_request_hash"]=preview["request_hash"];core.write_json(core.prod(self.video)/"youtube_meta.json",meta)
        core.write_json(core.prod(self.video)/"youtube.json",{"status":"UNKNOWN","request_hash":preview["request_hash"]})
        with self.assertRaisesRegex(core.Stop,"outcome is uncertain"):youtube.upload(self.video,channel,apply=True)
        receipt={"status":"COMPLETE","request_hash":preview["request_hash"],"id":"abc"}
        core.write_json(core.prod(self.video)/"youtube.json",receipt)
        self.assertEqual(youtube.upload(self.video,channel,apply=True),receipt)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"FFmpeg required")
    def test_real_ffmpeg_probe_decode_and_numeric_order(self):
        p=self.root/"clip30.mp4"
        core.run(["ffmpeg","-nostdin","-v","error","-f","lavfi","-i","color=c=gray:s=320x180:r=30",
                  "-f","lavfi","-i","sine=frequency=200:sample_rate=48000","-t","6","-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac",p])
        m=core.probe(p,decode=True)
        self.assertTrue(m["audio"] and m["video"]);self.assertAlmostEqual(m["fps"],30)
        self.assertAlmostEqual(m["duration"],6,places=1)
        p.write_bytes(b"unfinished copy")
        with self.assertRaises(core.Stop):core.probe(p,decode=True)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"FFmpeg required")
    def test_conform_with_real_numbered_mp3_files(self):
        initial=install(self.video)
        folder=self.video/"voice";folder.mkdir()
        tone=self.root/"timing_fixture.mp3"
        core.run(["ffmpeg","-nostdin","-v","error","-f","lavfi","-i","sine=frequency=220:sample_rate=16000",
                  "-t","13.25","-c:a","libmp3lame","-b:a","32k",tone])
        for v in initial["voice"]:shutil.copyfile(tone,folder/f"{v['id']}.mp3")
        result=pipeline.conform(self.video)
        plan=story.load_plan(self.video,conformed=True)
        self.assertEqual(result["blocks"],len(initial["voice"]))
        self.assertNotEqual(initial["voice"][0]["duration_f"],plan["voice"][0]["duration_f"])
        self.assertTrue(.85<result["occupancy"]<.93)
        self.assertEqual(core.read_json(core.prod(self.video)/"state.json")["stage"],"VOICE_CONFORMED")

    def test_a3_intro_music_then_synthesized_wind(self):
        plan=self.prepare_shots();r=Resolve(self.video.name)
        resolve_ops.apply(self.video,"voice",r);resolve_ops.apply(self.video,"shots",r)
        lib=self.root/"lib";lib.mkdir();song=lib/"artist-tense-123.mp3"
        core.run(["ffmpeg","-nostdin","-v","error","-f","lavfi","-i",TENSE_SONG,"-t","90",song])
        with self.assertRaisesRegex(core.Stop,"license"):resolve_ops.music(self.video,song,resolve=r)
        (lib/"orchestral-tense-123-license.txt").write_text("Pixabay license")
        cut=max(s["end_f"] for s in plan["slots"] if s["phase"]=="hook")
        body=[sc for sc in plan["scenes"] if sc["end_f"]>cut]
        # a licensed bed long enough for its scene is placed as-is; a scene without one gets synthesized wind
        bed=lib/"blizzard-777.mp3";core.run(["ffmpeg","-nostdin","-v","error","-f","lavfi","-i",
            "anoisesrc=c=pink:r=48000","-t","300",bed]);(lib/"blizzard-777.license.txt").write_text("Epidemic")
        bird=lib/"chough-55.mp3";core.run(["ffmpeg","-nostdin","-v","error","-f","lavfi","-i",
            "sine=frequency=3000:sample_rate=48000","-t","3",bird]);(lib/"chough-55.license.txt").write_text("Epidemic")
        first=next(s for s in plan["slots"] if s["prompt_id"] and s["start_f"]>=cut)
        with self.assertRaisesRegex(core.Stop,"pre-lap"):  # A5 under the pre-lap is taken
            resolve_ops.music(self.video,song,resolve=r,birds={str(first["prompt_id"]):str(bird)})
        calm=next(s for s in plan["slots"] if s["prompt_id"] and s["start_f"]>=cut+96)
        result=resolve_ops.music(self.video,song,resolve=r,beds={body[1]["id"]:str(bed)},birds={str(calm["prompt_id"]):str(bird)})
        tl=r.project.timelines[0]
        # intro song: opening (A7) -> climax (A8) -> ending (A7), tiling the hook with one-beat crossfades
        a7=sorted(tl.items["audio",7],key=lambda x:x.start);a8=tl.items["audio",8]
        self.assertEqual((len(a7),len(a8)),(2,1))
        self.assertEqual((a7[0].start-86400,a7[1].end-86400),(0,cut))
        self.assertTrue(a8[0].start<a7[0].end and a8[0].end>a7[1].start)  # real overlaps = crossfades
        self.assertEqual(a7[0].fades["FadeIn"],0)  # the film opens on the song's own first sound
        self.assertAlmostEqual(result["score"]["bpm"],120.0,delta=0.5)
        # the loud stretch (from 20 s), not the quiet opening; the analysis grid may land one hop before 20.00
        self.assertGreater(result["score"]["climax_src_s"],19.5)
        a5=sorted(tl.items["audio",5],key=lambda x:x.start); pre,birds=a5[0],a5[1:]
        # pre-lap (user 2026-11-06): story 1's wind 4 s before the black gap -> 4 s into the story, 4 s fades
        gap=pipeline.intro_gap_f(plan)
        self.assertEqual((pre.start-86400,pre.end-86400,pre.fades),(cut-gap-96,cut+96,{"FadeIn":96,"FadeOut":96}))
        self.assertEqual(pre.properties["AudioVolume"],-3.36)
        self.assertEqual([(b.start-86400,b.end-86400) for b in birds],[(calm["start_f"],calm["end_f"])])
        self.assertEqual(birds[0].properties["AudioVolume"],-20.0)
        beds=sorted(tl.items["audio",3]+tl.items["audio",4],key=lambda x:x.start)
        self.assertEqual(beds[0].properties["AudioVolume"],-3.36)
        self.assertEqual(len(beds),len(body))  # one bed per scene after the hook
        self.assertEqual([len(tl.items["audio",3]),len(tl.items["audio",4])],[(len(body)+1)//2,len(body)//2])
        self.assertEqual((beds[0].start-86400,beds[-1].end-86400),(cut,plan["runtime_f"]))
        for x,y in zip(beds,beds[1:]): self.assertEqual(x.end-y.start,96)  # 4 s crossfade
        self.assertEqual((beds[0].fades,beds[1].fades,beds[-1].fades),
                         ({"FadeIn":96,"FadeOut":96},{"FadeIn":96,"FadeOut":96},{"FadeIn":96,"FadeOut":48}))
        self.assertEqual(beds[1].clip.path,str(bed))
        self.assertEqual(result["wind"],"synthesized")
        self.assertEqual(result["beds"][0],str(song))  # the song itself is placed; no file is made from it
        self.assertAlmostEqual(core.probe(beds[0].clip.path)["duration"],(beds[0].end-beds[0].start)/24,places=1)
        args=dict(resolve=r,beds={body[1]["id"]:str(bed)},birds={str(calm["prompt_id"]):str(bird)})
        self.assertEqual(resolve_ops.music(self.video,song,**args)["placed"],[])
        # body music on A7 after the hook is not `music`'s and survives a swap
        tl.items["audio",7].append(Item(Clip(str(lib/"body.mp3")),86400+cut+240,86400+cut+960,0))
        beds[0].SetProperty("AudioVolume",-6.0)  # user's manual gain survives a swap
        args["beds"]={body[2]["id"]:str(bed)}
        with self.assertRaisesRegex(core.Stop,"--replace"):resolve_ops.music(self.video,song,**args)
        swap=resolve_ops.music(self.video,song,replace=True,**args)
        beds=sorted(tl.items["audio",3]+tl.items["audio",4],key=lambda x:x.start)
        self.assertEqual((sorted(swap["placed"]),beds[0].properties["AudioVolume"],beds[2].clip.path,len(tl.items["audio",7])),
                         (sorted(["Bed "+body[1]["id"],"Bed "+body[2]["id"]]),-6.0,str(bed),3))
        with self.assertRaisesRegex(core.Stop,"unknown"):resolve_ops.music(self.video,song,resolve=r,beds={"S01":str(bed)})
        with self.assertRaisesRegex(core.Stop,"Birds for unknown"):resolve_ops.music(self.video,song,resolve=r,birds={"9999":str(bird)})

    def test_intro_song_cuts_land_on_the_beat(self):
        song=self.root/"tense.wav";core.run(["ffmpeg","-nostdin","-v","error","-f","lavfi","-i",TENSE_SONG,"-t","90",song])
        score=intro_music.plan(song,30.0)
        self.assertAlmostEqual(score["bpm"],120.0,delta=0.5)
        P=0.5
        for t,g in zip(score["cuts_s"],score["segments"][1:]):  # the source at each cut sits on a beat
            src=g["source_start_s"]+g["fade_in_s"]/2
            self.assertAlmostEqual((src/P)%1 if (src/P)%1<0.5 else (src/P)%1-1,0,delta=0.1)
        segs=score["segments"]
        self.assertEqual((segs[0]["start_s"],segs[-1]["end_s"]),(0.0,30.0))
        # the climax is the stretch with a kick on every beat, not a louder pad without hits
        pad=self.root/"pad.wav";core.run(["ffmpeg","-nostdin","-v","error","-f","lavfi","-i",PAD_VS_KICKS,"-t","90",pad])
        drums=intro_music.plan(pad,30.0)
        self.assertTrue(45<=drums["climax_src_s"]<=70,drums["climax_src_s"])
        self.assertGreaterEqual(drums["climax_drive"],0.8)
        with self.assertRaisesRegex(core.Stop,"longer song"):
            short=self.root/"short.wav";core.run(["ffmpeg","-nostdin","-v","error","-f","lavfi","-i",TENSE_SONG,"-t","20",short])
            intro_music.plan(short,30.0)

    def test_original_forward_test_example_stays_buildable(self):
        s=core.read_json(Path(__file__).with_name("last-dry-seam.story.json"))
        s["scenes"][0].pop("shots")  # written for the old five 6 s hook slots; the hook is voice only now
        s["scenes"][1]["shots"][0]["intensity"]=3  # the setup now needs one shot of real action
        p=story.compile_story(s)
        self.assertEqual(p["runtime_f"]/p["fps"],480)
        self.assertEqual(len(p["voice"]),32)
        self.assertEqual(len(p["slots"]),76)


if __name__=="__main__":unittest.main()
