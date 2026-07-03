#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自动爬取AI资讯、新工具、教程，生成Hugo文章"""

import os, sys, requests, re, json, time, random
from bs4 import BeautifulSoup
from datetime import datetime

OUTPUT_DIR = "content/posts"
NEWS_DIR = "content/posts/news"
TOOLS_DIR = "content/posts/tools"
TUTORIALS_DIR = "content/posts/tutorials"

for d in [NEWS_DIR, TOOLS_DIR, TUTORIALS_DIR]:
    os.makedirs(d, exist_ok=True)

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

def headers():
    return {'User-Agent': random.choice(USER_AGENTS), 'Accept-Language': 'zh-CN,zh;q=0.9'}

def safe_filename(title, max_len=50):
    s = re.sub(r'[^\w\u4e00-\u9fff\s-]', '', title)
    s = re.sub(r'[\s]+', '_', s).lower()
    return s[:max_len]

def extract_article_text(url, max_chars=1500):
    """智能提取文章正文，过滤导航/广告"""
    try:
        resp = requests.get(url, headers=headers(), timeout=15)
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, 'html.parser')
        # 移除无用元素
        for tag in soup.find_all(['script','style','nav','footer','header','aside','iframe','noscript']):
            tag.decompose()
        for tag in soup.find_all(class_=re.compile(r'(nav|menu|footer|sidebar|ad|banner|comment|share|login|header)', re.I)):
            tag.decompose()
        
        # 优先从article标签获取
        article = soup.find('article') or soup.find(class_=re.compile(r'(article|content|post|entry|text)', re.I))
        if article:
            text = article.get_text(separator='\n', strip=True)
        else:
            text = soup.get_text(separator='\n', strip=True)
        
        # 过滤短行和垃圾内容
        lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 8]
        # 跳过开头的导航残余
        meaningful_start = 0
        for i, line in enumerate(lines):
            if len(line) > 30:
                meaningful_start = i
                break
        lines = lines[meaningful_start:]
        
        return '\n'.join(lines)[:max_chars]
    except Exception as e:
        print(f"  内容提取失败: {e}")
        return ""

def make_summary(text, max_len=150):
    """从正文提取摘要"""
    if not text:
        return "AI领域最新动态，持续更新中"
    # 取前几个有意义的句子
    sentences = re.split(r'[。！？\.\!\?]', text)
    summary = ''
    for s in sentences:
        s = s.strip()
        if len(s) > 10:
            summary += s + '。'
            if len(summary) >= max_len:
                break
    return summary[:max_len] if summary else text[:max_len]

def make_frontmatter(title, category, tags, summary):
    date = datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00')
    return f"""---
title: "{title}"
date: {date}
draft: false
categories: ["{category}"]
tags: {json.dumps(tags, ensure_ascii=False)}
description: "{summary}"
---

"""

def gen_article(item, content_type):
    title = item['title'].strip()
    url = item['url']
    source = item['source']
    category = item['category']
    
    print(f"  📖 获取内容: {title[:30]}...")
    content = extract_article_text(url)
    summary = make_summary(content)
    
    tags = ['AI', source]
    if content_type == 'tools':
        tags += ['新工具', 'AI工具']
    elif content_type == 'tutorials':
        tags += ['教程', '实战']
    else:
        tags += ['资讯', '行业动态']
    
    fm = make_frontmatter(title, category, tags, summary)
    
    body = f"""> 来源：[{source}]({url}) · {datetime.now().strftime('%Y-%m-%d %H:%M')}

## 内容摘要

{summary}

## 详细内容

{content[:800] if content else '请访问原文链接查看完整内容。'}

---

[🔗 查看原文]({url})

*本文由AI自动整理，内容版权归原作者所有。*
"""
    
    dir_map = {'news': NEWS_DIR, 'tools': TOOLS_DIR, 'tutorials': TUTORIALS_DIR}
    filepath = os.path.join(dir_map[content_type], f"{safe_filename(title)}.md")
    
    # 避免重复
    if os.path.exists(filepath):
        print(f"  ⏭️ 已存在，跳过")
        return None
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(fm + body)
    print(f"  ✅ 生成: {filepath}")
    return filepath

