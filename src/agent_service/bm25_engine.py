import os
import jieba
from rank_bm25 import BM25Okapi

# ==========================================
# 1. 基础配置
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_VAULT_PATH = os.path.join(BASE_DIR, "shared_vault")

# ==========================================
# 2. 核心功能：极速纯内存 BM25 检索
# ==========================================
def query_bm25(query: str, scope: str = "global") -> dict:
    """在提问瞬间临时构建内存倒排索引，算完即焚"""
    print(f"BM25 Engine triggered for query: {query}")
    
    # 1. 读取全库 Markdown 文件
    docs = []
    
    if os.path.exists(SHARED_VAULT_PATH):
        if scope == "global" or scope == "🌐 全局知识库 (Global)":
            scan_dirs = [os.path.join(SHARED_VAULT_PATH, d) for d in os.listdir(SHARED_VAULT_PATH) if os.path.isdir(os.path.join(SHARED_VAULT_PATH, d))]
        else:
            username = scope.replace("👤", "").replace("的笔记", "").replace(" (自己)", "").strip()
            scan_dirs = [os.path.join(SHARED_VAULT_PATH, username)]
            
        for d in scan_dirs:
            if os.path.exists(d):
                for root, _, files in os.walk(d):
                    for f in files:
                        if f.endswith(".md"):
                            try:
                                with open(os.path.join(root, f), "r", encoding="utf-8") as file:
                                    docs.append({
                                        "title": f,
                                        "content": file.read(),
                                        "author": os.path.basename(d)
                                    })
                            except Exception:
                                pass

    if not docs:
        sample_path = os.path.join(BASE_DIR, "sample_vault")
        if os.path.exists(sample_path):
            for root, _, files in os.walk(sample_path):
                for f in files:
                    if f.endswith(".md"):
                        try:
                            with open(os.path.join(root, f), "r", encoding="utf-8") as file:
                                docs.append({
                                    "title": f,
                                    "content": file.read(),
                                    "author": "sample"
                                })
                        except Exception:
                            pass

    if not docs:
        return {"answer": "⚠️ 知识库与示例库均为空，无法进行 BM25 检索。"}

    # 2. 临时分词与构建倒排索引 (极速，纯内存)
    # 对每篇文档的正文进行 jieba 切词
    tokenized_corpus = [list(jieba.cut(doc["content"])) for doc in docs]
    
    # 构建 BM25 倒排索引字典 (一瞬间完成)
    bm25 = BM25Okapi(tokenized_corpus)
    
    # 3. 对用户的提问进行分词，并打分
    tokenized_query = list(jieba.cut(query))
    doc_scores = bm25.get_scores(tokenized_query)
    
    # 找到得分最高的 Top 3 篇文档
    top_n = 3
    # 按得分从高到低排序的文档索引
    top_indices = sorted(range(len(doc_scores)), key=lambda i: doc_scores[i], reverse=True)[:top_n]
    
    # 过滤掉得分为 0 的（完全没命中的）
    valid_indices = [i for i in top_indices if doc_scores[i] > 0]
    
    if not valid_indices:
         return {"answer": f"📚 **[倒排索引 BM25 RAG]**\n\n经过对 {len(docs)} 篇笔记的精准切词，未能匹配到任何包含词汇 `{query}` 的片段。"}

    matched_docs = [docs[i] for i in valid_indices]
    
    # 4. 组装上下文给 GLM-4 总结
    context_parts = []
    cited_titles = []
    for doc in matched_docs:
        title = doc["title"]
        cited_titles.append(f"[[{title}]]")
        
        # 截断太长的正文，防止撑爆 token
        content = doc["content"]
        if len(content) > 2000:
            content = content[:2000] + "..."
            
        context_parts.append(f"### 笔记：[[{title}]]\n{content}")
        
    context_str = "\n\n".join(context_parts)
    
    return {"answer": context_str}
