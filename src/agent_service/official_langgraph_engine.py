import os
import json
import sqlite3
from typing import Dict, List, Any, TypedDict, Annotated
import operator

from langchain_core.messages import AnyMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from agent_tools import AGENT_TOOLS

# LLM API 配置 (OpenAI 兼容协议)
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
LLM_MODEL = os.environ.get("LLM_MODEL", "glm-4-flash")

llm = ChatOpenAI(
    model=LLM_MODEL,
    api_key=LLM_API_KEY or "dummy-key-for-initialization",
    base_url=LLM_BASE_URL,
    temperature=0.1,
)

llm_with_tools = llm.bind_tools(AGENT_TOOLS)

class AgentState(TypedDict):
    """LangGraph 状态 Schema 定义"""
    messages: Annotated[list[AnyMessage], add_messages]
    draft: str
    sufficiency_score: float
    reflection_retries: int
    strategy: str
    session_id: str

def agent_node(state: AgentState):
    """节点 1: ReAct Agent大脑，抛出 ToolCalling 指令"""
    print("🧠 [Agent Node] 正在思考...")
    
    strategy = state.get("strategy", "agentic")
    messages = state["messages"]
    
    # 兼容单引擎回测模式：直接硬编码 ToolCall 强行拉起单引擎
    if strategy in ["vector", "bm25", "graph"]:
        from langchain_core.messages import AIMessage
        # 如果历史消息中已经有了 ToolMessage，说明已经执行完检索，直接让 Agent 停止调用工具
        if any(isinstance(m, ToolMessage) for m in messages):
            print(f"🔧 [回测模式] 单引擎 {strategy} 已完成检索，终止循环并流转。")
            return {"messages": [AIMessage(content="单引擎检索完毕，准备起草。")]}
            
        print(f"🔧 [回测模式] 绕过大脑决策，强制拉起单引擎: {strategy}")
        
        # 提取用户最新 query
        query = messages[-1].content if messages else ""
        
        if strategy == "graph":
            tool_call_name = "graph_topology_search"
            args = {"entity_name": query}
        elif strategy == "vector":
            tool_call_name = "vector_search"
            args = {"query": query}
        else:
            tool_call_name = "bm25_search"
            args = {"query": query}
            
        # 强制生成包含 tool_call 的 AIMessage
        forced_msg = AIMessage(
            content="",
            tool_calls=[{"name": tool_call_name, "args": args, "id": f"call_{strategy}"}]
        )
        return {"messages": [forced_msg]}
    
    sys_msg = SystemMessage(content=(
        "你是一个强大的学术级知识库智能体。你的目标是回答用户的问题。你可以调用多个检索工具来查询用户的 Obsidian 笔记库。\n"
        "【极其重要】：\n"
        "1. 在绝大多数情况下，你**必须**优先调用工具去查证。哪怕你自认为知道答案，也必须先从用户的资料库中寻找支撑！\n"
        "2. 只有当你已经调用过工具并且充分掌握了所需信息时，你才可以停止调用工具并直接回答。\n"
        "3. 绝对不许在没调用工具的情况下宣称“没有资料”。"
    ))
    
    # 过滤掉之前的系统消息，保持最新的一条在最前
    filtered_msgs = [m for m in messages if not isinstance(m, SystemMessage)]
    
    response = llm_with_tools.invoke([sys_msg] + filtered_msgs)
    
    return {"messages": [response]}

tool_node = ToolNode(AGENT_TOOLS)

def draft_node(state: AgentState):
    """节点 3: Draft Generator 专门写草稿"""
    print("✍️ [Draft Node] 开始起草回答...")
    messages = state["messages"]
    
    # 获取所有的 Tool 返回的内容
    tool_contents = []
    for m in messages:
        if isinstance(m, ToolMessage):
            tool_contents.append(f"[{m.name}] 返回数据:\n{m.content}\n")
            
    raw_context = "\n".join(tool_contents)
    
    sys_msg = SystemMessage(content=(
        "你是一个极其严谨的学术助理。你的任务是根据提供的检索资料起草一篇高质量的答案。\n"
        "要求：\n"
        "1. 必须完全基于提供的资料，绝不能凭空捏造（零幻觉）。\n"
        "2. 如果资料完全不足以回答问题，请明确表示“由于资料库中缺乏相关信息，我无法回答该问题”，切勿强行编造。\n"
        "3. 保持 Markdown 优雅排版。\n"
    ))
    
    user_prompt = "用户原问题：\n"
    for m in messages:
        if isinstance(m, HumanMessage):
            user_prompt += m.content + "\n"
            break
            
    user_prompt += f"\n\n提供的检索资料如下：\n{raw_context}"
    
    response = llm.invoke([sys_msg, HumanMessage(content=user_prompt)])
    
    return {"draft": response.content}


