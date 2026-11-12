# 心悦俱乐部活动监控

每 15 分钟检查一次心悦俱乐部首页（首页推荐 + 热门活动），发现新活动就通过 PushPlus 推送到微信。
含 Q币 / 红包 / 现金 等字样的活动，标题前会加 💰。

- `monitor.py`：监控程序（只用 Python 标准库）
- `.github/workflows/monitor.yml`：GitHub Actions 定时任务
- `seen.json`：已推送过的活动记录（程序自动生成，不用管）

## 配置
仓库 Settings → Secrets and variables → Actions → New repository secret
- Name：`PUSHPLUS_TOKEN`
- Secret：你的 PushPlus token

## 测试
Actions → 心悦活动监控 → Run workflow。第一次运行会推送一条“心悦监控已开启”。

## 修改
- 改检查频率：编辑 `monitor.yml` 里的 `cron`
- 改 💰 关键词：编辑 `monitor.py` 里的 `MONEY_WORDS`
