import sys
import os

# 确保无论在项目根目录还是 agent_service 目录内运行，模块都能正确定位
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import ai, upload

app = FastAPI(
    title="课题组私域知识库智能协同 Agent 服务 (Lab AI Copilot)",
    description="为 Obsidian 原生插件提供全局 AI 问答、多路 RAG 互补检索与双循环自省打分服务",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ai.router, prefix="/api")
app.include_router(upload.router, prefix="/api")

@app.get("/health")
async def health():
    return {"status": "ok", "service": "Python Agent Microservice active"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
