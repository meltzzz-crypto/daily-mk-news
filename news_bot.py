import feedparser
import requests
import os
import time
from datetime import datetime
from bs4 import BeautifulSoup

# 설정
RSS_URL = "https://www.mk.co.kr/rss/50300009/"
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

def get_summary_from_url(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        
        # 본문 찾기
        content = ""
        for selector in ["div.art_txt", "div.news_cnt_detail_wrap", ".txt_area"]:
            element = soup.select_one(selector)
            if element:
                content = element.get_text(separator=" ").strip()
                break
        
        if not content: return None

        # 요약 (3문장)
        sentences = content.split('다.')
        summary = []
        for s in sentences:
            s = s.strip()
            if len(s) > 30 and "기자" not in s: 
                summary.append(s + '다.')
                if len(summary) >= 3: break
        
        return summary
    except:
        return None

def fetch_rss_news():
    print("뉴스 7개 가져오는 중...")
    feed = feedparser.parse(RSS_URL)
    news_items = []
    
    # 딱 7개만 가져오기 (메시지 1개에 안전하게 들어감)
    for entry in feed.entries[:7]:
        link = entry.link
        print(f"처리 중: {entry.title}")
        
        # 본문 요약 시도
        summary_points = get_summary_from_url(link)
        
        if summary_points:
            desc = "\n".join([f"- {p}" for p in summary_points])
        else:
            desc = entry.description[:100] + "..."
            
        news_items.append({
            "title": entry.title,
            "link": link,
            "summary": desc,
            "published": entry.published
        })
        time.sleep(0.5)
    
    return news_items

def send_to_discord(items):
    if not items: return
    
    print(f"디스코드로 {len(items)}개 전송 중...")
    embeds = []
    
    # 헤더
    embeds.append({
        "title": "📰 매일경제 부동산 주요 뉴스 (7선)",
        "description": f"{datetime.now().strftime('%Y-%m-%d')} 핵심 요약",
        "color": 0x00ff00
    })
        
    for item in items:
        embeds.append({
            "title": item['title'],
            "url": item['link'],
            "description": item['summary'],
            "footer": {"text": "MK News"}
        })
        
    requests.post(WEBHOOK_URL, json={"username": "MK부동산뉴스봇", "embeds": embeds})
    print("전송 완료!")

if __name__ == "__main__":
    news = fetch_rss_news()
    send_to_discord(news)
