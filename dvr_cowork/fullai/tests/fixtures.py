"""Artificial timing fixtures only. These are not production narration/templates."""
from pathlib import Path
from dvr_cowork.fullai.core import object_hash,prod,write_json
from dvr_cowork.fullai.story import compile_story,documents


def source(minutes=8):
    roles=["threat","vulnerability","pursuit","obstacle","unanswered","none","none","none"]
    scenes=[]
    phases=[("hook",30),("setup",30)]+[("story",60)]*int(minutes-2)+[("ending",60)]
    for j,(phase,seconds) in enumerate(phases):
        ds=[] if phase=="hook" else [6]*5 if seconds==30 else [6,9,7,8,6,9,7,8]
        shots=[]
        for k,d in enumerate(ds):
            shot={"duration_s":d}
            if phase!="hook":
                shot.update(title=f"Fixture shot {j}/{k}",characters=["M","K"],action=f"Fixture action {j}/{k}",camera=f"camera {k}",
                    direction="left to right",start_state=f"shelf {j}-{k}",end_state=f"shelf {j}-{k+1}",
                    beats=[f"Moment {j}/{k}/{i}" for i in range(4)],hook_role=roles[k] if phase=="story" else "none",
                    intensity=min(k,5),spoiler=phase!="story")
            shots.append(shot)
        voice=[{"en":" ".join([f"fixture{j}_{i}"]*32),"vi":f"Đoạn lời dẫn thử nghiệm {j} phần {i}, chỉ dùng để kiểm tra thời gian."}
               for i in range(2 if seconds==30 else 4)]
        scene={"id":f"B{j}","title":f"Fixture {j}","phase":phase,"change":f"New consequence {j}","shots":shots,"voice":voice}
        if phase=="hook": scene.pop("shots")  # the hook is voice only: `hook` cuts it from reviewed body sources
        scenes.append(scene)
    return {"schema":2,"title":"Test mountain story","target_minutes":minutes,"fps":24,"wpm":145,
            "premise":"Test progression","central_question":"Will the pair cross?","payoff":"They reach the next shelf.",
            "characters":[{"id":"M","species":"ibex","count":1,"terms":["mother"],"lock":"Exactly one adult female, gray coat, right ear notch",
                           "details":["leads the climb"],"absolute_lock":"Notch on the RIGHT ear only."},
                          {"id":"K","species":"ibex","count":1,"terms":["kid"],"lock":"Exactly one small cream-colored kid","details":["stays close to the mother"]}],
            "environment":"Neutral daylight, white snow and gray rock.","geography":"One cliff, same eastbound shelf.",
            "synthetic_disclosure":"AI-generated dramatization, not actual event footage.",
            "count_lock":["Exactly 2 ibex: 1 mother + 1 kid"],"zones":["Fixture shelf"],
            "terrain_lock":["gray rock, white snow"],"light_lock":["neutral daylight, constant"],"scenes":scenes}


def install(video,minutes=8,conformed=False,pin=False):
    v=Path(video); v.mkdir(parents=True,exist_ok=True)
    from dvr_cowork.profile import create,load,pinned
    profile=load("full_ai_mountain")
    if pin:
        create(v,"full_ai_mountain",minutes=minutes);profile=pinned(v)[1]
    s=source(minutes); plan=compile_story(s,None,profile)
    if conformed:
        plan=compile_story(s,[x["duration_f"]/24 for x in plan["voice"]],profile)
    write_json(prod(v)/"story.json",s);write_json(prod(v)/"plan.json",plan)
    a=v/"audios";a.mkdir(exist_ok=True)
    for name,text in documents(plan).items(): (a/name).write_text(text,encoding="utf-8")
    return plan
