# test_io.py
import config
from scraper import get_thread_responses

# hanabino37 さん提示のテストURL
test_url = "https://egg.5ch.io/test/read.cgi/slotk/1772997878/l50"

print(f"📡 新ドメイン {config.BASE_DOMAIN} への接続テストを開始します...")

try:
    # データを取得
    raw_data = get_thread_responses(test_url, is_url=True)
    
    if raw_data and len(raw_data) > 0:
        print(f"✅ 取得成功！レス数: {len(raw_data)}件")
        
        # 1件目のデータの構造（キー名）を確認
        first_res = raw_data[0]
        print(f"🔍 データの構造を確認します: {list(first_res.keys())}")
        
        # 中身を直接表示
        print(f"📝 1件目の全内容: {first_res}")
    else:
        print("❌ 取得されたデータが空です。")

# try を書いた場合は、以下の except ブロックが必須です
except Exception as e:
    print(f"⚠️ 実行中にエラーが発生しました: {e}")