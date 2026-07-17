import sys

# Windows 控制台默认使用 GBK 编码，代码里大量 print 语句包含 emoji（✅❌⚠️ 等），
# 会导致 UnicodeEncodeError 把整个请求打断。强制 stdout/stderr 用 UTF-8，避免打印崩溃。
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import json
import os
import re
import time
import uuid
from utils.lammps_vis_eval_tools import auto_visualize_eval_lammps_files
from LammpsAgents_by_langgraph import workflow

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境请限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- 历史记录：每次运行结束后落盘一份完整消息记录，便于前端回看 ----
HISTORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_history")
os.makedirs(HISTORY_DIR, exist_ok=True)
_HISTORY_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def _history_path(run_id: str):
    # run_id 来自 URL 路径，必须校验字符集，防止路径穿越
    if not _HISTORY_ID_RE.match(run_id):
        return None
    return os.path.join(HISTORY_DIR, f"{run_id}.json")


def _save_history(record: dict):
    path = _history_path(record["id"])
    if path is None:
        return
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

from fastapi import Query
from fastapi.responses import FileResponse

@app.get("/file")
def get_file(path: str = Query(..., description="文件绝对路径")):
    """
    获取指定绝对路径的文件内容。
    参数：path - 文件绝对路径（query参数）
    返回：文件流或404错误信息
    """
    import os
    if not os.path.isfile(path):
        return JSONResponse({"error": "file not found"}, status_code=404)
    return FileResponse(path)

@app.post("/run_lammps_agents_stream")
async def run_lammps_agents_stream(request: Request):
    """
    运行 LAMMPS Agents 并以流式方式返回推理和执行过程。
    参数：user_input - 用户输入内容（json body）
    返回：event-stream流，包含各节点消息和状态
    """
    data = await request.json()
    user_input = data["user_input"]

    def event_stream():
        config = {"configurable": {"thread_id": "demo"}}
        input_dict = {
            "messages": [{
                "role": "human",
                "content": user_input
            }]
        }
        collected = []
        run_id = None
        status = "success"
        try:
            for output in workflow.stream(input_dict, config):
                for key, value in output.items():
                    msg = {
                        "node": key,
                        "message": value["messages"][-1].content,
                        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
                        "state": {
                            "final_score": value.get("final_score", 0),
                            "lammps_code": value.get("lammps_code", ""),
                            "run_result": value.get("run_result", ""),
                            "eval_result": value.get("eval_result", ""),
                            "round": value.get("round", 0),
                            "user_input": value.get("user_input", ""),
                            "generate_dir": value.get("generate_dir", ""),
                            "llm_name": value.get("llm_name", ""),
                            "checkout_filename_list": value.get("checkout_filename_list", []),
                            "abs_generate_dir": value.get("abs_generate_dir", "")
                        }
                    }
                    if not run_id and msg["state"].get("generate_dir"):
                        run_id = msg["state"]["generate_dir"]
                    collected.append(msg)
                    yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
        except Exception as e:
            # Surface backend failures (LLM errors, LAMMPS run errors, etc.) to the
            # frontend as a normal SSE event instead of letting the ASGI app crash
            # with no message reaching the client.
            status = "error"
            error_msg = {
                "node": "error",
                "message": str(e),
                "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            }
            collected.append(error_msg)
            yield f"data: {json.dumps(error_msg, ensure_ascii=False)}\n\n"
        finally:
            final_score = 0
            for m in reversed(collected):
                score = m.get("state", {}).get("final_score")
                if score:
                    final_score = score
                    break
            _save_history({
                "id": run_id or f"run-{uuid.uuid4().hex[:12]}",
                "user_input": user_input,
                "created_at": time.time(),
                "status": status,
                "final_score": final_score,
                "messages": collected,
            })

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/history")
async def list_history(limit: int = 50):
    """
    列出历史运行记录（不含完整消息内容，仅摘要）。
    """
    items = []
    for fname in os.listdir(HISTORY_DIR):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(HISTORY_DIR, fname), "r", encoding="utf-8") as f:
                data = json.load(f)
            items.append({
                "id": data.get("id"),
                "user_input": data.get("user_input", ""),
                "created_at": data.get("created_at", 0),
                "status": data.get("status", "success"),
                "final_score": data.get("final_score", 0),
            })
        except Exception:
            continue
    items.sort(key=lambda r: r.get("created_at", 0), reverse=True)
    return {"items": items[:limit]}


