import streamlit as st
from neo4j import GraphDatabase
import os
from pyvis.network import Network
import streamlit.components.v1 as components
from dotenv import load_dotenv

load_dotenv()

# Neo4j 配置
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

class Neo4jConnection:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def verify(self):
        self.driver.verify_connectivity()

    def close(self):
        self.driver.close()

    def query(self, query, parameters=None):
        with self.driver.session() as session:
            result = session.run(query, parameters)
            return [record for record in result]

def get_graph_data(conn, job_title):
    """
    查询指定岗位的技能图谱数据
    """
    cypher_query = """
    MATCH (j:Job {name: $job_title})-[r:REQUIRE_SKILL]->(s:Skill)
    RETURN j.name as job, s.name as skill, s.category as category
    LIMIT 50
    """
    try:
        results = conn.query(cypher_query, parameters={"job_title": job_title})
        return results
    except Exception as e:
        st.error(f"查询出错: {e}")
        return []

def visualize_graph(data, job_title):
    """
    使用 PyVis 可视化图谱
    """
    # 初始化网络图，启用 CDN 资源以确保在 Streamlit 中正常显示
    net = Network(height="600px", width="100%", bgcolor="#222222", font_color="white", cdn_resources='remote')
    
    # 添加中心节点 (Job)
    net.add_node(job_title, label=job_title, color="#ff5722", size=30)
    
    for record in data:
        skill = record["skill"]
        category = record["category"]
        
        # 根据类别设置颜色
        color = "#00b0ff" if category == "编程语言" else "#00e676"
        
        net.add_node(skill, label=skill, color=color, size=20)
        net.add_edge(job_title, skill, title="REQUIRE_SKILL")
    
    # 保存并读取 HTML
    net.save_graph("graph.html")
    with open("graph.html", "r", encoding="utf-8") as f:
        html_source = f.read()
    return html_source

def main():
    st.set_page_config(page_title="大数据人才需求知识图谱", layout="wide")
    st.title("📊 大数据人才需求知识图谱可视化")

    # Sidebar: 配置
    st.sidebar.header("数据库连接")
    uri = st.sidebar.text_input("Neo4j URI", value=NEO4J_URI)
    user = st.sidebar.text_input("Username", value=NEO4J_USER)
    password = st.sidebar.text_input("Password", value=NEO4J_PASSWORD, type="password")
    
    conn = None
    try:
        conn = Neo4jConnection(uri, user, password)
        conn.verify()
        st.sidebar.success("已连接到 Neo4j")
    except Exception as e:
        conn = None
        st.sidebar.warning(f"无法连接到 Neo4j (将使用模拟数据演示): {e}")

    # Main Area
    search_term = st.text_input("🔍 输入岗位名称查询 (例如: 大数据开发工程师)", "大数据开发工程师")
    
    if st.button("生成图谱"):
        if conn:
            data = get_graph_data(conn, search_term)
        else:
            # 模拟数据
            data = [
                {"job": search_term, "skill": "Hadoop", "category": "大数据组件"},
                {"job": search_term, "skill": "Spark", "category": "计算框架"},
                {"job": search_term, "skill": "Python", "category": "编程语言"},
                {"job": search_term, "skill": "Java", "category": "编程语言"},
                {"job": search_term, "skill": "SQL", "category": "数据库"},
                {"job": search_term, "skill": "Hive", "category": "大数据组件"},
            ]
            st.info("正在使用模拟数据展示...")

        if data:
            st.subheader(f"Job: {search_term}")
            html_source = visualize_graph(data, search_term)
            components.html(html_source, height=600)
            
            # 统计展示
            st.subheader("技能统计")
            skills = [d["skill"] for d in data]
            st.write(f"共找到 {len(skills)} 个关联技能: {', '.join(skills)}")
        else:
            st.warning("未找到相关数据，请尝试其他岗位名称。")

    if conn:
        conn.close()

if __name__ == "__main__":
    main()
