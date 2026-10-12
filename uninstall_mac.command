#!/bin/bash
# Piano Sheet の片付け(Mac)。setup_mac.command が入れた AI の部品を消します。
echo "============================================"
echo " Piano Sheet の片付け"
echo " 次の場所の AI の部品(約3GB)を消します:"
echo "   $HOME/Library/Application Support/PianoSheet"
echo " このフォルダの中の楽譜(data)は消えません。"
echo "============================================"
read -r -p "消してよければ y を押して Enter: " ans
[ "$ans" = "y" ] || exit 0
pkill -f "PianoSheet/venv/bin/python server.py" 2>/dev/null
rm -rf "$HOME/Library/Application Support/PianoSheet"
rm -f "$HOME/.cache/torch/hub/checkpoints/955717e8-8726e21a.th"
echo ""
echo "終わりました。全部消す時は、この piano-sheet-maker フォルダもゴミ箱へ入れてください。"
read -r -p "Enter キーで閉じます" _
