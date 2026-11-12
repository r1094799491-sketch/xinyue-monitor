# -*- coding: utf-8 -*-
"""
心悦俱乐部活动监控：发现新活动就通过 PushPlus 推送到微信。
只用 Python 标准库，不需要安装任何包。

环境变量：
  PUSHPLUS_TOKEN  你的 PushPlus token（在 GitHub Secrets 里配置）
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

STATE_FILE = "seen.json"
TZ = timezone(timedelta(hours=8))  # 北京时间

# 标题或描述里含这些词的活动会在推送里标 💰
MONEY_WORDS = ["Q币", "q币", "红包", "现金", "话费", "京东卡", "免费领"]

SOURCES = {
    "首页推荐": "https://bgw.xinyue.qq.com/website/website/home/banners",
    "热门活动": "https://bgw.xinyue.qq.com/website/website/home/modules",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Referer": "https://xinyue.qq.com/",
    "Origin": "https://xinyue.qq.com",
    "Accept": "application/json, text/plain, */*",
}


def get_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_activities():
    """返回 {key: {title, desc, url, source}}"""
    acts = {}

    # 首页推荐（轮播）
    data = get_json(SOURCES["首页推荐"])
    for it in data.get("data", {}).get("list", []) or []:
        title = (it.get("title") or "").strip()
        url = (it.get("navigate_url") or "").strip()
        if not title:
            continue
        key = url or title
        acts[key] = {"title": title, "desc": (it.get("desc") or "").strip(),
                     "url": url, "source": "首页推荐"}

    # 热门活动模块
    data = get_json(SOURCES["热门活动"])
    for m in data.get("data", {}).get("list", []) or []:
        if m.get("name") != "热门活动":
            continue
        for it in m.get("data", []) or []:
            title = (it.get("text_title") or "").strip()
            url = (it.get("navigate_url") or "").strip()
            if not title:
                continue
            key = url or title
            if key not in acts:
                acts[key] = {"title": title, "desc": (it.get("text_desc") or "").strip(),
                             "url": url, "source": "热门活动"}

    if not acts:
        raise RuntimeError("没有解析到任何活动，接口格式可能变了")
    return acts


def norm_key(k):
    # 去掉 via= 之类的追踪参数，避免同一活动换个参数就被当成新活动
    return k.split("?")[0] if k.startswith("http") else k


def is_money(a):
    text = a["title"] + a["desc"]
    return any(w in text for w in MONEY_WORDS)


def push(title, html):
    token = os.environ.get("PUSHPLUS_TOKEN", "").strip()
    if not token:
        print("[!] 没有设置 PUSHPLUS_TOKEN，跳过推送。内容：", title)
        return False
    body = json.dumps({"token": token, "title": title[:100], "content": html,
                       "template": "html"}).encode("utf-8")
    req = urllib.request.Request("https://www.pushplus.plus/send", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        res = json.loads(r.read().decode("utf-8"))
    print("PushPlus 返回：", res)
    return res.get("code") == 200


def render(items):
    parts = []
    for a in items:
        mark = "💰 " if is_money(a) else ""
        link = f'<a href="{a["url"]}">打开活动</a>' if a["url"] else ""
        parts.append(f'<p><b>{mark}{a["title"]}</b><br>{a["desc"]}<br>'
                     f'<small>来源：{a["source"]}</small> {link}</p>')
    return "".join(parts)


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return None


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1, sort_keys=True)


def main():
    now = datetime.now(TZ)
    state = load_state()
    first_run = state is None
    if first_run:
        state = {"seen": {}, "fail_count": 0, "heartbeat": ""}

    try:
        acts = fetch_activities()
    except Exception as e:  # 网络或接口问题：记一次失败，连续失败太多再提醒
        state["fail_count"] = state.get("fail_count", 0) + 1
        print("[!] 获取活动失败：", e, "连续失败次数：", state["fail_count"])
        if state["fail_count"] == 8:  # 大约 2 小时
            push("心悦监控：连续获取失败", f"<p>最近一次错误：{e}</p><p>可能是接口改了，回来找 Claude 看看。</p>")
        save_state(state)
        return

    state["fail_count"] = 0
    new_items = []
    for k, a in acts.items():
        nk = norm_key(k)
        if nk not in state["seen"]:
            state["seen"][nk] = {"title": a["title"], "first_seen": now.strftime("%Y-%m-%d %H:%M")}
            new_items.append(a)

    if first_run:
        push(f"心悦监控已开启，当前 {len(acts)} 个活动",
             "<p>以后出现新活动会第一时间推给你。当前活动：</p>" + render(list(acts.values())))
    elif new_items:
        money = [a for a in new_items if is_money(a)]
        head = money[0] if money else new_items[0]
        title = ("💰" if money else "") + "心悦新活动：" + head["title"]
        if len(new_items) > 1:
            title += f" 等{len(new_items)}个"
        push(title, render(new_items))
    else:
        print("没有新活动。当前活动数：", len(acts))

    # 只保留最近 300 条记录，防止文件无限变大
    if len(state["seen"]) > 300:
        items = sorted(state["seen"].items(), key=lambda kv: kv[1].get("first_seen", ""))
        state["seen"] = dict(items[-300:])

    # 每 30 天写一次心跳，防止 GitHub 因仓库长期无改动停掉定时任务
    hb = state.get("heartbeat", "")
    if not hb or (now - datetime.fromisoformat(hb)).days >= 30:
        state["heartbeat"] = now.isoformat(timespec="seconds")

    save_state(state)


if __name__ == "__main__":
    main()