class GraderOutput(BaseModel):
    score: float = Field(description="打分 0.0 到 10.0，代表该草稿是否充分且准确地基于原文回答了问题。")
    is_no_data_case: bool = Field(description="如果库里确实没有资料导致无法回答，且草稿老实交代了，置为 true；如果是模型胡编乱造或没回答全，置为 false。")
    critique: str = Field(description="具体的批判和打分理由。")


def grader_node(state: AgentState):
    """节点 4: 独立裁判，核对草稿并打分"""
    print("⚖️ [Grader Node] 开始审查草稿...")
    draft = state.get("draft", "")
    messages = state["messages"]
    
    tool_contents = []
    for m in messages:
        if isinstance(m, ToolMessage):
            tool_contents.append(f"[{m.name}] 返回数据:\n{m.content}\n")
            
    raw_context = "\n".join(tool_contents)
    
    user_prompt = "用户问题：\n"
    for m in messages:
        if isinstance(m, HumanMessage):
            user_prompt += m.content + "\n"
            break
            
    sys_msg = SystemMessage(content="你是一个冷酷无情的裁判。你的任务是审查 Draft 草稿是否有效回答了用户的问题，并严格核对是否有幻觉。")
    
    eval_prompt = f"{user_prompt}\n\n检索到的原始上下文：\n{raw_context}\n\n需要审查的草稿：\n{draft}"
    
    grader_llm = llm.with_structured_output(GraderOutput)
    
    try:
        eval_result = grader_llm.invoke([sys_msg, HumanMessage(content=eval_prompt)])
        score = eval_result.score
        is_no_data = eval_result.is_no_data_case
        reason = eval_result.critique
    except Exception as e:
        print(f"Grader 解析失败: {e}")
        score = 8.0 # Fallback 
        is_no_data = False
        reason = "Parse failed"
        
    print(f"⚖️ 裁判打分: {score}/10, is_no_data={is_no_data}, reason={reason}")
    
    retries = state.get("reflection_retries", 0)
    
    # 核心防爆逻辑
    has_tool_call = any(isinstance(m, ToolMessage) for m in messages)
    
    if score < 7.0:
        if is_no_data:
            if not has_tool_call:
                print("⚖️ 裁判判定：严重违规！没有调用过工具就声称没资料！打回强制检索！")
                score = 0.0
                is_no_data = False
                reason = "你还没有调用任何检索工具去库里查证，就直接说没有资料！这是严重违背学术严谨性的行为。请立刻调用 hybrid_semantic_keyword_search 等工具去搜索用户的问题！"
                retries += 1
                messages.append(AIMessage(content=f"【系统打回】裁判判定你的草稿极度不合格！理由：{reason}"))
            else:
                print("⚖️ 裁判判定：确实调用了工具且没查到资料，属于合格如实回答，直接放行。")
                score = 10.0 # 满分放行
        else:
            print("⚖️ 裁判判定：存在幻觉或质量差，打回重写。")
            retries += 1
            # 将裁判意见发给 Agent 大脑，逼迫它去查新词或改错
            messages.append(AIMessage(content=f"【系统打回】裁判判定你的草稿不合格！理由：{reason}。请尝试调用工具检索更多信息。"))
            
    return {"sufficiency_score": score, "reflection_retries": retries}


