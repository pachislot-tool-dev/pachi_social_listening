import streamlit as st
import sqlite3
import pandas as pd
import altair as alt
import os
import sys
import re
from datetime import datetime, timedelta

# --- 1. ページ設定を一番最初に記述（Streamlitの厳格なルール） ---
st.set_page_config(page_title="パチスロ分析結果ビューア", layout="wide")

# --- 2. ハイブリッド設定（本番サーバー・ローカル環境の両対応） ---
# GitHubに config.py が無くても絶対にエラーで止まらないようにする「セーフティネット」です
API_KEY = None

# ① まずStreamlit Cloudの「Secrets」を見に行く
if "GEMINI_API_KEY" in st.secrets:
    API_KEY = st.secrets["GEMINI_API_KEY"]

# ② ローカル環境（config.py）の読み込みを試みる
try:
    import config
    DB_PATH = config.DB_PATH
    BASE_DOMAIN = config.BASE_DOMAIN
    if not API_KEY and hasattr(config, 'GEMINI_API_KEY'):
        API_KEY = config.GEMINI_API_KEY
except ImportError:
    # サーバー上で config.py が無い場合のデフォルト値
    DB_PATH = "data/pachi_social_db.sqlite"
    BASE_DOMAIN = "5ch.net"
    if not API_KEY:
        API_KEY = os.getenv("GEMINI_API_KEY")

# プロジェクトディレクトリをパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# --- 3. データベースの初期化 ---
try:
    from database import init_db
    init_db()
except Exception as e:
    # database.py 側でエラーが起きてもアプリ全体を落とさないための保険
    pass

# --- 4. スタイル設定 ---
st.markdown("""
    <style>
    /* 全体の余白（パディング）をスマホ向けに最小化 */
    .block-container {
        padding-top: 3.5rem !important;
        padding-bottom: 0rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
    }
    /* メインタイトル（書き込み分析結果）のサイズ調整 */
    h1 {
        font-size: 1.6rem !important;
        white-space: nowrap !important;
    }
    /* 機種名（Header）のサイズ調整 */
    h2 {
        font-size: 1.3rem !important;
        line-height: 1.2 !important;
    }
    /* タブの文字サイズを少し小さくして1画面に収まりやすくする */
    button[data-baseweb="tab"] > div > p {
        font-size: 0.9rem !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 5. データ読み込み関数 ---
@st.cache_data(ttl=300) # 5分間キャッシュして動作を軽くする最適化
def load_machine_names_by_year():
    try:
        conn = sqlite3.connect(DB_PATH)
        query = """
        SELECT DISTINCT r.machine_name, c.year, c.display_name 
        FROM Raw_Posts r
        LEFT JOIN Machine_Config c ON r.machine_name = c.machine_name
        ORDER BY c.year DESC, r.machine_name ASC
        """
        df = pd.read_sql(query, conn)
        conn.close()
        
        df['year'] = df['year'].fillna("未設定")
        
        groups_by_year = {}
        group_to_machines = {}
        for _, row in df.iterrows():
            y = row['year']
            m = row['machine_name']
            d = row['display_name'] if 'display_name' in row else None
            
            eff_name = d if pd.notna(d) and str(d).strip() != "" else m
            
            if pd.notna(m):
                if y not in groups_by_year:
                    groups_by_year[y] = []
                if eff_name not in groups_by_year[y]:
                    groups_by_year[y].append(eff_name)
                    
                if eff_name not in group_to_machines:
                    group_to_machines[eff_name] = []
                group_to_machines[eff_name].append(m)
                
        return groups_by_year, group_to_machines
    except Exception as e:
        return {}, {}

groups_by_year, group_to_machines = load_machine_names_by_year()

if not groups_by_year:
    st.warning("データが見つかりません。先にデータベースへデータが保存されているか確認してください。")
    st.stop()

# --- 6. サイドバー ---
st.sidebar.header("設定")
years = list(groups_by_year.keys())
years = sorted(years, key=lambda x: (str(x) != "未設定", x), reverse=True)

selected_year = st.sidebar.selectbox("年を選択", years)
groups_in_year = groups_by_year[selected_year]
selected_group = st.sidebar.selectbox("分析する機種名を選択", groups_in_year)
target_machines = group_to_machines[selected_group]
rep_machine = target_machines[0]

st.sidebar.markdown("---")
st.sidebar.header("管理者設定")
admin_password = st.sidebar.text_input("パスワード", type="password")

current_year, current_release_date, special_label, special_start, special_end, current_display_name, is_active_flag = "", "", "", "", "", "", True

try:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT year, release_date, special_period_label, special_period_start, special_period_end, display_name, is_active FROM Machine_Config WHERE machine_name = ?", (rep_machine,))
    row = c.fetchone()
    conn.close()
    if row:
        current_year = str(row[0]) if row[0] is not None else ""
        current_release_date = row[1] if row[1] else ""
        special_label = row[2] if row[2] else ""
        special_start = row[3] if row[3] else ""
        special_end = row[4] if row[4] else ""
        current_display_name = row[5] if row[5] else ""
        is_active_flag = bool(row[6]) if len(row) > 6 and row[6] is not None else True
except Exception:
    pass

if admin_password == "admin": 
    st.sidebar.subheader("機種設定")
    display_name_input = st.sidebar.text_input("表示用名称（正式名称）", value=current_display_name)
    year_input = st.sidebar.text_input("年 (例: 2024)", value=current_year)
    release_date_input = st.sidebar.text_input("導入日 (例: 2024/05/20)", value=current_release_date)
    is_active_input = st.sidebar.checkbox("自動取得対象にするか (is_active)", value=is_active_flag)
    
    st.sidebar.subheader("注目期間設定")
    sp_label_input = st.sidebar.text_input("期間ラベル (例: 増産後)", value=special_label)
    sp_start_input = st.sidebar.text_input("開始日 (例: 2024/06/01)", value=special_start)
    sp_end_input = st.sidebar.text_input("終了日 (例: 2024/06/07)", value=special_end)
    
    if st.sidebar.button("設定を保存"):
        if year_input.isdigit() or year_input == "":
            y_val = int(year_input) if year_input else None
            try:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                for m in target_machines:
                    c.execute("""
                        INSERT OR REPLACE INTO Machine_Config 
                        (machine_name, release_date, year, special_period_label, special_period_start, special_period_end, display_name, is_active) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (m, release_date_input, y_val, sp_label_input, sp_start_input, sp_end_input, display_name_input, 1 if is_active_input else 0))
                conn.commit()
                conn.close()
                st.sidebar.success("設定を保存しました。画面をリロードしてください。")
                load_machine_names_by_year.clear() # 保存時にキャッシュをクリア
            except Exception as e:
                st.sidebar.error(f"保存に失敗しました: {e}")
        else:
            st.sidebar.error("年は数値で入力してください。")

