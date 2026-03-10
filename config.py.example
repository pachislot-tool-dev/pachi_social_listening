import os
from dotenv import load_dotenv

load_dotenv()

# --- 環境変数と定数 ---
BASE_DOMAIN = "5ch.io"
BOARD_LIST_URL = f"https://www2.{BASE_DOMAIN}/5ch.html"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BOARD_URL = f"https://egg.{BASE_DOMAIN}/slotk/"
SUBJECT_URL = f"{BOARD_URL}subject.txt"
DB_PATH = "data/pachi_social_db.sqlite"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# ノイズ除去用のパターンリスト (旧 keywords.py を包含)
NOISE_PATTERNS = [
    r'([wWｗＷ]{3,})',                 # 草(www)が多すぎる
    r'(^[wWｗＷ]+$)',                   # 草のみ
    r'(^[あ-んア-ン]{1,3}$)',           # 意味のない短文
    r'(\s{4,}|\n{3,})',               # AA（アスキーアート）や連続改行の疑い
    r'(http(s)?://[A-Za-z0-9\-._~:/?#\[\]@!$&\'()*+,;=]+)', # URLのみ、またはURLを含む宣伝
    r'(万枚|フリーズ|完走)',           # ガチャ自慢、結果自慢（分析要件によるが今回は除外例として）
    r'([!！?？]{4,})'                  # 異常な記号の連続
]
