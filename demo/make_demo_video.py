#!/usr/bin/env python3
"""Produce demo/recallgraph-demo-day3.mp4 from LIVE RecallGraph output.

Method (honest, headless-VM friendly): there is no display/browser
recorder on this VM, so each beat's frame is *rendered* with Pillow —
but every word and number on screen is taken verbatim from live
captures of the real pipeline (demo/dump_live.py against the running
FalkorDB + the Day-3 UI APIs' shared code path), following
DEMO-SCRIPT-day3.md beat for beat. The persistence beat performs a
REAL `podman restart` of the FalkorDB container between two stat
captures and only claims survival if they match.

Narration: English TTS (Meta Shortwave, voice MAI_03) of the exact VO
lines in DEMO-SCRIPT-day3.md. Beat durations follow the script's shot
list (hook 15s, beats 35/25/25/30s, close 20s ≈ 2:30 total); narration
shorter than its slot leaves reading time on screen, as the script's
recording notes require (reasoning paths stay ≥4s per panel).

Run:  python3 demo/make_demo_video.py        (system python: needs PIL)
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo"
FRAMES = DEMO / "frames"
AUDIO = DEMO / "audio"
WORK = DEMO / "_work"
VENV_PY = str(ROOT / ".venv" / "bin" / "python")
PODMAN = ["podman", "--root", "/home/hatch/podman-storage",
          "--runroot", "/home/hatch/podman-runroot",
          "--storage-driver", "vfs", "--runtime", "/home/hatch/bin/crun"]
OUT = DEMO / "recallgraph-demo-day3.mp4"

W, H = 1280, 720
BG = (15, 20, 32)
PANEL = (23, 30, 46)
LINE = (44, 56, 82)
TEXT = (232, 236, 244)
DIM = (154, 167, 189)
ACCENT = (94, 200, 165)
BLUE = (94, 168, 232)
WARN = (232, 161, 58)
BAD = (224, 93, 93)
COLORS = {"Paper": (232, 161, 58), "Concept": (94, 168, 232),
          "Claim": (94, 200, 165), "Question": (180, 138, 224)}
FONT_DIR = "/usr/share/fonts/truetype/dejavu"
F_TITLE = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans-Bold.ttf", 44)
F_H = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans-Bold.ttf", 27)
F_BODY = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans.ttf", 21)
F_SMALL = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans.ttf", 17)
F_MONO = ImageFont.truetype(f"{FONT_DIR}/DejaVuSansMono.ttf", 16)
F_BIG = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans-Bold.ttf", 54)

# (key, script slot seconds, VO text from DEMO-SCRIPT-day3.md)
BEATS = [
    ("hook", 15,
     "AI agents forget. RecallGraph gives them a memory they can explain, "
     "a FalkorDB graph where every answer shows the path it took."),
    ("beat1", 35,
     "Ask a question, and RecallGraph doesn't just answer, it walks the "
     "graph: question, answer edge, supporting claims, even a two-hop "
     "evidence chain, then checks for contradictions and cites the paper."),
    ("beat2", 25,
     "No stored question matches, so it falls back to concept traversal "
     "and still finds the claim, with its citation. Nothing is faked; "
     "the path shows the detour."),
    ("beat3", 25,
     "And when the memory doesn't know, it says so, no hallucinated "
     "answer, just the steps it tried and a high-priority action: "
     "ingest a source."),
    ("beat4", 30,
     "Two agents share one graph. The Librarian writes; the Scout reads "
     "and acts. A document only the Librarian ever touched, the Scout "
     "can already answer from it."),
    ("close", 20,
     "Restart the database, the memory survives. RecallGraph: agent "
     "memory that shows its work. Built on FalkorDB for Graph Hacks."),
]


def run(cmd, **kw):
    print("+", " ".join(str(c) for c in cmd)[:140])
    return subprocess.run(cmd, check=True, capture_output=True,
                          text=True, **kw)


def wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        trial = f"{cur} {w_}".strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w_
    if cur:
        lines.append(cur)
    return lines


def text_block(draw, xy, text, font, fill, max_w, leading=6, max_lines=None):
    x, y = xy
    lines = wrap(draw, text, font, max_w)
    if max_lines:
        lines = lines[:max_lines]
    for ln in lines:
        draw.text((x, y), ln, font=font, fill=fill)
        y += font.size + leading
    return y


def base_frame(beat_label):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 64], fill=PANEL)
    d.text((36, 18), "RecallGraph", font=F_H, fill=TEXT)
    d.text((238, 22), "agent memory that shows its work", font=F_SMALL,
           fill=DIM)
    tw = d.textlength(beat_label, font=F_SMALL)
    d.text((W - 36 - tw, 22), beat_label, font=F_SMALL, fill=ACCENT)
    d.text((36, H - 34), "Graph Hacks · WeMakeDevs x FalkorDB · Track 2 + Track 1",
           font=F_SMALL, fill=DIM)
    return img, d


def draw_graph(d, snap, cx, cy, scale=1.0):
    ring = {"Paper": 62, "Concept": 118, "Claim": 178, "Question": 224}
    groups = {}
    for n in snap["nodes"]:
        groups.setdefault(n["label"], []).append(n)
    pos = {}
    for label, lst in groups.items():
        for i, n in enumerate(lst):
            import math
            a = (i / max(1, len(lst))) * math.tau + (ord(label[0]) % 7) * 0.35
            r = ring.get(label, 170) * scale
            pos[n["key"]] = (cx + r * 1.28 * __import__("math").cos(a),
                             cy + r * 0.86 * __import__("math").sin(a), n)
    for e in snap["edges"]:
        if e["from"] in pos and e["to"] in pos:
            d.line([pos[e["from"]][:2], pos[e["to"]][:2]], fill=LINE, width=1)
    for x, y, n in pos.values():
        c = COLORS[n["label"]]
        d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=c)
    lx = cx - 300
    for i, (label, c) in enumerate(COLORS.items()):
        x = lx + i * 150
        d.ellipse([x, cy + 218, x + 12, cy + 230], fill=c)
        d.text((x + 18, cy + 214), label, font=F_SMALL, fill=DIM)


def steps_block(d, x, y, result, max_w, max_steps=5):
    for s in result["reasoning_steps"][:max_steps]:
        d.ellipse([x, y + 3, x + 22, y + 25], fill=ACCENT)
        d.text((x + 6, y + 4), str(s["step"]), font=F_SMALL, fill=(11, 21, 18))
        y = text_block(d, (x + 34, y), s["description"], F_BODY, TEXT,
                       max_w - 34, leading=4, max_lines=2)
        found = ", ".join(s["found"]) if s["found"] else "—"
        y = text_block(d, (x + 34, y + 1),
                       f"{s['traversal']}  ->  {found}", F_MONO, BLUE,
                       max_w - 34, leading=8, max_lines=1)
        y += 4
    return y


def render_hook(cap):
    img, d = base_frame("HOOK · THE GRAPH")
    snap, stats = cap["snapshot"], cap["stats"]
    d.text((36, 92), "AI agents forget.", font=F_TITLE, fill=TEXT)
    d.text((36, 146),
           "RecallGraph gives them a memory they can explain.",
           font=F_H, fill=ACCENT)
    draw_graph(d, snap, 640, 400, scale=1.0)
    s = (f"{stats['total_nodes']} nodes / {stats['total_edges']} edges · "
         f"{stats['nodes']['Paper']} papers · {stats['nodes']['Claim']} claims "
         f"· FalkorDB graph: {stats['graph']}")
    d.text((36, 648), s, font=F_BODY, fill=TEXT)
    return img


def render_ask_beat(cap, idx, label, note=None):
    img, d = base_frame(label)
    r = cap["asks"][idx]
    y = text_block(d, (36, 88), f"Q: {r['query']}", F_H, TEXT, W - 72)
    y += 6
    d.rectangle([36, y, W - 36, y + 86], fill=PANEL)
    text_block(d, (52, y + 10), f"A: {r['answer_text']}", F_BODY, ACCENT,
               W - 104, max_lines=3)
    y += 100
    meta = f"Confidence: {r['confidence']}"
    if r.get("matched_question"):
        meta += f" · matched Question {r['matched_question']['id']}"
    else:
        meta += " · no stored Question matched — fallback traversal"
    if r.get("citations"):
        meta += " · Citation: " + "; ".join(
            c["title"] for c in r["citations"])
    y = text_block(d, (36, y), meta, F_SMALL, DIM, W - 72) + 8
    if note:
        y = text_block(d, (36, y), note, F_BODY, WARN, W - 72) + 6
    steps_block(d, 36, y, r, W - 72)
    return img


def render_beat3(cap):
    img = render_ask_beat(cap, 2, "BEAT 3 · HONESTY + GAPS")
    d = ImageDraw.Draw(img)
    brief = cap["brief"]["summary"]
    d.rectangle([36, 592, W - 36, 656], fill=PANEL)
    text_block(d, (52, 602), f"Scout brief: {brief}", F_BODY, TEXT,
               W - 104, max_lines=2)
    return img


def render_beat4(zebra):
    img, d = base_frame("BEAT 4 · TWO AGENTS, ONE MEMORY")
    ing, ans = zebra["ingest"], zebra["answer"]
    d.text((36, 88), "Librarian ingests a new document — “Zebra Indexing”",
           font=F_H, fill=TEXT)
    c = ing["counts"]
    counts_h = (f"{c['papers']} paper · {c['concepts']} concept · "
                f"{c['claims']} claim · {c['questions']} question · "
                f"{c['edges']} edges")
    y = text_block(
        d, (36, 132),
        f"Ingest report: {counts_h} · new claims: "
        f"{', '.join(ing['new_claim_ids']) or '—'} · graph "
        f"{ing['nodes_before']} -> {ing['nodes_after']} nodes",
        F_BODY, DIM, W - 72)
    y += 14
    d.text((36, y), "Scout answers from that same graph — no re-teaching",
           font=F_H, fill=TEXT)
    y += 44
    y = text_block(d, (36, y), f"Q: {ans['query']}", F_BODY, TEXT, W - 72)
    d.rectangle([36, y + 4, W - 36, y + 88], fill=PANEL)
    text_block(d, (52, y + 14), f"A: {ans['answer_text']}", F_BODY, ACCENT,
               W - 104, max_lines=3)
    y += 104
    steps_block(d, 36, y, ans, W - 72, max_steps=4)
    return img


def render_close(before, after):
    img, d = base_frame("CLOSE · PERSISTENCE")
    b, a = before["stats"], after["stats"]
    same = (b["total_nodes"], b["total_edges"]) == \
        (a["total_nodes"], a["total_edges"]) and after["ping"]
    d.text((36, 96), "Restart the database —", font=F_TITLE, fill=TEXT)
    d.text((36, 152), "the memory survives.", font=F_TITLE, fill=ACCENT)
    d.text((36, 240), f"Before restart:  {b['total_nodes']} nodes / "
           f"{b['total_edges']} edges", font=F_BIG, fill=TEXT)
    d.text((36, 316), f"After restart:   {a['total_nodes']} nodes / "
           f"{a['total_edges']} edges", font=F_BIG, fill=TEXT)
    verdict = "IDENTICAL — graph reloaded intact from FalkorDB." \
        if same else "MISMATCH — see production log."
    d.text((36, 404), verdict, font=F_H, fill=ACCENT if same else BAD)
    d.text((36, 470), "RecallGraph: agent memory that shows its work.",
           font=F_H, fill=TEXT)
    d.text((36, 512), "Demo data is re-seeded to the pristine 17 nodes / "
           "30 edges after recording.", font=F_SMALL, fill=DIM)
    return img, same


def ffprobe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)], check=True, capture_output=True,
        text=True).stdout.strip()
    return float(out)


def main() -> int:
    for p in (FRAMES, AUDIO, WORK):
        p.mkdir(parents=True, exist_ok=True)
    dump = [VENV_PY, str(DEMO / "dump_live.py")]

    # 1 — live captures ------------------------------------------------------
    run(dump + ["seed"])
    cap_path = WORK / "capture.json"
    run(dump + ["capture", str(cap_path)])
    cap = json.loads(cap_path.read_text())
    zebra_path = WORK / "zebra.json"
    run(dump + ["zebra", str(zebra_path)])
    zebra = json.loads(zebra_path.read_text())

    before_path = WORK / "before.json"
    run(dump + ["stats", str(before_path)])
    # REAL restart for the persistence beat.
    run(PODMAN + ["restart", "falkordb-prep"])
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            with urllib.request.urlopen("http://localhost:3000",
                                        timeout=3) as resp:
                if resp.status == 200:
                    break
        except Exception:
            time.sleep(2)
    else:
        raise SystemExit("FalkorDB UI did not come back after restart")
    after_path = WORK / "after.json"
    run(dump + ["stats", str(after_path)])
    before = json.loads(before_path.read_text())
    after = json.loads(after_path.read_text())

    # 2 — narration ------------------------------------------------------------
    durations = {}
    for key, slot, vo in BEATS:
        mp3 = AUDIO / f"{key}.mp3"
        run(["/opt/hatch/bin/tts", "--text", vo, "--language", "en",
             "--output", str(mp3)])
        durations[key] = max(float(slot), ffprobe_duration(mp3) + 1.2)
    print("beat durations:", durations)

    # 3 — frames -----------------------------------------------------------------
    frames = {
        "hook": render_hook(cap),
        "beat1": render_ask_beat(cap, 0, "BEAT 1 · A REAL ANSWER, WITH ITS PATH"),
        "beat2": render_ask_beat(cap, 1, "BEAT 2 · FALLBACK THAT STILL WORKS"),
        "beat3": render_beat3(cap),
        "beat4": render_beat4(zebra),
    }
    close_img, same = render_close(before, after)
    frames["close"] = close_img
    if not same:
        raise SystemExit("persistence check FAILED — refusing to ship video")
    for key, img in frames.items():
        img.save(FRAMES / f"{key}.png")

    # 4 — assemble -----------------------------------------------------------------
    segments = []
    for key, _slot, _vo in BEATS:
        seg = WORK / f"seg-{key}.mp4"
        run(["ffmpeg", "-y", "-loop", "1", "-t", f"{durations[key]:.2f}",
             "-i", str(FRAMES / f"{key}.png"), "-i", str(AUDIO / f"{key}.mp3"),
             "-filter_complex", "[1:a]apad=whole_dur=PLACEHOLDER[a]"
             .replace("PLACEHOLDER", f"{durations[key]:.2f}"),
             "-map", "0:v", "-map", "[a]", "-c:v", "libx264",
             "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-shortest",
             str(seg)])
        segments.append(seg)
    concat_list = WORK / "concat.txt"
    concat_list.write_text("".join(f"file '{s}'\n" for s in segments))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i",
         str(concat_list), "-c", "copy", str(OUT)])
    total = ffprobe_duration(OUT)
    print(f"video: {OUT}  duration: {total:.1f}s")

    # 5 — leave the demo graph pristine for tomorrow's submission run --------
    run(dump + ["seed"])
    print("demo graph re-seeded to pristine demo data")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
