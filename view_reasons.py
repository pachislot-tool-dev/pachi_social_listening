import sqlite3

# データベースに接続
db_path = "data/pachi_social_db.sqlite"
machine_name = "スマスロ炎炎ノ消防隊2"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# スコアに大きな影響を与えた最新の10件を抽出
query = """
SELECT post_text, reason, weight, category, score
FROM Raw_Posts 
WHERE machine_name LIKE ? 
ORDER BY id DESC 
LIMIT 10;
"""

print(f"=== {machine_name} 分析理由の抜き出し ===")

try:
    cursor.execute(query, (f"%{machine_name}%",))
    rows = cursor.fetchall()
    
    if not rows:
        print("該当するデータが見つかりませんでした。機種名が正しくDBにあるか確認してください。")
    else:
        for i, row in enumerate(rows, 1):
            print(f"\n[{i}] 投稿内容:")
            # 長い投稿は100文字で省略
            content = row[0].replace('\n', ' ')
            print(f"    {content[:100]}..." if len(content) > 100 else f"    {content}")
            if row[3] is not None:
                print(f"【判定カテゴリ】: {row[3]} (スコア: {row[4]})")
            print(f"【AIの分析理由】: {row[1]}")
            print(f"【重要度スコア】: {row[2]}")
            print("-" * 50)

except sqlite3.OperationalError as e:
    print(f"データベースエラー: {e}")
finally:
    conn.close()