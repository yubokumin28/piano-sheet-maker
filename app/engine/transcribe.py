"""音源を解析して raw.json(メロディ・伴奏・ベース・拍・コード用クロマ)を作る。

流れ: ffmpeg で wav 化 -> demucs で 歌/ベース/その他/ドラム に分離
      -> basic-pitch で 歌=メロディ、ベース=ベース線、その他=伴奏 を採譜
      -> librosa で 拍(テンポ)と拍ごとのクロマ(和音の手がかり)を取る
"""
import json
import os
import subprocess
import tempfile
import threading

import numpy as np

SR = 44100
_model_lock = threading.Lock()
_demucs = None
_bp_model = None


class Cancelled(Exception):
    pass


def _check(cancel):
    if cancel is not None and cancel.is_set():
        raise Cancelled()


def ffmpeg_exe():
    """PC に ffmpeg が入っていればそれを、無ければ imageio-ffmpeg 同梱のものを使う(配布先で入れなくて済むように)。"""
    import shutil
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _ffmpeg_to_wav(src, dst, sr=SR, channels=2):
    cmd = [ffmpeg_exe(), "-y", "-loglevel", "error", "-i", src, "-ac", str(channels), "-ar", str(sr), "-f", "wav", dst]
    subprocess.run(cmd, check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _load_demucs():
    global _demucs
    if _demucs is None:
        from demucs.pretrained import get_model
        m = get_model("htdemucs")
        m.eval()
        _demucs = m
    return _demucs


def _load_bp():
    global _bp_model
    if _bp_model is None:
        from basic_pitch import ICASSP_2022_MODEL_PATH
        from basic_pitch.inference import Model
        onnx = os.path.join(os.path.dirname(str(ICASSP_2022_MODEL_PATH)), "nmp.onnx")
        _bp_model = Model(onnx if os.path.exists(onnx) else ICASSP_2022_MODEL_PATH)
    return _bp_model


def _separate(wav_path):
    import soundfile as sf
    import torch
    from demucs.apply import apply_model

    audio, sr = sf.read(wav_path, dtype="float32", always_2d=True)
    x = torch.from_numpy(audio.T.copy())  # (2, T)
    ref = x.mean(0)
    mean, std = ref.mean(), ref.std() + 1e-8
    x = (x - mean) / std
    model = _load_demucs()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    with torch.no_grad():
        out = apply_model(model, x[None], device=device, split=True, overlap=0.25, progress=False)[0]
    out = out * std + mean
    stems = {name: out[i].cpu().numpy() for i, name in enumerate(model.sources)}
    return stems, sr


def _transcribe_stem(path, fmin, fmax, onset=0.5, frame=0.3, min_len=90):
    from basic_pitch.inference import predict
    _, _, events = predict(
        path,
        _load_bp(),
        onset_threshold=onset,
        frame_threshold=frame,
        minimum_note_length=min_len,
        minimum_frequency=fmin,
        maximum_frequency=fmax,
        melodia_trick=True,
    )
    notes = [
        {"s": float(s), "e": float(e), "p": int(p), "a": float(a)}
        for (s, e, p, a, *_rest) in events
    ]
    notes.sort(key=lambda n: (n["s"], n["p"]))
    return notes


def _monophonic(notes, min_dur=0.08):
    """歌の採譜を1本の旋律にする(同時に鳴る音は大きい方を残す)。"""
    out = []
    for n in sorted(notes, key=lambda n: (n["s"], -n["a"])):
        if n["e"] - n["s"] < min_dur:
            continue
        if out:
            prev = out[-1]
            if n["s"] < prev["e"]:
                if n["s"] - prev["s"] < 0.05:
                    if n["a"] > prev["a"]:
                        out[-1] = n
                    continue
                prev["e"] = n["s"]
                if prev["e"] - prev["s"] < min_dur:
                    out.pop()
        out.append(dict(n))
    # 同じ高さで隙間が短いものはつなぐ(歌のしゃくり・ビブラートで切れた音)
    merged = []
    for n in out:
        if merged and merged[-1]["p"] == n["p"] and n["s"] - merged[-1]["e"] < 0.06:
            merged[-1]["e"] = n["e"]
        else:
            merged.append(n)
    return merged


def analyze(src_path, work_dir, progress=None, cancel=None):
    import librosa
    import soundfile as sf

    def step(pct, msg):
        _check(cancel)
        if progress:
            progress(pct, msg)

    os.makedirs(work_dir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="pianosheet_", dir=work_dir)
    wav = os.path.join(tmp, "mix.wav")
    step(3, "音源を読み込み中")
    _ffmpeg_to_wav(src_path, wav)

    with _model_lock:
        step(10, "歌と伴奏を分けています(初回はAIのダウンロードで数分かかります)")
        stems, sr = _separate(wav)
        step(45, "拍とテンポを解析中")
        paths = {}
        for name in ("vocals", "bass", "other", "drums"):
            p = os.path.join(tmp, f"{name}.wav")
            sf.write(p, stems[name].T, sr)
            paths[name] = p

        mix_mono = librosa.to_mono(stems["vocals"] + stems["bass"] + stems["other"] + stems["drums"])
        y = librosa.resample(mix_mono, orig_sr=sr, target_sr=22050)
        hop = 512
        oenv = librosa.onset.onset_strength(y=y, sr=22050, hop_length=hop)
        tempo, beat_frames = librosa.beat.beat_track(onset_envelope=oenv, sr=22050, hop_length=hop)
        tempo = float(np.atleast_1d(tempo)[0])
        beat_times = librosa.frames_to_time(beat_frames, sr=22050, hop_length=hop).tolist()
        duration = float(len(y) / 22050)

        # 伴奏(ベース+その他)のクロマを拍ごとに平均 -> コード推定に使う
        acc = librosa.to_mono(stems["bass"] + stems["other"])
        acc = librosa.resample(acc, orig_sr=sr, target_sr=22050)
        chroma = librosa.feature.chroma_cqt(y=acc, sr=22050, hop_length=hop)
        bounds = list(beat_frames) + [chroma.shape[1]]
        beat_chroma = []
        for i in range(len(beat_frames)):
            a, b = int(bounds[i]), int(max(bounds[i + 1], bounds[i] + 1))
            beat_chroma.append(chroma[:, a:b].mean(axis=1).round(4).tolist())

        # ベースの立ち上がり強さ -> 小節の頭(1拍目)の位置合わせに使う
        bass_y = librosa.resample(librosa.to_mono(stems["bass"]), orig_sr=sr, target_sr=22050)
        bass_env = librosa.onset.onset_strength(y=bass_y, sr=22050, hop_length=hop)

        step(55, "メロディを採譜中")
        melody = _monophonic(_transcribe_stem(paths["vocals"], 80, 1100, onset=0.45, frame=0.3, min_len=100))
        step(70, "ベースを採譜中")
        bass = _transcribe_stem(paths["bass"], 30, 400, onset=0.5, frame=0.3, min_len=100)
        step(82, "伴奏を採譜中")
        accomp = _transcribe_stem(paths["other"], 60, 2000, onset=0.55, frame=0.35, min_len=90)

    # 1拍目の候補(0〜3)のうち、ベースの立ち上がりとコードの変わり目が最も揃うものを選ぶ
    scores = []
    for ph in range(4):
        idx = [beat_frames[i] for i in range(ph, len(beat_frames), 4)]
        s = float(np.sum(bass_env[np.clip(idx, 0, len(bass_env) - 1)])) if idx else 0.0
        scores.append(s)
    phase = int(np.argmax(scores)) if scores else 0

    raw = {
        "version": 1,
        "tempo": tempo,
        "beats": beat_times,
        "phase": phase,
        "duration": duration,
        "beat_chroma": beat_chroma,
        "melody": melody,
        "bass": bass,
        "accomp": accomp,
    }
    try:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    except Exception:
        pass
    step(95, "楽譜を組み立て中")
    return raw


if __name__ == "__main__":
    import sys
    r = analyze(sys.argv[1], sys.argv[2], progress=lambda p, m: print(p, m))
    with open(os.path.join(sys.argv[2], "raw.json"), "w", encoding="utf-8") as f:
        json.dump(r, f)
    print("tempo", r["tempo"], "melody", len(r["melody"]), "bass", len(r["bass"]), "accomp", len(r["accomp"]))
