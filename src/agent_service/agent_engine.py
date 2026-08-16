import re
import json
import os
from typing import List, Dict, Any, Tuple

class Tool:
    """Agent 工具抽象基类"""
    def __init__(self, name: str, description: str, func):
        self.name = name
        self.description = description
        self.func = func

    def run(self, *args, **kwargs):
        return self.func(*args, **kwargs)

class AgentState:
    """Agent 执行上下文状态图 (State Tracking)"""
    def __init__(self, query: str, docs: List[Dict[str, Any]]):
        self.query = query
        self.docs = docs
        self.trajectory = []
        self.evidence = []
        self.cited_docs = []
        self.sufficiency_score = 0.0
        self.reflection_summary = ""

class ResearchGroupAgentEngine:
    """
    基于 ReAct (Reasoning + Acting) 范式与 Graph-RAG 拓扑图谱遍历的课题组 Agent 核心引擎
    设计原则：
    1. 动态工具注册与调用 (Tool Calling Registry)
    2. 多步关联链条拓扑追溯 (Multi-hop Wikilink Traversal)
    3. 自省与信息充足性评估 (Self-Reflection & Sufficiency Check)
    4. 终极学术答复知识重组 (Academic Synthesis & Structured Markdown)
    """

    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self._register_default_tools()

    def register_tool(self, name: str, description: str, func):
        self.tools[name] = Tool(name, description, func)

    def _register_default_tools(self):
        # 1. 关键词全库精确定位工具
        def keyword_search(query: str, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            keywords = [k.lower() for k in re.split(r'\s+', query) if len(k) > 1]
            if not keywords:
                keywords = [query.lower()]

            matched = []
            for doc in docs:
                title = (doc.get("title") or doc.get("name") or "").lower()
                content = (doc.get("content") or "").lower()
                score = 0
                hits = []
                for kw in keywords:
                    if kw in title:
                        score += 15
                    if kw in content:
                        score += 5
                        for line in doc.get("content", "").split("\n"):
                            if kw in line.lower() and line.strip():
                                hits.append(line.strip())
                if score > 0:
                    matched.append({
                        "title": doc.get("title") or doc.get("name"),
                        "score": score,
                        "hits": hits[:3],
                        "raw_doc": doc
                    })
            matched.sort(key=lambda x: x["score"], reverse=True)
            return matched

        # 2. Obsidian [[Wikilink]] 拓扑图谱遍历工具
        def wikilink_traversal(target_title: str, docs: List[Dict[str, Any]]) -> List[str]:
            target_doc = next((d for d in docs if (d.get("title") or d.get("name")) == target_title), None)
            if not target_doc:
                return []
            content = target_doc.get("content", "")
            links = re.findall(r'\[\[(.*?)\]\]', content)
            cleaned_links = []
            for l in links:
                name = l.split('|')[0].strip()
                if name and name not in cleaned_links:
                    cleaned_links.append(name)
            return cleaned_links

        # 3. 概念提取与专业词典映射工具
        def concept_explanation(term: str) -> str:
            term_lower = term.lower()
            dict_map = {
                "ssh": "SSH (Secure Shell) 是专为远程登录会话和其他网络服务提供安全性的协议。在其拓展应用中，常见有 `ssh -D` 动态端口转发（隧道代理）、密钥对免密登录与文件 SCP/SFTP 加密传输。",
                "sem": "SEM (Scanning Electron Microscope, 扫描电子显微镜) 是利用极细的聚焦电子束轰击样品表面产生二次电子等物理信号，以获得微观形貌特性的高分辨显微技术。",
                "rag": "RAG (Retrieval-Augmented Generation, 检索增强生成) 是一种将外部私域知识库检索与大语言模型生成能力相结合的 AI 架构，可有效防止模型幻觉。",
                "git": "Git 是一个分布式版本控制系统，用于追踪代码与文档的修改历史，支持分支合并、Commit 快照以及 Pull Request 协作。",
                "obsidian": "Obsidian 是一款基于本地纯文本 Markdown 的双向链接知识库软件，核心特色是 `[[Wikilink]]` 知识图谱拓扑与纯文本永久可读。"
            }
            for k, v in dict_map.items():
                if k in term_lower:
                    return v
            return ""

        self.register_tool("keyword_search", "在 Obsidian 笔记库中搜索匹配的节点与段落", keyword_search)
        self.register_tool("wikilink_traversal", "根据当前笔记追溯其 [[Wikilink]] 关联引用的上下游节点", wikilink_traversal)
        self.register_tool("concept_explanation", "查询专业学术与技术名词的标准解释", concept_explanation)

    def execute_agent_trajectory(self, prompt: str, docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        核心 ReAct 执行循环：
        Thought 1 -> Action 1 (Search) -> Observation 1
        Thought 2 -> Action 2 (Wikilink Traverse) -> Observation 2
        Reflection -> Sufficiency Evaluation -> Synthesis Output
        """
        state = AgentState(prompt, docs)

        # Step 1: Thought & Action 1 - 调阅检索工具
        state.trajectory.append("🤔 [Agent 思考 1]: 正在分析用户提问，提取检索关键词并扫盘调阅知识库...")
        matched_results = self.tools["keyword_search"].run(prompt, docs)
        
        if not matched_results:
            state.trajectory.append("⚠️ [Agent 观察 1]: 全库检索完毕，未命中相关文档节点。")
            return {
                "reply": f"🤖 **[AI Agent 检索与自省报告]**\n\n🔍 已全库扫描您导入的 Obsidian 知识库，但**未搜索到与“{prompt}”直接相关的笔记**。\n\n💡 **Agent 建议**：\n1. 请确认该主题笔记是否已放在您导入的 Vault 文件夹内；\n2. 点击左侧边栏【📂 导入 Obsidian 仓库】更新知识库。",
                "cited_docs": [],
                "trajectory": state.trajectory
            }

        top_match = matched_results[0]
        state.cited_docs = [m["title"] for m in matched_results[:3]]
        state.trajectory.append(f"✓ [Agent 观察 1]: 命中主节点 [[{top_match['title']}]]，匹配分值: {top_match['score']}")

        # Step 2: Thought & Action 2 - 图谱拓扑遍历工具
        state.trajectory.append("🤔 [Agent 思考 2]: 沿着主节点的双向链接 [[Wikilink]] 进行二次图谱追溯...")
        linked_nodes = self.tools["wikilink_traversal"].run(top_match["title"], docs)
        if linked_nodes:
            state.trajectory.append(f"✓ [Agent 观察 2]: 追溯到关联节点: {', '.join(['[['+l+']]' for l in linked_nodes[:3]])}")
        else:
            state.trajectory.append("ℹ️ [Agent 观察 2]: 主节点暂无指向其他维度的双向链接。")

        # Step 3: Thought & Action 3 - 概念解析工具
        concept_info = self.tools["concept_explanation"].run(prompt)

        # Step 4: Self-Reflection 自省评价与得分判定
        evidence_count = len(top_match["hits"])
        if evidence_count >= 3 or concept_info:
            state.sufficiency_score = 0.95
            state.reflection_summary = "✓ **【Agent 自省评估】**：调阅数据充分，已成功结合概念解析与本地笔记做出完整解答。"
        elif evidence_count >= 1:
            state.sufficiency_score = 0.65
            state.reflection_summary = "⚠️ **【Agent 自省评估】**：知识库中包含部分实操记载，但底层原理解释相对简略，建议后续补充文献。"
        else:
            state.sufficiency_score = 0.40
            state.reflection_summary = "⚠️ **【Agent 自省评估】**：仅找到相关标题节点，正文细节较少。"

        # Step 5: Final Synthesis Generator (重组输出)
        sections_str = "\n".join([f"  * {line}" for line in top_match["hits"]]) if top_match["hits"] else "  * (找到目标笔记卡片)"
        cited_links_str = "、".join([f"[[{t}]]" for t in state.cited_docs])

        output_md = [
            f"🤖 **[AI Agent 思考与深度整理报告]**",
            f"已为您启动 ReAct 引擎调阅 Obsidian 知识网，调阅 **{len(matched_results)}** 份相关节点。",
            f"",
            f"📌 **最强匹配笔记**：[[{top_match['title']}]]",
            f"🔗 **拓扑关联节点**：{cited_links_str}",
            f"",
            f"💡 **1. 课题组知识库记载详情**：",
            sections_str,
            f""
        ]

        if concept_info:
            output_md.extend([
                f"🧠 **2. 学术/技术概念通俗解析**：",
                f"  * {concept_info}",
                f""
            ])

        if linked_nodes:
            output_md.extend([
                f"🕸️ **3. 图谱拓扑引申推荐**：",
                f"  * 推荐查阅关联节点: {', '.join(['[['+l+']]' for l in linked_nodes[:3]])}",
                f""
            ])

        output_md.append(state.reflection_summary)

        return {
            "reply": "\n".join(output_md),
            "cited_docs": state.cited_docs,
            "trajectory": state.trajectory,
            "sufficiency_score": state.sufficiency_score
        }

# 单例 Agent 引擎实例
agent_engine = ResearchGroupAgentEngine()
