import json
import re
from datetime import datetime
from config import GEMINI_API_KEY
from google import genai
from google.genai import types

def analyze_with_ai(texts):
    """
    google.genai SDKを使用してGemini 2.0 Flash-Liteにプロンプトを投げる（150件バッチ用）
    """
    if not GEMINI_API_KEY:
        return []

    # APIキーを用いた新しいクライアント初期化
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = """
あなたはパチスロ専門の優秀なデータアナリストです。
以下の「分析定義書」に基づき、ユーザーの書き込みリスト（5chスレッドのレス）から5chのノイズを排除し、純粋な機種評価を抽出して、指定のJSON形式で出力してください。

【1. カテゴリ定義と優先順位】
1. スペック: 出玉性能、純増、天井、割、リール配列、技術介入要素。
2. ゲーム性: AT/CZのフロー、叩きどころ、自力感、通常時のバランス。
3. 演出グラフィック: 映像、キャラの可愛さ（IP愛含む）、液晶演出、筐体。
4. 演出法則: 出目、ボナ判別、違和感演出、確定パターン、Q&A。
5. ホール状況: 導入台数、設定状況、稼働率（※店への文句は除外）。
6. その他: 導入前の期待感、噂、オカルト、デマ、ユーザー間の雑談。

【2. スコア(val)と重み(weight)の判定基準】
・スコア (-2.0 ～ 2.0):
  - 明らかな皮肉は文脈から判断し、感情を反転させて判定すること。
  - 判定が難しい皮肉は、スコアを 0 に近い値（0.1や-0.1）に抑えること。
  - 1つのレスにポジ/ネガが混在する場合、相殺せずそれぞれのカテゴリに独立したスコアを付与すること。

・重み (1 ～ 5):
  - 5 (最高): その機種特有の固有名詞やシステム（例：魔女ポイント等）に深く言及し、数値や根拠を伴う鋭い考察。
  - 3: 具体的な体験談や、納得感のある評価。
  - 1 (最低): 根拠の薄い噂、オカルト、短文のQ&A、期待感のみの投稿。

【3. 徹底排除リスト（価値なしと判定）】
以下の投稿は「価値なし」と判定し、スコアを 0.0、重みを 0 とし集計および表示から除外すること（"is_good_post": false）：
- 日記・収支報告: 「〇万負けた」「二度と打たん」等の個人的な結果のみ。
- 極短文: 「神」「ゴミ」「クソ」等、理由のない単語。
- ホール/他人への不満: 冷房、店員の態度、隣の客への文句。
- 外部ヘイト: メーカー全体やパチンコ業界全体への攻撃、政治的発言。
- 5ch特有のノイズ: AA（アスキーアート）、コピペ連投、意味のない文字列、定型文の煽り。

【4. 代表的な意見の選定ロジック】
- 長文の扱い: 200文字を超えるような熱量の高い長文分析は、その機種の「魂の1件」として最高ウェイト（5）を付与せよ。ただし、このような超長文は全カテゴリを通じて1機種につき1件のみ選定されるよう、この回の分析の中で最も価値が高いと判断した1件のみにフラグ("is_good_post": true などの高い評価)を立てよ。
- 他の代表意見は、100〜200文字程度の「読みやすく核心を突いたもの」を優先せよ（重み3や5とし、"is_good_post": true にする）。
- 代表的な意見に選定した場合や、高評価（重み3以上）をつけた場合は、その理由を "reason" に短く記載すること。

【出力フォーマット】
以下の形式のJSONの配列（Array）として「のみ」出力してください。Markdownのコードブロック(```json ... ```)は付けないか、付けるにしても純粋なJSONとしてパース可能な形にしてください。

[
  {
    "id": "リストのインデックス番号(ID_0, ID_1...)",
    "scores": {
      "スペック": 0.0,
      "ゲーム性": 0.0,
      "演出グラフィック": 0.0,
      "演出法則": 0.0,
      "ホール状況": 0.0,
      "その他": 0.0
    },
    "weight": 1.0,  // 上記のロジックに従い 0から5のいずれか
    "is_good_post": false,
    "reason": "重み3以上の場合など、ここに評価理由を記載"
  },
  ...
]

【分析対象リスト】
"""
    for i, text in enumerate(texts):
        prompt += f"ID_{i}: {text[:300]}\n---\n" # 長すぎるテキストは切り詰め
        
    try:
        response = client.models.generate_content(
            model='models/gemma-3-27b-it',
            contents=prompt,
        )
        
        # JSON部分の抽出
        json_match = re.search(r'\[.*\]', response.text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        return []
    except Exception as e:
        # 呼び出し元でリトライ・エラーハンドリングを行うために例外をスロー
        raise e

def calculate_excitement(responses, new_res_count, elapsed_hours):
    """盛り上がり指数 = ユニークID数 * (1 + 新規レス数 / 経過時間) を算出"""
    unique_uids = len(set([r["uid"] for r in responses if r["uid"]]))
    
    if elapsed_hours <= 0:
        elapsed_hours = 1.0 # ゼロ除算回避
        
    idx = unique_uids * (1.0 + (new_res_count / elapsed_hours))
    return idx

def parse_elapsed_hours(responses):
    """レスの日時から全スレッド通しての経過時間を大まかに算出"""
    if len(responses) < 2:
        return 1.0
        
    dates = []
    date_pattern = re.compile(r'(\d{4}/\d{2}/\d{2})\([^)]+\)\s+(\d{2}:\d{2}:\d{2})')
    
    for r in responses:
        match = date_pattern.search(r.get("date_str", ""))
        if match:
            try:
                date_str = f"{match.group(1)} {match.group(2)}"
                d = datetime.strptime(date_str, "%Y/%m/%d %H:%M:%S")
                dates.append(d)
            except Exception:
                pass
                
    if len(dates) < 2:
        return 24.0
        
    diff = max(dates) - min(dates)
    hours = diff.total_seconds() / 3600.0
    return max(hours, 0.1)
