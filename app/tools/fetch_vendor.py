"""画面で使う公開ライブラリとピアノ音源を web/vendor に落とす(オフラインで動かすため。1回だけ)。"""
import os
import urllib.request

WEB = os.path.join(os.path.dirname(__file__), "..", "web", "vendor")
LIBS = {
    "opensheetmusicdisplay.min.js": "https://cdn.jsdelivr.net/npm/opensheetmusicdisplay@1.9.0/build/opensheetmusicdisplay.min.js",
    "Tone.js": "https://cdn.jsdelivr.net/npm/tone@15.1.22/build/Tone.js",
    "jspdf.umd.min.js": "https://cdn.jsdelivr.net/npm/jspdf@2.5.2/dist/jspdf.umd.min.js",
    "svg2pdf.umd.min.js": "https://cdn.jsdelivr.net/npm/svg2pdf.js@2.2.4/dist/svg2pdf.umd.min.js",
}
SAMPLE_BASE = "https://tonejs.github.io/audio/salamander/"
NOTES = ["A0", "C1", "Ds1", "Fs1", "A1", "C2", "Ds2", "Fs2", "A2", "C3", "Ds3", "Fs3", "A3", "C4", "Ds4", "Fs4",
         "A4", "C5", "Ds5", "Fs5", "A5", "C6", "Ds6", "Fs6", "A6", "C7", "Ds7", "Fs7", "A7", "C8"]


def get(url, dst):
    if os.path.exists(dst) and os.path.getsize(dst) > 0:
        return
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r, open(dst, "wb") as f:
        f.write(r.read())


os.makedirs(os.path.join(WEB, "piano"), exist_ok=True)
for name, url in LIBS.items():
    get(url, os.path.join(WEB, name))
    print("lib", name, os.path.getsize(os.path.join(WEB, name)))
for n in NOTES:
    get(SAMPLE_BASE + n + ".mp3", os.path.join(WEB, "piano", n + ".mp3"))
print("samples", len(os.listdir(os.path.join(WEB, "piano"))))

# バンド音源用の GeneralUser GS(31MB)。配布 ZIP を軽くするため、無ければ配布元の写しから落とす
SF2 = os.path.join(os.path.dirname(__file__), "..", "soundfont", "GeneralUser_GS.sf2")
SF2_URL = "https://github.com/yubokumin28/piano-sheet-maker/releases/download/v1.0/GeneralUser_GS.sf2"
os.makedirs(os.path.dirname(SF2), exist_ok=True)
get(SF2_URL, SF2)
print("soundfont", os.path.getsize(SF2))
