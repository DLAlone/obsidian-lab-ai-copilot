# 课题组智能知识库 Agent 协同插件 (PRD)

> **文档版本**：v2.0 (Enterprise/Industrial Grade)  
> **状态**：已落地方案  
> **适用对象**：系统架构师、后端 Agent 开发者、Obsidian 前端开发者及学术评估人员  

---

## 1. 执行摘要与项目愿景

### 1.1 业务背景与痛点
在学术界和科研课题组中，研究人员日常面临三大核心知识管理痛点：
1. **数据孤岛与隐私焦虑**：公有云 AI 知识库产品要求上传私密实验数据与未发表论文，存在泄密风险；而本地 Markdown 笔记（如 Obsidian）缺乏智能化问答与推理能力。
2. **传统 RAG 幻觉失控**：第一代单向 RAG（检索-生成）缺乏对检索质量的甄别机制。一旦检索召回不精准，大模型极易“强行胡编乱造”（产生幻觉），严重影响科研严谨性。
3. **知识沉没与单向流失**：课题组讨论、报错排查等高质量 Q&A 往往散落在聊天记录中，阅后即焚，无法自动化沉淀为结构化知识晶体。

### 1.2 产品定位
**课题组智能知识库 Agent 协同插件 (Lab AI Copilot)** 是一款**工业级、Local-First（本地优先）、双循环智能体驱动**的学术协同工具。
系统将 Obsidian 原生 TypeScript 插件与基于 **LangGraph** 的 Python 后端双循环 Agent 深度结合，在保证 100% 本地数据主权的前提下，提供具备“自主查阅”与“自我批评打分”能力的高可靠科研 Copilot。

---

## 2. 核心架构与功能矩阵

### 2.1 系统全局架构

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Obsidian Desktop (Client)                       │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ ChatView.ts (UI Layer: ItemView + Dropdown + Event Stream)       │  │
│  └─────────────────────────────────┬────────────────────────────────┘  │
└────────────────────────────────────┼───────────────────────────────────┘
                                     │ HTTP REST API (POST /chat)
┌────────────────────────────────────▼───────────────────────────────────┐
│                    FastAPI Backend Service (Server)                    │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ LangGraph Agentic Engine (StateGraph)                            │  │
│  │                                                                  │  │
│  │   ┌──────────────────────────────────────────────────────────┐   │  │
│  │   │ Node 1: ReAct Query Rewrite & Keyword Extraction         │   │  │
│  │   └────────────────────────────┬─────────────────────────────┘   │  │
│  │                                │ Strategy Route                  │  │
│  │   ┌────────────────────────────▼─────────────────────────────┐   │  │
│  │   │ Node 2: Heterogeneous Tool Execute                      │   │  │
│  │   │   ├── Vector Engine Tool (LlamaIndex + ChromaDB)         │   │  │
│  │   │   ├── Graph Engine Tool (Obsidian [[Wikilinks]])          │   │  │
│  │   │   └── BM25 Engine Tool (Lexical Frequency)               │   │  │
│  │   └────────────────────────────┬─────────────────────────────┘   │  │
│  │                                │ Raw Text Chunks                 │  │
│  │   ┌────────────────────────────▼─────────────────────────────┐   │  │
│  │   │ Node 3: Self-Reflection & Quality Assessment (Judge)     │   │  │
│  │   └────────────────────────────┬─────────────────────────────┘   │  │
│  │                                │ Loop or Reply                   │  │
│  └────────────────────────────────┼─────────────────────────────────┘  │
│                                   │                                    │
│  ┌────────────────────────────────▼─────────────────────────────────┐  │
│  │ SqliteSaver (Checkpoint Database Engine)                        │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心功能矩阵 (Feature Matrix)

| 模块编号 | 功能模块 | 功能描述 | 交付标准 |
|---|---|---|---|
| **F-01** | **双循环 Agent 引擎** | 基于 LangGraph 状态图，整合 ReAct 决策与 Self-Reflection 质量反思 | 评估打分 <7 分自动重搜，拒答/幻觉率降至 1% 以下 |
| **F-02** | **异构检索引擎池** | 包含 Vector (语义)、Graph (拓扑)、BM25 (字面) 三种正交工具 | 工具降级为纯文本输出，无中间层大模型信息衰减 |
| **F-03** | **状态持久化引擎** | 基于 `SqliteSaver` 保存完整的 Checkpoint 物理快照 | 支持多轮对话历史上下文无缝恢复与断点续传 |
| **F-04** | **UI 控制变量沙盒** | 前端动态下发 `strategy` (agentic/vector/graph/bm25) 策略 | 无需重启服务，支持实时对比不同检索引擎表现 |
| **F-05** | **LMVT 自动反刍** | 后台守护进程评估聊天记录价值，自动提炼为 Wiki 笔记 | 生成符合 `100-Schema` 规范的标准 Markdown 卡片 |

