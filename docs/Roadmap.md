# 课题组智能知识库 Agent 协同插件 (Roadmap)

> **文档版本**：v2.0 (Enterprise/Industrial Grade)  
> **规划周期**：2026 Q3 - 2027 Q1  
> **战略目标**：打造学术课题组首选的 Local-First 智能知识引擎与科研 Copilot  

---

## 1. 战略规划路线图 (Strategic Timeline)

```
2026 Q3 (已完成)                2026 Q4 (进行中)                2027 Q1 (未来规划)
┌────────────────────────┐      ┌────────────────────────┐      ┌────────────────────────┐
│ Phase 1 - 3: 架构奠基  │      │ Phase 4 - 5: 功能强化  │      │ Phase 6: 课题组网络    │
├────────────────────────┤      ├────────────────────────┤      ├────────────────────────┤
│ • Local-First TS 插件  │─────►│ • 多模态 PDF/图片 检索 │─────►│ • P2P 课题组共享网格   │
│ • LangGraph 双循环 Agent│      │ • SSE 流式打字机响应   │      │ • WebDAV/坚果云增量同步│
│ • 三大异构引擎与沙盒   │      │ • LMVT 自动知识反刍    │      │ • 自动化论文引用生成器 │
│ • SqliteSaver 物理记忆 │      │ • 检索可视化链路图     │      │ • 多用户权限隔离与审计 │
└────────────────────────┘      └────────────────────────┘      └────────────────────────┘
```

---

## 2. 阶段里程碑矩阵 (Milestone Matrix)

### [✅ Completed] Phase 1: 本地优先插件与基础设施 (Local-First Scaffolding)
- **目标**：搭建轻量级 C/S 通信通道，实现 Obsidian 侧边栏与 FastAPI 后端连通。
- **交付产物**：
  - [x] 基于 Rollup + TypeScript 的 Obsidian 插件框架。
  - [x] FastAPI RESTful 服务端与 CORS 跨域安全中间件。
  - [x] 前端 `ChatView.ts` 基础 UI 渲染器。

### [✅ Completed] Phase 2: 异构检索引擎池与工具降级 (Heterogeneous Engine Pool)
- **目标**：构建三种互补的检索 Pipeline，并将中间层大模型剥离，降级为 Raw Text 工具。
- **交付产物**：
  - [x] `vector_engine.py` (LlamaIndex + ChromaDB + bge-m3)。
  - [x] `graph_engine.py` (基于 Obsidian 双向链接拓扑关系的跳跃式检索)。
  - [x] `bm25_engine.py` (基于词频概率的字面精确匹配器)。

### [✅ Completed] Phase 3: LangGraph 双循环 Agent 与状态持久化 (Double-Loop Core)
- **目标**：解决传统 RAG 幻觉失控与多轮对话失忆问题。
- **交付产物**：
  - [x] LangGraph `StateGraph` 编排：Node 1 (ReAct)、Node 2 (Execute)、Node 3 (Reflection)。
  - [x] 反思打分机制：打分 <7 分自动重搜，硬性规则防幻觉。
  - [x] 挂载 `SqliteSaver Checkpointer`，实现基于 SQLite 的物理断点续传。

### [✅ Completed] Phase 4: 前端沙盒控制变量与 UI 优化 (UI Sandbox)
- **目标**：提供科研级别的检索引擎压测与效果对比手段。
- **交付产物**：
  - [x] 前端引擎切换下拉菜单 (Agentic / Vector / Graph / BM25)。
  - [x] 后端 `strategy` 动态路由与强制 Tool 注入逻辑。
  - [x] 保持对话 Session 上下文跨模式无缝延续。

### [🚧 In Progress] Phase 5: 多模态扩展与流式体验 (Multi-Modal & SSE)
- **目标**：支持文献 PDF 切片、图表 OCR 识别与毫秒级流式打字效果。
- **里程碑任务**：
  - [ ] 集成 Server-Sent Events (SSE) 协议，取代同步 JSON 响应。
  - [ ] 引入 `unstructured` / `fitz` 解析课题组 PDF 论文集。
  - [ ] 增加多模态 Vision 模型对论文结构图和实验数据图的理解。

### [📅 Planned] Phase 6: LMVT 自动知识反刍与课题组网络 (Knowledge Mesh)
- **目标**：打破个人知识库壁垒，构建越用越聪明的课题组共享脑。
- **里程碑任务**：
  - [ ] **LMVT 守护进程**：后台静默评估问答对话，自动提炼高质量知识卡片并入库。
  - [ ] **坚果云 / WebDAV 增量同步**：支持全组基于云盘无缝同步 `50-Wiki` 原子笔记。
  - [ ] **多用户权限与来源追溯**：标注每条知识卡片的贡献者与原始出处。

---

## 3. 技术风险矩阵与应对策略 (Risk & Mitigation Matrix)

| 风险编号 | 风险描述 | 风险等级 | 应对策略 (Mitigation) |
|---|---|---|---|
| **R-01** | **上下文窗口膨胀**<br/>长对话导致 Token 超限或费用激增 | 高 | 引入滑动窗口机制（Sliding Window）+ 定期自动生成上文摘要（Summary Node）。 |
| **R-02** | **SQLite 死锁风险**<br/>多线程/多窗口并发写入数据库导致 Lock | 中 | 将 SQLite 开启 WAL (Write-Ahead Logging) 模式，并留出迁移至 PostgreSQL 的接口。 |
| **R-03** | **向量漂移与稀疏匹配失效**<br/>生僻词向量距离远导致漏检索 | 中 | 强制使用 BM25 词频引擎与 Vector 进行 Rerank 混合重排序（Hybrid Fusion）。 |
| **R-04** | **Windows 编码冲突**<br/>非 UTF-8 环境引发批量文件破坏 | 高 | 后端及运维脚本全量显式声明 `encoding='utf-8'`，并在管道中增加 BOM 校验防爆门。 |
