"""raw.json(解析結果)と4つの設定から、ピアノ譜の中身(model)を組み立てる。

設定は本家と同じ4つ:
  level  : 1=入門 2=初級 3=中級 4=上級
  key    : auto=おまかせ / easy=簡単キー / original=原曲キー
  length : full=フル / short=1コーラス
  style  : solo=ソロ譜(メロディ+伴奏) / accomp=伴奏譜(弾き語り用)

model の形(拍単位。4/4 拍子で 1小節 = 4拍):
  {"meta": {...}, "rh": [{"o":拍, "d":長さ, "p":[MIDI番号...]}], "lh": [...], "chords": [{"o":拍, "name":"C"}]}
"""
import math

import numpy as np

SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
MAJOR_FIFTHS = {0: 0, 7: 1, 2: 2, 9: 3, 4: 4, 11: 5, 6: 6, 1: -5, 8: -4, 3: -3, 10: -2, 5: -1}
KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

GRID = {1: 1.0, 2: 0.5, 3: 0.5, 4: 0.5}
# v2: 歌の採譜を「弾ける旋律」に整える目安(単位は拍)
MIN_NOTE = {1: 0.5, 2: 0.4, 3: 0.3, 4: 0.2}   # これより短い音は、しゃくり・子音の拾い過ぎとみなして捨てる
BRIDGE = {1: 2.0, 2: 1.5, 3: 1.0, 4: 1.0}     # これ以下の切れ目は、前の音を伸ばしてつなぐ(息つぎで休符にしない)
DIATONIC_BONUS = 0.08                          # 調の中の和音を選びやすくする上乗せ
SNAP_MAX = 0.5                             # 調の外の音で、これより短く前後が調の中なら、聞き違いとみなして近い調の音へ寄せる(拍)
MEL_RANGE = {1: (60, 79), 2: (57, 84), 3: (55, 88), 4: (55, 88)}
LEVEL_NAMES = {1: "入門", 2: "初級", 3: "中級", 4: "上級"}


# ---------- 時間 -> 拍 ----------
def _time_to_beat_fn(beats, tempo):
    bt = np.asarray(beats, dtype=float)
    period = 60.0 / tempo if tempo > 0 else 0.5
    if len(bt) < 2:
        return lambda t: np.asarray(t) / period
    p0 = bt[1] - bt[0]
    p1 = bt[-1] - bt[-2]

    def f(t):
        t = np.asarray(t, dtype=float)
        r = np.interp(t, bt, np.arange(len(bt), dtype=float))
        r = np.where(t < bt[0], (t - bt[0]) / p0, r)
        r = np.where(t > bt[-1], len(bt) - 1 + (t - bt[-1]) / p1, r)
        return r

    return f


# ---------- 調とコード ----------
def detect_key(beat_chroma, melody):
    prof = np.zeros(12)
    if beat_chroma:
        prof += np.asarray(beat_chroma).sum(axis=0)
        prof /= prof.max() + 1e-9
    mel = np.zeros(12)
    for n in melody:
        mel[n["p"] % 12] += n["e"] - n["s"]
    if mel.max() > 0:
        prof += 0.7 * mel / mel.max()
    best = (-9, 0, "major")
    for t in range(12):
        for mode, ks in (("major", KS_MAJOR), ("minor", KS_MINOR)):
            c = np.corrcoef(prof, np.roll(ks, t))[0, 1]
            if c > best[0]:
                best = (c, t, mode)
    return best[1], best[2]


def key_fifths(tonic, mode):
    major_tonic = tonic if mode == "major" else (tonic + 3) % 12
    return MAJOR_FIFTHS[major_tonic]


def choose_transpose(tonic, mode, key_mode):
    if key_mode == "original":
        return 0
    target = 0 if mode == "major" else 9
    if key_mode == "easy":
        t = (target - tonic) % 12
        return t - 12 if t > 5 else t
    # おまかせ: 調号が2つ以内ならそのまま、多い時は調号1つ以内の近い調へ
    if abs(key_fifths(tonic, mode)) <= 2:
        return 0
    cands = [0, 7, 5] if mode == "major" else [9, 4, 2]
    best = None
    for c in cands:
        t = (c - tonic) % 12
        t = t - 12 if t > 5 else t
        if best is None or abs(t) < abs(best):
            best = t
    return best


SCALE = {"major": (0, 2, 4, 5, 7, 9, 11), "minor": (0, 2, 3, 5, 7, 8, 10, 11)}


def scale_pcs(tonic, mode):
    return {(tonic + i) % 12 for i in SCALE[mode]}


def _diatonic(r, q, scale):
    """その調の音だけでできた和音か。"""
    return all(pc in scale for pc in chord_tones(r, q))


