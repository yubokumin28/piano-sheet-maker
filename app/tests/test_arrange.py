"""raw.json から全設定の組み合わせで楽譜を作り、MusicXML と MIDI が書けるか確かめる。
使い方: python tests/test_arrange.py <raw.json> <出力フォルダ>
"""
import itertools
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from engine.arrange import arrange  # noqa: E402
from engine.notation import to_midi, to_musicxml  # noqa: E402

raw = json.load(open(sys.argv[1], encoding="utf-8"))
out = sys.argv[2]
os.makedirs(out, exist_ok=True)
ok = 0
combos = list(itertools.product([1, 2, 3, 4], ["auto", "easy", "original"], ["full", "short"], ["solo", "accomp"]))
for lv, k, ln, st in combos:
    t0 = time.time()
    m = arrange(raw, lv, k, ln, st, title="test", artist="me")
    name = f"L{lv}_{k}_{ln}_{st}"
    to_musicxml(m, os.path.join(out, name + ".musicxml"))
    to_midi(m, os.path.join(out, name + ".mid"))
    ok += 1
    mt = m["meta"]
    print(name, "measures", mt["measures"], "key", mt["orig_key_name"], "->", mt["key_name"], "rh", len(m["rh"]), "lh", len(m["lh"]), f"{time.time()-t0:.1f}s")
print("OK", ok, "/", len(combos))
