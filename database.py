import sqlite3
import os
from datetime import datetime

# --- ハイブリッド設定（本番・ローカル両対応） ---
# サーバー上に config.py がない場合でも動作するようにデフォルトパスを指定
try:
    import config
    DB_PATH = config.DB_PATH
except ImportError:
    DB_PATH = "data/pachi_social_db.sqlite"

def init_db():
    """データベースとテーブルの初期化。自動マイグレーションを含む。"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    # with句を使うことで、エラーが起きても確実に接続を閉じる（最適化）
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # 1. Trend_Summary テーブル作成
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Trend_Summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                machine_name TEXT,
                spec_score REAL,
                gameplay_score REAL,
                graphic_score REAL,
                rules_score REAL,
                hall_score REAL,
                other_score REAL,
                excitement_index REAL,
                thread_ids TEXT
            )
        ''')
        
        # 2. Machine_Config テーブル作成
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Machine_Config (
                machine_name TEXT PRIMARY KEY,
                release_date TEXT,
                year INTEGER,
                special_period_label TEXT,
                special_period_start TEXT,
                special_period_end TEXT,
                display_name TEXT
            )
        ''')
        
        # 3. Analyzed_Posts_Log テーブル作成
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Analyzed_Posts_Log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_name TEXT,
                post_text TEXT,
                date TEXT
            )
        ''')
        
        # 4. Raw_Posts テーブル作成
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Raw_Posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_name TEXT,
                category TEXT,
                score REAL,
                post_text TEXT,
                weight REAL,
                reason TEXT,
                date TEXT,
                post_date TEXT
            )
        ''')

        # 5. カラム追加のマイグレーション処理（最適化：ループでスッキリと）
        alter_queries = [
            "ALTER TABLE Machine_Config ADD COLUMN display_name TEXT",
            "ALTER TABLE Machine_Config ADD COLUMN is_active INTEGER DEFAULT 1",
            "ALTER TABLE Machine_Config ADD COLUMN special_period_label TEXT",
            "ALTER TABLE Machine_Config ADD COLUMN special_period_start TEXT",
            "ALTER TABLE Machine_Config ADD COLUMN special_period_end TEXT",
            "ALTER TABLE Trend_Summary ADD COLUMN thread_ids TEXT",
            "ALTER TABLE Raw_Posts ADD COLUMN category TEXT",
            "ALTER TABLE Raw_Posts ADD COLUMN score REAL",
            "ALTER TABLE Raw_Posts ADD COLUMN post_date TEXT"
        ]
        
        for query in alter_queries:
            try:
                cursor.execute(query)
            except sqlite3.OperationalError:
                # 既にカラムが存在する場合はエラーになるので無視する
                pass

def get_processed_thread_ids():
    """Trend_Summaryのthread_idsカラムから処理済みID一覧を取得。"""
    thread_ids = set()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT thread_ids FROM Trend_Summary WHERE thread_ids IS NOT NULL")
            for row in cursor.fetchall():
                for tid in str(row[0]).split(','):
                    if tid.strip():
                        thread_ids.add(tid.strip())
    except sqlite3.OperationalError:
        pass
    return thread_ids

def get_all_processed_texts_from_db(machine_name):
    """指定機種のRaw_PostsとAnalyzed_Posts_Logからすでに保存済みのレス本文を取得"""
    texts = set()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT post_text FROM Raw_Posts WHERE machine_name=?
                UNION
                SELECT post_text FROM Analyzed_Posts_Log WHERE machine_name=?
            ''', (machine_name, machine_name))
            texts = set([row[0] for row in cursor.fetchall()])
    except sqlite3.OperationalError:
        # Analyzed_Posts_Logが無い場合などのフォールバック
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT post_text FROM Raw_Posts WHERE machine_name=?", (machine_name,))
                texts = set([row[0] for row in cursor.fetchall()])
        except sqlite3.OperationalError:
            pass
    return texts

def is_thread_processed_globally(thread_id):
    """Trend_Summaryのthread_idsカラムを確認し、すでに取得・分析済みのスレッドIDか判定する"""
    if not thread_id:
        return False
        
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM Trend_Summary WHERE thread_ids LIKE ?", (f"%{thread_id}%",))
            count = cursor.fetchone()[0]
            return count > 0
    except sqlite3.OperationalError:
        return False

def get_all_machine_names(only_active=False):
    """Machine_Config からすべての機種名を取得する"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            if only_active:
                cursor.execute("SELECT DISTINCT machine_name FROM Machine_Config WHERE is_active = 1 OR is_active IS NULL")
            else:
                cursor.execute("SELECT DISTINCT machine_name FROM Machine_Config")
            return [row[0] for row in cursor.fetchall() if row[0]]
    except sqlite3.OperationalError:
        return []

def update_machine_active_status(machine_name, is_active):
    """機種の解析対象ステータス(is_active)を更新する"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE Machine_Config SET is_active = ? WHERE machine_name = ?", (is_active, machine_name))
    except sqlite3.OperationalError:
        pass

def save_analyzed_posts_log(machine_name, texts):
    """取得した本文をログとして保存"""
    if not texts:
        return
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.executemany('''
            INSERT INTO Analyzed_Posts_Log (machine_name, post_text, date)
            VALUES (?, ?, ?)
        ''', [(machine_name, text, date_str) for text in texts])

def save_summary(machine_name, scores_sum, excitement_idx, thread_ids_str=''):
    """分析結果のサマリーを保存"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO Trend_Summary 
            (date, machine_name, spec_score, gameplay_score, graphic_score, rules_score, hall_score, other_score, excitement_index, thread_ids)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            machine_name,
            scores_sum.get("スペック", 0),
            scores_sum.get("ゲーム性", 0),
            scores_sum.get("演出グラフィック", 0),
            scores_sum.get("演出法則", 0),
            scores_sum.get("ホール状況", 0),
            scores_sum.get("その他", 0),
            excitement_idx,
            thread_ids_str
        ))

def save_raw_post(machine_name, category, score, post_text, weight, reason, post_date=None):
    """個別の書き込み分析結果を保存"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO Raw_Posts (machine_name, category, score, post_text, weight, reason, date, post_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            machine_name,
            category,
            score,
            post_text,
            weight,
            reason,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            post_date
        ))