def crawl_36kr():
    """爬取36kr AI频道"""
    items = []
    try:
        print("📰 36kr AI频道...")
        r = requests.get('https://36kr.com/information/AI/', headers=headers(), timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            links = soup.select('a.article-item-title') or soup.select('a[class*="title"]')
            for a in links[:5]:
                t = a.get_text(strip=True)
                h = a.get('href','')
                if t and h and len(t) > 8:
                    if not h.startswith('http'): h = 'https://36kr.com' + h
                    items.append({'title':t,'url':h,'source':'36氪','category':'AI资讯'})
            print(f"  找到 {len(items)} 篇")
    except Exception as e:
        print(f"  失败: {e}")
    return items

def crawl_jiqizhixin():
    """爬取机器之心"""
    items = []
    try:
        print("📰 机器之心...")
        r = requests.get('https://www.jiqizhixin.com/', headers=headers(), timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            links = soup.select('a[href*="/articles/"]') or soup.select('a[href*="/dailies/"]')
            for a in links[:5]:
                t = a.get_text(strip=True)
                h = a.get('href','')
                if t and h and len(t) > 8:
                    if not h.startswith('http'): h = 'https://www.jiqizhixin.com' + h
                    items.append({'title':t,'url':h,'source':'机器之心','category':'AI资讯'})
            print(f"  找到 {len(items)} 篇")
    except Exception as e:
        print(f"  失败: {e}")
    return items

def crawl_aicpb():
    """爬取AI产品榜"""
    items = []
    try:
        print("🔧 AI产品榜...")
        r = requests.get('https://www.aicpb.com/', headers=headers(), timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            links = soup.select('a[href]')
            for a in links:
                t = a.get_text(strip=True)
                h = a.get('href','')
                if t and h and len(t) > 5 and 'AI' in t.upper():
                    if not h.startswith('http'): h = 'https://www.aicpb.com' + h
                    items.append({'title':t,'url':h,'source':'AICPB','category':'AI工具'})
                    if len(items) >= 3: break
            print(f"  找到 {len(items)} 个")
    except Exception as e:
        print(f"  失败: {e}")
    return items

def crawl_juejin():
    """爬取掘金AI教程"""
    items = []
    try:
        print("📚 掘金AI...")
        r = requests.get('https://juejin.cn/tag/AI', headers=headers(), timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            links = soup.select('a[href*="/post/"]')
            for a in links[:5]:
                t = a.get_text(strip=True)
                h = a.get('href','')
                if t and h and len(t) > 10:
                    if not h.startswith('http'): h = 'https://juejin.cn' + h
                    items.append({'title':t,'url':h,'source':'掘金','category':'AI教程'})
            print(f"  找到 {len(items)} 篇")
    except Exception as e:
        print(f"  失败: {e}")
    return items

def crawl_cnbeta():
    """爬取cnBeta AI新闻"""
    items = []
    try:
        print("📰 cnBeta AI...")
        r = requests.get('https://www.cnbeta.com.tw/tag/ai', headers=headers(), timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            links = soup.select('a[href*="/articles/"]')
            for a in links[:5]:
                t = a.get_text(strip=True)
                h = a.get('href','')
                if t and h and len(t) > 8:
                    if not h.startswith('http'): h = 'https://www.cnbeta.com.tw' + h
                    items.append({'title':t,'url':h,'source':'cnBeta','category':'AI资讯'})
            print(f"  找到 {len(items)} 篇")
    except Exception as e:
        print(f"  失败: {e}")
    return items

def main():
    print("=" * 50)
    print("🚀 极效AI - 自动内容爬取")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    generated = []
    
    # AI资讯（最多3篇）
    for src_func in [crawl_36kr, crawl_jiqizhixin, crawl_cnbeta]:
        items = src_func()
        for item in items[:2]:
            fp = gen_article(item, 'news')
            if fp: generated.append(fp)
            time.sleep(2)
        if len(generated) >= 3: break
    
    # 新工具（最多2个）
    for src_func in [crawl_aicpb]:
        items = src_func()
        for item in items[:2]:
            fp = gen_article(item, 'tools')
            if fp: generated.append(fp)
            time.sleep(2)
    
    # 教程（最多1篇）
    for src_func in [crawl_juejin]:
        items = src_func()
        for item in items[:1]:
            fp = gen_article(item, 'tutorials')
            if fp: generated.append(fp)
            time.sleep(2)
    
    print("\n" + "=" * 50)
    print(f"✅ 完成！共生成 {len(generated)} 篇")
    for f in generated: print(f"  → {f}")
    print("=" * 50)
    
    return 0 if generated else 1

if __name__ == '__main__':
    sys.exit(main())