@app.get("/history/{run_id}")
async def get_history_item(run_id: str):
    """
    获取指定历史运行的完整消息记录，供前端回放展示。
    """
    path = _history_path(run_id)
    if path is None:
        return JSONResponse({"error": "invalid run_id"}, status_code=400)
    if not os.path.isfile(path):
        return JSONResponse({"error": "not found"}, status_code=404)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.delete("/history/{run_id}")
async def delete_history_item(run_id: str):
    """
    删除指定历史运行记录。
    """
    path = _history_path(run_id)
    if path is None:
        return JSONResponse({"error": "invalid run_id"}, status_code=400)
    if not os.path.isfile(path):
        return JSONResponse({"error": "not found"}, status_code=404)
    os.remove(path)
    return {"status": "success"}

@app.post("/visualize_lammps")
async def visualize_lammps(request: Request):
    """
    输入一个Lammps文本结果的文件夹，进行可视化渲染，保存可视化图片和GIF文件到相同文件夹。
    参数：dir_path - 目录绝对路径（json body）
    返回：处理成功或失败信息
    """
    data = await request.json()
    dir_path = data.get("dir_path", "")
    if not os.path.isabs(dir_path):
        return JSONResponse({"error": "dir_path must be absolute path"}, status_code=400)
    if not os.path.isdir(dir_path):
        return JSONResponse({"error": "dir_path is not a valid directory"}, status_code=400)
    try:
        auto_visualize_lammps_files(dir_path)
        return {"status": "success", "message": "可视化处理完成"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    
@app.post("/list_files_in_dir")
async def list_files_in_dir(request: Request):
    """
    列出指定目录下的所有文件（递归）。
    参数：dir_path - 目录绝对路径（json body）
    返回：所有文件的绝对路径列表，或错误信息
    """
    data = await request.json()
    dir_path = data.get("dir_path", "")
    print('收到dir_path:', dir_path)
    print('路径是否存在:', os.path.exists(dir_path))
    print('是否为目录:', os.path.isdir(dir_path))
    auto_visualize_eval_lammps_files(dir_path)
    if not os.path.isabs(dir_path):
        return JSONResponse({"error": "dir_path must be absolute path"}, status_code=400)
    if not os.path.isdir(dir_path):
        return JSONResponse({"error": "dir_path is not a valid directory"}, status_code=400)
    file_list = []
    for root, dirs, files in os.walk(dir_path):
        for file in files:
            file_list.append(os.path.abspath(os.path.join(root, file)))
    return {"files": file_list}

@app.get("/test")
async def test_api():
    """
    测试接口，验证服务可访问。
    返回：简单的中文提示信息
    """
    return {"message": "测试成功，服务可访问"}

@app.post("/auto_visualize_lammps_files")
async def auto_visualize_lammps_files_api(request: Request):
    """
    自动可视化指定文件夹下的LAMMPS相关文件。
    参数：dir_path - 目录绝对路径（json body）
    返回：处理成功或失败信息
    """
    data = await request.json()
    dir_path = data.get("dir_path", "")
    if not os.path.isabs(dir_path):
        return JSONResponse({"error": "dir_path must be absolute path"}, status_code=400)
    if not os.path.isdir(dir_path):
        return JSONResponse({"error": "dir_path is not a valid directory"}, status_code=400)
    try:
        auto_visualize_eval_lammps_files(dir_path)
        return {"status": "success", "message": "可视化处理完成"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)