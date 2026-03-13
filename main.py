import os
import json
from dotenv import load_dotenv
from openai import OpenAI

# 1. 加载配置
load_dotenv()
client = OpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL")
)

# 2. 准备一段真实的测试招聘数据 (JD)
sample_jd = """
岗位名称：高级大数据开发工程师
岗位职责：
1. 负责公司 PB 级海量数据的实时和离线处理，构建企业级数据仓库。
2. 优化现有基于 Flink 的实时计算链路。
任职要求：
1. 本科及以上学历，计算机科学与技术、软件工程或数学等相关专业。
2. 3年以上大数据开发经验，精通 Java 或 Python。
3. 深入理解 Hadoop 体系，熟练使用 Spark、Hive、Kafka、Flink 等大数据组件。
4. 熟悉 MySQL 等关系型数据库。
"""

# 3. 编写核心 Prompt (提示词工程：定义规则并强制输出 JSON)
system_prompt = """
你是一个专业的大数据领域知识图谱抽取专家。
请从用户提供的招聘描述(JD)中抽取实体(Entity)和关系(Relation)。

【抽取规则】
1. 实体类型仅限：岗位、技能、专业、学历。
2. 关系类型仅限：要求技能、对口专业、要求学历。
3. 实体规范化（重要）：请务必对抽取的实体名称进行规范化和去重。
   - 学历规范化：如遇到“本科及以上”、“大学本科”等，统一规范输出为“本科”。
   - 技能规范化：如遇到“熟练使用 MySQL”、“精通 MySQL”，统一规范输出为“MySQL”。不要带修饰词。

【输出格式】
你必须严格输出一个 JSON 格式的字符串，不要有任何额外的解释文字（不要 Markdown 格式的 ```json 标记，直接输出纯 JSON）。格式如下：
{
  "entities": [
    {"label": "实体类型", "name": "实体名称"}
  ],
  "relations": [
    {"source": "头实体名称", "target": "尾实体名称", "type": "关系类型"}
  ]
}
"""

def extract_kg(text):
    print("⏳ 正在让大模型阅读 JD 并抽取知识图谱...\n")
    try:
        response = client.chat.completions.create(
            # 确保这里是你刚刚跑通的那个模型 ID (比如 deepseek-ai/DeepSeek-V3)
            model="Pro/zai-org/GLM-4.7", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请抽取以下 JD 的知识图谱数据：\n{text}"}
            ],
            temperature=0.1 # 抽取任务必须保持低温度，保证严谨性
        )
        
        # 获取大模型的文本回复
        result_text = response.choices[0].message.content.strip()
        
        # 尝试将其解析为 Python 字典，验证是不是合法的 JSON
        parsed_json = json.loads(result_text)
        print("✅ 抽取成功！大模型输出的结构化数据如下：")
        print(json.dumps(parsed_json, indent=4, ensure_ascii=False))
        
    except json.JSONDecodeError:
        print("❌ 解析 JSON 失败，大模型可能没有严格按照格式输出。它的原始回复是：\n", result_text)
    except Exception as e:
        print("❌ 调用发生错误：", e)

if __name__ == "__main__":
    extract_kg(sample_jd)