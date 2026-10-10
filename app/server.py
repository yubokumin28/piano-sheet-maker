"""Piano Sheet (自作版) のローカルサーバー。http://127.0.0.1:8790 で画面を出す。"""
import json
import os
import shutil
import sqlite3
import threading
import time
import traceback
import uuid
from datetime import datetime

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engine.arrange import LEVEL_NAMES, arrange
from engine.notation import to_midi, to_musicxml

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(APP_DIR), "data")
SCORES_DIR = os.path.join(DATA_DIR, "scores")
DB_PATH = os.path.join(DATA_DIR, "scores.db")
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".wma", ".mp4", ".mov", ".webm"}
os.makedirs(SCORES_DIR, exist_ok=True)

app = FastAPI(title="Piano Sheet")
_db_lock = threading.Lock()
_jobs = {}  # id -> {"progress", "message", "cancel": Event}


def db():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with _db_lock, db() as con:
        con.execute(
            """CREATE TABLE IF NOT EXISTS scores (
            id TEXT PRIMARY KEY, title TEXT, artist TEXT, level INTEGER, key_mode TEXT,
            length TEXT, style TEXT, source_name TEXT, status TEXT, error TEXT,
            key_name TEXT, tempo INTEGER, measures INTEGER,
            created_at TEXT, updated_at TEXT)"""
        )


init_db()


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def sdir(sid):
    if not sid or any(c not in "0123456789abcdef-" for c in sid):
        raise HTTPException(400, "bad id")
    return os.path.join(SCORES_DIR, sid)


def update_row(sid, **kw):
    kw["updated_at"] = now()
    cols = ", ".join(f"{k}=?" for k in kw)
    with _db_lock, db() as con:
        con.execute(f"UPDATE scores SET {cols} WHERE id=?", (*kw.values(), sid))


def get_row(sid):
    with db() as con:
        r = con.execute("SELECT * FROM scores WHERE id=?", (sid,)).fetchone()
    if not r:
        raise HTTPException(404, "not found")
    return dict(r)


def build_outputs(sid, model):
    d = sdir(sid)
    with open(os.path.join(d, "model.json"), "w", encoding="utf-8") as f:
        json.dump(model, f, ensure_ascii=False)
    to_musicxml(model, os.path.join(d, "score.musicxml"))
    to_midi(model, os.path.join(d, "score.mid"))
    m = model["meta"]
    update_row(sid, key_name=m.get("key_name"), tempo=m.get("tempo"), measures=m.get("measures"),
               level=m.get("level"), key_mode=m.get("key_mode"), length=m.get("length"), style=m.get("style"),
               title=m.get("title"), artist=m.get("artist"))


def read_tags(path, fallback):
    title, artist = fallback, ""
    try:
        import mutagen
        f = mutagen.File(path, easy=True)
        if f is not None and f.tags:
            title = (f.tags.get("title") or [title])[0] or title
            artist = (f.tags.get("artist") or [""])[0] or ""
    except Exception:
        pass
    return title, artist


def run_job(sid, src, opts):
    job = _jobs[sid]

    def progress(p, msg):
        job["progress"], job["message"] = p, msg

    try:
        from engine.transcribe import Cancelled, analyze
        raw = analyze(src, sdir(sid), progress=progress, cancel=job["cancel"])
        with open(os.path.join(sdir(sid), "raw.json"), "w", encoding="utf-8") as f:
            json.dump(raw, f)
        row = get_row(sid)
        model = arrange(raw, opts["level"], opts["key_mode"], opts["length"], opts["style"], row["title"], row["artist"])
        build_outputs(sid, model)
        update_row(sid, status="ready", error=None)
        progress(100, "完成しました")
    except Exception as e:  # noqa: BLE001
        from engine.transcribe import Cancelled
        if isinstance(e, Cancelled):
            update_row(sid, status="cancelled", error="キャンセルしました")
        else:
            traceback.print_exc()
            update_row(sid, status="error", error=str(e)[:500])
        job["message"] = "失敗しました" if not isinstance(e, Cancelled) else "キャンセルしました"
    finally:
        job["done"] = True


