# Smart HR（智能简历筛选系统）技术说明文档

## 1. 文档目的与范围
本文档面向研发/算法/架构评审读者，描述系统的端到端数据流、关键模块职责、核心算法与可配置参数，并给出可复现实验/运行方式。

范围包含：

* 候选人数据加载与统一文本构建
* 简历与JD的结构化抽取（LLM）
* 硬性条件（Hard）门槛判定
* 软性条件（Soft）相似度评分
* 缓存与容错策略
* Web 服务与结果展示

不包含：

* 生产级权限/审计/多租户方案
* 线上大规模向量检索的工程化部署（可作为扩展方向）

## 2. 运行时产物与目录结构

* `app.py`：Flask Web 入口
* `templates/index.html`：前端模板（Top 推荐 + 详细列表）
* `src/data_loader.py`：数据加载、Long Description 构建、LLM 解析与缓存
* `src/llm_service.py`：LLM 调用、JD/简历结构化抽取、English level 归一化
* `src/matcher.py`：核心匹配与打分（Hard/Soft/Final）
* `src/cache_manager.py`：Redis（可选）+ SQLite（默认）缓存层
* `src/vector_store.py`：向量存储与检索抽象（Chroma 可选，内存回退）
* `candidates.parquet`：候选人数据源（Parquet）
* `parsed_data.db`：SQLite 缓存库（结构化解析结果）
* `test_english_level.py`：英语等级归一化与比较单测

## 3. 数据模型与字段规范

### 3.1 输入数据（候选人）
系统默认从 `candidates.parquet` 读取候选人，核心字段（以当前实现为准）：

* `Position`
* `Moreinfo`
* `Looking For`
* `Highlights`
* `Primary Keyword`
* `English Level`
* `Experience Years`
* `CV`
* `id`

### 3.2 Long Description（统一候选人文本）
为减少字段分散导致的信息稀释，系统在 `src/data_loader.py` 内将上述字段拼接成带标签的统一文本 `Long Description`，作为：

* LLM 输入（简历结构化抽取）
* Soft 相似度评分的候选文本
* 语义检索/向量存储的基础语料（当前为 TF-IDF 向量）

拼接示例（逻辑结构）：

* `Position: ...`
* `Primary Keyword: ...`
* `English Level: ...`
* `Experience Years: ...`
* `Looking For: ...`
* `Highlights: ...`
* `Moreinfo: ...`
* `CV: ...`

### 3.3 结构化简历 Schema（LLM 输出）
LLM 解析结果写入每个候选人的 `structured` 字段（字典），当前主要使用的子路径包括：

* `structured.profile.english_level`
* `structured.profile.experience_years`
* `structured.skills_certs.tech_skills`
* `structured.education`
* `structured.work_experience`
* `structured.projects`

系统会在 `src/data_loader.py` 中对 LLM 输出做“兜底补全/规范化”：

* 对 `English Level` 做归一化，缺失时默认 `basic`
* 确保 `profile/skills_certs/contact/...` 等关键字段存在且类型稳定
* 将 `Primary Keyword` 合并进 `tech_skills`（避免遗漏主技能）

## 4. 英语等级（English Level）标准化与硬性匹配

### 4.1 允许值集合
系统将英语等级统一成 5 个等级：

* `basic`, `pre`, `intermediate`, `upper`, `fluent`

### 4.2 归一化逻辑
归一化在 `src/llm_service.py` 完成（适用于数据集原始值与LLM输出值），具备如下特性：

* 允许值直接透传（大小写/空白做清洗）
* 常见同义写法映射（如 `native`、`c2` → `fluent`）
* 数据集扩展值兜底（如 `no_english` → `basic`）

### 4.3 硬性匹配规则（严格等级比较）
若 JD 指定 `english_level`，候选人必须满足：

* `rank(candidate) >= rank(required)`

其中 rank 依据上述五级从低到高的序关系计算。若 JD 未指定则该项视为通过。

单测覆盖见 `test_english_level.py`。

## 5. LLM 结构化抽取（JD 与 Resume）

### 5.1 服务接口
LLM 调用封装在 `src/llm_service.py`：

* `parse_resume(resume_text)`：将候选人 `Long Description` 抽取为结构化 JSON
* `analyze_jd(jd_text)`：将 JD 抽取为 `hard_requirements` 与 `soft_requirements`

### 5.2 JD 输出结构
`analyze_jd` 输出结构（关键字段）：

* `hard_requirements.min_experience_years`：最低年限（默认 `0`）
* `hard_requirements.required_skills`：必须技能短语列表（默认 `[]`）
* `hard_requirements.education`：学历要求（默认 `null`，当前匹配逻辑未作为硬门槛参与计分）
* `hard_requirements.english_level`：英语等级（必须是五级之一或 `null`）
* `soft_requirements.traits`：软性特质列表（默认 `[]`）
* `soft_requirements.preferred`：加分偏好列表（默认 `[]`）

### 5.3 简历输出结构
`parse_resume` 输出结构在 `src/llm_service.py` 的 prompt 中定义（schema_version=2），包含 `profile/education/work_experience/projects/skills_certs/...` 等字段。系统后续计算主要用到 `english_level` 与 `tech_skills` 等。

### 5.4 调用与超时
LLM 默认使用 ModelScope 的 OpenAI 兼容接口：

* `BASE_URL`：`https://api-inference.modelscope.cn/v1/chat/completions`
* `model`：`Qwen/Qwen2.5-72B-Instruct`
* `timeout`：120 秒

