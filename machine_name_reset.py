import sqlite3

db_path = "data/pachi_social_db.sqlite"
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# 修正リスト (検索名: 正しい表示名)
correction_list = {
    "【スマスロ】サンダーV": "スマスロサンダーV",
    "スマスロ 甲鉄城のカバネリ 海門決戦": "スマスロ甲鉄城のカバネリ海門決戦",
    "スマスロ 甲鉄城のカバネリ": "スマスロ甲鉄城のカバネリ"
}

print("🔄 表示設定の修正を開始します...")

for machine, correct_display in correction_list.items():
    cur.execute("""
        UPDATE Machine_Config 
        SET display_name = ? 
        WHERE machine_name = ?
    """, (correct_display, machine))
    print(f"✅ {machine} -> {correct_display} に修正しました。")

conn.commit()
print("-" * 50)
print("🎊 修正がすべて完了しました！ダッシュボードを確認してください。")

conn.close()