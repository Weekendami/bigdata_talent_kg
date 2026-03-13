# 大数据人才需求知识图谱项目规格说明书 (Spec)

## 1. 项目目标
构建一个基于 LLM 的大数据领域人才需求知识图谱，实现从招聘数据的自动采集、知识抽取、图谱构建到可视化展示的全流程。

## 2. 系统架构
系统由四个主要模块组成：
1.  **数据采集模块 (Data Acquisition)**: 负责从招聘网站获取原始数据。
2.  **知识抽取模块 (Knowledge Extraction)**: 利用 LLM 从非结构化文本中抽取实体和关系。
3.  **知识融合与存储模块 (Knowledge Fusion & Storage)**: 处理实体对齐，并将数据存储到 Neo4j。
4.  **可视化模块 (Visualization)**: 提供用户交互界面，展示图谱和分析结果。

## 3. 技术栈
-   **编程语言**: Python 3.10+
-   **依赖管理**: `uv`
-   **爬虫框架**: Scrapy / Selenium
-   **LLM 接口**: OpenAI SDK (兼容 ZhipuAI/DeepSeek)
-   **图数据库**: Neo4j Community Edition
-   **可视化**: Streamlit + PyVis / ECharts
-   **微调框架**: PEFT (LoRA), Transformers

## 4. 数据模型 (Ontology)
### 4.1 实体 (Nodes)
-   `Position` (岗位): 如 "大数据开发工程师", "数据分析师"
-   `Skill` (技能): 如 "Python", "Hadoop", "Spark", "SQL"
-   `Major` (专业): 如 "计算机科学与技术", "统计学", "软件工程"
-   `Degree` (学历): 如 "本科", "硕士", "博士"
-   `Location` (地点): 如 "北京", "上海", "杭州"
-   `Company` (公司): 如 "字节跳动", "阿里巴巴"

### 4.2 关系 (Edges)
-   `(:Position)-[:REQUIRE_SKILL]->(:Skill)`: 岗位要求掌握某技能
-   `(:Position)-[:PREFER_MAJOR]->(:Major)`: 岗位优先考虑某专业
-   `(:Position)-[:REQUIRE_DEGREE]->(:Degree)`: 岗位要求最低学历
-   `(:Position)-[:LOCATED_IN]->(:Location)`: 岗位工作地点
-   `(:Position)-[:BELONGS_TO]->(:Company)`: 岗位所属公司

## 5. 模块详细设计

### 5.1 数据采集模块
-   **输入**: 招聘网站 URL 列表，关键词（如 "大数据"）。
-   **处理**: 模拟浏览器行为或直接请求 API，解析 HTML。
-   **输出**: CSV 文件 (`data/raw_jobs.csv`)，包含 `title`, `salary`, `job_description`, `company`, `location` 等列。方便后续使用 Pandas 进行清洗。

### 5.2 知识抽取模块
-   **输入**: 清洗后的 JSONL 数据 (`data/cleaned_jobs.jsonl`)。
-   **处理**:
    -   读取 CSV 进行去重、格式化清洗，转换为 JSONL。
    -   构造 Prompt，包含 Few-Shot 示例。
    -   调用 LLM API (GLM-4 / DeepSeek)。
    -   解析 LLM 返回的 JSON。
    -   验证 JSON 格式符合 Schema。
-   **输出**: 结构化的实体与关系列表 (JSON)。

### 5.3 知识融合与存储模块
-   **输入**: 结构化实体与关系列表。
-   **处理**:
    -   **实体对齐**: 使用规则或 Embedding 将 "Python开发" 和 "Python编程" 合并为 "Python"。
    -   **去重**: 移除重复的实体和关系。
    -   **Neo4j 导入**: 使用 `neo4j` Python 驱动批量插入节点和边。
-   **输出**: Neo4j 数据库中的图谱。

### 5.4 可视化模块
-   **输入**: 用户查询（如岗位名称）。
-   **处理**: 查询 Neo4j 数据库，获取相关子图。
-   **输出**: 交互式网络图 (Streamlit 页面)。

## 6. 微调策略 (可选)
-   **数据集**: 人工标注 100-200 条高质量 JD 抽取结果。
-   **方法**: LoRA 微调 ChatGLM3-6B 或 Llama-3-8B。
-   **目标**: 提升特定领域实体（如大数据组件名称）的识别准确率。
