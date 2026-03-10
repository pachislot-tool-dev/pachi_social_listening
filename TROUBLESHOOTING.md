機種データが混ざった・消えた場合の対処法

1. 現象
   ダッシュボード上で、特定の機種に別の機種のデータが合算されて表示される。

登録したはずの機種名が別の名前に書き換わっている。

2. 原因の切り分け（どこを確認すべきか）
   まずは「データそのものが混ざったのか」それとも「表示の紐付け（ラベル）が間違っているだけか」を確認します。

① データベース（SQLite）の確認
確認対象ファイル：data/pachi_social_db.sqlite

以下の2つのテーブルの整合性をチェックしてください。

Analyzed_Posts_Log テーブル:

ここには「検索時の正式名称（machine_name）」でデータが保存されています。

チェックポイント: SELECT DISTINCT machine_name FROM Analyzed_Posts_Log を実行し、意図しない名前が混ざっていないか確認する。

Machine_Config テーブル:

ここには「正式名称（machine_name）」と「ダッシュボード表示名（display_name）」の対応表が保存されています。

チェックポイント: display_name が重複していたり、別の機種の machine_name に紐付いていないか確認する。

3. 復旧手順
   ステップ1：現在の設定値を書き出す
   以下のスクリプト（machine_name_reset.py）を実行し、現在の対応表の「ズレ」を特定します。

Python
import sqlite3
conn = sqlite3.connect("data/pachi_social_db.sqlite")
cur = conn.cursor()
cur.execute("SELECT machine_name, display_name FROM Machine_Config")
for row in cur.fetchall():
print(f"正式名称: {row[0]} | 表示名: {row[1]}")
conn.close()
ステップ2：表示名の修正（リセット）
ズレが判明したら、SQLの UPDATE 文で修正します。

特定の機種だけ直す場合:

SQL
UPDATE Machine_Config SET display_name = '正しい表示名' WHERE machine_name = '正式名称';
すべて初期化（表示名を正式名称と同じにする）する場合:

SQL
UPDATE Machine_Config SET display_name = machine_name; 4. 再発防止策
管理者画面での操作: 表示名を変更する際は、既存の表示名と重複しないよう注意する。

バックアップ: 大規模な分析（2000件超など）を行う前や、管理者設定を変更する前には、pachi_social_db.sqlite のコピーを取っておく。
