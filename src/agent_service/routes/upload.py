from fastapi import APIRouter
from pydantic import BaseModel
import os
import re
import aiofiles
from cloud_db import db

router = APIRouter(prefix="/upload", tags=["Upload & Sync Status"])

class UploadRequest(BaseModel):
    username: str
    filename: str
    content: str

class FolderRequest(BaseModel):
    username: str
    foldername: str

@router.post("")
async def upload_markdown(req: UploadRequest):
    """接收 Obsidian 插件上传的 markdown 笔记，按 username 隔离保存并登记到总库"""
    
    # 基础路径 /agent-service/shared_vault/
    base_dir = os.path.join(os.path.dirname(__file__), "..", "shared_vault")
    user_dir = os.path.join(base_dir, req.username)
    
    os.makedirs(user_dir, exist_ok=True)
    
    # 确保路径分隔符正确，防止目录穿越
    clean_filename = req.filename.replace('\\', '/')
    parts = [p for p in clean_filename.split('/') if p and p != '..' and p != '.']
    if not parts:
        parts = ["untitled.md"]
        
    file_path = os.path.join(user_dir, *parts)
    
    # 递归创建必要的子文件夹
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
        await f.write(req.content)
        
    # 更新数据库状态
    db.update_member_upload(req.username, file_count=1)
        
    return {"success": True, "message": f"Successfully uploaded {req.filename} to {req.username}'s vault"}

@router.post("/folder")
async def create_folder(req: FolderRequest):
    """单独创建目录（包括空目录）"""
    base_dir = os.path.join(os.path.dirname(__file__), "..", "shared_vault")
    user_dir = os.path.join(base_dir, req.username)
    
    clean_foldername = req.foldername.replace('\\', '/')
    parts = [p for p in clean_foldername.split('/') if p and p != '..' and p != '.']
    if not parts:
        return {"success": True, "message": "Root folder handled."}
        
    folder_path = os.path.join(user_dir, *parts)
    os.makedirs(folder_path, exist_ok=True)
    
    return {"success": True, "message": f"Folder {req.foldername} created."}

@router.get("/status")
async def get_cloud_status():
    """获取云端总库成员列表及状态"""
    return {"status": "ok", "members": db.get_cloud_status()}

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def build_tree(path, rel_path=""):
    """递归构建目录树"""
    tree = []
    try:
        entries = sorted(os.listdir(path), key=natural_sort_key)
    except Exception:
        return tree
        
    for entry in entries:
        full_path = os.path.join(path, entry)
        current_rel = os.path.join(rel_path, entry).replace('\\', '/')
        if os.path.isdir(full_path):
            tree.append({
                "name": entry,
                "type": "folder",
                "path": current_rel,
                "children": build_tree(full_path, current_rel)
            })
        else:
            if entry.endswith('.md'):
                tree.append({
                    "name": entry,
                    "type": "file",
                    "path": current_rel
                })
    return tree

@router.get("/tree/{username}")
async def get_cloud_tree(username: str):
    """获取特定用户的云端目录结构树"""
    base_dir = os.path.join(os.path.dirname(__file__), "..", "shared_vault")
    user_dir = os.path.join(base_dir, username)
    
    if not os.path.exists(user_dir):
        return {"tree": []}
        
    tree = build_tree(user_dir)
    return {"tree": tree}
