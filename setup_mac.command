#!/bin/bash
# Piano Sheet の準備(Mac・最初の1回だけ)。10〜20分かかります。ネット接続が必要です。
cd "$(dirname "$0")" || exit 1
echo "============================================"
echo " Piano Sheet の準備(最初の1回だけ)"
echo " 10〜20分ほどかかります。このウィンドウは閉じないでください。"
echo "============================================"

fail() {
  echo ""
  echo "エラー: $1"
  echo "ネット接続を確かめて、もう一度 setup_mac.command を開いてください(済んだ所は飛ばすので2回目は速いです)。"
  read -r -p "Enter キーで閉じます" _
  exit 1
}

# 1. Python 3.11 を探す
PY=""
for c in python3.11 /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 /opt/homebrew/bin/python3.11 /usr/local/bin/python3.11; do
  if command -v "$c" >/dev/null 2>&1; then PY="$(command -v "$c")"; break; fi
done
if [ -z "$PY" ] && command -v brew >/dev/null 2>&1; then
  echo "[1/5] Python 3.11 を入れています(Homebrew)..."
  brew install python@3.11 || true
  for c in /opt/homebrew/bin/python3.11 /usr/local/bin/python3.11; do
    [ -x "$c" ] && PY="$c" && break
  done
fi
if [ -z "$PY" ]; then
  echo ""
  echo "Python 3.11 が見つかりませんでした。"
  echo "これからダウンロードページを開きます。「macOS 64-bit universal2 installer」を入れてから、"
  echo "もう一度 setup_mac.command を開いてください。"
  open "https://www.python.org/downloads/release/python-3119/"
  read -r -p "Enter キーで閉じます" _
  exit 1
fi
echo "[1/5] Python 3.11: $PY"

# 2. 専用の環境(フォルダの外の決まった場所。iCloud 同期にも乗せない)
VENV="$HOME/Library/Application Support/PianoSheet/venv"
echo ""
echo "[2/5] 専用の環境を作っています: $VENV"
[ -x "$VENV/bin/python" ] || "$PY" -m venv "$VENV" || fail "環境を作れませんでした"
VPY="$VENV/bin/python"
"$VPY" -m pip install --upgrade pip --quiet

# 3. AI の部品
echo ""
echo "[3/5] AI の部品を入れています(いちばん長い所です)..."
"$VPY" -m pip install torch torchaudio || fail "torch を入れられませんでした"
grep -v '^tinysoundfont' requirements.txt > /tmp/pianosheet_req.txt
"$VPY" -m pip install -r /tmp/pianosheet_req.txt || fail "部品を入れられませんでした"
"$VPY" -m pip install tinysoundfont==0.3.7 || echo "(注意) バンド音源の部品だけ入りませんでした。楽譜づくりには影響しません。"
"$VPY" -m pip install --no-deps demucs==4.1.0 dora-search openunmix julius lameenc einops treetable submitit retrying omegaconf antlr4-python3-runtime==4.9.3 || fail "歌を分ける部品を入れられませんでした"

# 4. 画面の部品とピアノの音
echo ""
echo "[4/5] 画面の部品とピアノの音を取ってきています..."
"$VPY" app/tools/fetch_vendor.py || fail "画面の部品を取れませんでした"

# 5. 歌と伴奏を分ける AI のモデル
echo ""
echo "[5/5] 歌と伴奏を分ける AI を取ってきています..."
"$VPY" app/tools/prefetch_model.py || fail "AI のモデルを取れませんでした"

echo ""
echo "============================================"
echo " 準備ができました。"
echo " start_mac.command を開くと起動します。"
echo "============================================"
read -r -p "Enter キーで閉じます" _
