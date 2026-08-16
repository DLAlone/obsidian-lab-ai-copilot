import os
from llama_index.readers.obsidian import ObsidianReader
from llama_index.core import Settings, KnowledgeGraphIndex, StorageContext, PromptTemplate
from llama_index.core.graph_stores import SimpleGraphStore

# ==========================================
# 1. 基础配置
# ==========================================
SILICONFLOW_API_KEY = os.environ.get("SILICONFLOW_API_KEY", "")
SILICONFLOW_BASE_URL = os.environ.get("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")



# 当不需要借助 LLM 瞎猜三元组时，我们可以配置 chunk_size
Settings.chunk_size = 2048

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GRAPH_DB_PATH = os.path.join(BASE_DIR, "graph_data")
SHARED_VAULT_PATH = os.path.join(BASE_DIR, "shared_vault")

# ==========================================
# 2. Native LlamaIndex 图谱构建
# ==========================================
def build_or_update_graph():
    """使用 LlamaIndex 官方原生 KnowledgeGraphIndex 进行全库拓扑构建"""
    target_dir = SHARED_VAULT_PATH
    has_files = False
    if os.path.exists(target_dir):
        for r, d, files in os.walk(target_dir):
            if any(f.endswith(".md") for f in files):
                has_files = True
                break
                
    if not has_files:
        sample_path = os.path.join(BASE_DIR, "sample_vault")
        if os.path.exists(sample_path):
            target_dir = sample_path
            print(f"INFO: shared_vault is empty, falling back to sample_vault: {target_dir}")

    # 使用官方插件提取内容与双链元数据
    reader = ObsidianReader(target_dir)
    documents = reader.load_data()
    
    if not documents:
        print("WARN: Both shared_vault and sample_vault are empty, skipping graph build.")
        return False
        
    # 定义原生的提取函数：直接从 ObsidianReader 提取的元数据里拿关系，绝对不让大模型瞎猜！
    def custom_triplet_extractor(text: str):
        # 这个函数实际上会被内部调用，但为了强制使用元数据，我们在建库时做一点处理
        return []

    # 初始化本地原生的图谱存储引擎
    graph_store = SimpleGraphStore()
    storage_context = StorageContext.from_defaults(graph_store=graph_store)
    
    # 强制将 Obsidian 双链转化为标准知识图谱的三元组 (Entity -> Relation -> Entity)
    for doc in documents:
        source_node = doc.metadata.get('note_name', 'Unknown')
        wikilinks = doc.metadata.get('wikilinks', [])
        for link in wikilinks:
            # 建立物理关联: (当前笔记, "提到/引用", 目标双链)
            graph_store.upsert_triplet(source_node, "引用", link)
            
    # 使用 LlamaIndex 原生的 KnowledgeGraphIndex 进行封装
    index = KnowledgeGraphIndex.from_documents(
        documents,
        kg_triplet_extract_fn=custom_triplet_extractor, # 关闭 LLM 猜测
        storage_context=storage_context,
        include_embeddings=False # 纯拓扑，不用向量
    )
    
    # 保存原生索引
    index.storage_context.persist(persist_dir=GRAPH_DB_PATH)
    print(f"SUCCESS: Native LlamaIndex Graph database built!")
    return True

# ==========================================
# 3. Native LlamaIndex 拓扑检索
# ==========================================
def query_graph_db(query: str, scope: str = "global") -> dict:
    """使用原生的 Retriever 进行图谱漫游检索"""
    try:
        if not os.path.exists(os.path.join(GRAPH_DB_PATH, "graph_store.json")):
            return {"answer": "⚠️ 图谱数据库未初始化，请先构建拓扑网络。"}
            
        # 恢复原生存储与索引
        storage_context = StorageContext.from_defaults(persist_dir=GRAPH_DB_PATH)
        index = KnowledgeGraphIndex.from_documents(
            [], 
            storage_context=storage_context
        )
        
        # 使用 LlamaIndex 原生的检索器
        retriever = index.as_retriever(
            include_text=True, 
            embedding_mode="none",
            graph_store_query_depth=2, # 自动发散到 2 度邻居
            similarity_top_k=3
        )
            
        # 执行原生检索
        nodes = retriever.retrieve(query)
        
        raw_texts = []
        for i, node in enumerate(nodes):
            file_name = node.metadata.get("file_name", "Unknown") if node.metadata else "Unknown"
            raw_texts.append(f"### [Graph Node {i+1}] Source: {file_name}\n{node.text}")
                
        raw_string = "\n\n".join(raw_texts)
        
        return {"answer": raw_string}
        
    except Exception as e:
        return {"answer": f"⚠️ 拓扑网络检索失败：{str(e)}\n\n(提示：请确保知识库已构建网络)"}

if __name__ == "__main__":
    build_or_update_graph()
