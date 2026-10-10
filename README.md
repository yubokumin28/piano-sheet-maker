# Piano Sheet (自作版) — 音源からピアノ譜を自動で作る Windows アプリ

好きな曲の音源(mp3 / mp4 / wav など)を入れると、AI が歌と伴奏を聞き分けて、ピアノ譜を自動で作ります。
できた楽譜は、ピアノの音で再生・その場で修正・PDF / MusicXML / MIDI / バンド音源(mp3)に書き出せます。
処理は全部あなたの PC の中で行い、曲をどこかへ送ることはありません。

## はじめ方(3ステップ)

1. このページ右上の緑の **Code** → **Download ZIP** で落とし、右クリック →「すべて展開」
   (または [Releases](../../releases) の ZIP)
2. 展開したフォルダの **setup.bat** をダブルクリック(最初の1回だけ・10〜20分)
3. **start_piano_sheet.bat** をダブルクリックで起動

くわしい使い方は、フォルダの中の **00_START_HERE_manual.html** をダブルクリックして開いてください。
お手本の曲と、そこから作った楽譜は **sample** フォルダにあります。

## 動く環境

- Windows 10 / 11(64bit)
- ネット接続(準備の時だけ)、空き容量 約3GB
- Python 3.11 が無ければ setup.bat が自動で入れます(winget)

## 中で使っている公開技術

| 役割 | 使っているもの | ライセンス |
|---|---|---|
| 歌・ベース・伴奏・ドラムの聞き分け | [Demucs](https://github.com/facebookresearch/demucs) (htdemucs) | MIT |
| 音の高さの聞き取り(採譜) | [Basic Pitch](https://github.com/spotify/basic-pitch) | Apache-2.0 |
| 拍・テンポ・和音の手がかり | [librosa](https://librosa.org/) | ISC |
| 楽譜データの書き出し | [music21](https://github.com/cuthbertLab/music21) / [pretty_midi](https://github.com/craffel/pretty-midi) | BSD |
| 画面の楽譜表示 | [OpenSheetMusicDisplay](https://opensheetmusicdisplay.org/) | BSD-3 |
| 再生 | [Tone.js](https://tonejs.github.io/) + Salamander Grand Piano | MIT / CC-BY 3.0 |
| バンド音源 | [GeneralUser GS](https://www.schristiancollins.com/generaluser.php) (S. Christian Collins) | 同梱の app/soundfont/GeneralUser_LICENSE.txt |

sample フォルダの曲は作者の自作曲です。
