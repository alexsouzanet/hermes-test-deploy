"""Build the Missão China style catalog (review video) from IMG_7707.

Each block = one MP4 at identical params (1080x1920, 30fps, h264 CRF 20, AAC 48k stereo),
then lossless concat, then two-pass loudnorm. Subtitles (ASS) are always the last video filter.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, "/root/Developer/video-use/helpers")
import kit  # noqa: E402
from grade import get_preset  # noqa: E402
from render import apply_loudnorm_two_pass  # noqa: E402

E = Path("/root/footage/catalogo/edit")
SRC = Path("/root/footage/catalogo/IMG_7707.MOV")
TR = E / "transcripts/IMG_7707.json"
G = E / "gfx"
B = E / "blocks"
B.mkdir(exist_ok=True)

GRADE_NEUTRAL = "eq=contrast=1.030:gamma=1.061:saturation=1.040"
GRADE_WARM = get_preset("warm_cinematic")
GRADE_VIVID = "eq=contrast=1.08:gamma=1.03:saturation=1.20,vibrance=intensity=0.12"

ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30",
       "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart"]
FADES = lambda d: f"afade=t=in:st=0:d=0.03,afade=t=out:st={d - 0.03:.3f}:d=0.03"  # noqa: E731


def run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"ffmpeg failed:\n{' '.join(cmd)}\n{r.stderr[-3000:]}")


def png(img, name: str) -> Path:
    p = G / name
    img.save(p)
    return p


def seq_input(d: Path) -> list[str]:
    return ["-framerate", "30", "-i", str(d / "f_%04d.png")]


def label(text: str, name: str) -> Path:
    return png(kit.review_label_frame(text), name)


def talk_block(out: Path, start: float, end: float, *, caption: str | None, labels: list[tuple[float, float, Path]],
               grade_segments: list[tuple[float, str]] | None = None, zoom_cuts: list[tuple[float, float]] | None = None,
               logo: str | None = "B", seqs: list[tuple[Path, float]] = (), audio_file: Path | None = None,
               ass_file: Path | None = None) -> float:
    """One block of the talking-head footage. Times in grade_segments/zoom_cuts/labels are block-relative."""
    dur = end - start
    inputs = ["-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(SRC)]
    fc: list[str] = []
    n_in = 1
    if audio_file:
        inputs += ["-t", f"{dur:.3f}", "-i", str(audio_file)]
        a_idx = n_in
        n_in += 1
    else:
        a_idx = 0
    base = "[0:v]scale=1080:1920,setsar=1,fps=30"

    # Zoom punch-ins: alternate crop levels per sub-range (crop keeps the face in the upper third).
    if zoom_cuts:
        fc.append(f"{base}[src]")
        fc.append(f"[src]split={len(zoom_cuts)}" + "".join(f"[z{i}]" for i in range(len(zoom_cuts))))
        parts = []
        for i, (t_end, z) in enumerate(zoom_cuts):
            t_start = 0.0 if i == 0 else zoom_cuts[i - 1][0]
            crop = f"crop=iw/{z}:ih/{z}:(iw-iw/{z})/2:(ih-ih/{z})*0.28,scale=1080:1920,setsar=1," if z != 1 else ""
            fc.append(f"[z{i}]trim={t_start:.3f}:{t_end:.3f},setpts=PTS-STARTPTS,{crop}null[zz{i}]")
            parts.append(f"[zz{i}]")
        fc.append("".join(parts) + f"concat=n={len(parts)}:v=1:a=0[v0]")
    else:
        fc.append(f"{base}[v0]")

    # Grade: one filter, or several switched over time (catalog colour comparison).
    if grade_segments:
        fc.append(f"[v0]split={len(grade_segments)}" + "".join(f"[g{i}]" for i in range(len(grade_segments))))
        parts = []
        for i, (t_end, flt) in enumerate(grade_segments):
            t_start = 0.0 if i == 0 else grade_segments[i - 1][0]
            fc.append(f"[g{i}]trim={t_start:.3f}:{t_end:.3f},setpts=PTS-STARTPTS,{flt}[gg{i}]")
            parts.append(f"[gg{i}]")
        fc.append("".join(parts) + f"concat=n={len(parts)}:v=1:a=0[v1]")
    else:
        fc.append(f"[v0]{GRADE_NEUTRAL}[v1]")
    cur = "[v1]"

    # Overlays: logo bug, animated sequences, review labels.
    ov_inputs: list[tuple[list[str], str]] = []
    if logo:
        ov_inputs.append((["-loop", "1", "-t", f"{dur:.3f}", "-i", str(png(kit.logo_bug_frame(logo), f"logo_{logo}.png"))],
                          "between(t,0,9999)"))
    for d, t0 in seqs:
        ov_inputs.append((["-itsoffset", f"{t0:.3f}"] + seq_input(d), f"gte(t,{t0:.3f})"))
    for a, b, p in labels:
        ov_inputs.append((["-loop", "1", "-t", f"{dur:.3f}", "-i", str(p)], f"between(t,{a:.3f},{b:.3f})"))
    for k, (args, enable) in enumerate(ov_inputs):
        inputs += args
        nxt = f"[o{k}]"
        fc.append(f"{cur}[{n_in}:v]overlay=0:0:eof_action=pass:enable='{enable}'{nxt}")
        cur = nxt
        n_in += 1

    # Captions LAST.
    if caption or ass_file:
        ass = ass_file or (E / f"captions_{out.stem}.ass")
        if caption:
            kit.captions_ass(kit.load_words(TR, start, end), caption, start, ass)
        fc.append(f"{cur}ass='{ass}'[vout]")
    else:
        fc.append(f"{cur}null[vout]")

    fc.append(f"[{a_idx}:a]aresample=48000,aformat=channel_layouts=stereo,{FADES(dur)}[aout]")
    run(["ffmpeg", "-nostdin", "-y", *inputs, "-filter_complex", ";".join(fc),
         "-map", "[vout]", "-map", "[aout]", "-t", f"{dur:.3f}", *ENC, str(out)])
    return dur


def card_block(out: Path, frames_dir: Path, dur: float, label_png: Path | None) -> float:
    inputs = seq_input(frames_dir) + ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
    fc = "[0:v]fps=30,format=yuv420p[v0]"
    if label_png:
        inputs += ["-loop", "1", "-t", f"{dur:.3f}", "-i", str(label_png)]
        fc = "[0:v]fps=30[v];[v][2:v]overlay=0:0[v0]"
    run(["ffmpeg", "-nostdin", "-y", *inputs, "-filter_complex", fc, "-map", "[v0]", "-map", "1:a",
         "-t", f"{dur:.3f}", *ENC, str(out)])
    return dur


def main() -> None:
    still = G / "still_title.png"
    run(["ffmpeg", "-nostdin", "-y", "-ss", "8", "-i", str(SRC), "-frames:v", "1", "-vf", "scale=1080:1920", str(still)])
    blocks: list[Path] = []
    total = 0.0

    # 1. Opening title card, then caption style A.
    title = G / "seq_title"
    shutil.rmtree(title, ignore_errors=True)
    kit.title_card_frames(still, "Missão China 2026", "Inteligência\nartificial\nem Hangzhou", "Dia 3 · Hangzhou", 2.6, title)
    total += card_block(B / "01_title.mp4", title, 2.6, label("ABERTURA · CARTÃO DE TÍTULO", "lbl_01.png"))
    blocks.append(B / "01_title.mp4")
    total += talk_block(B / "02_capA.mp4", 1.69, 4.88, caption="A",
                        labels=[(0, 99, label("LEGENDA A · CAIXA ALTA", "lbl_02.png"))])
    blocks.append(B / "02_capA.mp4")

    # 2. Caption style B + location tag.
    tag = G / "seq_tag"
    shutil.rmtree(tag, ignore_errors=True)
    kit.location_tag_frames("Dia 3", "Hangzhou", 12.70 - 5.09 - 0.2, tag)
    total += talk_block(B / "03_capB_tag.mp4", 5.09, 12.70, caption="B", seqs=[(tag, 0.2)],
                        labels=[(0, 99, label("LEGENDA B · FRASE + SELO DE LOCAL", "lbl_03.png"))])
    blocks.append(B / "03_capB_tag.mp4")

    # 3. Caption style C (karaoke) + zoom punch-ins on phrase gaps (block-relative cut times).
    s = 12.95
    cuts = [(14.82 - s, 1.0), (16.36 - s, 1.18), (17.78 - s, 1.0), (19.38 - s, 1.18)]
    total += talk_block(B / "04_capC_zoom.mp4", s, 19.38, caption="C", zoom_cuts=cuts,
                        labels=[(0, 99, label("LEGENDA C · KARAOKÊ + ZOOM", "lbl_04.png"))])
    blocks.append(B / "04_capC_zoom.mp4")

    # 4. Name card (lower third) over caption A.
    lt = G / "seq_lower"
    shutil.rmtree(lt, ignore_errors=True)
    kit.lower_third_frames("Alexandre de Souza", "Gerente de Inovação · Sebrae/SC", 4.8, lt)
    total += talk_block(B / "05_lower.mp4", 22.17, 30.70, caption="A", seqs=[(lt, 0.3)],
                        labels=[(0, 99, label("CARTÃO DE NOME E CARGO", "lbl_05.png"))])
    blocks.append(B / "05_lower.mp4")

    # 5. Colour: neutral / warm / vivid, switched on the picture while audio runs on.
    s, e = 30.83, 36.50
    d = e - s
    total += talk_block(B / "06_color.mp4", s, e, caption="A",
                        grade_segments=[(d / 3, GRADE_NEUTRAL), (2 * d / 3, GRADE_WARM), (d, GRADE_VIVID)],
                        labels=[(0, d / 3, label("COR 1 · NEUTRA (PADRÃO)", "lbl_06a.png")),
                                (d / 3, 2 * d / 3, label("COR 2 · QUENTE", "lbl_06b.png")),
                                (2 * d / 3, 99, label("COR 3 · VIBRANTE", "lbl_06c.png"))])
    blocks.append(B / "06_color.mp4")

    # 6. Audio: simulated expo noise, then the same take after ElevenLabs voice isolation.
    total += talk_block(B / "07_noisy.mp4", 5.09, 10.18, caption="A", audio_file=E / "audio/b_noisy.wav",
                        labels=[(0, 99, label("ÁUDIO 1 · RUÍDO DE FEIRA (SEM TRATAMENTO)", "lbl_07.png"))])
    blocks.append(B / "07_noisy.mp4")
    total += talk_block(B / "08_isolated.mp4", 5.09, 10.18, caption="A", audio_file=E / "audio/b_isolated.bin",
                        labels=[(0, 99, label("ÁUDIO 2 · VOZ ISOLADA (ELEVENLABS)", "lbl_08.png"))])
    blocks.append(B / "08_isolated.mp4")

    # 7. Translation: PT line small, EN line large (template for interviews in English/Mandarin).
    s, e = 19.57, 22.02
    ass = E / "captions_09_translate.ass"
    kit.bilingual_ass([(0.05, 1.10, "E o nome dessa ação", "And this initiative"),
                       (1.10, e - s, "é o Startup Summit Week.", "is called Startup Summit Week")], ass)
    total += talk_block(B / "09_translate.mp4", s, e, caption=None, ass_file=ass,
                        labels=[(0, 99, label("TRADUÇÃO · PT + INGLÊS", "lbl_09.png"))])
    blocks.append(B / "09_translate.mp4")

    # 8. End card.
    end = G / "seq_end"
    shutil.rmtree(end, ignore_errors=True)
    kit.end_card_frames(still, 3.0, end)
    total += card_block(B / "10_end.mp4", end, 3.0, label("ENCERRAMENTO · ASSINATURA", "lbl_10.png"))
    blocks.append(B / "10_end.mp4")

    lst = E / "_concat.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in blocks))
    pre = E / "catalogo.prenorm.mp4"
    run(["ffmpeg", "-nostdin", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(pre)])
    apply_loudnorm_two_pass(pre, E / "catalogo.mp4")
    pre.unlink()
    lst.unlink()
    print(f"expected duration {total:.2f}s")


if __name__ == "__main__":
    main()
