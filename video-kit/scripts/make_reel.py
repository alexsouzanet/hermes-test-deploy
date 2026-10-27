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


def zoom_plan(words: list[dict], start: float, end: float, z0: float = 1.0) -> list[tuple[float, float]]:
    """Alternate 1.0 / ZOOM_IN at silences, never closer than ZOOM_MIN_PIECE. Range-relative end times."""
    cuts, last, z = [], start, z0
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


BREATH_PRE, BREATH_POST, BREATH_MARGIN = 0.20, 0.30, 0.06


def breathe(all_words: list[dict], start: float, end: float) -> tuple[float, float]:
    """Extend a range into the surrounding silence (never into a neighbouring word) so cuts can breathe."""
    prev_end = max((w["end"] for w in all_words if w["end"] <= start + 0.01), default=0.0)
    next_start = min((w["start"] for w in all_words if w["start"] >= end - 0.01), default=end + BREATH_POST + 1)
    new_start = min(start, max(prev_end + BREATH_MARGIN, start - BREATH_PRE, 0.0))
    new_end = max(end, min(next_start - BREATH_MARGIN, end + BREATH_POST))
    return new_start, new_end


VOICE_EQ = "equalizer=f=3500:t=q:w=1.2:g=3,highshelf=f=8000:g=2"


def isolated_track(src: Path, cache_dir: Path) -> Path | None:
    """Voice-isolate the whole source once (cached), so every range is clean whatever its length."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / f"{src.stem}.mp3"
    if out.exists():
        return out
    wav = cache_dir / f"{src.stem}.wav"
    run(["ffmpeg", "-nostdin", "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "48000", str(wav)])
    ok = isolate(wav, out)
    wav.unlink(missing_ok=True)
    return out if ok else None


def extract_range(src: Path, start: float, end: float, words: list[dict], out: Path, *,
                  auto_zoom: bool, clean_audio: Path | None, draft: bool,
                  blur_band: tuple[float, float] | None = None, z0: float = 1.0,
                  original_mix: float = 0.25) -> float:
    dur = end - start
    pre = TONEMAP_CHAIN + "," if is_hdr_source(src) else ""
    fill = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30"
    grade, _ = auto_grade_for_clip(src, start=start, duration=dur)
    grade = grade or "null"
    inputs = ["-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src)]
    if blur_band:
        # Hide captions already burned into the source (e.g. a re-used Instagram post).
        y0, y1 = blur_band
        fc = [f"[0:v]{pre}{fill},split[bg][bb]",
              f"[bb]crop=iw:ih*{y1 - y0:.3f}:0:ih*{y0:.3f},boxblur=28:3[blur]",
              f"[bg][blur]overlay=0:H*{y0:.3f}[base]"]
    else:
        fc = [f"[0:v]{pre}{fill}[base]"]
    cuts = zoom_plan(words, start, end, z0) if auto_zoom else [(dur, 1.0)]
    fc.append(f"[base]split={len(cuts)}" + "".join(f"[s{i}]" for i in range(len(cuts))))
    for i, (t_end, z) in enumerate(cuts):
        t0 = 0.0 if i == 0 else cuts[i - 1][0]
        crop = f",crop=iw/{z}:ih/{z}:(iw-iw/{z})/2:(ih-ih/{z})*0.28,scale=1080:1920,setsar=1" if z != 1.0 else ""
        fc.append(f"[s{i}]trim={t0:.3f}:{t_end:.3f},setpts=PTS-STARTPTS{crop}[p{i}]")
    fc.append("".join(f"[p{i}]" for i in range(len(cuts))) + f"concat=n={len(cuts)}:v=1:a=0,{grade}[v]")

    fades = f"afade=t=in:st=0:d=0.03,afade=t=out:st={dur - 0.03:.3f}:d=0.03"
    if clean_audio:
        # Isolated voice + some of the original room sound, so the voice is clean but not boxed in.
        inputs += ["-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(clean_audio)]
        fc.append(f"[1:a]aresample=48000,aformat=channel_layouts=stereo[iso]")
        fc.append(f"[0:a]aresample=48000,aformat=channel_layouts=stereo,volume={original_mix}[room]")
        fc.append(f"[iso][room]amix=inputs=2:normalize=0:duration=first,{VOICE_EQ},"
                  f"atrim=0:{dur:.3f},{fades}[a]")
    else:
        fc.append(f"[0:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{dur:.3f},{fades}[a]")
    run(["ffmpeg", "-nostdin", "-y", *inputs, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
         "-t", f"{dur:.3f}", *enc(draft), str(out)])
    return cuts[-1][1]


def fix_token(tok: str, fixes: dict[str, str]) -> str:
    """Exact token (with punctuation) wins, e.g. {"Startup,": "Startups,"} leaves "Startup Summit" alone."""
    if tok in fixes:
        return fixes[tok]
    core = tok.rstrip(".,?!;:")
    return fixes[core] + tok[len(core):] if core in fixes else tok


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
    day_label = cfg.get("tag_day") or f"Dia {cfg.get('day')}"
    place_tag = f"{day_label} · {cfg['place']}"

    # 1. Talk ranges → body.mp4, and caption cues on the body timeline (Rule 5).
    # Neighbouring ranges of the same file with only a pause between them become one range (fewer cuts).
    merged: list[dict] = []
    for r in cfg["ranges"]:
        if merged and merged[-1]["source"] == r["source"] and 0 <= r["start"] - merged[-1]["end"] < 0.6:
            merged[-1] = {**merged[-1], "end": r["end"]}
        else:
            merged.append(dict(r))
    cfg["ranges"] = merged
    seg_paths, cue_words, offset, z_next = [], [], 0.0, 1.0
    for i, r in enumerate(cfg["ranges"]):
        src = find_source(vdir, r["source"])
        tr = tr_dir / f"{r['source']}.json"
        if not tr.exists():
            sys.exit(f"missing transcript {tr}. Run transcribe_batch.py on {vdir} first.")
        words = kit.load_words(tr, r["start"], r["end"])
        for w in words:  # per-video name fixes, e.g. {"COEN": "Qwen"} (exact token, punctuation kept)
            w["text"] = " ".join(fix_token(t, cfg.get("fixes", {})) for t in w["text"].split(" "))
        out = work / f"seg_{i:02d}.mp4"
        start, end = r["start"], r["end"]
        if cfg.get("breath", True):
            all_words = [w for w in json.loads(tr.read_text())["words"] if w["type"] != "spacing"]
            start, end = breathe(all_words, start, end)
        print(f"  range {i}: {r['source']} {start:.2f}-{end:.2f} ({len(words)} words)")
        clean = isolated_track(src, edit / "isolated") if cfg.get("isolate_voice") else None
        last_z = extract_range(src, start, end, words, out, auto_zoom=cfg.get("auto_zoom", True),
                               clean_audio=clean, draft=args.draft, blur_band=cfg.get("blur_band"),
                               z0=z_next, original_mix=cfg.get("original_mix", 0.25))
        z_next = ZOOM_IN if last_z == 1.0 else 1.0  # every cut changes framing, so jumps read as intentional
        for k, w in enumerate(words):  # a caption cue never spans a cut
            cue_words.append({**w, "start": w["start"] - start + offset, "end": w["end"] - start + offset,
                              "cut_after": k == len(words) - 1})
        offset += end - start
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
    kit.location_tag_frames(place_tag.split(' · ')[0], cfg["place"], min(6.0, body_dur - 0.2), tag_dir)
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
