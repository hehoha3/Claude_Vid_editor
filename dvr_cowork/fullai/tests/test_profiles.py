"""Profile routing, pinned snapshots, v2 intro (2–4 s cuts from body sources) and the one-call voice step."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from dvr_cowork import profile as dvr_profile
from dvr_cowork.fullai import core, pipeline, resolve_ops, story
from dvr_cowork.fullai.tests.fixtures import install, source
from dvr_cowork.fullai.tests.fake_resolve import Resolve
from dvr_cowork.videokey import timeline_name


def v2_profile():
    return dvr_profile.load("full_ai_mountain", 2)


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.video = self.root / "Chann_3_WildPeril" / "vid_041126_1"
        # The fixture films are v2 (6-9 s, four beats); v3 (user 2026-11-09, 3-7 s, 1-2 beats) is tested on its own.
        real = dvr_profile.load
        self.v2 = patch.object(dvr_profile, "load", lambda name, version=None, allow_disabled=False:
                               real(name, version or (2 if dvr_profile.profile_id(name) == "full_ai_mountain" else None),
                                    allow_disabled))
        self.v2.start()
    def tearDown(self): self.v2.stop(); self.temp.cleanup()

    def test_migrate_v2_to_v3_only_without_shots(self):
        dvr_profile.create(self.video, "full_ai_mountain", region="himalaya", minutes=8, title="T")
        dry = dvr_profile.migrate(self.video, 3)
        self.assertTrue(dry["dry_run"]); self.assertEqual(dvr_profile.pinned(self.video)[0]["profile_version"], 2)
        (self.video / "shots").mkdir(); (self.video / "shots" / "1.mp4").write_bytes(b"x")
        with self.assertRaisesRegex(core.Stop, "already holds 1"): dvr_profile.migrate(self.video, 3, apply=True)
        (self.video / "shots" / "1.mp4").unlink()
        self.assertTrue(dvr_profile.migrate(self.video, 3, apply=True)["migrated"])
        d, p = dvr_profile.pinned(self.video)
        self.assertEqual((d["profile_version"], d["region_id"], d["title"], p["body"]["shot_max_s"]), (3, "frozen", "T", 7))
        self.assertEqual(len(list(self.video.glob("video.project.v2_*.json"))), 1)

    # --- routing / descriptor -------------------------------------------------------------------------------------
    def test_aliases_versions_and_disabled_ocean(self):
        self.assertEqual(dvr_profile.load("full_ai_mountain")["intro"]["mode"], "cuts_from_body")
        self.assertEqual(sorted(p.name for p in dvr_profile.PROFILES.glob("full_ai_mountain.*")),
                         ["full_ai_mountain.v1.json", "full_ai_mountain.v2.json", "full_ai_mountain.v3.json"])  # v1/v2 = pinned films
        self.assertEqual(dvr_profile.load("full_ai_mountain")["runtime"]["max_minutes"], 15)
        self.assertEqual(dvr_profile.load("footage_ai_long")["runtime"]["max_minutes"], 180)
        self.assertEqual(dvr_profile.load("footage_ai_long")["engine_id"], "footage_long")
        with self.assertRaisesRegex(core.Stop, "disabled"): dvr_profile.load("ocean")
        with self.assertRaisesRegex(core.Stop, "Unknown profile"): dvr_profile.load("full AI ocean")

    def test_descriptor_pins_snapshot_and_workspace_edits_do_not_move_the_film(self):
        work = self.root / "profiles"; shutil.copytree(dvr_profile.PROFILES, work)
        with patch.object(dvr_profile, "PROFILES", work):
            d = dvr_profile.create(self.video, "full_ai_mountain", minutes=10)
            self.assertEqual((d["channel_key"], d["video_id"], d["region_id"]), ("Chann_3", "Chann_3__vid_041126_1", "frozen"))
            f = work / "full_ai_mountain.v2.json"; p = json.loads(f.read_text("utf-8"))
            p["body"]["shot_max_s"] = 12; f.write_text(json.dumps(p), "utf-8")
            self.assertEqual(dvr_profile.pinned(self.video)[1]["body"]["shot_max_s"], 9)
            with self.assertRaisesRegex(core.Stop, "exists"): dvr_profile.create(self.video, "full_ai_mountain")
        with self.assertRaisesRegex(core.Stop, "outside"): dvr_profile.create(self.root / "Chann_3_x" / "v2", "full_ai_mountain", minutes=16)
        lock = core.prod(self.video) / "profile.lock.json"; data = core.read_json(lock)
        data["profile"]["body"]["shot_max_s"] = 10; core.write_json(lock, data)
        with self.assertRaisesRegex(core.Stop, "does not match"): dvr_profile.pinned(self.video)

    def test_same_folder_name_in_two_channels_gets_two_ids(self):
        a = dvr_profile.create(self.root / "Chann_1_a" / "vid_1", "full_ai_mountain")
        b = dvr_profile.create(self.root / "Chann_2_b" / "vid_1", "full_ai_mountain")
        self.assertNotEqual(a["video_id"], b["video_id"])

    def test_day_project_from_folder_name(self):
        self.assertEqual(core.day_project("himalaya_051126_1"), "vid_051126")
        self.assertEqual(core.day_project("africa_051126"), "vid_051126")
        self.assertEqual(core.day_project("vid_021126_1"), "vid_021126_1")
        self.assertEqual(core.day_project("my film"), "my film")

    def test_legacy_detection_conflict_and_backfill_dry_run(self):
        m = self.root / "Chann_1_a" / "vid_old"; (m / ".production").mkdir(parents=True); (m / ".production/story.json").write_text("{}")
        l = self.root / "Chann_1_a" / "africa_1"; (l / "audios").mkdir(parents=True); (l / "audios/X_Timestamp_EN_VI.md").write_text("x")
        self.assertEqual(dvr_profile.detect(m)["profile"], "full_ai_mountain")
        self.assertEqual(dvr_profile.detect(l)["profile"], "footage_ai_long")
        self.assertEqual(dvr_profile.detect(l / "audios")["video"], str(l.resolve()))
        dry = dvr_profile.backfill(m)
        self.assertTrue(dry["dry_run"]); self.assertFalse((m / "video.project.json").exists())
        dvr_profile.backfill(m, apply=True)
        self.assertEqual(dvr_profile.pinned(m)[1]["profile_version"], 1)
        e = self.root / "Chann_1_a" / "vid_empty"; e.mkdir()
        self.assertIsNone(dvr_profile.detect(e)["profile"])  # never guessed
        with self.assertRaisesRegex(core.Stop, r"ask footage / footage\+AI / full-AI"): dvr_profile.context(e, "voice")
        (l / "plan.md").write_text("x"); (l / ".production").mkdir(); (l / ".production/story.json").write_text("{}")
        with self.assertRaisesRegex(core.Stop, "Both engines"): dvr_profile.detect(l)

    def test_region_prompt_locks_and_reminder(self):
        self.assertIn("snow", story.region_locks("himalaya")["motion"])
        self.assertEqual(story.region_locks("alps"), story.region_locks("himalaya"))  # v1 mountain regions
        for region in ("amazon", "africa"):  # user 2026-11-05: remind until the user writes these locks
            with self.assertRaisesRegex(core.Stop, "No full-AI prompt locks"): story.region_locks(region)

    def test_context_pack_is_short_and_phase_scoped(self):
        install(self.video, pin=True)
        pack = dvr_profile.context(self.video, "sound")
        self.assertEqual(pack["refs"], [".claude/skills/doc-edit/references/full-ai.md"])
        self.assertEqual(pack["contract"]["intro"]["cut_max_s"], 4)
        self.assertLess(len(json.dumps(pack)), 900)
        self.assertIn("no voice/", " ".join(dvr_profile.context(self.video, "voice")["blockers"]))

    # --- v2 compile -------------------------------------------------------------------------------------------------
    def test_v2_runtime_window_and_body_contract(self):
        p = v2_profile()
        for minutes in (8, 10, 15):
            plan = story.compile_story(source(minutes), None, p)
            hook = plan["slots"][0]
            self.assertEqual((hook["id"], hook["end_f"]), ("HOOK", 720))
            self.assertEqual(plan["runtime_f"], minutes * 1440)
            self.assertTrue(all(144 <= s["end_f"] - s["start_f"] <= 216 for s in plan["slots"][1:]))
            self.assertIn("2–4s from reviewed body sources", story.documents(plan)["visual_plan.md"])
        with self.assertRaisesRegex(core.Stop, "target_minutes 8–15"): story.compile_story(source(16), None, p)
        s = source(); s["scenes"][0]["shots"] = [{"duration_s": 6}] * 5
        with self.assertRaisesRegex(core.Stop, "voice only"): story.compile_story(s, None, p)

    def test_v2_contact_words_and_calm_setup_rejected_in_one_run(self):
        p = v2_profile(); s = source()
        s["scenes"][3]["shots"][1]["beats"][2] = "the leopard bites the kid's flank"
        s["scenes"][4]["shots"][0]["action"] = "Horns clash on the ledge"
        with self.assertRaises(core.Stop) as e: story.compile_story(s, None, p)
        self.assertIn("bites", str(e.exception)); self.assertIn("horns clash", str(e.exception))
        s2 = source(); s2["scenes"][5]["shots"][2]["beats"][1] = "mother and kid stare at each other"
        with self.assertRaisesRegex(core.Stop, "stare"): story.compile_story(s2, None, p)
        s = source()
        for sh in s["scenes"][1]["shots"]: sh["intensity"] = 1
        with self.assertRaisesRegex(core.Stop, "setup needs action"): story.compile_story(s, None, p)

    # --- v2 hook + assemble -----------------------------------------------------------------------------------------
    def prepare_shots(self, speed=None, clean=None):
        plan = install(self.video, conformed=True, pin=True)
        folder = self.video / "voice"; folder.mkdir()
        data = {}
        for v in plan["voice"]:
            f = folder / f"{v['id']}.mp3"; f.write_bytes(f"v{v['id']}".encode())
            data[str(v["id"])] = {"path": str(f), "sha256": core.digest(f), "duration": v["duration_f"] / 24}
        core.write_json(core.prod(self.video) / "voice_media.json", data)
        r = Resolve(self.video.name)
        resolve_ops.apply(self.video, "voice", r); pipeline.missing_prompts(self.video)
        shots = self.video / "shots"; shots.mkdir()
        ev = core.prod(self.video) / "review/e.jpg"; ev.parent.mkdir(); ev.write_bytes(b"e")
        media, qc = {}, {"plan_hash": core.object_hash(plan), "shots": {}}
        for row in core.read_json(core.prod(self.video) / "manifest.json")["rows"]:
            i = str(row["prompt_id"]); f = shots / f"{i}.mp4"; f.write_bytes(f"s{i}".encode())
            media[i] = {"path": str(f), "sha256": core.digest(f), "duration": 10, "fps": 24,
                        "prompt_sha256": row["prompt_sha256"], "audio": True, "video": True}
            q = {"sha256": media[i]["sha256"], "prompt_sha256": row["prompt_sha256"], "approved": True, "reviewer": "test",
                 "notes": "fixture", "hook_ok": True, "hook_start_s": 1, "evidence": [str(ev)]}
            if speed: q["hook_speed"] = speed
            if clean: q["hook_end_s"] = 1 + clean
            qc["shots"][i] = q
        core.write_json(core.prod(self.video) / "shot_media.json", media)
        core.write_json(core.prod(self.video) / "shot_qc.json", qc)
        return plan, r

    def test_v2_hook_tiles_30s_with_2_to_4s_cuts_one_per_source(self):
        plan, _ = self.prepare_shots()
        out = pipeline.hook(self.video)
        cuts = core.read_json(core.prod(self.video) / "hook.json")["cuts"]
        self.assertTrue(10 <= out["cuts"] <= 12)
        gap = pipeline.intro_gap_f(plan)  # 0.6 s black before story 1, as the 1h films (user 2026-11-06)
        self.assertEqual(gap, 14)
        self.assertEqual(sum(c["end_f"] - c["start_f"] for c in cuts), 720 - gap)
        self.assertEqual(cuts[-1]["end_f"], pipeline.hook_window(plan)[1] - gap)
        self.assertTrue(all(48 <= c["end_f"] - c["start_f"] <= 96 for c in cuts))
        self.assertEqual(len({c["source_prompt"] for c in cuts}), len(cuts))
        self.assertEqual(cuts[-1]["role"], "unanswered")
        self.assertEqual(len({c["role"] for c in cuts}), 5)  # several cuts may share a role, every role is present

    def test_v2_retime_span_and_short_clean_range(self):
        self.prepare_shots(speed=1.2, clean=4.0)
        pipeline.hook(self.video)
        for c in core.read_json(core.prod(self.video) / "hook.json")["cuts"]:
            self.assertAlmostEqual(c["source_span_s"], (c["end_f"] - c["start_f"]) / 24 * 1.2)
            self.assertLessEqual(c["source_span_s"], 4.0 + 1e-9)
            self.assertEqual(c["a1"], "mute")
        q = core.read_json(core.prod(self.video) / "shot_qc.json")
        for x in q["shots"].values(): x["hook_end_s"] = 2.5; x["hook_speed"] = 1.0  # 1.5 s clean < 2 s cut
        core.write_json(core.prod(self.video) / "shot_qc.json", q)
        with self.assertRaisesRegex(core.Stop, "too short"): pipeline.hook(self.video)
        for x in q["shots"].values(): x["hook_speed"] = 1.05
        core.write_json(core.prod(self.video) / "shot_qc.json", q)
        with self.assertRaisesRegex(core.Stop, "must be 1.0 or within"): pipeline.hook(self.video)

    def test_v2_assemble_keeps_every_body_slot_and_live_check_passes(self):
        plan, r = self.prepare_shots(speed=1.2)
        pipeline.hook(self.video)
        cuts = core.read_json(core.prod(self.video) / "hook.json")["cuts"]
        res = resolve_ops.apply(self.video, "shots", r)
        body = [s for s in plan["slots"] if s["prompt_id"]]
        self.assertEqual(res["verified"], len(cuts) + 2 * len(body))  # muted retimed cuts: V1 only
        tl = next(t for t in r.project.timelines if t.name == timeline_name(self.video))
        self.assertTrue(all(getattr(i, "speed", 1) == 1.2 for i in tl.items["video", 1][:len(cuts)]))
        self.assertEqual(resolve_ops.check(self.video, r)["v1_shots"], len(cuts) + len(body))
        self.assertEqual(resolve_ops.apply(self.video, "shots", r)["placed"], 0)

    def test_ingest_reuses_unchanged_files_and_rechecks_only_the_changed_one(self):
        self.prepare_shots()
        (core.prod(self.video) / "shot_media.json").unlink()
        calls = []
        def fake(path, decode=False):
            calls.append(Path(path).name); st = Path(path).stat()
            return {"duration": 10, "fps": 24, "video": True, "audio": True, "width": 1920, "height": 1080,
                    "size": st.st_size, "mtime_ns": st.st_mtime_ns, "sha256": core.digest(path)}
        with patch.object(pipeline, "probe", side_effect=fake):
            n = pipeline.ingest(self.video)["technical_pass"]
            self.assertEqual(len(calls), n)
            q = core.read_json(core.prod(self.video) / "shot_qc.json")
            for x in q["shots"].values(): x["approved"] = True
            core.write_json(core.prod(self.video) / "shot_qc.json", q)
            calls.clear(); self.assertEqual(pipeline.ingest(self.video)["reused_unchanged"], n); self.assertEqual(calls, [])
            (self.video / "shots/3.mp4").write_bytes(b"regenerated clip")
            out = pipeline.ingest(self.video)
        self.assertEqual((calls, out["reused_unchanged"]), (["3.mp4"], n - 1))

    def test_voice_ready_stops_before_resolve_when_voice_is_missing(self):
        install(self.video, conformed=True, pin=True)
        r = Resolve(self.video.name)
        with self.assertRaisesRegex(core.Stop, "missing"): resolve_ops.voice_ready(self.video, True, r)
        self.assertEqual(r.project.timelines, [])

    def test_voice_ready_places_a2_and_issues_prompts_in_one_call(self):
        plan = install(self.video, conformed=True, pin=True)
        folder = self.video / "voice"; folder.mkdir()
        for v in plan["voice"]: (folder / f"{v['id']}.mp3").write_bytes(b"x")
        durations = {str(folder / f"{v['id']}.mp3"): v["duration_f"] / 24 for v in plan["voice"]}
        fake = lambda p, decode=False: {"duration": durations[str(Path(p))], "fps": 0, "video": False, "audio": True,
                                        "width": 0, "height": 0, "size": 1, "sha256": core.digest(p)}
        with patch.object(pipeline, "probe", side_effect=fake):
            out = resolve_ops.voice_ready(self.video, True, Resolve(self.video.name))
        self.assertEqual(out["a2_verified"], len(plan["voice"]))
        self.assertEqual(out["prompts"], sum(bool(s["prompt_id"]) for s in plan["slots"]))
        self.assertEqual(out["next"], "stop: the user generates the shots")


if __name__ == "__main__":
    unittest.main()
