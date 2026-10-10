"""歌と伴奏を分ける AI(demucs htdemucs)を先に落としておく。初回の変換で待たされないように。"""
from demucs.pretrained import get_model

m = get_model("htdemucs")
print("model ready:", type(m).__name__, list(m.sources))