def _chord_for(chroma, bass_pc, prev, scale=None):
    v = np.asarray(chroma, dtype=float)
    if v.sum() < 1e-6:
        return prev
    v = v / (np.linalg.norm(v) + 1e-9)
    best, best_s = prev, -9
    for r in range(12):
        for q, iv in (("", (0, 4, 7)), ("m", (0, 3, 7))):
            tpl = np.zeros(12)
            for i in iv:
                tpl[(r + i) % 12] = 1
            tpl[r] = 1.2
            s = float(v @ tpl) / np.linalg.norm(tpl)
            if bass_pc is not None and bass_pc == r:
                s += 0.12
            if prev is not None and prev == (r, q):
                s += 0.04
            if scale is not None and _diatonic(r, q, scale):
                s += DIATONIC_BONUS  # v2: 調の外の和音(A調の Am など)は、はっきり聞こえる時だけ選ぶ
            if s > best_s:
                best, best_s = (r, q), s
    return best


def chord_tones(root, q):
    return [root % 12, (root + (3 if q == "m" else 4)) % 12, (root + 7) % 12]


def use_sharp(pc, fifths):
    """黒鍵を#で書くか♭で書くか。#系の調(#2つ以上)は#、それ以外は♭(ただしF#だけは#)。"""
    if fifths >= 2:
        return True
    if fifths <= -2:
        return False
    return pc % 12 == 6 and fifths >= 0


def spell(pc, fifths):
    return (SHARP if use_sharp(pc, fifths) else FLAT)[pc % 12]


def chord_name(root, q, bass_pc, fifths):
    n = spell(root, fifths) + q
    if bass_pc is not None and bass_pc % 12 != root % 12:
        n += "/" + spell(bass_pc, fifths)
    return n


def _place(pc, lo, hi):
    """音名(0-11)を lo 以上 hi 以下で一番低い位置に置く。"""
    m = lo + ((pc - lo) % 12)
    return m if m <= hi else m - 12


def _fold(p, lo, hi):
    while p < lo:
        p += 12
    while p > hi:
        p -= 12
    return p


# ---------- 旋律の整形 ----------
def _quantize_mono(notes, g):
    q = []
    for n in notes:
        s = round(n["o"] / g) * g
        e = round((n["o"] + n["d"]) / g) * g
        if e <= s:
            e = s + g
        q.append({"o": s, "d": e - s, "p": n["p"], "a": n.get("a", 0.5)})
    q.sort(key=lambda n: (n["o"], -n["a"]))
    out = []
    for n in q:
        if out and n["o"] == out[-1]["o"]:
            continue
        if out and out[-1]["o"] + out[-1]["d"] > n["o"]:
            out[-1]["d"] = n["o"] - out[-1]["o"]
        out.append(n)
    return [n for n in out if n["d"] > 0]


def _bridge(notes, max_gap):
    """短い切れ目は前の音を次の音の頭まで伸ばす。"""
    for a, b in zip(notes, notes[1:]):
        gap = b["o"] - (a["o"] + a["d"])
        if 0 < gap <= max_gap + 1e-6:
            a["d"] = b["o"] - a["o"]
    return notes


def _clean_melody(mel, level, scale=None):
    """v2: 細切れの採譜を、休符の少ない1本の旋律にする。"""
    notes = sorted((dict(n) for n in mel if n["d"] >= MIN_NOTE[level]), key=lambda n: n["o"])
    # 調の外の短い音で、前後が調の中なら、半音隣の調の音へ寄せる(歌の音程の揺れの聞き違い)
    if scale:
        for i, n in enumerate(notes):
            if n["p"] % 12 in scale or n["d"] > SNAP_MAX:
                continue
            nb = [notes[j]["p"] for j in (i - 1, i + 1) if 0 <= j < len(notes)]
            if not all(p % 12 in scale for p in nb):
                continue
            ups, downs = n["p"] + 1, n["p"] - 1
            ok = [p for p in (downs, ups) if p % 12 in scale]
            if ok:
                ref = sum(nb) / len(nb) if nb else n["p"]
                n["p"] = min(ok, key=lambda p: abs(p - ref))
    # 前後がなめらかなのに1音だけ大きく飛んだ所は、倍音の聞き違いとみなしてオクターブを戻す
    for i in range(1, len(notes) - 1):
        a, b, c = notes[i - 1]["p"], notes[i]["p"], notes[i + 1]["p"]
        ref = (a + c) / 2
        if abs(b - ref) >= 9 and abs(a - c) <= 5:
            notes[i]["p"] = b + 12 * round((ref - b) / 12)
    return _bridge(notes, BRIDGE[level])


