import sqlite3
import os
from datetime import datetime
from config import DB_PATH

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
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
    
    try:
        cursor.execute("ALTER TABLE Machine_Config ADD COLUMN display_name TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE Machine_Config ADD COLUMN is_active INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE Machine_Config ADD COLUMN special_period_label TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE Machine_Config ADD COLUMN special_period_start TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE Machine_Config ADD COLUMN special_period_end TEXT")
    except sqlite3.OperationalError:
        pass
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Analyzed_Posts_Log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_name TEXT,
            post_text TEXT,
            date TEXT
        )
    ''')
    
    # 既存テーブルにカラムがない場合の互換性追加
    try:
        cursor.execute("ALTER TABLE Trend_Summary ADD COLUMN thread_ids TEXT")
    except sqlite3.OperationalError:
        pass
    
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
    
    # 既存テーブルにカラムがない場合の互換性追加 (Raw_Posts)
    try:
        cursor.execute("ALTER TABLE Raw_Posts ADD COLUMN category TEXT")
    except sqlite3.OperationalError:
        pass
        
    try:
        cursor.execute("ALTER TABLE Raw_Posts ADD COLUMN score REAL")
    except sqlite3.OperationalError:
        pass
        
    try:
        cursor.execute("ALTER TABLE Raw_Posts ADD COLUMN post_date TEXT")
    except sqlite3.OperationalError:
        pass
        
    conn.commit()
    conn.close()

def get_processed_thread_ids():
    """Trend_Summaryのthread_idsカラムから処理済みID一覧を取得。"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT thread_ids FROM Trend_Summary WHERE thread_ids IS NOT NULL")
        rows = cursor.fetchall()
        thread_ids = set()
        for row in rows:
            for tid in str(row[0]).split(','):
                if tid.strip():
                    thread_ids.add(tid.strip())
        return thread_ids
    except sqlite3.OperationalError:
        return set()
    finally:
        conn.close()

def get_all_processed_texts_from_db(machine_name):
    """指定機種のRaw_PostsとAnalyzed_Posts_Logからすでに保存済みのレス本文を取得"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT post_text FROM Raw_Posts WHERE machine_name=?
            UNION
            SELECT post_text FROM Analyzed_Posts_Log WHERE machine_name=?
        ''', (machine_name, machine_name))
        rows = cursor.fetchall()
        return set([row[0] for row in rows])
    except sqlite3.OperationalError:
        try:
            cursor.execute("SELECT post_text FROM Raw_Posts WHERE machine_name=?", (machine_name,))
            rows = cursor.fetchall()
            return set([row[0] for row in rows])
        except sqlite3.OperationalError:
            return set()
    finally:
        conn.close()

def is_thread_processed_globally(thread_id):
    """Trend_Summaryのthread_idsカラムを確認し、
    他の機種を含めてすでに取得・分析済みのスレッドIDか判定する"""
    if not thread_id:
        return False
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # thread_idsには "1234567890,1234567891" のような形式で保存されている
        # LIKE句で部分一致検索を行う (%thread_id%)
        # 厳密な判定のためにカンマ区切りの前後を考慮するパターンも考えられるが、
        # 5chのIDは10桁の一意な数値なので単純なLIKEでもほぼ安全
        cursor.execute("SELECT COUNT(*) FROM Trend_Summary WHERE thread_ids LIKE ?", (f"%{thread_id}%",))
        count = cursor.fetchone()[0]
        return count > 0
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()

def get_all_machine_names(only_active=False):
    """Machine_Config からすべての機種名を取得する
    only_active=True の場合、is_active=1 (またはNULL) の機種のみ取得
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        if only_active:
            cursor.execute("SELECT DISTINCT machine_name FROM Machine_Config WHERE is_active = 1 OR is_active IS NULL")
        else:
            cursor.execute("SELECT DISTINCT machine_name FROM Machine_Config")
        rows = cursor.fetchall()
        return [row[0] for row in rows if row[0]]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()

def update_machine_active_status(machine_name, is_active):
    """機種の解析対象ステータス(is_active)を更新する"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Machine_Config SET is_active = ? WHERE machine_name = ?", (is_active, machine_name))
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()

def save_analyzed_posts_log(machine_name, texts):
    if not texts:
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.executemany('''
        INSERT INTO Analyzed_Posts_Log (machine_name, post_text, date)
        VALUES (?, ?, ?)
    ''', [(machine_name, text, date_str) for text in texts])
    conn.commit()
    conn.close()

def save_summary(machine_name, scores_sum, excitement_idx, thread_ids_str=''):
    conn = sqlite3.connect(DB_PATH)
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
    conn.commit()
    conn.close()

def save_raw_post(machine_name, category, score, post_text, weight, reason, post_date=None):
    conn = sqlite3.connect(DB_PATH)
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
    conn.commit()
    conn.close()
