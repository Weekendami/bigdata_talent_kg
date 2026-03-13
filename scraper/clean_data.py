import pandas as pd
import json
import os

# 路径配置
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DATA_PATH = os.path.join(BASE_DIR, 'data', 'raw_jobs.csv')
CLEANED_DATA_PATH = os.path.join(BASE_DIR, 'data', 'cleaned_jobs.jsonl')

def clean_and_convert():
    """
    读取 CSV，清洗数据，并转换为 JSONL 格式
    """
    if not os.path.exists(RAW_DATA_PATH):
        print(f"Error: {RAW_DATA_PATH} not found.")
        return

    try:
        # 读取 CSV
        df = pd.read_csv(RAW_DATA_PATH)
        print(f"Loaded {len(df)} raw records.")

        # 1. 去重 (根据公司和职位名称)
        initial_count = len(df)
        df.drop_duplicates(subset=['title', 'company', 'job_description'], inplace=True)
        print(f"Removed {initial_count - len(df)} duplicates.")

        # 2. 处理缺失值 (简单的填充或删除)
        df.fillna('', inplace=True)

        # 3. 简单的文本清洗 (可选：去除 HTML 标签等，这里假设爬虫已处理)
        # df['job_description'] = df['job_description'].apply(clean_text)

        # 4. 转换为 JSONL
        with open(CLEANED_DATA_PATH, 'w', encoding='utf-8') as f:
            for _, row in df.iterrows():
                record = row.to_dict()
                json_line = json.dumps(record, ensure_ascii=False)
                f.write(json_line + '\n')
        
        print(f"Successfully saved {len(df)} cleaned records to {CLEANED_DATA_PATH}")

    except Exception as e:
        print(f"Error during cleaning: {e}")

if __name__ == "__main__":
    clean_and_convert()
