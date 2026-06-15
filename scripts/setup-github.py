import os, json, urllib.request, subprocess

# 读取 token
token = None
with open(os.path.expanduser("~/.secrets/github.env")) as f:
    for line in f:
        if "GITHUB_TOKEN" in line:
            token = line.strip().split("=", 1)[1].strip("\'").strip('"')
            break

if not token:
    print("ERROR: No GitHub token found")
    exit(1)

username = "nickliqian"
repo_name = "stock-flow"
headers = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "Python"
}

# 1. 检查仓库是否已存在
try:
    req = urllib.request.Request(f"https://api.github.com/repos/{username}/{repo_name}", headers=headers)
    urllib.request.urlopen(req)
    print(f"Repo {repo_name} already exists")
except urllib.error.HTTPError as e:
    if e.code == 404:
        # 创建公开仓库
        data = json.dumps({
            "name": repo_name,
            "description": "A-share capital flow analysis system with real-time market data, sector analysis, and AI-powered research",
            "public": True,
            "auto_init": False
        }).encode()
        req = urllib.request.Request("https://api.github.com/user/repos", data=data, headers=headers, method="POST")
        resp = urllib.request.urlopen(req)
        print(f"Created repo: {json.loads(resp.read()).get('html_url')}")
    else:
        print(f"Error checking repo: {e.code}")
        exit(1)

# 2. 初始化 git repo
os.chdir(os.path.expanduser("~/projects/stock-flow"))
subprocess.run(["git", "init"], check=True, capture_output=True)
subprocess.run(["git", "config", "user.name", "nickliqian"], check=True, capture_output=True)
subprocess.run(["git", "config", "user.email", "nickliqian@users.noreply.github.com"], check=True, capture_output=True)

# 3. 创建 .gitignore
gitignore = """
node_modules/
dist/
.env
*.db
__pycache__/
*.pyc
.DS_Store
.vscode/
*.log
.cache/
"""
with open(".gitignore", "w") as f:
    f.write(gitignore)

# 4. 添加远程仓库
remote_url = f"https://{username}:{token}@github.com/{username}/{repo_name}.git"
subprocess.run(["git", "remote", "remove", "origin"], capture_output=True)
subprocess.run(["git", "remote", "add", "origin", remote_url], check=True, capture_output=True)

# 5. 添加所有文件并提交
subprocess.run(["git", "add", "-A"], check=True, capture_output=True)
result = subprocess.run(["git", "commit", "-m", "feat: 资金流向分析系统 v1.0\n\n- 大盘总览/板块资金/个股资金\n- 选股工具/策略中心/智能分析\n- 市场宽度/筹码分析/Alpha评分\n- AI日志/研究资料浏览\n- 数据同步: Tushare API\n- 定时任务: 数据同步/代码审查/资料搜集"], check=True, capture_output=True, text=True)
print(f"Commit: {result.stdout.strip()}")

# 6. 推送
result = subprocess.run(["git", "push", "-u", "origin", "main", "--force"], capture_output=True, text=True, timeout=60)
if result.returncode == 0:
    print(f"Pushed successfully!")
    print(f"URL: https://github.com/{username}/{repo_name}")
else:
    # 尝试 master 分支
    subprocess.run(["git", "branch", "-M", "main"], check=True, capture_output=True)
    result2 = subprocess.run(["git", "push", "-u", "origin", "main", "--force"], capture_output=True, text=True, timeout=60)
    if result2.returncode == 0:
        print(f"Pushed successfully!")
        print(f"URL: https://github.com/{username}/{repo_name}")
    else:
        print(f"Push error: {result2.stderr[:200]}")
