from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
import time
from typing import List, Optional
import os
import json
from official_langgraph_engine import official_agent_workflow
import vector_engine
import graph_engine
import bm25_engine

router = APIRouter(prefix="/ai", tags=["AI Copilot & Agents"])

def sync_evaluate_and_ingest(question: str, answer: str, author: str):
    from official_langgraph_engine import llm
    from langchain_core.messages import SystemMessage, HumanMessage
    import re
    
    print(f"🕵️ [LMVT 自动沉淀] 开始后台偷偷评估问答价值...")
    sys_msg = SystemMessage(content=(
        "你是一个严格的学术知识筛选器。请评估以下问答是否具有长期沉淀到全局知识库的价值。\n"
        "如果只是日常寒暄、无意义报错或信息量极低的闲聊，请打低分。\n"
        "如果包含了专业知识探讨、深入解析或有参考价值的经验，请打高分。\n"
        "请直接输出一个0到10的分数，不要输出任何其他字符。例如：9"
    ))
    user_prompt = f"提问者：{author}\n问题：{question}\n解答：{answer}"
    
    try:
        response = llm.invoke([sys_msg, HumanMessage(content=user_prompt)])
        score_str = response.content.strip()
        match = re.search(r'\d+', score_str)
        score = int(match.group()) if match else 0
    except Exception as e:
        print(f"打分失败: {e}")
        score = 0
        
    print(f"🕵️ [LMVT 评估结果] 价值得分: {score}/10")
    if score >= 8:
        print("📥 触发二次入库，生成 Markdown 文件并重建索引...")
        archive_dir = os.path.join(os.path.dirname(__file__), "..", "shared_vault", "Global_QA_Archive")
        os.makedirs(archive_dir, exist_ok=True)
        
        safe_title = "".join([c for c in question[:20] if c.isalnum() or c in [' ', '_', '-']]).strip()
        if not safe_title:
            safe_title = f"qa_archive_{int(time.time())}"
        
        filename = f"{safe_title}_{int(time.time())}.md"
        filepath = os.path.join(archive_dir, filename)
        
        content = f"---\ntitle: {safe_title}\nsource: 二次入库 (Secondary Ingestion)\ntype: QA_Archive\nauthor: {author}\n---\n\n# 核心问题\n{question}\n\n# 沉淀解答\n{answer}\n\n> **系统注记**：本知识由大模型后台判定为高价值知识 (得分 {score}) 并触发 LMVT 二次入库机制自动沉淀。\n"
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
            
        print(f"✅ 文件已落盘: {filepath}")
        
        try:
            vector_engine.build_or_update_index()
            graph_engine.build_or_update_graph()
            print("🚀 [全库重建完成] 新知识已无缝切入 Vector 和 Graph 索引池！")
        except Exception as e:
            print(f"重建索引失败: {e}")

async def async_evaluate_and_ingest(question: str, answer: str, author: str):
    import asyncio
    await asyncio.to_thread(sync_evaluate_and_ingest, question, answer, author)


class CopilotRequest(BaseModel):
    prompt: str
    docs: Optional[List[dict]] = []

class AutoLinkRequest(BaseModel):
    document_id: str
    content: str

@router.post("/copilot")
async def global_copilot(req: CopilotRequest):
    """由官方 LangGraph StateGraph 执行引擎完成问答与 RAG 检索"""
    prompt = req.prompt.strip()
    docs = req.docs or []

    if not docs:
        base_dir = os.path.join(os.path.dirname(__file__), "..", "shared_vault")
        if os.path.exists(base_dir):
            for root, dirs, files in os.walk(base_dir):
                for f in files:
                    if f.endswith(".md"):
                        try:
                            with open(os.path.join(root, f), "r", encoding="utf-8") as file:
                                docs.append({
                                    "title": f,
                                    "content": file.read(),
                                    "author": "system"
                                })
                        except Exception:
                            pass

    # 调用 Official LangGraph 状态图管线
    result = official_agent_workflow.run(prompt, docs)
    return result

class ChatRequest(BaseModel):
    query: str
    scope: str
    strategy: str = "agentic"
    session_id: str = "default_session"
    history: list = []

