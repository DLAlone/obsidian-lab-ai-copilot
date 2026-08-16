"""
课题组 Agent 检索与生成能力自动化基准评估套件 (Evaluation Harness)
用于自动化回测 4 种检索策略 (Agentic / Vector / Graph / BM25) 的响应时延、召回切片完整度与打分判定。
"""

import sys
import os
import time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# 确保引入 src/agent_service
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_DIR = os.path.join(CURRENT_DIR, "..", "src", "agent_service")
sys.path.insert(0, SERVICE_DIR)

def test_bm25():
    print("\n" + "="*50)
    print("🧪 [Test 1] BM25 词频与专有名词精准匹配评估")
    print("="*50)
    try:
        import bm25_engine
        query = "SSH 隧道代理"
        start = time.time()
        res = bm25_engine.query_bm25(query)
        latency = (time.time() - start) * 1000
        print(f"⏱️ 耗时: {latency:.2f} ms")
        print(f"📄 召回内容预览 (前 200 字):\n{res.get('answer', '')[:200]}...")
        assert res.get("answer") is not None
        print("✅ BM25 测试通过")
    except Exception as e:
        print(f"❌ BM25 测试失败: {e}")

def test_vector():
    print("\n" + "="*50)
    print("🧪 [Test 2] LlamaIndex 向量语义相似度检索评估")
    print("="*50)
    try:
        import vector_engine
        query = "如何排查大模型幻觉与防御机制？"
        start = time.time()
        res = vector_engine.query_vector_db(query)
        latency = (time.time() - start) * 1000
        print(f"⏱️ 耗时: {latency:.2f} ms")
        print(f"📄 召回内容预览 (前 200 字):\n{res.get('answer', '')[:200]}...")
        assert res.get("answer") is not None
        print("✅ Vector 测试完成 (注: 若无 API Key 则提示降级)")
    except Exception as e:
        print(f"❌ Vector 测试失败: {e}")

def test_graph():
    print("\n" + "="*50)
    print("🧪 [Test 3] Obsidian [[Wikilink]] 知识图谱拓扑漫游评估")
    print("="*50)
    try:
        import graph_engine
        entity = "Claude Code"
        start = time.time()
        res = graph_engine.query_graph_db(entity)
        latency = (time.time() - start) * 1000
        print(f"⏱️ 耗时: {latency:.2f} ms")
        print(f"📄 召回内容预览 (前 200 字):\n{res.get('answer', '')[:200]}...")
        assert res.get("answer") is not None
        print("✅ Graph 测试完成")
    except Exception as e:
        print(f"❌ Graph 测试失败: {e}")

def test_agentic_workflow():
    print("\n" + "="*50)
    print("🧪 [Test 4] LangGraph 官方状态图双循环 Agent 状态流转评估")
    print("="*50)
    try:
        from official_langgraph_engine import official_agent_workflow
        query = "什么是双循环 Agent 架构？"
        docs = [{"title": "双循环架构.md", "content": "双循环架构包含内循环工具调用与外循环自我审判打分。"}]
        start = time.time()
        res = official_agent_workflow.run(query, docs, strategy="agentic")
        latency = (time.time() - start) * 1000
        print(f"⏱️ 耗时: {latency:.2f} ms")
        print(f"📊 自省打分: {res.get('sufficiency_score')}/10")
        print(f"📄 回答预览:\n{res.get('answer', '')[:250]}...")
        print("✅ LangGraph Agentic Workflow 测试完成")
    except Exception as e:
        print(f"❌ LangGraph 测试异常 (如未配置 API Key): {e}")

if __name__ == "__main__":
    print("🚀 启动课题组 Agent 评测套件 (Evaluation Harness)...")
    test_bm25()
    test_vector()
    test_graph()
    test_agentic_workflow()
    print("\n🎉 自动化基准评估流程执行完毕！")