# --- 7. メインコンテンツ ---
st.title("書き込み分析結果")

def load_data(machine_names):
    if not machine_names:
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    placeholders = ','.join(['?'] * len(machine_names))
    query = f"SELECT * FROM Raw_Posts WHERE machine_name IN ({placeholders})"
    df = pd.read_sql(query, conn, params=tuple(machine_names))
    conn.close()
    
    if 'post_text' in df.columns:
        df = df.rename(columns={'post_text': 'message'})
        
    df = df.drop_duplicates(subset=['message', 'post_date'], keep='first')
    return df

df_posts = load_data(target_machines)

if df_posts.empty:
    st.warning("この機種のデータはまだありません。")
    st.stop()

df_posts['post_date_dt'] = pd.to_datetime(df_posts['post_date'], errors='coerce')
df_posts['date_only'] = df_posts['post_date_dt'].dt.strftime('%Y-%m-%d')

tab1, tab2, tab3 = st.tabs(["分析まとめ", "時系列トレンド", "期間別比較"])

with tab1:
    CATEGORIES = ["スペック", "ゲーム性", "演出グラフィック", "演出法則", "ホール状況", "その他"]
    st.header(selected_group)
    st.subheader("詳細データ")
    
    chart_data = []
    st.markdown("### 🏷️ カテゴリ別詳細")
    
    df_for_primary = df_posts.copy()
    df_for_primary['abs_score'] = df_for_primary['score'].abs()
    df_for_primary['weight_num'] = df_for_primary['weight'].fillna(1.0).astype(float)
    
    primary_cats = df_for_primary.sort_values(['weight_num', 'abs_score'], ascending=[False, False]) \
        .groupby('message', as_index=False).first()
    primary_category_map = dict(zip(primary_cats['message'], primary_cats['category']))
    
    for category in CATEGORIES:
        cat_df_all = df_posts[df_posts['category'] == category].copy()
        
        total_score = 0.0
        opinions = {"large_pos": 0, "mid_pos": 0, "small_pos": 0, "small_neg": 0, "mid_neg": 0, "large_neg": 0}
        
        for _, row in cat_df_all.iterrows():
            val = float(row['score'])
            weight = float(row['weight']) if pd.notna(row['weight']) else 1.0
            
            if val > 0:
                total_score += val * weight
                if val >= 1.5: opinions["large_pos"] += 1
                elif val >= 1.0: opinions["mid_pos"] += 1
                else: opinions["small_pos"] += 1
            elif val < 0:
                total_score += val * weight
                if val <= -1.5: opinions["large_neg"] += 1
                elif val <= -1.0: opinions["mid_neg"] += 1
                else: opinions["small_neg"] += 1
                    
        pos_counts = [opinions["large_pos"], opinions["mid_pos"], opinions["small_pos"]]
        neg_counts = [opinions["small_neg"], opinions["mid_neg"], opinions["large_neg"]]
        
        pos_total = sum(pos_counts)
        neg_total = sum(neg_counts)
        valid_total = pos_total + neg_total
        
        with st.container():
            st.markdown(f'''
            <div style="display: flex; align-items: center; margin-bottom: 15px; flex-wrap: wrap; gap: 10px;">
                <h4 style="margin: 0; font-size: 1.4rem;">📌 {category}</h4>
                <span style="background-color: #ffd43b; color: #d9480f; font-weight: bold; padding: 4px 12px; border-radius: 12px; font-size: 1.1rem; border: 1px solid #fab005;">
                    累積スコア: {total_score:.1f}
                </span>
            </div>
            ''', unsafe_allow_html=True)
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.metric(label="有効意見数", value=f"{valid_total}件")
                
                if valid_total > 0:
                    pos_pct = pos_total / valid_total * 100
                    neg_pct = neg_total / valid_total * 100
                    
                    chart_data.append({
                        "カテゴリ": category,
                        "ポジティブ (%)": pos_pct,
                        "ネガティブ (%)": neg_pct
                    })
                else:
                    st.markdown("**意見なし**")
                    chart_data.append({
                        "カテゴリ": category,
                        "ポジティブ (%)": 0.0,
                        "ネガティブ (%)": 0.0
                    })
    
            with col2:
                st.markdown("##### 感情バランス")
                if valid_total > 0:
                    st.markdown(f'''
                    <div style="margin-bottom: 15px;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 5px; font-weight: bold; font-size: 1.1rem;">
                            <span style="color: #4dabf7;">ポジ {int(pos_pct)}%</span>
                            <span style="color: #ff6b6b;">ネガ {int(neg_pct)}%</span>
                        </div>
                        <div style="width: 100%; height: 24px; background-color: #f1f3f5; border-radius: 12px; overflow: hidden; display: flex; border: 1px solid #dee2e6;">
                            <div style="width: {pos_pct}%; background-color: #4dabf7; height: 100%;"></div>
                            <div style="width: {neg_pct}%; background-color: #ff6b6b; height: 100%;"></div>
                        </div>
                    </div>
                    ''', unsafe_allow_html=True)
                    
                    is_primary = cat_df_all['message'].map(primary_category_map) == category
                    cat_df_pickup = cat_df_all[is_primary].copy()
                    
                    cat_df_pickup['weight_num'] = cat_df_pickup['weight'].fillna(1.0).astype(float)
                    pos_posts = cat_df_pickup[cat_df_pickup['score'] > 0].sort_values(by="weight_num", ascending=False).head(2)
                    neg_posts = cat_df_pickup[cat_df_pickup['score'] < 0].sort_values(by="weight_num", ascending=False).head(2)
                    
                    if not pos_posts.empty or not neg_posts.empty:
                        st.markdown("##### 代表的な意見")
                        if not pos_posts.empty:
                            st.markdown("**👍 ポジティブな意見**")
                            for _, p_row in pos_posts.iterrows():
                                reason_str = f"（理由: {p_row['reason']}）" if pd.notna(p_row['reason']) and p_row['reason'] else ""
                                date_str = f" [{p_row['post_date']}]" if 'post_date' in p_row and pd.notna(p_row['post_date']) and p_row['post_date'] else ""
                                
                                # config.BASE_DOMAIN を BASE_DOMAIN に変更
                                text_disp = str(p_row['message']).replace("5ch.net", BASE_DOMAIN)
                                text_disp = re.sub(r'(https?://[^\s()]+)', r'[\1](\1)', text_disp)
                                reason_disp = reason_str.replace("5ch.net", BASE_DOMAIN)
                                reason_disp = re.sub(r'(https?://[^\s()]+)', r'[\1](\1)', reason_disp)
                                
                                st.success(f"(スコア: {p_row['score']}){date_str} - {text_disp} {reason_disp}")
                        
                        if not neg_posts.empty:
                            st.markdown("**👎 ネガティブな意見**")
                            for _, p_row in neg_posts.iterrows():
                                reason_str = f"（理由: {p_row['reason']}）" if pd.notna(p_row['reason']) and p_row['reason'] else ""
                                date_str = f" [{p_row['post_date']}]" if 'post_date' in p_row and pd.notna(p_row['post_date']) and p_row['post_date'] else ""
                                
                                # config.BASE_DOMAIN を BASE_DOMAIN に変更
                                text_disp = str(p_row['message']).replace("5ch.net", BASE_DOMAIN)
                                text_disp = re.sub(r'(https?://[^\s()]+)', r'[\1](\1)', text_disp)
                                reason_disp = reason_str.replace("5ch.net", BASE_DOMAIN)
                                reason_disp = re.sub(r'(https?://[^\s()]+)', r'[\1](\1)', reason_disp)
                                
                                st.error(f"(スコア: {p_row['score']}){date_str} - {text_disp} {reason_disp}")
                else:
                    st.markdown("<div style='color: #868e96; font-style: italic; margin-bottom: 15px;'>意見なし</div>", unsafe_allow_html=True)
                    
            st.divider()
    
    st.subheader("📊 全体ポジ・ネガ比率比較")
    
    if chart_data:
        df_chart = pd.DataFrame(chart_data)
        df_melted = df_chart.melt(id_vars=["カテゴリ"], var_name="感情", value_name="割合(%)")
        
        color_scale = alt.Scale(
            domain=["ポジティブ (%)", "ネガティブ (%)"],
            range=["#4dabf7", "#ff6b6b"]
        )
        
        chart = alt.Chart(df_melted).mark_bar().encode(
            y=alt.Y("カテゴリ:N", axis=alt.Axis(labelLimit=300, labelFontSize=14, titleFontSize=15), title="", sort=None),
            x=alt.X("割合(%):Q", title="割合 (%)", scale=alt.Scale(domain=[0, 100])),
            color=alt.Color("感情:N", scale=color_scale, legend=alt.Legend(title="", orient="top", labelFontSize=14)),
            tooltip=["カテゴリ", "感情", alt.Tooltip("割合(%):Q", format=".1f")]
        ).properties(
            height=350
        )
        
        st.altair_chart(chart, width="stretch")