# ---------------- API ----------------
@app.get("/api/scores")
def list_scores():
    with db() as con:
        rows = [dict(r) for r in con.execute("SELECT * FROM scores ORDER BY updated_at DESC")]
    for r in rows:
        j = _jobs.get(r["id"])
        if j and not j.get("done"):
            r["progress"], r["message"] = j["progress"], j["message"]
        r["level_name"] = LEVEL_NAMES.get(r["level"] or 0, "")
    return rows


@app.post("/api/scores")
async def create_score(file: UploadFile = File(...), level: int = Form(3), key_mode: str = Form("auto"),
                       length: str = Form("full"), style: str = Form("solo")):
    name = os.path.basename(file.filename or "audio")
    ext = os.path.splitext(name)[1].lower()
    if ext not in AUDIO_EXT:
        raise HTTPException(400, "音声ファイル(mp3 / wav / m4a など)を選んでください")
    if level not in (1, 2, 3, 4) or key_mode not in ("auto", "easy", "original") \
            or length not in ("full", "short") or style not in ("solo", "accomp"):
        raise HTTPException(400, "設定が正しくありません")
    sid = str(uuid.uuid4())
    d = sdir(sid)
    os.makedirs(d)
    src = os.path.join(d, "source" + ext)
    with open(src, "wb") as f:
        shutil.copyfileobj(file.file, f)
    title, artist = read_tags(src, os.path.splitext(name)[0])
    with _db_lock, db() as con:
        con.execute(
            "INSERT INTO scores (id,title,artist,level,key_mode,length,style,source_name,status,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (sid, title, artist, level, key_mode, length, style, name, "processing", now(), now()),
        )
    _jobs[sid] = {"progress": 0, "message": "待機中", "cancel": threading.Event(), "done": False}
    opts = {"level": level, "key_mode": key_mode, "length": length, "style": style}
    threading.Thread(target=run_job, args=(sid, src, opts), daemon=True).start()
    return {"id": sid}


@app.get("/api/scores/{sid}")
def score_status(sid: str):
    r = get_row(sid)
    j = _jobs.get(sid)
    if j:
        r["progress"], r["message"] = j["progress"], j["message"]
    r["level_name"] = LEVEL_NAMES.get(r["level"] or 0, "")
    return r


@app.post("/api/scores/{sid}/cancel")
def cancel(sid: str):
    j = _jobs.get(sid)
    if j:
        j["cancel"].set()
    return {"ok": True}


@app.delete("/api/scores/{sid}")
def delete_score(sid: str):
    get_row(sid)
    j = _jobs.get(sid)
    if j and not j.get("done"):
        j["cancel"].set()
    with _db_lock, db() as con:
        con.execute("DELETE FROM scores WHERE id=?", (sid,))
    shutil.rmtree(sdir(sid), ignore_errors=True)
    return {"ok": True}


class MetaIn(BaseModel):
    title: str | None = None
    artist: str | None = None


@app.patch("/api/scores/{sid}")
def rename(sid: str, body: MetaIn):
    model = read_model(sid)
    if body.title is not None:
        model["meta"]["title"] = body.title.strip() or model["meta"]["title"]
    if body.artist is not None:
        model["meta"]["artist"] = body.artist.strip()
    build_outputs(sid, model)
    return {"ok": True}


def read_model(sid):
    p = os.path.join(sdir(sid), "model.json")
    if not os.path.exists(p):
        raise HTTPException(404, "楽譜がまだありません")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/scores/{sid}/model")
def get_model(sid: str):
    return read_model(sid)