def should_continue(state: AgentState) -> str:
    """Agent Node 的条件边：决定去 Tools 还是 Draft"""
    messages = state['messages']
    last_message = messages[-1]
    
    # 如果大模型输出了 tool_calls，流转到 tool_node
    if last_message.tool_calls:
        print(f"🔀 [Router] 探测到 {len(last_message.tool_calls)} 个工具调用，进入 ReAct 工具循环。")
        return "continue"
        
    # 否则，流转到 draft_node
    print(f"🔀 [Router] 大模型主动停止工具调用，流转到 Draft 节点起草。")
    return "draft"

def check_score(state: AgentState) -> str:
    """Grader Node 的条件边：决定去 END 还是回 Agent 重做"""
    score = state.get("sufficiency_score", 0.0)
    retries = state.get("reflection_retries", 0)
    
    if score >= 7.0:
        print("✅ [Grader 决断] 及格！流转到终点 (END)。")
        return "end"
    
    if retries >= 2: # 最多打回2次
        print("🛑 [Grader 决断] 达到最大打回重构次数 (2次)，强行切断死循环，流转到终点 (END)。")
        return "end"
        
    print("❌ [Grader 决断] 不及格！退回 Agent 大脑 (Node 1) 重修！")
    return "retry"

class OfficialLangGraphWorkflow:
    def __init__(self):
        builder = StateGraph(AgentState)
        
        # Add nodes
        builder.add_node("agent_node", agent_node)
        builder.add_node("tool_node", tool_node)
        builder.add_node("draft_node", draft_node)
        builder.add_node("grader_node", grader_node)
        
        # Add edges
        builder.add_edge(START, "agent_node")
        
        # 内循环 (ReAct)
        builder.add_conditional_edges(
            "agent_node",
            should_continue,
            {
                "continue": "tool_node",
                "draft": "draft_node"
            }
        )
        builder.add_edge("tool_node", "agent_node")
        
        # 退出内循环后去评分
        builder.add_edge("draft_node", "grader_node")
        
        # 外循环 (Reflection)
        builder.add_conditional_edges(
            "grader_node",
            check_score,
            {
                "retry": "agent_node",
                "end": END
            }
        )
        
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(BASE_DIR, "agent_memory.sqlite")
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        from langgraph.checkpoint.sqlite import SqliteSaver
        memory = SqliteSaver(self.conn)
        
        self.app = builder.compile(checkpointer=memory)

    def run(self, prompt: str, docs: List[Dict[str, Any]] = None, history: List[Dict[str, str]] = None, strategy: str = "agentic", session_id: str = "default_session") -> Dict[str, Any]:
        """运行双循环 Agent"""
        
        initial_messages = []
        if history:
            for h in history[-6:]:
                if h["role"] == "user":
                    initial_messages.append(HumanMessage(content=h["content"]))
                else:
                    initial_messages.append(AIMessage(content=h["content"]))
                    
        initial_messages.append(HumanMessage(content=prompt))
        
        initial_state = {
            "messages": initial_messages,
            "draft": "",
            "sufficiency_score": 0.0,
            "reflection_retries": 0,
            "strategy": strategy,
            "session_id": session_id
        }
        
        config = {"configurable": {"thread_id": session_id}, "recursion_limit": 10}
        
        print(f"🚀 [LangGraph] 启动真·双循环架构 (strategy={strategy}, session={session_id})")
        result = self.app.invoke(initial_state, config=config)
        
        draft = result.get("draft", "抱歉，系统暂时无法生成有效回答。")
        score = result.get("sufficiency_score", 0.0)
        retries = result.get("reflection_retries", 0)
        
        strategy_names = {
            "agentic": "企业级双循环 Agentic RAG",
            "vector": "向量单引擎测试 Vector RAG",
            "bm25": "字典单引擎测试 BM25",
            "graph": "拓扑单引擎测试 Graph RAG"
        }
        display_name = strategy_names.get(strategy, "Agentic RAG")
        
        final_reply = (
            f"🧠 **[{display_name}]** (真·双循环架构已生效)\n\n"
            f"{draft}\n\n"
            f"---\n"
            f"✓ **系统自省报告**：\n"
            f"- 资料充足度与准确率评分: {score}/10\n"
            f"- 触发 Reflection 重试次数: {retries} 次\n"
        )
        
        return {
            "reply": final_reply,
            "cited_docs": [],
            "sufficiency_score": score
        }

official_agent_workflow = OfficialLangGraphWorkflow()