---

## 3. 详细功能需求规范 (FSD)

### 3.1 F-01: Agentic 双循环推理流程 (LangGraph StateGraph)
- **Node 1: ReAct 意图解析 (Query Rewrite)**
  - 输入：当前用户问题 `prompt` + 历史对话 `history` + 当前策略 `strategy`。
  - 职责：提取 1-3 个精炼的学术关键词，去除口语化干扰。若策略为 `agentic`，自主选择最佳工具指令。
- **Node 2: 工具执行 (Tool Execute)**
  - 职责：根据 Node 1 指令调用对应检索工具。要求检索工具只返回原始文档切片（Raw Text），避免在工具内部调用大模型二次总结。
  - 输出：将抓取到的片段装载进状态 `matched_docs` 中。
- **Node 3: Self-Reflection 自我反思与打分 (Judge)**
  - 职责：中央大模型作为裁判，比对 `prompt` 与 `matched_docs`。
  - 判定条件：
    1. 评估依据充分性（打出 1-10 分）。
    2. 检查大模型草稿是否包含无中生有的虚假论文或定理。
  - 路由逻辑：Score < 7 且递归深度未超限，路由回 Node 1 强制重搜；否则输出最终回复并附带双链引用。

### 3.2 F-02: 三大异构检索引擎规范
1. **Vector Engine**：基于 LlamaIndex + ChromaDB，使用 `bge-m3` 向量模型，Chunk Size = 500 tokens，Overlap = 50 tokens。
2. **Graph Engine**：提取 Obsidian 原生 `[[概念]]` 双向链接拓扑关系，构建图谱邻接矩阵，支持 1-2 跳（Hop）关系检索。
3. **BM25 Engine**：针对生僻专有名词、代码配置参数进行精确字面匹配，作为向量模糊匹配的补充。

### 3.3 F-03: Session 上下文与物理持久化
- **Session 隔离**：每个 ChatView 侧边栏分配唯一 `session_id`。
- **持久化方案**：使用 `SqliteSaver` 挂载 `checkpoints.db`。每次对话结束后自动写入当前状态快照（包括消息历史、反思得分、匹配切片）。

---

## 4. 非功能性需求 (NFR)

### 4.1 性能 SLA (Service Level Agreement)
- **检索召回响应时间**：单引擎检索 Latency < 800ms。
- **E2E 首字响应时间**：Agentic 模式下首字返回 < 2.5s，打字机流式渲染速度 > 20 chars/s。
- **物理资源占用**：后端常驻内存 < 400MB（无大模型本地加载，调用 API 模式）。

### 4.2 数据安全与隐私
- **Local-First 保证**：原始 Markdown 文件绝不上传第三方服务器。仅检索到的 Raw Text 切片在推理时加密传输至 API 端。
- **密钥安全**：所有 API Key 仅保存在本地 `agent-service/.env` 文件中，禁止提交至 Git 仓库。

### 4.3 容错与降级机制 (Fault Tolerance)
- **递归保护 (Recursion Limit)**：设定 LangGraph 递归上限为 `recursion_limit = 5`，防止因检索困难导致死循环。
- **网络中断降级**：API 请求超时（> 15s）自动触发退避重试，若重试失败则优雅提示用户检查网络。

---

## 5. API 接口契约规范

### 5.1 POST `/chat` 接口

#### 请求 Payload
```json
{
  "prompt": "如何配置 LangGraph 的 SqliteSaver 持久化？",
  "strategy": "agentic",  // agentic | vector | graph | bm25
  "session_id": "session-1723276800",
  "history": [
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "你好！我是课题组 Copilot。"}
  ]
}
```

#### 响应 Payload
```json
{
  "reply": "配置 LangGraph 的 SqliteSaver 需要以下步骤...",
  "strategy_used": "agentic",
  "score": 9,
  "sources": [
    "50-Wiki/Ai学习/concepts/LangGraph SqliteSaver.md"
  ]
}
```
