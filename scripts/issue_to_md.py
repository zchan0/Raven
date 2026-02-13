"""
GitHub Issue → Markdown 转换脚本

由 GitHub Actions 触发，将带有 'journal' 标签的 Issue 转换为 Markdown 文章。

流程：
1. 读取 Issue 内容
2. 提取标题、正文、标签、创建时间
3. 生成 frontmatter（YAML）
4. 写入到 YYYY/MM/DD/HH-MM-SS.md
5. 关闭 Issue 并打上 'published' 标签
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import yaml


def get_env(name: str) -> str:
    """获取必填环境变量"""
    val = os.getenv(name, "").strip()
    if not val:
        print(f"❌ 缺少环境变量: {name}")
        sys.exit(1)
    return val


def fetch_issue(owner: str, repo: str, issue_number: int, token: str) -> dict:
    """获取 Issue 详情"""
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


def close_and_label_issue(owner: str, repo: str, issue_number: int, token: str, published_label: str) -> None:
    """关闭 Issue 并打上 published 标签"""
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    
    # 添加标签
    requests.post(
        f"{url}/labels",
        headers=headers,
        json={"labels": [published_label]},
    ).raise_for_status()
    
    # 关闭 Issue
    requests.patch(
        url,
        headers=headers,
        json={"state": "closed"},
    ).raise_for_status()


def issue_to_markdown(issue: dict, journal_label: str, timezone: ZoneInfo) -> tuple[str, str]:
    """
    将 Issue 转换为 Markdown 文件。

    Returns:
        (file_path, markdown_content)
    """
    # 解析创建时间
    created_at = datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00"))
    created_at = created_at.astimezone(timezone)
    
    # 提取标签（排除 journal 和 published）
    tags = [
        label["name"]
        for label in issue.get("labels", [])
        if label["name"] not in {journal_label, "published"}
    ]
    
    # 清理 body：移除自动生成的日记时间戳
    body = issue["body"] or ""
    # 移除 ---\n*自动生成的日记* | YYYY-MM-DD 格式的内容
    body = re.sub(r'\n?---\n\*自动生成的日记\*\s*\|\s*\d{4}-\d{2}-\d{2}\s*$', '', body, flags=re.MULTILINE)
    body = body.strip()
    
    # 构建 frontmatter
    frontmatter = {
        "title": issue["title"],
        "date": created_at.isoformat(),
        "tags": tags,
        "github_issue": issue["number"],
        "github_url": issue["html_url"],
    }
    
    # 构建 Markdown 内容
    frontmatter_yaml = yaml.dump(frontmatter, allow_unicode=True, sort_keys=False)
    markdown = f"---\n{frontmatter_yaml}---\n\n{body}\n"

    # 生成文件路径：YYYY/MMdd.md (简化层级结构)
    year = created_at.strftime("%Y")
    month_day = created_at.strftime("%m%d")
    file_path = f"{year}/{month_day}.md"

    return file_path, markdown


def main() -> None:
    """主流程"""
    # 读取环境变量
    github_token = get_env("GITHUB_TOKEN")
    github_owner = get_env("GITHUB_OWNER")
    github_repo = get_env("GITHUB_REPO")
    issue_number = int(get_env("ISSUE_NUMBER"))
    article_dir = os.getenv("ARTICLE_DIR", "content/posts").strip()
    journal_label = os.getenv("JOURNAL_LABEL", "journal").strip()
    published_label = os.getenv("PUBLISHED_LABEL", "published").strip()
    
    tz_name = os.getenv("JOURNAL_TZ", "Asia/Shanghai").strip()
    try:
        tz = ZoneInfo(tz_name)
    except KeyError:
        print(f"⚠️ 无法识别时区 '{tz_name}'，使用 Asia/Shanghai")
        tz = ZoneInfo("Asia/Shanghai")
    
    print(f"📥 处理 Issue #{issue_number}")
    
    # 获取 Issue 详情
    issue = fetch_issue(github_owner, github_repo, issue_number, github_token)
    
    # 检查是否有 journal 标签
    label_names = {label["name"] for label in issue.get("labels", [])}
    if journal_label not in label_names:
        print(f"⚠️ Issue #{issue_number} 没有 '{journal_label}' 标签，跳过")
        return
    
    # 转换为 Markdown
    file_path, markdown_content = issue_to_markdown(issue, journal_label, tz)
    full_path = Path(article_dir) / file_path
    
    # 写入文件
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(markdown_content, encoding="utf-8")
    print(f"✅ 文章已生成: {full_path}")
    
    # 关闭 Issue 并打标签
    close_and_label_issue(github_owner, github_repo, issue_number, github_token, published_label)
    print(f"✅ Issue #{issue_number} 已关闭并标记为 '{published_label}'")


if __name__ == "__main__":
    main()
