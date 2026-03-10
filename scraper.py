import requests
from bs4 import BeautifulSoup
import re
import time
from config import SUBJECT_URL, USER_AGENT, NOISE_PATTERNS
import config
import urllib.parse

def get_thread_list(keyword):
    """機種名からsubject.txtを検索して関連スレッド一覧を取得"""
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(SUBJECT_URL, headers=headers)
        response.raise_for_status()
    except Exception as e:
        print(f"subject.txtの取得に失敗しました: {e}")
        return []

    # 5chの文字コード（通常はShift_JIS。たまに判定ミスるので手動指定が吉）
    response.encoding = 'shift_jis'
    
    threads = []
    lines = response.text.split('\n')
    
    # 全角半角・大文字小文字の違いを吸収するため正規化（簡易版）
    import unicodedata
    normalized_kw = unicodedata.normalize('NFKC', keyword).lower()
    
    for line in lines:
        if line.strip():
            # フォーマット: xxxxxxxxxx.dat<>スレッドタイトル (レス数)
            match = re.match(r'^(\d+)\.dat<>(.*) \((\d+)\)$', line)
            if match:
                dat_id = match.group(1)
                title = match.group(2)
                res_count = match.group(3)
                
                normalized_title = unicodedata.normalize('NFKC', title).lower()
                
                if normalized_kw in normalized_title:
                    threads.append({"id": dat_id, "title": title})
    return threads

def extract_previous_thread_urls(msg):
    """レス本文から、slotk板に含まれるすべてのスレッドURLを抽出する"""
    url_pattern = re.compile(rf'https?://egg\.{re.escape(config.BASE_DOMAIN)}/test/read\.cgi/slotk/(\d+)')
    urls = []
    seen = set()
    
    # 本文全体からURLを検索
    matches = url_pattern.finditer(msg)
    for match in matches:
        numeric_id = match.group(1)
        if numeric_id not in seen:
            seen.add(numeric_id)
            url = f"https://egg.{config.BASE_DOMAIN}/test/read.cgi/slotk/{numeric_id}/"
            urls.append(url)
            print(f"      [抽出ログ] 関連URLを発見: {url}")
            
    if not urls:
        print("      [抽出ログ] 関連URLは見つかりませんでした。")
        
    return urls

def get_thread_first_post(thread_id, is_url=False):
    """ディスカバリー用：1〜3レス目を取得し、タイトルと前スレURLを返す"""
    if is_url:
        # URL指定の時は最大で末尾がどうなっているか不確定だが、必要なら/1-3等に置換できる
        # しかし既に末尾があるかもしれないのでそのままアクセス
        url = thread_id
    else:
        url = f"https://egg.{config.BASE_DOMAIN}/test/read.cgi/slotk/{thread_id}/1-3"
        
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except Exception as e:
        return "", "", None
        
    # エンコーディングの堅牢化 (cp932優先)
    try:
        html_text = response.content.decode('cp932', errors='replace')
    except Exception:
        html_text = response.content.decode('utf-8', errors='replace')
        
    try:
        soup = BeautifulSoup(html_text, "lxml")
    except Exception:
        soup = BeautifulSoup(html_text, "html.parser")
        
    title_elem = soup.find("title")
    title = title_elem.text.strip() if title_elem else ""
    title = re.sub(r'\s*-\s*5ちゃんねる掲示板.*$', '', title)
    title = re.sub(r'\s*\[無断転載禁止\].*$', '', title)
    title = re.sub(rf'\s*©(2ch\.net|5ch\.net|{re.escape(config.BASE_DOMAIN)}).*$', '', title)
    title = title.strip()
        
    posts = soup.find_all("div", class_="post")
    if not posts:
        return title, "", None
        
    combined_msg = ""
    for post in posts[:3]:
        content_elem = post.find("div", class_="post-content") or post.find("div", class_="message")
        if content_elem:
            combined_msg += content_elem.text.strip() + "\n---\n"
            
    prev_thread_urls = extract_previous_thread_urls(combined_msg)
        
    return title, combined_msg, prev_thread_urls