当前实现将 API Key 存放在 `src/llm_service.py` 常量中，建议在生产化时改为环境变量注入，避免密钥泄露风险。

## 6. 匹配与评分（Hard / Soft / Final）

### 6.1 处理总览
核心匹配逻辑在 `src/matcher.py` 的 `SmartMatcher.match()`：

1. LLM 解析 JD 得到 `hard_requirements` 与 `soft_requirements`
2. 遍历候选人，计算：
   * `hard_pass_rate`：硬性条件通过率（0~1）
   * `soft_score`：软性相似度得分（0~1）
3. 合成最终得分：
   * `final_score = (hard_pass_rate*0.7 + soft_score*0.3) * 100`
4. 按 `final_score` 降序排序（并以经验年限做简单 tie-break），输出 Top 500

### 6.2 Hard：经验年限
若 JD 指定 `min_experience_years`：

* 候选人 `Experience Years >= min_experience_years` 视为通过，否则不通过

该项参与 `hard_pass_rate` 计算。

### 6.3 Hard：英语等级
若 JD 指定 `english_level`：

* 使用 `LLMService.english_level_satisfies(candidate, required)` 判定是否通过

候选人等级来源优先级：

1. `structured.profile.english_level`
2. `structured.english_level`
3. 原始列 `English Level`

### 6.4 Hard：必须技能（短语级语义匹配 + 覆盖率门槛）
对 `required_skills` 与候选人的 `tech_skills` 进行短语级相似度匹配（目标：禁止子串规则，允许语义近似表达）：

* 技能向量化：字符 n-gram TF-IDF（`char_wb`, `ngram_range=(3,5)`）
* 对每个 required skill，计算其与候选技能集合的余弦相似度，取最大值
* 相似度 >= `skill_match_threshold` 计为匹配
* 匹配覆盖率需达到 `>= 0.6` 才认为“技能硬门槛通过”

当前默认参数（见 `src/matcher.py` 初始化）：

* `skill_match_threshold = 0.3`
* 覆盖率门槛 `0.6`

### 6.5 Soft：软性特质（分块相似度 + 单调映射增强）
软性要求（traits/preferred）通常是短句且分散，直接与整段简历比较会被“长文本稀释”。系统采取：

1. 将 `traits + preferred` 合并为一个查询串 `soft_query`
2. 将候选 `Long Description` 做滑窗分块（默认 80 词窗口，40 词重叠，上限 50 块）
3. 对 `soft_query` 与每块计算余弦相似度，取最大值作为 `raw_sim`
4. 用单调凸映射函数拉开差异，得到 `soft_score`：
   * `soft_score = (1 - exp(-k*raw_sim)) / (1 - exp(-k))`

默认参数：

* `soft_similarity_sharpness = 4.0`（k 越大，越强调高相似度的区分）

### 6.6 Final：综合分与输出字段
每个候选人的输出（供 UI 展示）包含：

* `total_score`：综合得分（0~100）
* `hard_pass_rate`：硬性通过率（0~100）
* `soft_score`：软性得分（0~1，保留两位）
* `english_level`：候选人英语等级（归一化后）
* `skills/education/experience/projects/certifications`：用于解释与复核的关键信息

## 7. 缓存与容错

### 7.1 缓存分层
结构化解析结果由 `src/cache_manager.py` 管理：

* Redis（可选，7 天过期）作为一级缓存
* SQLite（默认，`parsed_data.db`）作为二级缓存

缓存 key 由 `resume_id` 与 `content_hash` 共同确定，避免因输入文本变化导致脏读。

### 7.2 LLM 失败熔断（数据加载阶段）
在 `src/data_loader.py` 里维护 LLM 调用失败计数，达到阈值后临时禁用 LLM，避免在网络/额度异常时长时间阻塞批处理流程。

## 8. Web 服务与交互

### 8.1 路由
Flask 入口为 `app.py`：

* `GET /`：渲染输入页面
* `POST /match`：接收 JD 文本，调用 `matcher.match(jd_text)`，将结果渲染到模板

### 8.2 展示层
模板 `templates/index.html` 展示：

* Top 推荐列表
* 全量候选列表（包含 English level、Hard/Soft 分数等字段）

## 9. 运行与测试

### 9.1 安装依赖
依赖以 `requirements.txt` 为准（Python 环境）。

### 9.2 启动 Web
在项目根目录：

* `python app.py`
* 访问 `http://127.0.0.1:5000/`

### 9.3 仅重跑数据加载（触发解析与缓存）

* `python src/data_loader.py`

### 9.4 运行单测

* `python -m unittest`

## 10. 参数调优建议

* `skill_match_threshold`：提升可减少误报但可能降低召回；降低可提高召回但可能引入泛匹配
* 技能覆盖率门槛（当前 0.6）：岗位越“刚性”，建议越高；岗位越“宽泛”，可适当降低
* 分块参数（80/40）：文本越长越复杂，可适当增大窗口；若软性证据很短，窗口偏小更敏感
* `soft_similarity_sharpness`：k 越大越强调“高匹配者领先”，但也可能让中等候选差异被压缩

## 11. 已知限制与扩展方向

* 当前语义表示使用 TF-IDF，适合原型验证与可控环境；若要跨语言/跨表达鲁棒性更强，可替换为 embedding 模型并接入向量库
* `VectorStore` 已提供 Chroma 可选实现，但当前匹配流程主要采用逐候选打分；可扩展为“先检索 Top-K 再精排”的两阶段体系
* 目前 `initialize()` 默认按 `position_filter="Data Engineer"` 过滤候选人；若要支持全岗位，需要调整加载策略与 UI 交互

