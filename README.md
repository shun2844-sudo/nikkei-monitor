# nikkei-monitor

日経新聞のトピックページを30分ごとに巡回し、
「企業名 + プラス材料キーワード」を含むタイトルだけ
Discord に通知する個人用ツール。

## 構成
- GitHub Actions (cron */30)
- Python (requests / BeautifulSoup / Janome)
- Discord Webhook

## セットアップ
1. このリポジトリを fork or clone
2. Discord で Webhook URL を取得
3. Settings → Secrets and variables → Actions に
   `DISCORD_WEBHOOK_URL` を登録
4. Actions タブで workflow を有効化

詳細は手順書を参照。