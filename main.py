import time
import re
import argparse
from config import GEMINI_API_KEY
import config
from database import init_db, get_processed_thread_ids, get_all_processed_texts_from_db, save_summary, save_raw_post, save_analyzed_posts_log, get_all_machine_names, is_thread_processed_globally
from scraper import get_thread_list, discover_threads, get_thread_responses, clean_responses
from analyzer import analyze_with_ai, calculate_excitement, parse_elapsed_hours

def main():
    print("=== 5ch パチスロ分析ツール ===")
    
    if not GEMINI_API_KEY:
        print("警告: .envファイルにGEMINI_API_KEYが設定されていません。API解析をスキップします。")
        
    init_db()
    
    parser = argparse.ArgumentParser(description="5ch パチスロ分析ツール")
    parser.add_argument("--all", action="store_true", help="DBに登録されている全機種を自動で更新する")
    parser.add_argument("--confirm", action="store_true", help="各機種の処理前に確認プロンプトを表示する")
    args = parser.parse_args()

    if args.all:
        machine_names = get_all_machine_names(only_active=True)
        if not machine_names:
            print("有効(is_active)な登録機種がありません。")
            return
            
        print(f"全 {len(machine_names)} 機種の自動一括更新を開始します。")
        
        for i, machine_name in enumerate(machine_names):
            print(f"\n==================================================")
            print(f"[{i+1}/{len(machine_names)}] {machine_name} を更新中...")
            print(f"==================================================")
            process_single_machine(machine_name, url_input="", auto_mode=True, confirm_mode=args.confirm)
            
            if i < len(machine_names) - 1:
                print("\n5chへのアクセス遮断を防ぐため、10秒待機します...")
                time.sleep(10)
                
        print("\n全機種の自動一括更新が完了しました。")
    else:
        machine_name = input("分析したい機種名を入力してください: ")
        url_input = input("スレッドのURLを直接入力しますか？（複数ある場合はカンマ区切り。Enterでスキップ）: ").strip()
        process_single_machine(machine_name, url_input=url_input, auto_mode=False, confirm_mode=args.confirm)

