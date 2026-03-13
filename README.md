# 大数据人才需求知识图谱

基于招聘数据、LLM 抽取和 Neo4j 的大数据岗位知识图谱项目。当前主流程已经覆盖：

- 招聘数据采集
- CSV 清洗为 JSONL
- 基于 LLM 的结构化知识抽取
- Neo4j 导入
- Streamlit 图谱可视化

当前最稳定的数据源是智联招聘。

## 项目结构

```text
bigdata_talent_kg/
├─ app/
│  └─ main_app.py                # Streamlit 可视化入口
├─ data/
│  ├─ zhaopin_jobs.csv           # 智联原始招聘数据
│  ├─ cleaned_jobs.jsonl         # 清洗后的 JSONL
│  └─ extracted_knowledge.jsonl  # LLM 抽取结果
├─ extraction/
│  ├─ schema.py                  # 抽取结果 Schema
│  ├─ prompt_builder.py          # Prompt 构造
│  └─ batch_extract.py           # 批量抽取
├─ knowledge/
│  └─ neo4j_importer.py          # Neo4j 导入
├─ scraper/
│  ├─ job_sites_scraper.py       # 多站点爬虫入口
│  └─ clean_data.py              # CSV 清洗为 JSONL
├─ AGENTS.md
├─ main.py
├─ pyproject.toml
└─ uv.lock
```

## 技术栈

- Python 3.13
- `uv`
- Selenium + lxml
- Pandas
- OpenAI SDK 兼容接口
- Neo4j
- Streamlit + PyVis

## 环境准备

安装依赖：

```powershell
uv sync
```

配置环境变量，创建 `.env`：

```ini
LLM_API_KEY="your_api_key"
LLM_BASE_URL="https://api.openai.com/v1"
NEO4J_URI="neo4j://127.0.0.1:7687"
NEO4J_USER="neo4j"
NEO4J_PASSWORD="your_password"
```

## 数据采集

### 智联招聘

当前推荐只使用智联招聘数据：

```powershell
uv run .\scraper\job_sites_scraper.py --site zhaopin --keyword 大数据 --city 上海 --pages 3 --concurrency 1 --headless --output .\data\zhaopin_jobs.csv
```

输出字段：

- `title`
- `company`
- `location`
- `salary`
- `experience`
- `degree`
- `tags`
- `job_description`
- `job_url`

### 前程无忧

项目中已经保留 `51job` 适配器，但目前详情页正文抓取仍不稳定，不建议作为主数据源推进整条 pipeline。

## 数据清洗

`clean_data.py` 默认读取 `data/raw_jobs.csv` 并输出 `data/cleaned_jobs.jsonl`。

如果你当前主要使用智联数据，建议先将 `data/zhaopin_jobs.csv` 复制或重命名为 `data/raw_jobs.csv`，再执行：

```powershell
uv run .\scraper\clean_data.py
```

清洗逻辑当前包括：

- 去重
- 缺失值填充
- CSV 转 JSONL

## 知识抽取

运行批量抽取：

```powershell
uv run .\extraction\batch_extract.py
```

该步骤会：

- 读取 `data/cleaned_jobs.jsonl`
- 构造 Prompt
- 调用 LLM 接口
- 输出 `data/extracted_knowledge.jsonl`

抽取结构由 [`extraction/schema.py`](/d:/project/bigdata_talent_kg/extraction/schema.py) 定义，核心字段包括：

- `position_name`
- `skills`
- `majors`
- `degree`
- `location`
- `min_salary`
- `max_salary`

## 导入 Neo4j

启动 Neo4j 后执行：

```powershell
uv run .\knowledge\neo4j_importer.py
```

当前会导入这些实体和关系：

- `Job`
- `Skill`
- `Major`
- `Degree`
- `Location`

关系包括：

- `REQUIRE_SKILL`
- `PREFER_MAJOR`
- `REQUIRE_DEGREE`
- `LOCATED_IN`

## 可视化

启动 Streamlit：

```powershell
uv run streamlit run .\app\main_app.py
```

默认地址：

```text
http://localhost:8501
```

如果 Neo4j 可连接，页面会查询真实图谱；否则会使用模拟数据演示。

## 当前推荐流程

推荐按下面顺序执行：

1. 抓取智联数据
2. 将抓取结果整理为 `data/raw_jobs.csv`
3. 执行清洗脚本生成 `cleaned_jobs.jsonl`
4. 执行 LLM 抽取生成 `extracted_knowledge.jsonl`
5. 导入 Neo4j
6. 启动 Streamlit 查看图谱

## 已知问题

- `scraper/clean_data.py` 当前默认读取 `data/raw_jobs.csv`，如果你直接产出的是 `data/zhaopin_jobs.csv`，需要先统一文件名或修改脚本
- `51job` 的职位详情正文抓取仍不稳定
- `extraction/batch_extract.py` 当前已导入 Schema，但还没有把 Pydantic 校验完整接入到抽取结果保存流程中
- 图数据库导入当前以 `Job` 为中心，尚未导入 `Company` 节点和 `BELONGS_TO` 关系

## 后续建议

- 将 `clean_data.py` 改为支持命令行传入输入/输出路径
- 在 `batch_extract.py` 中接入 `JobExtractionResult.model_validate(...)`
- 为 `51job` 单独补充详情接口或页面内嵌 JSON 解析
- 在 Neo4j 导入阶段增加 `Company` 节点
