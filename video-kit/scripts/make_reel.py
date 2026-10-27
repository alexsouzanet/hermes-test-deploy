"""Build a Missão China Reel in the approved house style from a small JSON config.

Approved style (27/10/2026): title card → talk (caption C karaoke, zoom punch-ins on phrase gaps,
neutral grade, logo bug, location tag, name cards) → end card. No music (added in Instagram).

Pipeline follows video-use's hard rules: per-range extract with 30ms fades, lossless concat,
overlays, captions LAST, output-timeline caption offsets, two-pass loudnorm (-14 LUFS / -1 dBTP).

Usage:
    python make_reel.py reel.json            # writes <videos_dir>/edit/<name>.mp4
    python make_reel.py reel.json --draft    # fast, for checking cuts

Config (times in seconds of the source file; transcripts must exist in <videos_dir>/edit/transcripts/):
{
  "name": "dia3_alibaba",
  "videos_dir": "/root/footage/dia3",
  "day": 3, "place": "Hangzhou",
  "title": {"kicker": "Missão China 2026", "title": "Por dentro\\nda Alibaba\\nCloud"},
  "ranges": [{"source": "IMG_0001", "start": 1.2, "end": 9.8}, ...],
  "name_cards": [{"name": "Alexandre de Souza", "role": "Gerente de Inovação · Sebrae/SC", "at": 0.6}],
  "isolate_voice": false,
  "auto_zoom": true,
  "captions": "C"            // or a path to a hand-written .ass (e.g. PT+EN translation)
}
`title` and the end card are optional (omit "title"; set "end_card": false).
`at` in name_cards is in OUTPUT talk time (seconds after the title card).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(Path.home() / "Developer/video-use/helpers"))
import kit  # noqa: E402
from grade import auto_grade_for_clip  # noqa: E402
from render import TONEMAP_CHAIN, apply_loudnorm_two_pass, is_hdr_source  # noqa: E402

ZOOM_IN = 1.18
ZOOM_MIN_PIECE = 2.2   # seconds; shorter zoom pieces feel jumpy
ZOOM_GAP = 0.18        # only switch zoom inside a silence at least this long
VIDEO_EXTS = (".MOV", ".mov", ".MP4", ".mp4", ".m4v", ".MKV", ".mkv")


def run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"ffmpeg failed:\n{' '.join(map(str, cmd))}\n{r.stderr[-3000:]}")


def enc(draft: bool) -> list[str]:
    preset, crf = ("ultrafast", "28") if draft else ("medium", "20")
    return ["-c:v", "libx264", "-preset", preset, "-crf", crf, "-pix_fmt", "yuv420p", "-r", "30",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart"]


def find_source(videos_dir: Path, stem: str) -> Path:
    for ext in VIDEO_EXTS:
        p = videos_dir / f"{stem}{ext}"
        if p.exists():
            return p
    sys.exit(f"source not found: {stem} in {videos_dir}")


def zoom_plan(words: list[dict], start: float, end: float) -> list[tuple[float, float]]:
    """Alternate 1.0 / ZOOM_IN at silences, never closer than ZOOM_MIN_PIECE. Range-relative end times."""
    cuts, last, z = [], start, 1.0
    for a, b in zip(words, words[1:]):
        gap_mid = (a["end"] + b["start"]) / 2
        if b["start"] - a["end"] >= ZOOM_GAP and gap_mid - last >= ZOOM_MIN_PIECE and end - gap_mid >= ZOOM_MIN_PIECE:
            cuts.append((gap_mid - start, z))
            last, z = gap_mid, (ZOOM_IN if z == 1.0 else 1.0)
    cuts.append((end - start, z))
    return cuts


def isolate(audio_in: Path, audio_out: Path) -> bool:
    """ElevenLabs voice isolation. Needs >= 4.6 s of audio. Returns False (keeps original) on any failure."""
    key = os.environ.get("ELEVENLABS_API_KEY") or next(
        (ln.split("=", 1)[1].strip() for ln in (Path.home() / "Developer/video-use/.env").read_text().splitlines()
         if ln.startswith("ELEVENLABS_API_KEY=")), "")
    import requests
    with open(audio_in, "rb") as f:
        r = requests.post("https://api.elevenlabs.io/v1/audio-isolation", headers={"xi-api-key": key},
                          files={"audio": (audio_in.name, f, "audio/wav")}, timeout=600)
    if r.status_code != 200:
        print(f"  voice isolation skipped ({r.status_code}): {r.text[:160]}")
        return False
    audio_out.write_bytes(r.content)
    return True


def extract_range(src: Path, start: float, end: float, words: list[dict], out: Path, *,
                  auto_zoom: bool, isolate_voice: bool, draft: bool, tmp: Path) -> None:
    dur = end - start
    pre = TONEMAP_CHAIN + "," if is_hdr_source(src) else ""
    fill = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30"
    grade, _ = auto_grade_for_clip(src, start=start, duration=dur)
    grade = grade or "null"
    inputs = ["-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src)]
    fc = [f"[0:v]{pre}{fill}[base]"]
    cuts = zoom_plan(words, start, end) if auto_zoom else [(dur, 1.0)]
    fc.append(f"[base]split={len(cuts)}" + "".join(f"[s{i}]" for i in range(len(cuts))))
    for i, (t_end, z) in enumerate(cuts):
        t0 = 0.0 if i == 0 else cuts[i - 1][0]
        crop = f",crop=iw/{z}:ih/{z}:(iw-iw/{z})/2:(ih-ih/{z})*0.28,scale=1080:1920,setsar=1" if z != 1.0 else ""
        fc.append(f"[s{i}]trim={t0:.3f}:{t_end:.3f},setpts=PTS-STARTPTS{crop}[p{i}]")
    fc.append("".join(f"[p{i}]" for i in range(len(cuts))) + f"concat=n={len(cuts)}:v=1:a=0,{grade}[v]")

    a_idx = 0
    if isolate_voice and dur >= 4.6:
        wav, clean = tmp / f"{out.stem}.wav", tmp / f"{out.stem}_iso.mp3"
        run(["ffmpeg", "-nostdin", "-y", *inputs, "-vn", "-ac", "1", "-ar", "48000", str(wav)])
        if isolate(wav, clean):
            inputs += ["-i", str(clean)]
            a_idx = 1
    fades = f"afade=t=in:st=0:d=0.03,afade=t=out:st={dur - 0.03:.3f}:d=0.03"
    fc.append(f"[{a_idx}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{dur:.3f},{fades}[a]")
    run(["ffmpeg", "-nostdin", "-y", *inputs, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
         "-t", f"{dur:.3f}", *enc(draft), str(out)])


def card(frames: Path, dur: float, out: Path, draft: bool) -> None:
    run(["ffmpeg", "-nostdin", "-y", "-framerate", "30", "-i", str(frames / "f_%04d.png"),
         "-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo",
         "-map", "0:v", "-map", "1:a", "-t", f"{dur:.3f}", *enc(draft), str(out)])


def concat(parts: list[Path], out: Path, tmp: Path) -> None:
    lst = tmp / f"{out.stem}_list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    run(["ffmpeg", "-nostdin", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("config", type=Path)
    ap.add_argument("--draft", action="store_true")
    args = ap.parse_args()
    cfg = json.loads(args.config.read_text())
    vdir = Path(cfg["videos_dir"]).resolve()
    edit = vdir / "edit"
    tr_dir = edit / "transcripts"
    name = cfg.get("name", "reel") + ("_draft" if args.draft else "")
    work = edit / f"_work_{name}"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    tmp = Path(tempfile.mkdtemp())
    place_tag = f"Dia {cfg['day']} · {cfg['place']}"

    # 1. Talk ranges → body.mp4, and caption cues on the body timeline (Rule 5).
    seg_paths, cue_words, offset = [], [], 0.0
    for i, r in enumerate(cfg["ranges"]):
        src = find_source(vdir, r["source"])
        tr = tr_dir / f"{r['source']}.json"
        if not tr.exists():
            sys.exit(f"missing transcript {tr}. Run transcribe_batch.py on {vdir} first.")
        words = kit.load_words(tr, r["start"], r["end"])
        out = work / f"seg_{i:02d}.mp4"
        print(f"  range {i}: {r['source']} {r['start']:.2f}-{r['end']:.2f} ({len(words)} words)")
        extract_range(src, r["start"], r["end"], words, out, auto_zoom=cfg.get("auto_zoom", True),
                      isolate_voice=cfg.get("isolate_voice", False), draft=args.draft, tmp=tmp)
        for w in words:
            cue_words.append({**w, "start": w["start"] - r["start"] + offset, "end": w["end"] - r["start"] + offset})
        offset += r["end"] - r["start"]
        seg_paths.append(out)
    body_raw = work / "body_raw.mp4"
    concat(seg_paths, body_raw, tmp)
    body_dur = offset

    # 2. Overlays on the body: logo bug, location tag, name cards; captions LAST.
    inputs = ["-i", str(body_raw)]
    logo = work / "logo.png"
    kit.logo_bug_frame("B").save(logo)
    inputs += ["-loop", "1", "-t", f"{body_dur:.3f}", "-i", str(logo)]
    tag_dir = work / "tag"
    kit.location_tag_frames(cfg.get("tag_day", f"Dia {cfg['day']}"), cfg["place"], min(6.0, body_dur - 0.2), tag_dir)
    inputs += ["-itsoffset", "0.2", "-framerate", "30", "-i", str(tag_dir / "f_%04d.png")]
    overlays = [("1", "1"), ("2", "gte(t,0.2)")]
    for k, nc in enumerate(cfg.get("name_cards", [])):
        d = work / f"name_{k}"
        kit.lower_third_frames(nc["name"], nc["role"], nc.get("dur", 4.5), d)
        inputs += ["-itsoffset", f"{nc['at']:.3f}", "-framerate", "30", "-i", str(d / "f_%04d.png")]
        overlays.append((str(3 + k), f"gte(t,{nc['at']:.3f})"))
    fc, cur = [], "[0:v]"
    for k, (idx, en) in enumerate(overlays):
        fc.append(f"{cur}[{idx}:v]overlay=0:0:eof_action=pass:enable='{en}'[o{k}]")
        cur = f"[o{k}]"
    cap = cfg.get("captions", "C")
    ass = work / "captions.ass"
    if cap in ("A", "B", "C"):
        kit.captions_ass(cue_words, cap, 0.0, ass)
    else:
        shutil.copy(cap, ass)
    fc.append(f"{cur}ass='{ass}'[v]")
    body = work / "body.mp4"
    run(["ffmpeg", "-nostdin", "-y", *inputs, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "0:a",
         "-t", f"{body_dur:.3f}", *enc(args.draft)[:-10], "-c:a", "copy", "-movflags", "+faststart", str(body)])

    # 3. Title card + body + end card → loudnorm.
    first = cfg["ranges"][0]
    still = work / "still.png"
    src0 = find_source(vdir, first["source"])
    pre = TONEMAP_CHAIN + "," if is_hdr_source(src0) else ""
    run(["ffmpeg", "-nostdin", "-y", "-ss", f"{first['start'] + 1:.3f}", "-i", str(src0), "-frames:v", "1",
         "-vf", f"{pre}scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920", str(still)])
    parts = []
    if cfg.get("title"):
        t = cfg["title"]
        d = work / "title"
        kit.title_card_frames(still, t.get("kicker", "Missão China 2026"), t["title"], t.get("sub", place_tag),
                              t.get("dur", 2.4), d)
        card(d, t.get("dur", 2.4), work / "title.mp4", args.draft)
        parts.append(work / "title.mp4")
    parts.append(body)
    if cfg.get("end_card", True):
        d = work / "end"
        kit.end_card_frames(still, 2.8, d)
        card(d, 2.8, work / "end.mp4", args.draft)
        parts.append(work / "end.mp4")
    pre_norm = work / "prenorm.mp4"
    concat(parts, pre_norm, tmp)
    final = edit / f"{name}.mp4"
    apply_loudnorm_two_pass(pre_norm, final, preview=args.draft)
    shutil.rmtree(tmp, ignore_errors=True)
    if not args.draft:
        shutil.rmtree(work, ignore_errors=True)
    total = body_dur + (cfg["title"].get("dur", 2.4) if cfg.get("title") else 0) + (2.8 if cfg.get("end_card", True) else 0)
    print(f"done: {final}  (expected {total:.2f}s)")


if __name__ == "__main__":
    main()