def discover_threads(initial_threads):
    """ディスカバリーフェーズ：過去スレ・関連スレを辿る（キュー方式）"""
    queue = []
    # 初期の検索ヒットスレッドをキューに追加
    for t in initial_threads:
        queue.append({
            "id": t["id"],
            "title": t["title"],
            "is_url": False,
            "is_active": True
        })
        
    discovered = []
    processed_ids = set()
    
    while queue:
        current = queue.pop(0)
        current_id_or_url = current["id"]
        is_url = current["is_url"]
        current_title = current["title"]
        
        # Numeric ID抽出
        match = re.search(r'(\d+)/?$', current_id_or_url)
        numeric_id = match.group(1) if match else current_id_or_url
        
        if numeric_id in processed_ids:
            continue
            
        processed_ids.add(numeric_id)
        
        # レス本文と正しいタイトル、前スレURLをまず取得する
        title, first_msg, prev_urls = get_thread_first_post(current_id_or_url, is_url=is_url)
        
        # タイトルが取得できた場合は上書き、できなかった場合はキューに入っていた仮タイトルを維持
        final_title = title if title else current_title
        
        # 取得できた正しいタイトルで discovered リストへ本登録
        discovered.append({
            "id": current_id_or_url,
            "title": final_title,
            "is_url": is_url,
            "is_active": current.get("is_active", False)
        })
        
        title_lower = final_title.lower()
        if re.search(r'part\s*1\b|その\s*1\b|第\s*1\s*弾', title_lower):
            continue
        
        for url in prev_urls:
            url_match = re.search(r'(\d+)/?$', url)
            url_numeric_id = url_match.group(1) if url_match else url
            if url_numeric_id not in processed_ids:
                queue.append({
                    "id": url,
                    "title": final_title + " の関連スレ",
                    "is_url": True,
                    "is_active": False
                })
                
        time.sleep(1)
        
    # IDの昇順にソート（古い順）
    def extract_numeric_id_for_sort(item):
        m = re.search(r'(\d+)/?$', item['id'])
        return int(m.group(1)) if m else 0
        
    discovered.sort(key=extract_numeric_id_for_sort)
    return discovered

def get_thread_responses(thread_id, is_url=False):
    """特定のスレッド（IDまたはURL）内の全レスを取得"""
    if is_url:
        url = thread_id
    else:
        url = f"https://egg.{config.BASE_DOMAIN}/test/read.cgi/slotk/{thread_id}/"
        
    headers = {"User-Agent": USER_AGENT}
    try:
        print(f"Accessing: {url}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except Exception as e:
        print(f"スレッド取得エラー({url}): {e}")
        return []
    
    try:
        html_text = response.content.decode('cp932', errors='replace')
    except Exception:
        html_text = response.content.decode('utf-8', errors='replace')
    
    try:
        soup = BeautifulSoup(html_text, "lxml")
    except Exception:
        soup = BeautifulSoup(html_text, "html.parser")
        
    responses = []
    posts = soup.find_all("div", class_="post")
    
    if not posts:
        print(f"警告: スレッド({url})からレスを取得できませんでした。")
        return []
    
    for post in posts:
        name_elem = post.find("span", class_="name")
        uid_elem = post.find("span", class_="uid")
        date_elem = post.find("span", class_="date")
        
        content_elem = post.find("div", class_="post-content")
        if not content_elem:
            content_elem = post.find("div", class_="message")
            
        name = name_elem.text.strip() if name_elem else ""
        uid = uid_elem.text.strip() if uid_elem else ""
        date_str = date_elem.text.strip() if date_elem else ""
        message = content_elem.text.strip() if content_elem else ""
        
        message = message.strip()
        
        # 投稿日時の標準化 (YYYY/MM/DD(W) HH:MM:SS -> YYYY-MM-DD HH:MM:SS)
        post_date = date_str
        match = re.search(r'(\d{4})/(\d{2})/(\d{2})[^\d]*(\d{2}):(\d{2}):(\d{2})', date_str)
        if match:
            post_date = f"{match.group(1)}-{match.group(2)}-{match.group(3)} {match.group(4)}:{match.group(5)}:{match.group(6)}"
        
        if message:
            responses.append({
                "name": name,
                "uid": uid,
                "message": message,
                "date_str": date_str,
                "post_date": post_date
            })
            
    return responses

def clean_responses(responses):
    """ノイズ（自慢、AA、短文など）を除外"""
    cleaned = []
    for res in responses:
        msg = res["message"]
        
        if len(msg.replace("\n", "").strip()) <= 5:
            continue
            
        is_noise = False
        for pattern in NOISE_PATTERNS:
            if re.search(pattern, msg):
                is_noise = True
                break
                
        if not is_noise:
            cleaned.append(res)
            
    return cleaned
