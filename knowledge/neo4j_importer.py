import json
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# 路径配置
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTRACTED_DATA_PATH = os.path.join(BASE_DIR, 'data', 'extracted_knowledge.jsonl')

class KnowledgeGraphImporter:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def create_constraints(self):
        """创建唯一性约束，防止重复节点"""
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (j:Job) REQUIRE j.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Skill) REQUIRE s.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (m:Major) REQUIRE m.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Degree) REQUIRE d.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (l:Location) REQUIRE l.city IS UNIQUE",
        ]
        with self.driver.session() as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                    print(f"Constraint created: {constraint}")
                except Exception as e:
                    print(f"Error creating constraint: {e}")

    def import_data(self):
        """导入数据到 Neo4j"""
        if not os.path.exists(EXTRACTED_DATA_PATH):
            print(f"Error: {EXTRACTED_DATA_PATH} not found.")
            return

        with open(EXTRACTED_DATA_PATH, 'r', encoding='utf-8') as f:
            data = [json.loads(line) for line in f]

        print(f"Starting import of {len(data)} records...")
        
        with self.driver.session() as session:
            for item in data:
                try:
                    session.execute_write(self._create_job_graph, item)
                except Exception as e:
                    print(f"Error importing item: {item.get('position_name', 'Unknown')}, {e}")
        
        print("Import completed.")

    @staticmethod
    def _create_job_graph(tx, item):
        # 1. 创建 Job 节点
        query_job = """
        MERGE (j:Job {name: $position_name})
        SET j.min_salary = $min_salary, j.max_salary = $max_salary
        RETURN j
        """
        tx.run(query_job, 
               position_name=item.get('position_name', 'Unknown'),
               min_salary=item.get('min_salary'),
               max_salary=item.get('max_salary'))

        # 2. 创建 Skill 节点并建立关系
        if item.get('skills'):
            for skill in item['skills']:
                query_skill = """
                MATCH (j:Job {name: $position_name})
                MERGE (s:Skill {name: $skill_name})
                SET s.category = $category
                MERGE (j)-[:REQUIRE_SKILL]->(s)
                """
                tx.run(query_skill, 
                       position_name=item.get('position_name', 'Unknown'),
                       skill_name=skill.get('name', 'Unknown'),
                       category=skill.get('category'))

        # 3. 创建 Major 节点并建立关系
        if item.get('majors'):
            for major in item['majors']:
                query_major = """
                MATCH (j:Job {name: $position_name})
                MERGE (m:Major {name: $major_name})
                MERGE (j)-[:PREFER_MAJOR]->(m)
                """
                tx.run(query_major, 
                       position_name=item.get('position_name', 'Unknown'),
                       major_name=major.get('name', 'Unknown'))

        # 4. 创建 Degree 节点并建立关系
        if item.get('degree'):
            degree_name = item['degree'].get('name')
            if degree_name:
                query_degree = """
                MATCH (j:Job {name: $position_name})
                MERGE (d:Degree {name: $degree_name})
                MERGE (j)-[:REQUIRE_DEGREE]->(d)
                """
                tx.run(query_degree, 
                       position_name=item.get('position_name', 'Unknown'),
                       degree_name=degree_name)

        # 5. 创建 Location 节点并建立关系
        if item.get('location'):
            city_name = item['location'].get('city')
            if city_name:
                query_location = """
                MATCH (j:Job {name: $position_name})
                MERGE (l:Location {city: $city_name})
                MERGE (j)-[:LOCATED_IN]->(l)
                """
                tx.run(query_location, 
                       position_name=item.get('position_name', 'Unknown'),
                       city_name=city_name)

if __name__ == "__main__":
    importer = KnowledgeGraphImporter(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    try:
        importer.create_constraints()
        importer.import_data()
    finally:
        importer.close()
