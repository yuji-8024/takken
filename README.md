# 宅建 過去10年 問題バンク

RETIO公式過去問（平成28〜令和7）を3層構成で学習するWebアプリ。

## ローカルで確認

```bash
# 正解番号抽出 + サイト用データ生成
python3 scripts/extract_answers.py
python3 scripts/build_site_data.py

# 簡易サーバー（site ディレクトリで）
cd site && python3 -m http.server 8080
# → http://localhost:8080
```

## Netlify デプロイ

1. [Netlify](https://www.netlify.com/) で Git リポジトリを連携
2. ビルド設定（`netlify.toml` 済み）:
   - **Build command**: `python3 scripts/build_site_data.py`
   - **Publish directory**: `site`
3. デプロイ

手動デプロイ:

```bash
python3 scripts/build_site_data.py
npx netlify deploy --prod --dir=site
```

## 構成

| パス | 内容 |
|------|------|
| `site/` | 静的サイト（HTML/CSS/JS） |
| `site/data/bank.json` | 問題データ（ビルドで生成） |
| `scripts/build_site_data.py` | JSON 生成 |
| `data/pdfs/` | 公式PDF（gitignore） |

## データ更新

PDFを再取得・抽出したあと:

```bash
python3 scripts/download_pdfs.py
python3 scripts/extract_questions.py
python3 scripts/build_site_data.py
```