def merge_edits(sid, model):
    old = read_model(sid)
    for hand in ("rh", "lh"):
        clean = []
        for n in model.get(hand, []):
            ps = [int(p) for p in n.get("p", []) if 21 <= int(p) <= 108]
            if ps and float(n["d"]) > 0:
                item = {"o": round(float(n["o"]), 4), "d": round(float(n["d"]), 4), "p": sorted(set(ps))}
                if n.get("h"):
                    item["h"] = 1
                clean.append(item)
        old[hand] = sorted(clean, key=lambda n: n["o"])
    last = max([n["o"] + n["d"] for n in old["rh"] + old["lh"]] + [0])
    old["meta"]["measures"] = max(int(old["meta"]["measures"]), int(-(-last // 4)))
    old["meta"]["edited"] = True
    return old


@app.put("/api/scores/{sid}/model")
def put_model(sid: str, model: dict):
    build_outputs(sid, merge_edits(sid, model))
    return {"ok": True}


@app.post("/api/scores/{sid}/preview")
def preview(sid: str, model: dict):
    """保存せずに、編集中の model から MusicXML だけ作って返す。"""
    import tempfile
    m = merge_edits(sid, model)
    fd, tmp = tempfile.mkstemp(suffix=".musicxml")
    os.close(fd)
    try:
        to_musicxml(m, tmp)
        with open(tmp, encoding="utf-8") as f:
            xml = f.read()
    finally:
        os.remove(tmp)
    return Response(xml, media_type="application/xml")


class RecreateIn(BaseModel):
    level: int = 3
    key_mode: str = "auto"
    length: str = "full"
    style: str = "solo"


@app.post("/api/scores/{sid}/recreate")
def recreate(sid: str, body: RecreateIn):
    row = get_row(sid)
    p = os.path.join(sdir(sid), "raw.json")
    if not os.path.exists(p):
        raise HTTPException(400, "解析データがありません")
    with open(p, encoding="utf-8") as f:
        raw = json.load(f)
    model = arrange(raw, body.level, body.key_mode, body.length, body.style, row["title"], row["artist"])
    build_outputs(sid, model)
    return {"ok": True}


@app.get("/api/scores/{sid}/musicxml")
def get_xml(sid: str, download: int = 0):
    p = os.path.join(sdir(sid), "score.musicxml")
    if not os.path.exists(p):
        raise HTTPException(404, "not ready")
    title = get_row(sid)["title"] or "score"
    return FileResponse(p, media_type="application/vnd.recordare.musicxml+xml",
                        filename=f"{title}.musicxml" if download else None,
                        headers={"Cache-Control": "no-store"})


@app.get("/api/scores/{sid}/midi")
def get_midi(sid: str):
    p = os.path.join(sdir(sid), "score.mid")
    if not os.path.exists(p):
        raise HTTPException(404, "not ready")
    title = get_row(sid)["title"] or "score"
    return FileResponse(p, media_type="audio/midi", filename=f"{title}.mid")


@app.get("/api/scores/{sid}/band")
def get_band(sid: str, parts: str = "piano,strings,bass,drums"):
    """楽譜をバンド(ピアノ・ストリングス・ベース・ドラム)で鳴らした mp3。"""
    from engine.band import render
    model = read_model(sid)
    want = tuple(p for p in parts.split(",") if p in ("piano", "strings", "bass", "drums")) or ("piano",)
    out = os.path.join(sdir(sid), "band_" + "_".join(want) + ".mp3")
    mpath = os.path.join(sdir(sid), "model.json")
    if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(mpath):
        render(model, out, parts=want)
    title = get_row(sid)["title"] or "score"
    return FileResponse(out, media_type="audio/mpeg", filename=f"{title}_band.mp3")


@app.get("/api/scores/{sid}/source")
def get_source(sid: str):
    d = sdir(sid)
    for fn in os.listdir(d):
        if fn.startswith("source."):
            return FileResponse(os.path.join(d, fn))
    raise HTTPException(404, "no source")


app.mount("/", StaticFiles(directory=os.path.join(APP_DIR, "web"), html=True), name="web")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8790, log_level="warning")
