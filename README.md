# 大数据人才需求知识图谱 (BigData Talent KG)

本项目旨在构建一个基于 LLM 的大数据领域人才需求知识图谱，从招聘网站获取数据，利用大模型抽取知识，并使用 Neo4j 存储和 Streamlit 可视化。

## 项目结构
- `scraper/`: 数据采集与清洗模块
  - `spider_main.py`: 招聘数据爬虫（含模拟数据生成）
  - `clean_data.py`: 数据清洗脚本 (CSV -> JSONL)
- `extraction/`: 知识抽取模块
  - `schema.py`: 实体与关系定义
  - `prompt_builder.py`: 提示词构建
  - `batch_extract.py`: 批量抽取脚本
- `knowledge/`: 知识存储模块
  - `neo4j_importer.py`: Neo4j 数据导入脚本
- `app/`: 可视化模块
  - `main_app.py`: Streamlit 可视化应用
- `data/`: 数据存储目录
  - `raw_jobs.csv`: 原始招聘数据
  - `cleaned_jobs.jsonl`: 清洗后的数据
  - `extracted_knowledge.jsonl`: 抽取出的结构化知识

## 快速开始

### 1. 环境准备
确保已安装 Python 3.10+ 和 `uv` 包管理工具。
```bash
uv sync
```

### 2. 配置环境变量
复制 `.env.example` (如果有) 或直接编辑 `.env` 文件，填入你的 API Key 和 Neo4j 配置：
```ini
LLM_API_KEY="your_api_key"
LLM_BASE_URL="https://api.openai.com/v1"  # 或其他兼容接口
NEO4J_URI="bolt://localhost:7687"
NEO4J_USER="neo4j"
NEO4J_PASSWORD="password"
```

### 3. 数据获取
运行爬虫获取数据（默认生成模拟数据，如需真实爬取请配置 ChromeDriver）：
```bash
uv run python scraper/spider_main.py
```
这将在 `data/` 目录下生成 `raw_jobs.csv`。

### 4. 数据清洗
将 CSV 转换为 JSONL 格式：
```bash
uv run python scraper/clean_data.py
```

### 5. 知识抽取
利用 LLM 抽取实体和关系：
```bash
uv run python extraction/batch_extract.py
```
这将生成 `data/extracted_knowledge.jsonl`。

### 6. 导入图数据库
确保 Neo4j 服务已启动，然后运行导入脚本：
```bash
uv run python knowledge/neo4j_importer.py
```

### 7. 可视化展示
启动 Streamlit 应用：
```bash
uv run streamlit run app/main_app.py
```
浏览器访问 http://localhost:8501 查看图谱。

## 常见问题
- **Selenium 报错**: 请确保已安装 Chrome 浏览器和对应版本的 ChromeDriver，并将其加入系统 PATH。
- **Neo4j 连接失败**: 请检查 Neo4j 服务是否启动，以及 `.env` 中的账号密码是否正确。如果无法连接，应用将使用模拟数据进行演示。