with tab2:
    st.header("📈 時系列トレンド")
    st.markdown("導入日以降のポジティブ率の推移（日別）")
    
    if current_release_date:
        release_dt = pd.to_datetime(current_release_date.replace('/', '-'), errors='coerce')
    else:
        release_dt = None
        
    df_trend = df_posts.dropna(subset=['date_only'])
    
    if release_dt is not None:
        df_trend = df_trend[df_trend['post_date_dt'] >= release_dt]
        st.info(f"※導入日（{current_release_date}）以降のデータを表示しています。")
    else:
        st.info("※導入日が設定されていないため、すべての期間のデータを表示しています。")
        
    if not df_trend.empty:
        trend_data = []
        for date_str, group in df_trend.groupby('date_only'):
            valid_posts = group[group['score'] != 0]
            pos_count = len(valid_posts[valid_posts['score'] > 0])
            total_valid = len(valid_posts)
            
            if total_valid > 0:
                pos_rate = pos_count / total_valid * 100
                trend_data.append({
                    "date": date_str,
                    "ポジティブ率": pos_rate,
                    "有効意見数": total_valid
                })
                
        if trend_data:
            df_trend_agg = pd.DataFrame(trend_data).sort_values('date')
            
            line_chart = alt.Chart(df_trend_agg).mark_line(point=True).encode(
                x=alt.X('date:T', title='投稿日', axis=alt.Axis(format='%m/%d', labelAngle=-45)),
                y=alt.Y('ポジティブ率:Q', title='ポジティブ率 (%)', scale=alt.Scale(domain=[0, 100])),
                tooltip=['date:T', alt.Tooltip('ポジティブ率:Q', format='.1f'), '有効意見数:Q']
            ).properties(
                height=400
            )
            
            st.altair_chart(line_chart, width="stretch")
        else:
            st.warning("有効なスコアを持つデータがありません。")
    else:
        st.warning("指定された期間のデータがありません。")

