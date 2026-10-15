# 世界のニュース

世界と経済のニュースの見出しを30分ごとに集めて、1枚のページにする。費用はかからない（GitHub Actions と GitHub Pages の無料枠）。

- ページ：https://aisuke-202.github.io/world-news/
- 取得元：Googleニュース（国際・ビジネス）、BBC日本語、朝日新聞（国際）のRSS。見出しとリンクだけを載せ、本文は各媒体のサイトで読む。
- 過去36時間・タブごとに20件まで。同じ媒体は5件まで。

## 仕組み
```
GitHub Actions（30分ごと） → build.py → site/index.html → GitHub Pages
```
| ファイル | 役割 |
|---|---|
| `build.py` | RSSを読んで見出しを並べる。取得元の追加・削除は `FEEDS` を編集する |
| `template.html` | ページのデザイン |
| `.github/workflows/update.yml` | 30分ごとの実行と公開。毎月1日に `keepalive.txt` を書き換える（60日間動きがないと定期実行が止まるため） |

## 確認
```
python3 build.py && open site/index.html
```
ページ上部の更新時刻が2時間以上前なら「更新が止まっています」と出る。そのときは GitHub の Actions タブでエラーを確認する。
