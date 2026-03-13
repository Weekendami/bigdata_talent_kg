import json

def build_prompt(job_description: str) -> str:
    """
    构建用于信息抽取的 Prompt
    """
    system_prompt = """你是一个专业的大数据领域招聘信息分析专家。请从给定的招聘职位描述（JD）中提取关键信息，并严格按照 JSON 格式输出。

提取目标：
1. position_name: 岗位名称
2. skills: 岗位要求的核心技能（如 Hadoop, Spark, Python, Java 等），如果是复合技能请拆分。
3. majors: 优先考虑的专业（如 计算机科学, 统计学）。
4. degree: 最低学历要求（如 本科, 硕士）。
5. location: 工作城市。
6. min_salary: 最低薪资（单位：k，例如 20k -> 20）。
7. max_salary: 最高薪资（单位：k，例如 40k -> 40）。

注意事项：
- 如果没有明确提到的字段，请返回 null 或空列表。
- 技能名称请尽量标准化（如 "Python编程" -> "Python"）。
- 不要输出任何 Markdown 标记或额外的解释性文字，只输出纯 JSON。
"""

    few_shot_example = """
示例输入：
【岗位名称】大数据开发工程师
【薪资】20-40K
【地点】北京
【职位描述】
1. 负责数据仓库的建设和维护；
2. 精通 Hadoop 生态圈技术，如 HDFS, MapReduce, Hive, HBase 等；
3. 熟悉 Spark/Flink 等流式计算框架；
4. 熟练掌握 Java 或 Scala 语言；
5. 本科及以上学历，计算机相关专业。

示例输出：
{
    "position_name": "大数据开发工程师",
    "skills": [
        {"name": "Hadoop", "category": "大数据组件"},
        {"name": "HDFS", "category": "大数据组件"},
        {"name": "MapReduce", "category": "大数据组件"},
        {"name": "Hive", "category": "大数据组件"},
        {"name": "HBase", "category": "大数据组件"},
        {"name": "Spark", "category": "计算框架"},
        {"name": "Flink", "category": "计算框架"},
        {"name": "Java", "category": "编程语言"},
        {"name": "Scala", "category": "编程语言"}
    ],
    "majors": [{"name": "计算机科学与技术"}],
    "degree": {"name": "本科"},
    "location": {"city": "北京"},
    "min_salary": 20,
    "max_salary": 40
}
"""

    user_input = f"""
请分析以下招聘信息：
{job_description}
"""

    return f"{system_prompt}\n{few_shot_example}\n{user_input}"
