# -*- coding: utf-8 -*-
"""
Nikkei topic pages → 企業名 + ポジティブワード を含む見出しを Discord 通知。
30分ごとに GitHub Actions で実行する想定。
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from janome.tokenizer import Tokenizer

# ====== 設定 ======
URLS = [
    "https://www.nikkei.com/topics/24032501?page=2",
    "https://www.nikkei.com/topics/22080201",
]

POSITIVE_KEYWORDS = [
    "増", "最高益", "上方修正", "増益", "最高",
    "好調", "拡大", "急伸", "過去最高", "黒字転換",
]

# ゆるめ企業辞書（必要に応じて追記してください）
COMPANY_DICT = {
    # 自動車
    "トヨタ", "ホンダ", "日産", "スズキ", "マツダ", "スバル", "三菱自", "いすゞ", "日野",
    # 電機・半導体
    "ソニー", "ソニーG", "パナソニック", "シャープ", "日立", "東芝", "富士通", "NEC",
    "キヤノン", "リコー", "セイコー", "カシオ", "村田", "村田製作所", "TDK", "ローム",
    "京セラ", "ルネサス", "東京エレクトロン", "アドバンテスト", "ディスコ", "レーザーテック",
    "SUMCO", "信越", "信越化学", "キーエンス", "ファナック", "安川電機", "オムロン",
    # 自動車部品・素材
    "デンソー", "アイシン", "ブリヂストン", "横浜ゴム", "住友ゴム",
    "旭化成", "住友化", "三菱ケミ", "東レ", "帝人", "クラレ", "三井化学",
    "新日鉄", "日本製鉄", "JFE", "神戸製鋼",
    # ゲーム・コンテンツ
    "任天堂", "バンナム", "バンダイ", "セガ", "カプコン", "スクエニ", "コナミ", "サイバー",
    "サイバーエージェント", "DeNA", "GREE", "ガンホー",
    # 通信・IT
    "ソフトバンク", "NTT", "KDDI", "楽天", "LINE", "ZHD",
    "ZOZO", "メルカリ", "freee", "マネフォ", "BASE",
    # 金融
    "三菱UFJ", "三井住友", "みずほ", "りそな", "SBI", "野村", "大和",
    "東京海上", "MS&AD", "オリックス", "三菱HCキャピタル",
    # 小売
    "ファーストリテイリング", "ユニクロ", "しまむら", "アダストリア",
    "イオン", "セブン", "セブン&アイ", "ローソン", "ファミマ",
    "ニトリ", "良品計画", "高島屋", "髙島屋", "三越伊勢丹", "J.フロント",
    # 製薬・化粧品
    "アステラス", "武田", "武田薬品", "第一三共", "エーザイ", "中外製薬", "塩野義",
    "小林製薬", "ロート", "資生堂", "コーセー", "花王", "ライオン",
    # 食品・飲料
    "JT", "アサヒ", "キリン", "サントリー", "サッポロ", "明治", "森永", "日清",
    "味の素", "ハウス", "カゴメ", "キッコーマン", "ヤクルト",
    # 重工・機械
    "三菱重", "三菱重工", "IHI", "川崎重工", "クボタ", "コマツ", "日立建機",
    "三菱マテリアル", "JX金属", "住友金属鉱山",
    # エネルギー・インフラ
    "INPEX", "ENEOS", "出光", "東京ガス", "大阪ガス",
    "東京電力", "関西電力", "中部電力", "東北電力", "九州電力",
    # 運輸
    "JR東", "JR東日本", "JR西日本", "JR東海", "JR九州",
    "ANA", "JAL", "ヤマト", "佐川", "日本郵船", "商船三井", "川崎汽船",
    # 不動産・鉄道
    "三菱地所", "三井不動産", "住友不動産", "東急", "阪急", "近鉄", "名鉄",
    # サービス・人材
    "リクルート", "パーソル", "ベネッセ", "電通", "博報堂",
    # 外食
    "ゼンショー", "すかいらーく", "吉野家", "くら寿司", "スシロー", "トリドール",
    # 機械・光学
    "ニコン", "オリンパス", "HOYA", "テルモ", "シスメックス", "ダイキン",
    "三菱電機", "富士電機",
    # 警備
    "セコム", "ALSOK",
    # 印刷
    "凸版", "凸版印刷", "大日本印刷", "DNP",
    # ドラッグストア
    "マツキヨ", "ウエルシア", "スギ薬局", "サンドラッグ", "ツルハ",
}

# 固有名詞判定で除外する一般語
EXCLUDE_PROPER = {
    "日本", "中国", "米国", "アメリカ", "欧州", "ヨーロッパ",
    "韓国", "台湾", "東京", "大阪", "名古屋", "京都", "アジア",
    "国内", "海外", "政府", "首相", "社長", "経済", "市場", "産業",
}

# 環境変数
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()

SEEN_FILE = Path("data/seen.json")
HTTP_TIMEOUT = 20
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36"
)

JST = timezone(timedelta(hours=9))


# ====== ロガー ======
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("nikkei-monitor")


# ====== Janome（重いので遅延生成）======
_tokenizer = None
def tokenizer():
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = Tokenizer()
    return _tokenizer


# ====== 関数群 ======
def fetch_html(url: str) -> str | None:
    try:
        r = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "ja,en;q=0.8"},
            timeout=HTTP_TIMEOUT,
        )
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        return r.text
    except requests.RequestException as e:
        log.error(f"HTTPエラー {url}: {e}")
        return None


def extract_articles(html: str) -> list[tuple[str, str]]:
    """(title, url) のリストを返す。日経のHTML変更にある程度耐える汎用セレクタ。"""
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    results: list[tuple[str, str]] = []
    seen_urls: set[str] = set()

    # 日経の記事URLは概ね /article/xxxxxx を含む
    for a in soup.select("a[href*='/article/']"):
        href = (a.get("href") or "").strip()
        title = a.get_text(" ", strip=True)

        if not title or len(title) < 6:
            continue
        # ナビゲーション系の短文を弾く
        if title in {"続きを読む", "もっと見る", "詳細"}:
            continue
        if href.startswith("/"):
            href = "https://www.nikkei.com" + href
        if not href.startswith("https://www.nikkei.com"):
            continue
        # クエリ除去
        clean = href.split("?")[0]
        if clean in seen_urls:
            continue
        seen_urls.add(clean)
        results.append((title, clean))
    return results


def has_positive_keyword(title: str) -> bool:
    return any(kw in title for kw in POSITIVE_KEYWORDS)


def has_company_name(title: str) -> bool:
    """辞書 → Janome 固有名詞判定 の二段構え"""
    # 1) 辞書ヒット
    for c in COMPANY_DICT:
        if c in title:
            return True
    # 2) Janome 固有名詞（組織 or 一般）で2文字以上
    try:
        for token in tokenizer().tokenize(title):
            parts = token.part_of_speech.split(",")
            if len(parts) >= 3 and parts[0] == "名詞" and parts[1] == "固有名詞":
                if parts[2] in ("組織", "一般"):
                    surf = token.surface
                    if len(surf) >= 2 and surf not in EXCLUDE_PROPER:
                        return True
    except Exception as e:
        log.warning(f"形態素解析失敗 '{title}': {e}")
    return False


def load_seen() -> set[str]:
    if not SEEN_FILE.exists():
        return set()
    try:
        with SEEN_FILE.open(encoding="utf-8") as f:
            return set(json.load(f))
    except Exception as e:
        log.warning(f"seen.json 読み込み失敗（初期化します）: {e}")
        return set()


def save_seen(seen: set[str]) -> None:
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    # 無制限に増えないよう新しい順に5000件まで保持
    data = list(seen)[-5000:]
    with SEEN_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def notify_discord(title: str, url: str, detected_at: str) -> bool:
    if not DISCORD_WEBHOOK_URL:
        log.error("DISCORD_WEBHOOK_URL が未設定です")
        return False
    payload = {
        "username": "Nikkei Monitor",
        "embeds": [{
            "title": "📈 ポジティブ材料ニュース検出",
            "description": f"**{title}**\n\n[記事を読む]({url})",
            "color": 0x2ecc71,
            "footer": {"text": f"検出時刻: {detected_at} (JST)"},
        }],
    }
    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        return True
    except requests.RequestException as e:
        log.error(f"Discord通知失敗: {e}")
        return False


def main() -> int:
    log.info("=== 日経ニュース監視 開始 ===")
    seen = load_seen()
    log.info(f"既知タイトル: {len(seen)} 件")

    hits: list[tuple[str, str]] = []
    for url in URLS:
        log.info(f"取得: {url}")
        html = fetch_html(url)
        if html is None:
            continue
        articles = extract_articles(html)
        log.info(f"  候補記事 {len(articles)} 件")
        for title, link in articles:
            if title in seen:
                continue
            if has_positive_keyword(title) and has_company_name(title):
                hits.append((title, link))
                seen.add(title)
                log.info(f"  ★HIT: {title}")
        time.sleep(2)  # 連続アクセス回避

    detected_at = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
    sent = 0
    for title, link in hits:
        ok = notify_discord(title, link, detected_at)
        if ok:
            sent += 1
        else:
            # 通知失敗時は次回再試行できるようseenから外す
            seen.discard(title)
        time.sleep(1)

    save_seen(seen)
    log.info(f"=== 完了 検出 {len(hits)} / 通知 {sent} ===")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log.exception(f"想定外エラー: {e}")
        # GitHub Actionsのジョブを赤くしたい場合は1
        sys.exit(1)