def process_single_machine(machine_name, url_input="", auto_mode=False, confirm_mode=False):
    target_threads = []
    
    if url_input:
        urls = [url.strip() for url in url_input.split(',') if url.strip()]
        for url in urls:
            match = re.search(r'(\d+)/?$', url)
            numeric_id = match.group(1) if match else url
            target_threads.append({
                "id": url,
                "title": f"{machine_name} (直接指定URL: {numeric_id})",
                "is_url": True,
                "is_active": False
            })
    else:
        print(f"「{machine_name}」のスレッドを検索中...")
        threads = get_thread_list(machine_name)
        
        if not threads:
            if auto_mode:
                print(f"「{machine_name}」に関連するスレッドが見つかりませんでした。スキップします。")
                return
            url_input = input("該当スレッドは見つかりませんでした。スレッドのURLを直接入力しますか？（複数ある場合はカンマ区切り。Enterで終了）: ").strip()
            if url_input:
                urls = [url.strip() for url in url_input.split(',') if url.strip()]
                for url in urls:
                    match = re.search(r'(\d+)/?$', url)
                    numeric_id = match.group(1) if match else url
                    target_threads.append({
                        "id": url,
                        "title": f"{machine_name} (直接指定URL: {numeric_id})",
                        "is_url": True,
                        "is_active": False
                    })
            else:
                return
                
        if not target_threads and threads:
            print("\n--- 過去スレを探索中（ディスカバリー・クロール） ---")
            all_discovered_threads = discover_threads(threads)
            
            print("\n=== スレッド一覧 ===")
            processed_threads = get_processed_thread_ids() 
            
            for i, t in enumerate(all_discovered_threads):
                # Numeric ID抽出
                match = re.search(r'(\d+)/?$', t['id'])
                numeric_id = match.group(1) if match else t['id']
                
                is_done_local = numeric_id in processed_threads
                is_done_global = False if is_done_local else is_thread_processed_globally(numeric_id)
                
                if is_done_local:
                    status = "[済]"
                elif is_done_global:
                    status = "[他機種で済]"
                else:
                    status = "[未]"
                    
                archive_label = "[現行]" if t.get("is_active") else "[過去ログ]"
                
                print(f"[{i+1}] {status} {archive_label} {t['title']} (ID: {numeric_id})")
                
                # 自動モードの場合は、他機種で済みのスレッドを candidate から除外するフラグを立てておく処理は後で実施する
                t['_is_done_global'] = is_done_global
                
            if auto_mode:
                for t in all_discovered_threads:
                    if t.get('_is_done_global'):
                        print(f"[スキップ] 別機種名で取得済みのスレッドです: {t['title']}")
                    else:
                        target_threads.append(t)
            else:
                choice = input("\n分析するスレッド番号（複数選択はカンマ区切り、または 'all'）: ").strip()
                
                if choice.lower() == 'all':
                    for t in all_discovered_threads:
                        if t.get('_is_done_global'):
                            print(f"[スキップ] 別機種名で取得済みのスレッドです: {t['title']}")
                        else:
                            target_threads.append(t)
                else:
                    for part in choice.split(','):
                        part = part.strip()
                        if part.isdigit() and 1 <= int(part) <= len(all_discovered_threads):
                            t = all_discovered_threads[int(part)-1]
                            if t.get('_is_done_global'):
                                print(f"[スキップ] 別機種名で取得済みのスレッドです: {t['title']}")
                            else:
                                target_threads.append(t)
                            
            if not target_threads:
                print("有効なスレッドがありません。処理を終了します。")
                return
                
            if confirm_mode:
                confirm = input(f"\nこの機種({machine_name})のデータを取得・分析しますか？ [Y/n]: ").strip().lower()
                if confirm == 'n':
                    print(f"-> {machine_name} をスキップします。")
                    return

    if not target_threads:
        return
        
    print(f"\n選択された {len(target_threads)}件 のスレッドから全レスデータを取得します...")
    
    all_raw_responses = []
    thread_ids_to_save = []
    
    # 選択されたスレッドのみをループ（過去スレへの自動遡行はディスカバリーで完了しているため不要）
    for target_thread in target_threads:
        print(f"\n■ 取得中: {target_thread['title']}")
        
        current_id_or_url = target_thread["id"]
        is_url = target_thread.get("is_url", False)
        
        match = re.search(r'(\d+)/?$', current_id_or_url)
        numeric_id = match.group(1) if match else current_id_or_url
        thread_ids_to_save.append(numeric_id)
        
        time.sleep(2)  # 5chへの負荷軽減のためのディレイ
        
        raw_responses = get_thread_responses(current_id_or_url, is_url=is_url)
        print(f"    レス取得: {len(raw_responses)}件")
        all_raw_responses.extend(raw_responses)
        
    print(f"\n全レス取得完了: 合計 {len(all_raw_responses)}件")
    
    if not all_raw_responses:
        print("レスが1件も取得できませんでした。")
        return
        
    cleaned_responses = clean_responses(all_raw_responses)
    print(f"クレンジング完了: 有効レス {len(cleaned_responses)}件 (除外: {len(all_raw_responses) - len(cleaned_responses)}件)")
    
    if not cleaned_responses:
        print("分析対象のレスがありません。")
        return
        
    # 既読スキップ処理
    processed_texts = get_all_processed_texts_from_db(machine_name)
    target_responses = [r for r in cleaned_responses if r["message"] not in processed_texts]
    skipped_count = len(cleaned_responses) - len(target_responses)
    print(f"全 {len(cleaned_responses)}件中、既保存の {skipped_count}件 をスキップし、残り {len(target_responses)}件 を分析します")
    
    # 盛り上がり指数算出
    elapsed_hours = parse_elapsed_hours(cleaned_responses)
    excitement_idx = calculate_excitement(cleaned_responses, len(cleaned_responses), elapsed_hours)
    
    if not target_responses:
        print("全て分析済みです。データベースへのサマリー保存のみ行い終了します。")
        save_summary(machine_name, {}, excitement_idx, ",".join(thread_ids_to_save))
        return
    
    # 集計処理の初期化
    total_scores = {
        "スペック": 0, "ゲーム性": 0, "演出グラフィック": 0,
        "演出法則": 0, "ホール状況": 0, "その他": 0
    }
    category_opinions = {k: {"large_pos": 0, "mid_pos": 0, "small_pos": 0, "small_neg": 0, "mid_neg": 0, "large_neg": 0} for k in total_scores}
    
    analyzed_count = 0

    # APIの制約を考慮し、バッチ処理でGemini APIに投げる
    if GEMINI_API_KEY:
        batch_size = 50
        total_batches = (len(target_responses) + batch_size - 1) // batch_size
        print(f"\nGemini API(genai)による感情分析をバッチ処理で実行中... (対象: 全 {len(target_responses)}件 / {total_batches}バッチ)")
        
        api_limit_reached = False
        for i in range(0, len(target_responses), batch_size):
            batch = target_responses[i:i + batch_size]
            texts_to_analyze = [r["message"] for r in batch]
            current_batch_num = i // batch_size + 1
            print(f"[{current_batch_num}/{total_batches}] バッチ ({i+1}〜{min(i+batch_size, len(target_responses))}件目) を分析中...")
            
            retry_count = 0
            while retry_count < 3:
                try:
                    batch_result = analyze_with_ai(texts_to_analyze)
                    for res in batch_result:
                        post_date = None
                        idx_str = str(res.get("id", "")).replace("ID_", "")
                        if idx_str.isdigit() and int(idx_str) < len(texts_to_analyze):
                            post_text = texts_to_analyze[int(idx_str)]
                            res["original_text"] = post_text 
                            post_date = batch[int(idx_str)].get("post_date")
                        
                        weight = res.get("weight", 1.0)
                        scores = res.get("scores", {})
                        is_good = res.get("is_good_post")
                        original_text = res.get("original_text")
                        reason = res.get("reason", "")
                        
                        for k, v in scores.items():
                            if v is not None and k in total_scores:
                                try:
                                    val = float(v)
                                except ValueError:
                                    val = 0.0

                                if val > 0:
                                    total_scores[k] += val * float(weight)
                                    if val >= 1.5: category_opinions[k]["large_pos"] += 1
                                    elif val >= 1.0: category_opinions[k]["mid_pos"] += 1
                                    else: category_opinions[k]["small_pos"] += 1
                                elif val < 0:
                                    total_scores[k] += val * float(weight)
                                    if val <= -1.5: category_opinions[k]["large_neg"] += 1
                                    elif val <= -1.0: category_opinions[k]["mid_neg"] += 1
                                    else: category_opinions[k]["small_neg"] += 1
                                    
                                if val != 0.0 and original_text:
                                    save_raw_post(machine_name, k, val, original_text, weight, reason, post_date=post_date)

                    # バッチ内の全レスを処理済みとしてDBに記録
                    save_analyzed_posts_log(machine_name, texts_to_analyze)
                    analyzed_count += len(texts_to_analyze)

                    # バッチごとに待機時間を設けてAPIの制限を回避する
                    if current_batch_num < total_batches:
                        print("API制限回避のため、次のバッチまで12秒待機します...")
                        time.sleep(12)
                        
                    break # 成功時ループ脱出
                except Exception as e:
                    error_msg = str(e).lower()
                    if "429" in error_msg or "quota" in error_msg or "403" in error_msg or "exhausted" in error_msg:
                        if retry_count < 2:
                            print(f"API制限エラー (残リトライ: {2-retry_count}回) - 20秒待機後にリトライします: {e}")
                            time.sleep(20)
                            retry_count += 1
                        else:
                            print(f"\n⚠️ API制限に達したため、以降のバッチ処理を中断します。")
                            print(f"ここまでの {analyzed_count}件 の分析結果は既に保存済みです。安全に終了します。")
                            api_limit_reached = True
                            break
                    else:
                        print(f"予期せぬAPIエラーでスキップ: {e}")
                        break
                        
            if api_limit_reached:
                break
                
            time.sleep(2)  # API制限回避（基本ディレイ）

    # 集計と保存はバッチ実行時に完了しています

    print("\n--- 分析結果 ---")
    print(f"盛り上がり指数: {excitement_idx:.2f}")
    
    def distribute_chars(total_chars, counts):
        if sum(counts) == 0:
            return [0] * len(counts)
        exact = [total_chars * c / sum(counts) for c in counts]
        allocated = [int(f) for f in exact]
        remainders = [(exact[i] - allocated[i], i) for i in range(len(counts))]
        remainders.sort(reverse=True, key=lambda x: x[0])
        diff = total_chars - sum(allocated)
        for i in range(diff):
            allocated[remainders[i][1]] += 1
        return allocated

    for k in total_scores.keys():
        opinions = category_opinions[k]
        pos_counts = [opinions["large_pos"], opinions["mid_pos"], opinions["small_pos"]]
        neg_counts = [opinions["small_neg"], opinions["mid_neg"], opinions["large_neg"]]
        
        pos_total = sum(pos_counts)
        neg_total = sum(neg_counts)
        valid_total = pos_total + neg_total
        
        print(f"---")
        print(f"[{k}] 累積スコア: {total_scores[k]:.1f}")
        print(f"有効意見数：{valid_total}件")
        
        if valid_total > 0:
            pos_pct = pos_total / valid_total * 100
            neg_pct = neg_total / valid_total * 100
            
            bar_width = 24
            pos_chars = int(round(bar_width * (pos_total / valid_total)))
            neg_chars = bar_width - pos_chars
            
            pos_dist = distribute_chars(pos_chars, pos_counts)
            neg_dist = distribute_chars(neg_chars, neg_counts)
            
            pos_bar = ("#" * pos_dist[0]) + ("=" * pos_dist[1]) + ("+" * pos_dist[2])
            neg_bar = ("-" * neg_dist[0]) + ("=" * neg_dist[1]) + ("#" * neg_dist[2])
            
            print(f"[ {pos_bar} | {neg_bar} ]")
            print(f"ポジ {int(pos_pct)}% : ネガ {int(neg_pct)}%")
        else:
            print("[ 意見なし ]")
    print("---")
            
    save_summary(machine_name, total_scores, excitement_idx, ",".join(thread_ids_to_save))
    print("\nデータベースへの保存が完了しました。")

if __name__ == "__main__":
    main()