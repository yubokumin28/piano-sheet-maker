"""model(拍単位の音符リスト)を MusicXML と MIDI に書き出す。"""
import re

from music21 import chord, clef, harmony, key, layout, meter, metadata, note, pitch, stream, tempo


def _pitch(midi, fifths):
    from engine.arrange import use_sharp
    p = pitch.Pitch(midi=midi)
    if p.accidental is not None and p.accidental.alter != 0:
        want_sharp = use_sharp(midi % 12, fifths)
        if (p.accidental.alter > 0) != want_sharp:
            p = p.getEnharmonic()
    return p


def _m21_figure(name):
    """'Bbm/Eb' -> 'B-m/E-'(music21 は♭を '-' で書く)。"""
    def fix(part):
        return part[0] + "-" + part[2:] if len(part) > 1 and part[1] == "b" else part
    root, _, bass = name.partition("/")
    return fix(root) + ("/" + fix(bass) if bass else "")


def _voice_events(notes):
    """同じ手の中で重なる音を、同じ開始位置は和音に、ずれる重なりは前の音を切って1声にする。"""
    by_o = {}
    for n in notes:
        if not n.get("p"):
            continue
        cur = by_o.get(n["o"])
        if cur is None:
            by_o[n["o"]] = {"o": n["o"], "d": n["d"], "p": sorted(set(n["p"])), "h": bool(n.get("h"))}
        else:
            cur["p"] = sorted(set(cur["p"]) | set(n["p"]))
            cur["d"] = max(cur["d"], n["d"])
            cur["h"] = cur["h"] and bool(n.get("h"))
    evs = sorted(by_o.values(), key=lambda e: e["o"])
    for i in range(len(evs) - 1):
        gap = evs[i + 1]["o"] - evs[i]["o"]
        if evs[i]["d"] > gap:
            evs[i]["d"] = gap
    return [e for e in evs if e["d"] > 0]


def _build_part(notes, measures, fifths, is_right, chords, bpm, meta):
    p = stream.Part()
    p.id = "RH" if is_right else "LH"
    p.insert(0, clef.TrebleClef() if is_right else clef.BassClef())
    p.insert(0, key.KeySignature(fifths))
    p.insert(0, meter.TimeSignature("4/4"))
    if is_right:
        p.insert(0, tempo.MetronomeMark(number=bpm))
    for e in _voice_events(notes):
        if len(e["p"]) == 1:
            el = note.Note(_pitch(e["p"][0], fifths))
        else:
            el = chord.Chord([_pitch(m, fifths) for m in e["p"]])
        el.quarterLength = e["d"]
        if e.get("h"):
            el.style.hideObjectOnPrint = True
        p.insert(e["o"], el)
    total = measures * 4
    p.makeRests(fillGaps=True, inPlace=True)
    hi = p.highestTime
    if hi < total:
        r = note.Rest(quarterLength=total - hi)
        p.insert(hi, r)
    if is_right and chords:
        for c in chords:
            try:
                cs = harmony.ChordSymbol(_m21_figure(c["name"]))
            except Exception:
                continue
            cs.writeAsChord = False
            p.insert(c["o"], cs)
    p.makeMeasures(inPlace=True)
    p.makeTies(inPlace=True)
    try:
        p.makeBeams(inPlace=True)
    except Exception:
        pass
    return p


def to_musicxml(model, path):
    m = model["meta"]
    fifths = int(m.get("fifths", 0))
    measures = max(1, int(m.get("measures", 1)))
    bpm = int(m.get("tempo", 120))
    sc = stream.Score()
    md = metadata.Metadata()
    md.title = m.get("title") or "Untitled"
    if m.get("artist"):
        md.composer = m["artist"]
    sc.insert(0, md)
    rh = _build_part(model.get("rh", []), measures, fifths, True, model.get("chords", []), bpm, m)
    lh = _build_part(model.get("lh", []), measures, fifths, False, None, bpm, m)
    sc.insert(0, rh)
    sc.insert(0, lh)
    sc.insert(0, layout.StaffGroup([rh, lh], name="Piano", abbreviation="Pno.", symbol="brace"))
    sc.write("musicxml", fp=path)
    # music21 が勝手に入れる「作曲者 Music21」と、曲名の二重表示(movement-title)を消す
    with open(path, encoding="utf-8") as f:
        xml = f.read()
    xml = re.sub(r"\s*<creator type=\"composer\">Music21</creator>", "", xml)
    xml = re.sub(r"\s*<movement-title>.*?</movement-title>", "", xml)
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml)
    return path


def to_midi(model, path, bpm=None):
    import pretty_midi

    bpm = bpm or model["meta"].get("tempo", 120)
    sec = 60.0 / float(bpm)
    pm = pretty_midi.PrettyMIDI(initial_tempo=float(bpm))
    for name, arr, vel in (("Right", model.get("rh", []), 90), ("Left", model.get("lh", []), 72)):
        inst = pretty_midi.Instrument(program=0, name=name)
        for n in arr:
            for p in n["p"]:
                s = n["o"] * sec
                inst.notes.append(pretty_midi.Note(velocity=vel, pitch=int(p), start=s, end=s + max(n["d"], 0.05) * sec))
        pm.instruments.append(inst)
    pm.write(path)
    return path
