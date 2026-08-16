# 课题组智能知识库 Agent 协同插件 (SOP)

> **文档版本**：v2.0 (Enterprise/Industrial Grade)  
> **适用对象**：运维工程师、系统二次开发人员、课题组知识库管理员  
> **核心原则**：标准工程化、可复现、严禁隐式假设  

---

## 1. 开发与运行环境搭建 SOP

### 1.1 依赖准备与检查
在执行任何代码前，请确保开发机环境满足以下基线标准：
- **Node.js**：`>= v16.14.0` (推荐 LTS 版本)
- **npm**：`>= v8.0.0`
- **Python**：`>= v3.10.0` (推荐 Python 3.10 或 3.11)
- **SQLite3**：系统已安装 `sqlite3` 动态库

### 1.2 后端 Python 环境初始化
1. 进入后端服务目录：
   ```bash
   cd agent-service
   ```
2. 创建独立的 Python 虚拟环境（推荐使用 `venv` 或 `conda`）：
   ```bash
   python -m venv venv
   # Windows PowerShell 激活
   .\venv\Scripts\Activate.ps1
   # Linux/macOS 激活
   source venv/bin/activate
   ```
3. 安装依赖项（严格遵循版本号）：
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
4. 环境变量配置：在 `agent-service/` 根目录创建 `.env` 文件（参照 `.env.example`）：
   ```ini
   # 大模型 API Key 配置
   DASHSCOPE_API_KEY=sk-xxxxxx       # 通义千问 API 密钥
   ZHIPUAI_API_KEY=xxxxxx.xxxxxx     # 智谱 GLM-4 API 密钥
   OPENAI_API_KEY=sk-xxxxxx          # (可选) OpenAI 密钥
   
   # 后端端口与跨域配置
   PORT=8000
   ALLOWED_ORIGINS=app://obsidian.md,*
   ```

### 1.3 前端 Obsidian 插件环境初始化
1. 进入前端插件目录：
   ```bash
   cd obsidian-plugin-agent
   ```
2. 安装 Node 模块：
   ```bash
   npm install
   ```

---

## 2. 服务启动与热重载运维 SOP

### 2.1 后端 API 服务启动 SOP
在终端执行以下命令启动 Uvicorn 异步服务器：
```bash
python main.py
```
* **健康检查验证**：打开浏览器访问 `http://127.0.0.1:8000/docs`，确保能看到 Swagger UI 交互式 API 文档页面。

### 2.2 前端插件热编译与热重载 SOP
1. **Watch 监听模式 (开发时使用)**：
   ```bash
   npm run dev
   ```
   *修改 TypeScript 代码后，Rollup 会自动重新编译生成 `main.js`。*

2. **生产打包模式 (发布时使用)**：
   ```bash
   npm run build
   ```

3. **双写自动同步机制 (Hot-Sync)**：
   在 `package.json` 的 `build` 脚本中配置了自动复制逻辑。构建完成后，`main.js`、`manifest.json` 和 `styles.css` 会被自动同步至指定的 Obsidian Vault 插件目录：
   ```json
   "scripts": {
     "build": "tsc && rollup -c && cp main.js manifest.json styles.css \"E:/Obsidian仓库/Alone的知识库/.obsidian/plugins/obsidian-plugin-agent/\""
   }
   ```
4. **Obsidian 界面刷新**：修改代码后，在 Obsidian 中按 `Ctrl + R` (或在第三方插件列表中点击刷新按钮) 重新加载插件。

---

## 3. 标准二次开发 SOP (How-To Guides)

### SOP-01: 如何新增一种底层检索引擎 (Retriever Tool)

若需要为系统增加一种全新的检索能力（例如基于 ElasticSearch 或 DuckDB 的引擎），请遵循以下标准 4 步流程：

```
步骤 1: 编写纯 Raw Text 引擎脚本 (your_engine.py)
   │
步骤 2: 在 official_langgraph_engine.py 的 Node 2 注册策略分支
   │
步骤 3: 在 ChatView.ts 下拉菜单注册新 Strategy 枚举
   │
步骤 4: 执行控制变量沙盒联调测试
```

#### 规范代码示例：
1. **新建 `your_engine.py`**：
   ```python
   # 必须遵循 Tool 降级规范：只返回 Raw Text，禁止在此调用 LLM
   def query_your_engine(query: str, top_k: int = 3) -> str:
       # ... 执行检索逻辑 ...
       raw_text = "检索到的原始 MD 切片片段..."
       return raw_text
   ```
2. **在 `official_langgraph_engine.py` 的 Node 2 (`tool_execute_node`) 中增加分支**：
   ```python
   elif strategy == "your_engine":
       raw_res = query_your_engine(keywords)
       state["matched_docs"] = [{"title": "Your Engine Hits", "content": raw_res}]
   ```

---

### SOP-02: 如何修改 LangGraph 图路由逻辑

1. 打开 `official_langgraph_engine.py`。
2. 修改 `AgentState` 字典结构（如需新增状态字段）：
   ```python
   class AgentState(TypedDict):
       prompt: str
       strategy: str
       history: List[Dict[str, str]]
       matched_docs: List[Dict[str, str]]
       sufficiency_score: int  # 反思打分
   ```
3. 修改条件路由边 (Conditional Edge)：
   ```python
   def route_after_reflection(state: AgentState) -> str:
       if state["sufficiency_score"] < 7:
           return "query_rewrite_node"  # 打分不及格，退回重搜
       return END  # 及格，输出回复
   ```

---

## 4. 故障排查与应急救援 SOP (Disaster Recovery)

### 🚨 灾难场景：Windows 文件编码冲突 (Mojibake 乱码)
- **触发原因**：使用 PowerShell 脚本批量处理 Markdown 知识库时，未使用 UTF-8 显式声明，导致 GBK 覆盖物理文件。
- **救援 SOP 步骤**：
  1. 立即停止任何写盘脚本，保存现场。
  2. 检查开发项目中是否存在 `lab_knowledge_store.json` 或最近的离线 JSON 存储文件。
  3. 运行专用恢复脚本提取原始 UTF-8 字符串：
     ```python
     import json, os
     with open("lab_knowledge_store.json", "r", encoding="utf-8") as f:
         data = json.load(f)
     for doc in data["documents"]:
         # 恢复写盘逻辑...
     ```
  4. 重新扫描全库 Markdown 文件，确保 BOM 标记和 UTF-8 编码完全恢复。

---

## 5. 发布前工程检查清单 (Pre-Release Checklist)

在将代码交付或合并至主分支前，执行人必须逐条勾选确认：

- [ ] **TypeScript 编译**：执行 `tsc --noEmit` 无类型错误。
- [ ] **CORS 跨域测试**：确认后端 API 支持来自 `app://obsidian.md` 的请求。
- [ ] **SqliteSaver 持久化验证**：重启 Python 后端后，发起相同 `session_id` 的提问，确认能恢复上文。
- [ ] **编码规范审计**：确认所有新建 Python 文件的 `open()` 均带有 `encoding='utf-8'`。
- [ ] **敏感信息隔离**：确认 `.env` 已加入 `.gitignore`，未硬编码 API Key。
