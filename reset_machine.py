import sqlite3
import os

# --- ここにリセットしたい機種名の一部を入れる ---
target_machine = 'スマスロ北斗の拳転生の章2'
# ------------------------------------------------

db_path = 'data/pachi_social_db.sqlite'
if not os.path.exists(db_path):
    print(f"エラー: {db_path} が見つかりません。")
    exit()

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# データベース内の全テーブルを取得
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [t[0] for t in cur.fetchall()]

target_like = f'%{target_machine}%'
total_to_delete = 0
tables_to_clean = []

# 1. まずは削除せずに「何件あるか（COUNT）」だけを調べる
for table in tables:
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE machine_name LIKE ?", (target_like,))
        count = cur.fetchone()[0]
        if count > 0:
            total_to_delete += count
            tables_to_clean.append(table)
    except sqlite3.OperationalError:
        # machine_name カラムがない管理用テーブルなどはスキップ
        continue

# 2. データが0件の場合はそのまま終了
if total_to_delete == 0:
    print(f"\n『{target_machine}』のデータは見つかりませんでした。")
    conn.close()
    exit()

# 3. 【ストッパー】ユーザーに最終確認を行う
print(f"\n⚠️ 警告: 『{target_machine}』に関する全 {total_to_delete} 件のデータを削除しようとしています。")
confirm = input("本当に削除してよろしいですか？ (y/n): ")

if confirm.lower() == 'y':
    # 4. 'y'が入力された場合のみ、実際に削除（DELETE）を実行
    total_deleted = 0
    print("\n削除を実行します...")
    for table in tables_to_clean:
        cur.execute(f"DELETE FROM {table} WHERE machine_name LIKE ?", (target_like,))
        deleted = cur.rowcount
        print(f"✅ {table} から {deleted} 件のデータを抹消しました。")
        total_deleted += deleted
    
    conn.commit()
    print(f"\n--- 削除完了（合計 {total_deleted} 件） ---")
    print(f"これで『{target_machine}』は完全に新台状態に戻りました。")
else:
    # 'y'以外が入力された場合はキャンセル
    print("\n🚫 削除をキャンセルしました。データは安全に保持されています。")

conn.close()