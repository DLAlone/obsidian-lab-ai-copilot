from langchain_core.tools import tool
import concurrent.futures
from vector_engine import query_vector_db
from bm25_engine import query_bm25
from graph_engine import query_graph_db

def run_in_thread(func, *args, **kwargs):
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return func(*args, **kwargs)
    finally:
        loop.close()

@tool
def hybrid_semantic_keyword_search(query: str) -> str:
    """
    Comprehensive text retrieval tool that combines Vector (semantic meaning) and BM25 (exact keyword matching) search.
    Use this tool to find factual information, content, and details from the user's knowledge base.
    """
    print(f"[Tool Calling] Executing hybrid_semantic_keyword_search for query: {query}")
    
    raw_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(run_in_thread, query_vector_db, query): "Vector",
            executor.submit(run_in_thread, query_bm25, query): "BM25"
        }
        
        for future in concurrent.futures.as_completed(futures):
            db_name = futures[future]
            try:
                res = future.result()
                ans = res.get("answer", "").strip()
                if ans and "⚠️" not in ans:
                    raw_results.append(f"=== {db_name} Search Results ===\n{ans}")
            except Exception as e:
                print(f"Error querying {db_name}: {e}")

    if not raw_results:
        return "未能从知识库中检索到相关信息。请尝试其他关键词。"
        
    return "\n\n".join(raw_results)

@tool
def vector_search(query: str) -> str:
    """
    Vector retrieval tool. Use this for semantic similarity search.
    """
    print(f"[Tool Calling] Executing vector_search for query: {query}")
    try:
        res = run_in_thread(query_vector_db, query)
        ans = res.get("answer", "").strip()
        if ans and "⚠️" not in ans:
            return f"=== Vector Search Results ===\n{ans}"
        else:
            return "未能从知识库中检索到相关信息。"
    except Exception as e:
        print(f"Error querying Vector: {e}")
        return "向量检索失败。"

@tool
def bm25_search(query: str) -> str:
    """
    BM25 retrieval tool. Use this for exact keyword matching search.
    """
    print(f"[Tool Calling] Executing bm25_search for query: {query}")
    try:
        res = run_in_thread(query_bm25, query)
        ans = res.get("answer", "").strip()
        if ans and "⚠️" not in ans:
            return f"=== BM25 Search Results ===\n{ans}"
        else:
            return "未能从知识库中检索到相关信息。"
    except Exception as e:
        print(f"Error querying BM25: {e}")
        return "BM25检索失败。"


@tool
def graph_topology_search(entity_name: str) -> str:
    """
    Graph retrieval tool. Use this tool specifically when you need to understand the relationships, connections, or topology between entities (e.g., 'What is the relationship between A and B?', 'Which projects is person X involved in?').
    Pass the core entity name as the parameter.
    """
    print(f"[Tool Calling] Executing graph_topology_search for entity: {entity_name}")
    
    try:
        res = run_in_thread(query_graph_db, entity_name)
        ans = res.get("answer", "").strip()
        if ans and "⚠️" not in ans:
            return f"=== Graph Search Results ===\n{ans}"
        else:
            return "图谱中未找到相关实体关系。"
    except Exception as e:
        print(f"Error querying Graph: {e}")
        return "图谱检索失败。"

@tool
def python_data_interpreter(code: str) -> str:
    """
    Python code interpreter sandbox tool. Use this ONLY when you need to perform complex calculations, data analysis, or manipulate structured data that cannot be done just by reading text.
    Pass the raw Python code string to execute. The output (stdout/stderr) of the script will be returned to you.
    Note: Do not use this tool for simple text queries.
    """
    import subprocess
    import tempfile
    import os
    
    print(f"🧑‍💻 [Tool Calling] Executing python_data_interpreter with code length: {len(code)}")
    
    # Create a scratch directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    scratch_dir = os.path.join(base_dir, "scratch")
    os.makedirs(scratch_dir, exist_ok=True)
    
    # Write code to a temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", dir=scratch_dir, delete=False, encoding="utf-8") as temp_file:
        temp_file.write(code)
        temp_file_path = temp_file.name

    try:
        # Execute the python script safely with a timeout
        result = subprocess.run(
            ["python", temp_file_path],
            capture_output=True,
            text=True,
            timeout=15 # 15s timeout to prevent infinite loops
        )
        
        output = result.stdout
        if result.stderr:
            output += f"\n[Error]: {result.stderr}"
            
        if not output.strip():
            output = "[Code executed successfully with no output]"
            
        return output
    except subprocess.TimeoutExpired:
        return "[Error]: Code execution timed out after 15 seconds."
    except Exception as e:
        return f"[Error]: Failed to execute code - {str(e)}"
    finally:
        # Cleanup
        try:
            os.remove(temp_file_path)
        except:
            pass

# 导出工具列表供 Agent 使用
AGENT_TOOLS = [hybrid_semantic_keyword_search, graph_topology_search, python_data_interpreter, vector_search, bm25_search]
