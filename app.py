from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import json
import os
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
        for output in workflow.stream(input_dict, config):
            for key, value in output.items():
                msg = {
                    "node": key,
                    "message": value["messages"][-1].content,
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
                yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

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