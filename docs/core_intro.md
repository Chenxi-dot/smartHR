# 智能简历匹配核心逻辑概览

## 总览
- 目标：对用户提交的 JD 进行两阶段匹配，先基于意愿与技能的快速筛选，再对 Top 候选人做 LLM 深度评估，输出最终排名。
- 关键文件：
  - `src/data_loader.py`：加载候选人数据（无逐人 LLM）、提取技能/意愿文本。
  - `src/matcher.py`：两阶段打分（Stage-1 本地、Stage-2 LLM 深评）。
  - `src/llm_service.py`：Qwen API 调用，JD 解析 + 候选人深度评估。
  - `templates/index.html`：前端展示与提交。

## 数据加载（无逐人 LLM）
- 读取 `candidates.parquet`，最多 `MAX_CANDIDATES`（默认 120）。
- 为每条候选人生成：
  - `Long Description`：职位/关键字/英语/年限/Highlights/Moreinfo/CV 的简要串接。
  - `skill_hints`：从 Primary Keyword/Highlights/Moreinfo/CV 里分隔出的技能词。
  - `looking_for_text`：候选人意愿字段。
- 不做 per-candidate LLM 解析（节约配额/时间）。

## 每次 JD 查询的流程
1) **JD 解析（1 次 LLM）**
   - `LLMService.analyze_jd(jd_text)` 提取：`role_title`、`role_keywords`、`hard_requirements`（经验/技能/教育/英语）、`soft_requirements`。
2) **Stage-1 本地快速打分（无 LLM）**
   - 意愿匹配：`role_keywords` 与候选人 `looking_for_text` 重叠。
   - 技能匹配：`required_skills` 与候选人 `skill_hints` 重叠。
   - 经验/英语：规则打分。
   - Stage-1 分数 = 0.5*技能 + 0.3*意愿 + 0.1*经验 + 0.1*英语。
   - 保留前 `STAGE1_LIMIT`（默认 50）。
3) **Stage-2 LLM 深度评估（最多 10 次）**
   - 对 Stage-1 前 `STAGE2_LIMIT`（默认 10）调用 `LLMService.score_candidate_for_jd`，获取 `fit_score`、strengths、risks、verdict。
   - 最终分 = (1-`STAGE2_WEIGHT`)*Stage-1 + `STAGE2_WEIGHT`*fit_score（默认 0.4）。
   - 排序后取前 `TOP_K_RESULTS`（默认 100）返回前端。
4) **进度提示**
   - `matcher.last_progress` 记录“JD 分析”“Stage-1 完成”“Stage-2 进度”等，页面展示。

## LLM 调用次数（每次 JD）
- 固定 1 次 JD 解析。
- 最多 `STAGE2_LIMIT` 次候选人深评（默认 10）。
- 不再对所有候选人逐一解析。

## 关键环境变量
- Qwen：`QWEN_API_KEY` / `QWEN_BASE_URL` / `QWEN_MODEL`
- 控制规模/性能：`MAX_CANDIDATES`（默认 120）、`TOP_K_RESULTS`（默认 100）、`STAGE1_LIMIT`（默认 50）、`STAGE2_LIMIT`（默认 10）、`STAGE2_WEIGHT`（默认 0.4）

## 部署与运行（内网访问）
- 安装依赖：`pip install -r requirements.txt`
- 设置环境变量（示例）：
  ```bash
  export QWEN_API_KEY=你的Key
  export QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
  export QWEN_MODEL=qwen-plus
  export MAX_CANDIDATES=120
  export STAGE1_LIMIT=50
  export STAGE2_LIMIT=10
  export STAGE2_WEIGHT=0.4
  ```
- 启动：`gunicorn app:app --bind 0.0.0.0:8000 --workers 2`
- 访问：`http://<内网IP>:8000`，同网段同事可直接用浏览器打开。

## 对外可访问的方案
- **内网**：确保端口（例如 8000）在服务器防火墙/安全组开放，同网段同事直接访问 `http://内网IP:8000`。
- **临时公网**：
  - cloudflared：`cloudflared tunnel --url http://localhost:8000`，获得一个公网 URL 分享。
  - ngrok：`ngrok http 8000`，获得公网 URL。
- **正式公网**（需要公网或云主机）：
  - 在云主机上运行 gunicorn，开放 80/443 端口，或用 Nginx/Caddy 反代到 8000。
  - 可配域名与 HTTPS（Caddy/Certbot）。
- **不需要服务器账号的同学访问**：只要对方能访问到你的公网/隧道 URL 即可，不需登录；若只在内网，需确保对方与服务器同网段或有 VPN/隧道。

## 前端说明
- 页面表单：JD + 可选 Target Role；显示进度列表；展示 Top-5 与 Top 结果列表。
- 进度信息来自 `matcher.last_progress`。