with tab3:
    st.header("📅 期間別比較")
    
    if current_release_date:
        release_dt = pd.to_datetime(current_release_date.replace('/', '-'), errors='coerce')
        if pd.isna(release_dt):
            st.error("導入日の形式が不正です。設定からYYYY/MM/DD形式で登録してください。")
        else:
            df_comp = df_posts.dropna(subset=['post_date_dt']).copy()
            df_comp['days_since_release'] = (df_comp['post_date_dt'] - release_dt).dt.days
            
            weekly_stats = []
            for week in range(4):
                start_day = week * 7
                end_day = start_day + 6
                
                week_df = df_comp[(df_comp['days_since_release'] >= start_day) & (df_comp['days_since_release'] <= end_day)]
                valid_posts = week_df[week_df['score'] != 0]
                pos_count = len(valid_posts[valid_posts['score'] > 0])
                total_valid = len(valid_posts)
                
                if total_valid > 0:
                    pos_rate = pos_count / total_valid * 100
                    neg_rate = 100 - pos_rate
                else:
                    pos_rate = 0
                    neg_rate = 0
                    
                weekly_stats.append({
                    "label": f"第{week+1}週 ({start_day}〜{end_day}日目)",
                    "pos_rate": pos_rate,
                    "neg_rate": neg_rate,
                    "total_valid": total_valid
                })
                
            special_stat = None
            if special_label and special_start and special_end:
                sp_start_dt = pd.to_datetime(special_start.replace('/', '-'), errors='coerce')
                sp_end_dt = pd.to_datetime(special_end.replace('/', '-'), errors='coerce')
                sp_end_dt_end_of_day = sp_end_dt + timedelta(days=1) - timedelta(seconds=1) if pd.notna(sp_end_dt) else pd.NaT
                
                if pd.notna(sp_start_dt) and pd.notna(sp_end_dt_end_of_day):
                    sp_df = df_comp[(df_comp['post_date_dt'] >= sp_start_dt) & (df_comp['post_date_dt'] <= sp_end_dt_end_of_day)]
                    valid_posts = sp_df[sp_df['score'] != 0]
                    pos_count = len(valid_posts[valid_posts['score'] > 0])
                    total_valid = len(valid_posts)
                    
                    if total_valid > 0:
                        pos_rate = pos_count / total_valid * 100
                        neg_rate = 100 - pos_rate
                    else:
                        pos_rate = 0
                        neg_rate = 0
                    
                    special_stat = {
                        "label": f"★{special_label}",
                        "pos_rate": pos_rate,
                        "neg_rate": neg_rate,
                        "total_valid": total_valid
                    }

            cols = st.columns(len(weekly_stats) + (1 if special_stat else 0))
            
            all_stats = weekly_stats.copy()
            if special_stat:
                all_stats.append(special_stat)
                
            for i, stat in enumerate(all_stats):
                with cols[i]:
                    st.markdown(f"**{stat['label']}**")
                    st.markdown(f"<small>意見数: {stat['total_valid']}件</small>", unsafe_allow_html=True)
                    
                    if stat['total_valid'] > 0:
                        st.markdown(f'''
                        <div style="margin-top: 5px;">
                            <div style="display: flex; justify-content: space-between; font-size: 0.8rem; font-weight: bold;">
                                <span style="color: #4dabf7;">{int(stat['pos_rate'])}%</span>
                                <span style="color: #ff6b6b;">{int(stat['neg_rate'])}%</span>
                            </div>
                            <div style="width: 100%; height: 16px; background-color: #f1f3f5; border-radius: 8px; overflow: hidden; display: flex;">
                                <div style="width: {stat['pos_rate']}%; background-color: #4dabf7;"></div>
                                <div style="width: {neg_rate}%; background-color: #ff6b6b;"></div>
                            </div>
                        </div>
                        ''', unsafe_allow_html=True)
                    else:
                        st.markdown("<div style='color: #868e96; font-style: italic; font-size: 0.9rem;'>データなし</div>", unsafe_allow_html=True)
                        
    else:
        st.warning("導入日（release_date）が設定されていません。管理者設定から導入日を設定してください。")