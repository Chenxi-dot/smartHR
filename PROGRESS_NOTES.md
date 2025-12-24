# 运行时进度提示改动

- 在 `SmartMatcher` 中新增 `last_progress` 记录，并通过 `_log` 在关键步骤写入：
  1) JD LLM 分析开始/结束。
  2) 评分阶段开始（含候选人数）。
  3) 排序截断完成（返回 top K 数量）。
  4) 初始化时记录加载的候选人数。
- `app.py` 将 `progress` 传给模板；`index.html` 在表单卡片上方显示进度列表。
- 当前为同步请求内的“步骤列表”，用于告知流程状态；若需实时进度条，可进一步改为轮询或 SSE。

可调控：
- `MAX_CANDIDATES`（DataLoader）默认 120，限制初始解析数量。
- `TOP_K_RESULTS`（Matcher）默认 100，限制返回候选数量。
