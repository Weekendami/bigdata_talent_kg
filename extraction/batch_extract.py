import json
import os
import time
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from prompt_builder import build_prompt
from schema import JobExtractionResult

# 加载环境变量
load_dotenv()
API_KEY = os.getenv("LLM_API_KEY")
BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")

# 路径配置
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLEANED_DATA_PATH = os.path.join(BASE_DIR, 'data', 'cleaned_jobs.jsonl')
EXTRACTED_DATA_PATH = os.path.join(BASE_DIR, 'data', 'extracted_knowledge.jsonl')

def init_client():
    if not API_KEY:
        print("Warning: LLM_API_KEY not found in .env. Skipping API calls.")
        return None
    return OpenAI(api_key=API_KEY, base_url=BASE_URL)

def extract_knowledge(client, job_data):
    """
    调用 LLM 提取知识
    """
    if not client:
        return None

    # 构建 Prompt
    jd_text = f"【岗位名称】{job_data.get('title', '')}\n【薪资】{job_data.get('salary', '')}\n【地点】{job_data.get('location', '')}\n【职位描述】\n{job_data.get('job_description', '')}"
    prompt = build_prompt(jd_text)

    try:
        response = client.chat.completions.create(
            model="Pro/zai-org/GLM-4.7",  # 使用 main.py 中提到的模型，或者是 .env 中配置的模型
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print(f"Error extracting knowledge: {e}")
        return None

def batch_process(limit=10):
    """
    批量处理清洗后的数据
    """
    if not os.path.exists(CLEANED_DATA_PATH):
        print(f"Error: {CLEANED_DATA_PATH} not found.")
        return

    client = init_client()
    if not client:
        return

    processed_count = 0
    results = []

    print(f"Starting extraction pipeline (Limit: {limit})...")
    
    with open(CLEANED_DATA_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            if processed_count >= limit:
                break
            
            try:
                job_data = json.loads(line)
                print(f"Extracting job {processed_count + 1}: {job_data.get('title', 'Unknown')}")
                
                extracted_data = extract_knowledge(client, job_data)
                
                if extracted_data:
                    # 合并原始信息以便后续使用
                    extracted_data['original_id'] = processed_count
                    results.append(extracted_data)
                
                processed_count += 1
                time.sleep(1)  # 避免触发 API 速率限制

            except json.JSONDecodeError:
                continue

    # 保存结果
    if results:
        with open(EXTRACTED_DATA_PATH, 'w', encoding='utf-8') as f:
            for res in results:
                f.write(json.dumps(res, ensure_ascii=False) + '\n')
        print(f"Successfully extracted {len(results)} records to {EXTRACTED_DATA_PATH}")
    else:
        print("No results extracted.")

if __name__ == "__main__":
    batch_process(limit=5)  # 默认处理前 5 条用于测试