def _fill_pattern(tones, o, d, level):
    """メロディの無い区間を、コードの音で埋める右手の型。"""
    v = sorted(_place(pc, 60, 71) for pc in tones)
    if level <= 2:
        return [{"o": o, "d": d, "p": v}]
    step = 0.5 if level == 4 else 1.0
    seq = v + v[1:-1][::-1] if len(v) > 2 else v  # 上がって下がる分散和音
    out, k, t = [], 0, o
    while t < o + d - 1e-6:
        out.append({"o": t, "d": min(step, o + d - t), "p": [seq[k % len(seq)]]})
        k += 1
        t += step
    return out


def arrange(raw, level=3, key_mode="auto", length="full", style="solo", title="", artist=""):
    level = int(level)
    tempo = float(raw.get("tempo") or 120)
    to_beat = _time_to_beat_fn(raw.get("beats") or [], tempo)
    phase = int(raw.get("phase", 0))
    beat_chroma = raw.get("beat_chroma") or []

    def conv(notes):
        out = []
        for n in notes:
            s = float(to_beat(n["s"])) - phase
            e = float(to_beat(n["e"])) - phase
            out.append({"o": s, "d": max(e - s, 0.05), "p": n["p"], "a": n.get("a", 0.5)})
        return out

    mel = conv(raw.get("melody", []))
    bass = conv(raw.get("bass", []))
    acc = conv(raw.get("accomp", []))

    allnotes = mel + bass + acc
    if not allnotes:
        raise ValueError("音が見つかりませんでした")
    first = min(n["o"] for n in allnotes)
    shift = 4 * math.ceil(-first / 4) if first < 0 else 0
    for arr in (mel, bass, acc):
        for n in arr:
            n["o"] += shift

    # ---- 範囲(フル / 1コーラス) ----
    end_all = max(n["o"] + n["d"] for n in allnotes) + shift
    total_measures = int(math.ceil(end_all / 4))
    mel_first = min((n["o"] for n in mel), default=0)
    start_m = int(mel_first // 4) if mel else 0
    if length == "short":
        remain = max(total_measures - start_m, 1)
        L = int(round(remain * 0.45 / 4)) * 4
        L = max(16, min(40, L))
        end_m = min(total_measures, start_m + L)
    else:
        start_m = int(min(n["o"] for n in allnotes) // 4)
        end_m = total_measures
    lo_b, hi_b = start_m * 4, end_m * 4

    def trim(arr):
        out = []
        for n in arr:
            if n["o"] >= hi_b or n["o"] + n["d"] <= lo_b or n["o"] < lo_b:
                continue
            m = dict(n)
            m["o"] -= lo_b
            m["d"] = min(m["d"], hi_b - n["o"])
            out.append(m)
        return out

    mel, bass, acc = trim(mel), trim(bass), trim(acc)
    measures = end_m - start_m

    # ---- 調と移調 ----
    tonic, mode = detect_key(beat_chroma, raw.get("melody", []))
    scale = scale_pcs(tonic, mode)
    t = choose_transpose(tonic, mode, key_mode)
    new_tonic = (tonic + t) % 12
    fifths = key_fifths(new_tonic, mode)

    # ---- コード(入門は1小節ごと、それ以外は2拍ごと) ----
    win = 4 if level == 1 else 2
    chords = []
    prev = None
    for k in range(int(measures * 4 / win)):
        o = k * win
        raw_idx0 = int(o + lo_b - shift + phase)
        vec = np.zeros(12)
        for bi in range(raw_idx0, raw_idx0 + win):
            if 0 <= bi < len(beat_chroma):
                vec += np.asarray(beat_chroma[bi])
        bw = {}
        for n in bass:
            ov = min(n["o"] + n["d"], o + win) - max(n["o"], o)
            if ov > 0:
                bw[n["p"] % 12] = bw.get(n["p"] % 12, 0) + ov
        bass_pc = max(bw, key=bw.get) if bw else None
        ch = _chord_for(vec, bass_pc, prev, scale) or (0, "")
        prev = ch
        root = (ch[0] + t) % 12
        tones = chord_tones(root, ch[1])
        bpc = (bass_pc + t) % 12 if bass_pc is not None else root
        if bpc not in tones:
            bpc = root
        chords.append({"o": o, "d": win, "root": root, "q": ch[1], "bass": bpc, "tones": tones})

    # ---- メロディ ----
    g = GRID[level]
    mel = _clean_melody(mel, level, scale)
    for n in mel:
        n["p"] += t
    if mel:
        med = float(np.median([n["p"] for n in mel]))
        k = round((71 - med) / 12)
        lo, hi = MEL_RANGE[level]
        for n in mel:
            n["p"] = _fold(n["p"] + 12 * k, lo, hi)
    mel_q = _bridge(_quantize_mono(mel, g), BRIDGE[level])

    def chord_at(o):
        for c in chords:
            if c["o"] <= o < c["o"] + c["d"]:
                return c
        return chords[-1] if chords else None

    rh, lh = [], []

    # ---- 左手 ----
    prev_key = None
    for c in chords:
        b = _place(c["bass"], 41, 52)
        o, d = c["o"], c["d"]
        if level == 1:
            lh.append({"o": o, "d": d, "p": [b]})
        elif level == 2:
            same = prev_key == (c["root"], c["q"], c["bass"]) and o % 4 != 0 and lh
            if same:
                lh[-1]["d"] += d
            else:
                lh.append({"o": o, "d": d, "p": [b]})
        elif level == 3:
            fifth = b + ((c["root"] + 7 - b) % 12 or 12)
            lh.append({"o": o, "d": d, "p": sorted({b, fifth})})
        else:
            fifth = b + ((c["root"] + 7 - b) % 12 or 12)
            pat = [b, fifth, b + 12, fifth]
            for i, p in enumerate(pat):
                lh.append({"o": o + i * 0.5, "d": 0.5, "p": [p]})
        prev_key = (c["root"], c["q"], c["bass"])

    # ---- 右手 ----
    if style == "accomp":
        prev_v = None
        for c in chords:
            cands = []
            for inv in range(3):
                ts = c["tones"][inv:] + c["tones"][:inv]
                v, lo = [], 58
                for pc in ts:
                    p = _place(pc, lo, lo + 11)
                    v.append(p)
                    lo = p + 1
                cands.append(v)
            if prev_v is None:
                v = min(cands, key=lambda v: abs(sum(v) / 3 - 65))
            else:
                v = min(cands, key=lambda v: sum(abs(a - b) for a, b in zip(v, prev_v)))
            prev_v = v
            o, d = c["o"], c["d"]
            if level in (1, 2):
                rh.append({"o": o, "d": d, "p": v})
            elif level == 3:
                for i in range(int(d)):
                    rh.append({"o": o + i, "d": 1, "p": v})
            else:
                for off, dd in ((0, 1.0), (1.0, 0.5), (1.5, 0.5)):
                    rh.append({"o": o + off, "d": dd, "p": v})
    else:
        starts = {c["o"] for c in chords}
        for n in mel_q:
            ps = [n["p"]]
            c = chord_at(n["o"])
            if c and level >= 3:
                strong = n["o"] in starts
                if level == 4:
                    strong = strong or (n["o"] % 2 == 0)
                if strong:
                    below = sorted(
                        (_place(pc, n["p"] - 9, n["p"] - 3) for pc in c["tones"] if pc != n["p"] % 12),
                        reverse=True,
                    )
                    below = [p for p in below if n["p"] - 9 <= p <= n["p"] - 3 and p >= 55]  # 右手の段から下へはみ出さない
                    take = 2 if (level == 4 and n["o"] in starts) else 1
                    ps = sorted(set(ps + below[:take]))
            rh.append({"o": n["o"], "d": n["d"], "p": ps})
        # v2: メロディの無い所(前奏・間奏・1拍以上の休み)は、コードの音で右手を埋める
        for c in chords:
            a, b = c["o"], c["o"] + c["d"]
            free, cur = [], a
            for n in sorted((n for n in mel_q if n["o"] < b and n["o"] + n["d"] > a), key=lambda n: n["o"]):
                if n["o"] > cur:
                    free.append((cur, n["o"]))
                cur = max(cur, n["o"] + n["d"])
            if cur < b:
                free.append((cur, b))
            for s, e in free:
                s = math.ceil(s / g - 1e-6) * g
                if e - s >= 1.0 - 1e-6:
                    rh.extend(_fill_pattern(c["tones"], s, e - s, level))
        rh.sort(key=lambda n: n["o"])

    chord_syms = []
    last = None
    for c in chords:
        name = chord_name(c["root"], c["q"], c["bass"], fifths)
        if (c["root"], c["q"]) != last:  # v2: 低音だけの違い(G と G/D)では書き直さない
            chord_syms.append({"o": c["o"], "name": name})
            last = (c["root"], c["q"])

    for arr in (rh, lh):
        for n in arr:
            n["o"] = round(n["o"], 4)
            n["d"] = round(n["d"], 4)
            n["p"] = [int(p) for p in n["p"]]

    kn = lambda pc, f: (FLAT if f < 0 else SHARP)[pc] + ("" if mode == "major" else "m")  # noqa: E731
    return {
        "meta": {
            "title": title,
            "artist": artist,
            "tempo": int(round(tempo)),
            "fifths": fifths,
            "mode": mode,
            "key_name": kn(new_tonic, fifths),
            "orig_key_name": kn(tonic, key_fifths(tonic, mode)),
            "transpose": t,
            "measures": measures,
            "level": level,
            "key_mode": key_mode,
            "length": length,
            "style": style,
        },
        "rh": rh,
        "lh": lh,
        "chords": chord_syms,
    }
