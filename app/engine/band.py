"""楽譜(model)をバンドの音(ピアノ・ストリングス・ベース・ドラム)で鳴らして音声ファイルにする。

楽譜どおりに鳴らすのはピアノ(右手・左手)。ベースとストリングスは楽譜のコード記号から、
ドラムはテンポと小節から自動で付ける。音源は GeneralUser GS(無料・商用可)。
"""
import os
import re
import subprocess
import wave

import numpy as np

SF2 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "soundfont", "GeneralUser_GS.sf2")
SR = 44100
PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

# GM の音色番号(0始まり)
PIANO, STRINGS, BASS = 0, 48, 33
KICK, SNARE, HAT_C, HAT_O, CRASH = 36, 38, 42, 46, 49


def _pc(name):
    p = PC[name[0]]
    if len(name) > 1 and name[1] == "#":
        p += 1
    elif len(name) > 1 and name[1] == "b":
        p -= 1
    return p % 12


def parse_chord(name):
    m = re.match(r"^([A-G][#b]?)(m?)(?:/([A-G][#b]?))?", name)
    if not m:
        return None
    root = _pc(m.group(1))
    minor = m.group(2) == "m"
    bass = _pc(m.group(3)) if m.group(3) else root
    return root, minor, bass


def _events(model, parts):
    """(拍, 種類, ch, 音, 強さ) の一覧を作る。"""
    ev = []
    total = model["meta"]["measures"] * 4

    def note(o, d, ch, p, v):
        ev.append((o, 1, ch, p, v))
        ev.append((o + max(d, 0.05) * 0.97, 0, ch, p, 0))

    if "piano" in parts:
        for hand, vel in (("rh", 100), ("lh", 70)):
            for n in model.get(hand, []):
                for p in n["p"]:
                    note(n["o"], n["d"], 0, p, vel)

    chords = model.get("chords", [])
    segs = []
    for i, c in enumerate(chords):
        end = chords[i + 1]["o"] if i + 1 < len(chords) else total
        pc = parse_chord(c["name"])
        if pc and end > c["o"]:
            segs.append((c["o"], end, pc))

    for o, end, (root, minor, bass) in segs:
        if "strings" in parts:
            tri = [root, (root + (3 if minor else 4)) % 12, (root + 7) % 12]
            for t in tri:
                p = 55 + ((t - 55) % 12)
                note(o, end - o, 1, p, 52)
        if "bass" in parts:
            b = 28 + ((bass - 28) % 12)  # E1〜D#2
            beat = o
            while beat < end - 1e-6:
                d = min(1.0, end - beat)
                note(beat, d * 0.9, 2, b, 92 if abs(beat % 2) < 1e-6 else 78)
                beat += 1.0

    if "drums" in parts:
        measures = model["meta"]["measures"]
        for m in range(measures):
            base = m * 4
            fill = (m % 8 == 7) and m != measures - 1
            if m % 8 == 0:
                note(base, 0.5, 9, CRASH, 100)
            for k in range(8):
                t = base + k * 0.5
                if fill and k >= 6:
                    continue
                note(t, 0.25, 9, HAT_O if k == 7 and m % 4 == 3 and not fill else HAT_C, 72 if k % 2 == 0 else 48)
            for t in (0, 2, 2.5):
                note(base + t, 0.25, 9, KICK, 105 if t != 2.5 else 80)
            for t in (1, 3):
                if fill and t == 3:
                    continue
                note(base + t, 0.25, 9, SNARE, 100)
            if fill:
                for i, t in enumerate((3.0, 3.25, 3.5, 3.75)):
                    note(base + t, 0.2, 9, SNARE, 70 + i * 10)
    ev.sort(key=lambda e: (e[0], e[1]))
    return ev


def render(model, out_path, parts=("piano", "strings", "bass", "drums"), tempo=None):
    import tinysoundfont

    bpm = float(tempo or model["meta"].get("tempo", 120))
    spb = 60.0 / bpm
    synth = tinysoundfont.Synth(samplerate=SR)
    sfid = synth.sfload(SF2)
    synth.program_select(0, sfid, 0, PIANO)
    synth.program_select(1, sfid, 0, STRINGS)
    synth.program_select(2, sfid, 0, BASS)
    synth.program_select(9, sfid, 128, 0, True)
    synth.control_change(1, 7, 70)  # ストリングスは控えめ

    ev = _events(model, parts)
    chunks = []
    cur = 0
    for beat, kind, ch, p, v in ev:
        at = int(beat * spb * SR)
        if at > cur:
            chunks.append(np.frombuffer(synth.generate(at - cur), dtype=np.float32).copy())
            cur = at
        if kind == 1:
            synth.noteon(ch, p, v)
        else:
            synth.noteoff(ch, p)
    chunks.append(np.frombuffer(synth.generate(int(2.5 * SR)), dtype=np.float32).copy())
    audio = np.concatenate(chunks).reshape(-1, 2)
    peak = float(np.max(np.abs(audio))) or 1.0
    audio = audio / peak * 0.89
    pcm = (audio * 32767).astype(np.int16)

    wav_path = os.path.splitext(out_path)[0] + ".wav"
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    if out_path.lower().endswith(".mp3"):
        from engine.transcribe import ffmpeg_exe
        subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-i", wav_path, "-b:a", "192k", out_path],
                       check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        os.remove(wav_path)
    return out_path, len(audio) / SR


if __name__ == "__main__":
    import json
    import sys
    m = json.load(open(sys.argv[1], encoding="utf-8"))
    path, sec = render(m, sys.argv[2])
    print(path, f"{sec:.1f}s")
