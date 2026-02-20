#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, 'bot/sync')

from datetime import datetime
from weather_service import get_diary_header, get_lunar_date

# Issues 数据
issues = [
    (6, "2026-02-19"),
    (5, "2026-02-18"),
    (4, "2026-02-17"),
    (3, "2026-02-16"),  # 实际是2月16日内容
    (2, "2026-02-15"),
    (1, "2026-02-13"),
]

print("=== 生成新标题 ===\n")

for num, date_str in issues:
    date = datetime.strptime(date_str, "%Y-%m-%d")
    new_title = get_diary_header(date, "Shanghai")
    lunar = get_lunar_date(date)
    print(f"Issue #{num}: {date_str}")
    print(f"  农历: {lunar}")
    print(f"  新标题: {new_title}")
    print()

print("\n=== 开始更新 Issues ===\n")

import requests

token = os.getenv('GITHUB_TOKEN')
owner = os.getenv('GITHUB_OWNER', 'zchan0')
repo = os.getenv('GITHUB_REPO', 'Raven')

headers = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github.v3+json",
}

for num, date_str in issues:
    date = datetime.strptime(date_str, "%Y-%m-%d")
    new_title = get_diary_header(date, "Shanghai")
    
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{num}"
    
    response = requests.patch(url, headers=headers, json={"title": new_title})
    
    if response.status_code == 200:
        print(f"✅ Issue #{num} 标题已更新: {new_title}")
    else:
        print(f"❌ Issue #{num} 更新失败: {response.status_code} - {response.text}")

print("\n=== 完成 ===")
