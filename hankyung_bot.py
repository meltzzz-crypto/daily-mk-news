import os
import time
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# Configuration
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
TARGET_URL = "https://www.hankyung.com/mr"

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def get_article_summary(driver, url):
    try:
        driver.get(url)
        time.sleep(2) # 충분히 로딩 대기
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        content_element = soup.select_one("#articletxt") or soup.select_one(".article-body") or soup.select_one(".article_body") or soup.select_one("#article-body")
        
        if not content_element:
            return None
            
        text = content_element.get_text(separator="\n").strip()
        sentences = text.split('.')
        
        summary = []
        for s in sentences:
            s = s.strip()
            if len(s) > 30 and "기자" not in s and "이메일" not in s and "ⓒ" not in s:
                summary.append(s + '.')
                if len(summary) >= 3:
                    break
        return summary
    except:
        return None

def fetch_hankyung_mr():
    print(f"🔍 [1/3] 접속 시도 중: {TARGET_URL}")
    driver = setup_driver()
    data = {"youtube_link": None, "articles": []}
    
    try:
        driver.get(TARGET_URL)
        time.sleep(5) # 페이지가 완전히 뜰 때까지 넉넉히 대기
        
        # 화면을 아래로 살짝 내리기 (데이터 로딩 유도)
        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(2)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # 1. 유튜브 링크 찾기
        links = soup.find_all("a", href=True)
        for a in links:
            href = a['href']
            if "youtube.com/watch" in href or "youtu.be" in href:
                data["youtube_link"] = href
                break
        print(f"📺 유튜브 링크 찾음: {data['youtube_link']}")

        # 2. 기사 찾기 (가장 강력한 방식)
        print("🕵️ [2/3] 기사 목록 검색 중...")
        
        article_candidates = []
        # '오늘의 기사' 텍스트 주변에서 찾기
        headers = soup.find_all(string=lambda t: t and "오늘의 기사" in t)
        
        if headers:
            print("✅ '오늘의 기사' 섹션 발견!")
            # 해당 섹션 주변의 모든 링크 수집
            parent = headers[0].parent
            for _ in range(6): # 위로 6단계까지 올라가며 컨테이너 검색
                if parent:
                    found_links = parent.find_all("a", href=True)
                    for l in found_links:
                        url = l['href']
                        title = l.get_text(strip=True)
                        if "/article/" in url and len(title) > 10:
                            if not url.startswith("http"): url = "https://www.hankyung.com" + url
                            article_candidates.append({"title": title, "url": url})
                parent = parent.parent if parent else None
        
        # 만약 섹션으로 못찾았다면, 페이지 전체에서 뉴스처럼 보이는 링크 다 긁어오기 (최후의 보루)
        if not article_candidates:
            print("⚠️ 섹션을 못 찾아 전체 페이지에서 검색합니다.")
            for l in links:
                url = l['href']
                title = l.get_text(strip=True)
                if "/article/" in url and len(title) > 15:
                    if not url.startswith("http"): url = "https://www.hankyung.com" + url
                    article_candidates.append({"title": title, "url": url})

        # 중복 제거 및 상위 10개만 선정
        seen = set()
        final_articles = []
        for art in article_candidates:
            if art['url'] not in seen:
                final_articles.append(art)
                seen.add(art['url'])
                if len(final_articles) >= 10: break
        
        print(f"📝 [3/3] 기사 {len(final_articles)}개 발견! 요약 시작...")
        
        for art in final_articles:
            print(f"   - {art['title'][:20]}... 요약 중")
            art['summary'] = get_article_summary(driver, art['url'])
            
        data["articles"] = final_articles
        
    except Exception as e:
        print(f"❌ 에러 발생: {e}")
    finally:
        driver.quit()
    return data

def send_to_discord(data):
    if not WEBHOOK_URL or not WEBHOOK_URL.startswith("http"):
        print("❌ 에러: 디스코드 웹훅 주소가 설정되지 않았거나 틀립니다!")
        return
        
    articles = data["articles"]
    if not articles:
        print("😿 보낼 기사가 없습니다.")
        return
        
    print(f"🚀 디스코드로 슝! ({len(articles)}개)")
    
    # 첫 번째 메시지 (제목 및 유튜브)
    header = {
        "title": "☕ 한경 모닝루틴 브리핑",
        "description": f"🗓️ {datetime.now().strftime('%Y-%m-%d')}\n" + (f"📺 [라이브 방송]({data['youtube_link']})" if data['youtube_link'] else ""),
        "color": 0x1E90FF,
        "url": TARGET_URL
    }
    
    embed_list = [header]
    for i, art in enumerate(articles):
        summary = "\n".join([f"• {s}" for s in art['summary']]) if art.get('summary') else "링크를 참조하세요."
        embed_list.append({
            "title": f"{i+1}. {art['title']}",
            "url": art['url'],
            "description": summary,
            "color": 0xFFFFFF
        })
        
        if len(embed_list) == 10:
            requests.post(WEBHOOK_URL, json={"embeds": embed_list})
            embed_list = []
            time.sleep(1)
            
    if embed_list:
        requests.post(WEBHOOK_URL, json={"embeds": embed_list})
    print("✨ 전송 완료!")

if __name__ == "__main__":
    results = fetch_hankyung_mr()
    send_to_discord(results)
