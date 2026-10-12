#!/bin/bash
# Piano Sheet の起動(Mac)。手元のサーバーを立ち上げて、ブラウザで画面を開きます。
cd "$(dirname "$0")/app" || exit 1
VPY="$HOME/Library/Application Support/PianoSheet/venv/bin/python"
if [ ! -x "$VPY" ]; then
  echo "まだ準備ができていません。先に setup_mac.command を開いてください。"
  read -r -p "Enter キーで閉じます" _
  exit 1
fi
URL="http://127.0.0.1:8790"
if ! curl -s -m 2 "$URL/api/scores" >/dev/null; then
  echo "Piano Sheet を起動しています。少しお待ちください..."
  echo "(このウィンドウを閉じると Piano Sheet も終わります)"
  "$VPY" server.py &
  SERVER=$!
  for _ in $(seq 1 90); do
    curl -s -m 2 "$URL/api/scores" >/dev/null && break
    sleep 1
  done
  if ! curl -s -m 2 "$URL/api/scores" >/dev/null; then
    echo "起動できませんでした。setup_mac.command をもう一度開いてから、やり直してください。"
    read -r -p "Enter キーで閉じます" _
    exit 1
  fi
  open "$URL"
  wait $SERVER
else
  open "$URL"
fi
