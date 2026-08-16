import graph_engine
import time

if __name__ == "__main__":
    print("=== 初始化本地原生知识图谱 (Graph RAG) ===")
    start = time.time()
    graph_engine.build_or_update_graph()
    end = time.time()
    print(f"=== 拓扑提取耗时: {end - start:.2f} 秒 ===")
