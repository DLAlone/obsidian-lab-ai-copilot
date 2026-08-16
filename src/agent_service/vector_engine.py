import os
import chromadb
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.siliconflow import SiliconFlowEmbedding

# ==========================================
# 1. 配置 SiliconFlow API 与 LlamaIndex
# ==========================================
SILICONFLOW_API_KEY = os.environ.get("SILICONFLOW_API_KEY", "")
SILICONFLOW_BASE_URL = os.environ.get("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")

# 使用官方推荐配置，不再自己造轮子
# 配置嵌入模型 (Embedding)
Settings.embed_model = SiliconFlowEmbedding(
    model="BAAI/bge-m3",
    api_key=SILICONFLOW_API_KEY or "dummy-key-for-initialization",
    api_base=SILICONFLOW_BASE_URL
)



# ==========================================
# 2. 配置本地 ChromaDB 向量数据库
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DB_PATH = os.path.join(BASE_DIR, "chroma_data")
SHARED_VAULT_PATH = os.path.join(BASE_DIR, "shared_vault")

def get_storage_context(collection_name: str = "lab_knowledge"):
    """初始化 ChromaDB 并返回 LlamaIndex 的 StorageContext"""
    # 确保存储目录存在
    os.makedirs(CHROMA_DB_PATH, exist_ok=True)
    
    # 实例化一个持久化的 Chroma 客户端
    chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    
    # 创建或获取 Collection
    chroma_collection = chroma_client.get_or_create_collection(collection_name)
    
    # 包装为 LlamaIndex 的 VectorStore
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    return StorageContext.from_defaults(vector_store=vector_store)

# ==========================================
# 3. 核心功能：全库切片入库
# ==========================================
def build_or_update_index():
    """扫描 shared_vault 目录，切片并生成向量索引"""
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

    # LlamaIndex 内置的神器：自动读取目录下的所有文件
    documents = SimpleDirectoryReader(
        input_dir=target_dir, 
        recursive=True,
        required_exts=[".md"]
    ).load_data()
    
    if not documents:
        print("WARN: Both shared_vault and sample_vault are empty, skipping vector index build.")
        return False

    print(f"SUCCESS: Read {len(documents)} Markdown chunks, preparing to embed and store...")
    
    # 获取存储上下文
    storage_context = get_storage_context()
    
    # 执行 ETL：切片 -> Embedding API 转换 -> 存入 ChromaDB
    # VectorStoreIndex 会自动使用 Settings 里的 embed_model 和 chunk_size
    index = VectorStoreIndex.from_documents(
        documents, 
        storage_context=storage_context,
        show_progress=True
    )
    
    print("SUCCESS: Vector database build complete!")
    return True

# ==========================================
# 4. 核心功能：语义检索问答
# ==========================================
def query_vector_db(query: str, scope: str = "global") -> dict:
    """根据问题进行向量检索并返回原文本"""
    try:
        # 直接从现有的 ChromaDB 加载索引
        storage_context = get_storage_context()
        index = VectorStoreIndex.from_vector_store(
            vector_store=storage_context.vector_store
        )
        
        # 组装检索器，设定召回最相似的 3 个切片 (top_k=3)
        retriever = index.as_retriever(similarity_top_k=3)
            
        # 让 LlamaIndex 去执行召回
        nodes = retriever.retrieve(query)
        
        # 格式化节点信息为字符串
        raw_texts = []
        for i, node in enumerate(nodes):
            file_name = node.metadata.get("file_name", "Unknown") if node.metadata else "Unknown"
            raw_texts.append(f"### [Vector Node {i+1}] Source: {file_name}\n{node.text}")
                
        raw_string = "\n\n".join(raw_texts)
        
        return {
            "answer": raw_string
        }
    except Exception as e:
        return {
            "answer": f"⚠️ 向量库检索失败：{str(e)}\n\n(提示：请确保您已经点击过同步或构建过向量数据库)"
        }

if __name__ == "__main__":
    # 允许直接运行该文件来测试构建
    build_or_update_index()