@router.post("/chat")
async def plugin_chat(req: ChatRequest, background_tasks: BackgroundTasks):
    """供 Obsidian 插件使用的聊天接口"""
    prompt = req.query
    scope = req.scope
    
    docs = []
    base_dir = os.path.join(os.path.dirname(__file__), "..", "shared_vault")
    
    if os.path.exists(base_dir):
        # Determine which folder to scan
        if scope == "global" or scope == "🌐 全局知识库 (Global)":
            scan_dirs = [os.path.join(base_dir, d) for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
        else:
            # Try to extract name (e.g. "👤 张同学的笔记" -> "张同学")
            username = scope.replace("👤", "").replace("的笔记", "").replace(" (自己)", "").strip()
            scan_dirs = [os.path.join(base_dir, username)]
            
        for d in scan_dirs:
            if os.path.exists(d):
                for root, dirs, files in os.walk(d):
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
        sample_dir = os.path.join(os.path.dirname(__file__), "..", "sample_vault")
        if os.path.exists(sample_dir):
            for root, dirs, files in os.walk(sample_dir):
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
                            
    # Fallback response for missing OpenAI key in local tests
    try:
        result = official_agent_workflow.run(prompt, docs, history=req.history, strategy=req.strategy, session_id=req.session_id)
    except Exception as e:
        # If the engine fails (e.g. no API key), we provide a mock comprehensive response
        result = {
            "answer": f"**[模拟回答]** 针对问题：`{prompt}`\n\n"
                      f"根据您的检索范围 `{scope}`，我们在云端 {len(docs)} 篇笔记中进行了搜索提炼。\n"
                      f"由于当前可能未配置大模型 API Key，这是本地代理返回的测试回复。\n\n"
                      f"**(提示：您可以在后台配置有效的 OpenAI API Key 以体验真正的 LangGraph 跨界推理功能)**\n"
                      f"错误信息: {str(e)}"
        }
    
    # 触发 LMVT 二次入库价值判定 (后台异步执行，不阻塞用户响应)
    final_answer = result.get("reply") or result.get("answer", "")
    if final_answer and "模拟回答" not in final_answer:
        author = req.scope.replace("👤", "").replace("的笔记", "").replace(" (自己)", "").strip()
        if not author or author == "global":
            author = "User"
        background_tasks.add_task(async_evaluate_and_ingest, prompt, final_answer, author)
        
    return result

@router.post("/build_vector")
async def build_vector_db():
    """手动触发全库切片与向量构建"""
    success = vector_engine.build_or_update_index()
    if success:
        return {"success": True, "message": "全库向量化构建完成！"}
    else:
        return {"success": False, "message": "构建失败或知识库为空。"}

@router.post("/build_graph")
async def build_graph_db():
    """手动触发全库图谱构建"""
    success = graph_engine.build_or_update_graph()
    if success:
        return {"success": True, "message": "全库知识图谱构建完成！"}
    else:
        return {"success": False, "message": "构建失败或知识库为空。"}

@router.post("/auto-link")
async def auto_link_generator(req: AutoLinkRequest):
    """后台双链自动关联节点"""
    suggested_keywords = ["纳米材料", "实验步骤A", "SEM扫描", "SSH隧道"]
    links_added = []
    new_content = req.content

    for kw in suggested_keywords:
        if kw in new_content and f"[[{kw}]]" not in new_content:
            new_content = new_content.replace(kw, f"[[{kw}]]", 1)
            links_added.append(kw)

    return {
        "document_id": req.document_id,
        "author": "🤖 Official LangGraph Agent",
        "commit_message": f"AI 自动巡检：补全课题组知识关联 [[{', '.join(links_added)}]]",
        "updated_content": new_content,
        "links_added": links_added
    }

@router.post("/trigger_nightly_benchmark")
async def trigger_nightly_benchmark():
    """幽灵巡检节点 (Nightly Self-Benchmarking)
    模拟定时任务触发，随机抽取最近的 3 个历史沉淀知识，重新在当前的知识库中推演，对比裁判打分，生成体检报告。
    """
    import random
    from datetime import datetime
    
    archive_dir = os.path.join(os.path.dirname(__file__), "..", "shared_vault", "Global_QA_Archive")
    if not os.path.exists(archive_dir):
        return {"success": False, "message": "尚未有沉淀知识可供基准测试。"}
        
    md_files = [f for f in os.listdir(archive_dir) if f.endswith(".md")]
    if not md_files:
        return {"success": False, "message": "尚无沉淀知识。"}
        
    sample_files = random.sample(md_files, min(3, len(md_files)))
    
    reports = []
    total_score = 0
    
    print("👻 [幽灵巡检] 开始夜间自我对抗基准测试...")
    for f_name in sample_files:
        filepath = os.path.join(archive_dir, f_name)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                
            # 提取原问题
            question = ""
            if "# 核心问题" in content:
                question = content.split("# 核心问题")[1].split("# 沉淀解答")[0].strip()
            else:
                continue
                
            if not question:
                continue
                
            print(f"👻 测试案例: {question[:30]}...")
            # 静默跑全量重构图谱
            result = official_agent_workflow.run(question, docs=[], strategy="agentic", session_id="nightly_bench")
            new_score = result.get("sufficiency_score", 0.0)
            
            # 解析原得分
            old_score = 10.0 # 默认入库分数
            import re
            old_match = re.search(r'得分\s*(\d+(\.\d+)?)', content)
            if old_match:
                old_score = float(old_match.group(1))
                
            diff = new_score - old_score
            status = "✅ 稳定" if diff >= -1 else "⚠️ 退化"
            
            reports.append(f"- **测试用例**: `{question}`\n  - 历史得分: {old_score}/10\n  - 今日重测: {new_score}/10\n  - 状态判定: {status}\n")
            total_score += new_score
            
        except Exception as e:
            print(f"测试 {f_name} 时发生错误: {e}")
            
    avg_score = total_score / len(reports) if reports else 0
    
    report_content = f"""# 幽灵巡检：知识库夜间体检报告
**巡检时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**综合健康度**: {avg_score:.1f}/10

## 抽样回测清单
{chr(10).join(reports)}

> **架构师注记**: 如果出现大面积“退化”，说明近期涌入的高级噪声或错误笔记破坏了向量/图谱的干涉边界。请及时审查新入库的笔记。
"""
    reports_dir = os.path.join(os.path.dirname(__file__), "..", "shared_vault", "System_Reports")
    os.makedirs(reports_dir, exist_ok=True)
    report_file = os.path.join(reports_dir, f"nightly_report_{int(time.time())}.md")
    
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print(f"👻 [幽灵巡检完成] 报告已生成至 {report_file}")
    
    return {"success": True, "message": "夜间基准测试完成！报告已落盘。"}

# --------------------------------------------------------------------------
# 课题组 3 端分布式中转服务端 API (Server Hub Endpoints)
# --------------------------------------------------------------------------

# 内存/文件持久化中转数据结构
MEMBERS_DB = [
    {"id": "m1", "name": "张同学", "role": "student", "status": "approved", "join_date": "2026-07-15"},
    {"id": "m2", "name": "李同学", "role": "student", "status": "approved", "join_date": "2026-07-18"},
    {"id": "m3", "name": "王同学", "role": "student", "status": "pending", "join_date": "2026-08-08"},
]

QA_DB = []

GIT_COMMITS_DB = [
    {"hash": "e9a18f2", "author": "张同学", "message": "feat: 新增 [[系统代理 vs TUN模式]] 对比架构笔记", "time": "10 分钟前"},
    {"hash": "c8b4012", "author": "李同学", "message": "docs: 补全 [[自建科学上网节点完整指南]] 双链索引", "time": "25 分钟前"},
    {"hash": "f4721d9", "author": "🤖 Agent", "message": "auto: LangGraph 自省优化 [[代理协议]] 语法定义", "time": "1 小时前"},
]

class MemberJoinRequest(BaseModel):
    name: str

class MemberApproveRequest(BaseModel):
    member_id: str

class QASubmitRequest(BaseModel):
    student_name: str
    question: str

class QAReplyRequest(BaseModel):
    qa_id: str
    author_name: str
    reply_text: str

@router.get("/server/members")
async def get_members():
    """查看全课题组成员清单与审核状态"""
    return {"members": MEMBERS_DB}

@router.post("/server/members/join")
async def join_member(req: MemberJoinRequest):
    """学生端提交加入课题组申请"""
    new_m = {
        "id": f"m{len(MEMBERS_DB) + 1}",
        "name": req.name,
        "role": "student",
        "status": "pending",
        "join_date": "2026-08-08"
    }
    MEMBERS_DB.append(new_m)
    return {"success": True, "message": "申请已成功发送至导师端审批！", "member": new_m}

@router.post("/server/members/approve")
async def approve_member(req: MemberApproveRequest):
    """导师端审批通过新成员加入"""
    for m in MEMBERS_DB:
        if m["id"] == req.member_id:
            m["status"] = "approved"
            return {"success": True, "message": f"已成功批准 {m['name']} 加入课题组！", "member": m}
    raise HTTPException(status_code=404, detail="未找到该成员记录")

@router.get("/server/qa")
async def get_qa_list():
    """调阅课题组 Q&A 问答流"""
    return {"qa_list": QA_DB}

@router.post("/server/qa/submit")
async def submit_qa(req: QASubmitRequest):
    """学生向导师提问"""
    new_qa = {
        "id": f"qa{len(QA_DB) + 1}",
        "student_name": req.student_name,
        "question": req.question,
        "status": "pending",
        "replies": [],
        "created_at": "刚刚"
    }
    QA_DB.insert(0, new_qa)
    return {"success": True, "message": "提问已发送至导师端！", "qa": new_qa}

@router.post("/server/qa/reply")
async def reply_qa(req: QAReplyRequest, background_tasks: BackgroundTasks):
    """任何成员都可以回复一个提问（类似朋友圈评论）"""
    for qa in QA_DB:
        if qa["id"] == req.qa_id:
            # Generate a unique reply ID
            reply_id = f"r{len(qa['replies']) + 1}-{int(time.time())}"
            qa["replies"].append({
                "id": reply_id,
                "author": req.author_name,
                "content": req.reply_text,
                "time": "刚刚"
            })
            qa["status"] = "answered"
            
            # 触发社区探讨二次入库 (后台异步执行)
            background_tasks.add_task(async_evaluate_and_ingest, qa["question"], req.reply_text, req.author_name)
            
            return {"success": True, "message": "回复成功！", "qa": qa}
    raise HTTPException(status_code=404, detail="未找到该提问记录")

class QADeleteRequest(BaseModel):
    qa_id: str
    username: str

@router.delete("/server/qa/delete")
async def delete_qa(req: QADeleteRequest):
    """删除整个提问 (仅提问者自己可删)"""
    for i, qa in enumerate(QA_DB):
        if qa["id"] == req.qa_id:
            if qa["student_name"] != req.username:
                raise HTTPException(status_code=403, detail="无权删除他人的问题")
            del QA_DB[i]
            return {"success": True, "message": "问题已删除"}
    raise HTTPException(status_code=404, detail="未找到该记录")

class ReplyDeleteRequest(BaseModel):
    qa_id: str
    reply_id: str
    username: str

@router.delete("/server/qa/reply/delete")
async def delete_reply(req: ReplyDeleteRequest):
    """撤回/删除一条回复 (仅回复者自己可删)"""
    for qa in QA_DB:
        if qa["id"] == req.qa_id:
            for i, rep in enumerate(qa["replies"]):
                if rep.get("id") == req.reply_id:
                    if rep["author"] != req.username:
                        raise HTTPException(status_code=403, detail="无权撤回他人的回复")
                    del qa["replies"][i]
                    # Check if empty replies
                    if len(qa["replies"]) == 0:
                        qa["status"] = "pending"
                    return {"success": True, "message": "回复已撤回"}
            raise HTTPException(status_code=404, detail="未找到该回复")
    raise HTTPException(status_code=404, detail="未找到该问题")

@router.get("/server/git/commits")
async def get_git_commits():
    """获取课题组分布式 Git Commit 变更审计流"""
    return {"commits": GIT_COMMITS_DB}

