import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import vector_engine

if __name__ == "__main__":
    print("=== 开始初始化全量向量库 ===")
    vector_engine.build_or_update_index()
    print("=== 初始化结束 ===")
