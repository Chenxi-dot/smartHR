# LLM 调用与匹配流程说明

## 模型与接口
- 默认使用 Qwen DashScope 兼容接口：`QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`
- 模型：`QWEN_MODEL=qwen-plus`（可改为 qwen-max / qwen-turbo），API Key 由环境变量 `QWEN_API_KEY` 提供。
- 兼容 OpenAI Chat Completions 路径：`<BASE_URL>/chat/completions`。

## 入口与加载
- `DataLoader.load_candidates`：读取 `candidates.parquet`，按 `MAX_CANDIDATES`（默认 120）截断，构建 `Long Description`、`skill_hints`、`looking_for_text`，不再做逐候选人 LLM 解析。

## 每次 JD 匹配的 LLM 调用
1) `LLMService.analyze_jd(jd_text)`（1 次）：提取 role_title、role_keywords、hard/soft 要求。
2) Stage-2 深评（最多 10 次）：对 Stage-1 得分前 `STAGE2_LIMIT`（默认 10）名候选人调用 `LLMService.score_candidate_for_jd`，输出 fit_score/strengths/risks。

## 打分流程（两阶段）
- Stage-1（本地，无额外 LLM）：
  - 意愿匹配：JD role_keywords 与候选人 `Looking For` 文本的重叠。
  - 技能匹配：JD required_skills 与候选人 skill_hints 重叠。
  - 经验/英语：基于年限与英语等级的规则分。
  - Stage-1 分数 = 0.5*技能 + 0.3*意愿 + 0.1*经验 + 0.1*英语。
  - 保留前 `STAGE1_LIMIT`（默认 50）。
- Stage-2（LLM 深评）：对前 `STAGE2_LIMIT`（默认 10）做 LLM 评分；最终分 = (1-`STAGE2_WEIGHT`)*Stage-1 + `STAGE2_WEIGHT`*fit_score（默认权重 0.4）。
- 返回前 `TOP_K_RESULTS`（默认 100）。

## 调用次数粗算
- 每次 JD：1 次 JD 解析 + 最多 10 次候选人深评。
- 不再对所有候选人做批量 LLM 解析。

## 关键环境变量
- `QWEN_API_KEY` / `QWEN_BASE_URL` / `QWEN_MODEL`
- `MAX_CANDIDATES`（默认 120）
- `TOP_K_RESULTS`（默认 100）
- `STAGE1_LIMIT`（默认 50）
- `STAGE2_LIMIT`（默认 10）
- `STAGE2_WEIGHT`（默认 0.4）

## 关键环境变量
- `QWEN_API_KEY` / `QWEN_BASE_URL` / `QWEN_MODEL`
- `MAX_CANDIDATES`：候选人截断，默认 120。
- `TOP_K_RESULTS`：返回前端的候选人条数，默认 100。

## 失败与降级
- 若未配置 API Key 或调用失败，`matcher.last_error` 会传到前端，页面展示红色错误框；不会继续匹配。
- 未安装 Redis / Chroma 时自动回退本地缓存与内存向量，不影响 LLM 逻辑。

