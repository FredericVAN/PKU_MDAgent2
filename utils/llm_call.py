# LLM-based LAMMPS script generator from natural language tasks
import json
import time
import openai
from openai import OpenAI  # 取代旧版 openai.ChatCompletion
import concurrent.futures
from datetime import datetime
from tqdm import tqdm
import os
from dotenv import load_dotenv
import time

# 加载.env文件中的环境变量
load_dotenv()

# 从环境变量获取API密钥
openai.api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai.api_key)
RETRY_LIMIT = 5


qwen_client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)
# vllm服务配置
# 可以通过环境变量 VLLM_API_BASE 和 VLLM_API_KEY 来配置
# 例如: export VLLM_API_BASE="http://localhost:8000/v1"
vllm_api_key = os.getenv("VLLM_API_KEY", "EMPTY")
vllm_api_base = os.getenv("VLLM_API_BASE", "http://localhost:8000/v1")
print(f"vllm_api_base: {vllm_api_base}")
def get_vllm_client():
    """获取vllm客户端，使用最新的配置"""
    return OpenAI(
        api_key=vllm_api_key,
        base_url=vllm_api_base,
    )

def check_vllm_service_status():
    """
    检查vllm服务状态和可用模型
    返回: (is_available: bool, available_models: list, error_message: str)
    """
    import requests
    try:
        # 检查健康状态
        health_url = vllm_api_base.replace('/v1', '/health')
        response = requests.get(health_url, timeout=5)
        if response.status_code != 200:
            return False, [], f"健康检查失败: HTTP {response.status_code}"
        
        # 获取可用模型列表
        try:
            resp = requests.get(f"{vllm_api_base}/models")
            print(resp.json())

            available_models = [model['id'] for model in resp.json()['data']]
            return True, available_models, None
        except Exception as e:
            return True, [], f"无法获取模型列表: {e}"
            
    except requests.exceptions.ConnectionError:
        return False, [], f"无法连接到vllm服务 ({vllm_api_base})，请确保服务正在运行"
    except Exception as e:
        return False, [], f"检查服务状态时出错: {e}"

def call_vllm(system_prompt: str= 'You are a helpful assistant.', user_prompt: str='', temperature=0.7, model="Qwen/Qwen3-8B",enable_thinking=True) -> str:
    import requests
    from openai import APIError, APIConnectionError, APITimeoutError
    
    for attempt in range(1, RETRY_LIMIT + 1):
        try:
            start = time.time()
            # 使用最新的配置创建client
            client = get_vllm_client()
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                extra_body={
                "chat_template_kwargs": {"enable_thinking": enable_thinking},
                },
            )
            duration = time.time() - start
            return response.choices[0].message.content.strip()
        except APIConnectionError as e:
            error_msg = f"连接错误: {e}"
            if "502" in str(e) or "Bad Gateway" in str(e):
                error_msg += f"\n   可能原因: vllm服务未运行或已崩溃，请检查服务状态"
            elif "Connection refused" in str(e) or "无法连接" in str(e):
                error_msg += f"\n   可能原因: vllm服务未启动，请检查 {vllm_api_base} 是否可访问"
            print(f"⚠️ Attempt {attempt} failed: {error_msg}")
            if attempt == RETRY_LIMIT:
                return f"ERROR: {error_msg}"
            time.sleep(8)
        except APIError as e:
            error_msg = f"API错误: {e}"
            if hasattr(e, 'status_code'):
                if e.status_code == 502:
                    error_msg += f"\n   502 Bad Gateway: vllm服务可能已崩溃或过载，请检查服务日志"
                    # 在502错误时检查服务状态
                    if attempt == 1:
                        is_available, available_models, check_error = check_vllm_service_status()
                        if not is_available:
                            error_msg += f"\n   服务状态检查: {check_error}"
                        elif available_models:
                            error_msg += f"\n   可用模型: {', '.join(available_models)}"
                elif e.status_code == 404:
                    error_msg += f"\n   404 Not Found: 模型 '{model}' 可能不存在"
                    # 在404错误时列出可用模型
                    if attempt == 1:
                        is_available, available_models, check_error = check_vllm_service_status()
                        if available_models:
                            error_msg += f"\n   可用模型: {', '.join(available_models)}"
                            error_msg += f"\n   提示: 请使用上述模型名称之一"
                elif e.status_code == 503:
                    error_msg += f"\n   503 Service Unavailable: vllm服务暂时不可用，可能正在处理其他请求"
            print(f"⚠️ Attempt {attempt} failed: {error_msg}")
            if attempt == RETRY_LIMIT:
                return f"ERROR: {error_msg}"
            time.sleep(8)
        except APITimeoutError as e:
            error_msg = f"请求超时: {e}"
            print(f"⚠️ Attempt {attempt} failed: {error_msg}")
            if attempt == RETRY_LIMIT:
                return f"ERROR: {error_msg}"
            time.sleep(8)
        except Exception as e:
            error_type = type(e).__name__
            error_msg = f"{error_type}: {e}"
            # 检查是否是HTTP错误
            if "502" in str(e) or "Bad Gateway" in str(e):
                error_msg += f"\n   可能原因: vllm服务未运行或已崩溃"
            elif "Connection" in error_type or "连接" in str(e):
                error_msg += f"\n   可能原因: 无法连接到vllm服务 ({vllm_api_base})"
            print(f"⚠️ Attempt {attempt} failed: {error_msg}")
            if attempt == RETRY_LIMIT:
                return f"ERROR: {error_msg}"
            time.sleep(8)

def call_qwen(system_prompt: str = 'You are a helpful assistant.', user_prompt: str='', temperature=0.7, model="qwen-turbo-1101",is_print=False,enable_thinking=False) -> str:
    for attempt in range(1, RETRY_LIMIT + 1):
        try:
            # ✅ 启用流式输出 + enable_thinking
            stream = qwen_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                stream=True,
                extra_body={"enable_thinking": enable_thinking}
            )
            full_output = ""
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    if is_print:
                        print(delta, end="", flush=True)
                    full_output += delta
            if is_print:
                print()  # 换行
            return full_output.strip()

        except Exception as e:
            print(f"⚠️ Attempt {attempt} failed: {e}")
            if attempt == RETRY_LIMIT:
                return f"ERROR: {e}"
            time.sleep(8)


#最好改用gpt-o3
def call_openai(system_prompt: str, user_prompt: str, temperature=0.7, model="gpt-4.1") -> str:
    for attempt in range(1, RETRY_LIMIT + 1):
        try:
            start = time.time()
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
            )
            duration = time.time() - start
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"⚠️ Attempt {attempt} failed: {e}")
            if attempt == RETRY_LIMIT:
                return f"ERROR: {e}"
            time.sleep(8)

def batch_call_openai(system_prompt: str, user_prompts: list, temperature=0.7, model="gpt-4.1", max_workers=5) -> list:
    """
    批量调用OpenAI API进行推理
    
    Args:
        system_prompt: 系统提示词
        user_prompts: 用户提示词列表
        temperature: 温度参数
        model: 模型名称
        max_workers: 最大并发数
    
    Returns:
        结果列表，包含每个提示词的响应
    """
    results = []
    
    def process_single_prompt(user_prompt):
        return call_openai(system_prompt, user_prompt, temperature, model)
    
    # 使用线程池进行并发处理
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_prompt = {executor.submit(process_single_prompt, prompt): prompt for prompt in user_prompts}
        
        # 使用tqdm显示进度
        with tqdm(total=len(user_prompts), desc="批量推理进度") as pbar:
            for future in concurrent.futures.as_completed(future_to_prompt):
                prompt = future_to_prompt[future]
                try:
                    result = future.result()
                    results.append({
                        "prompt": prompt,
                        "response": result,
                        "timestamp": datetime.now().isoformat()
                    })
                except Exception as e:
                    results.append({
                        "prompt": prompt,
                        "response": f"ERROR: {e}",
                        "timestamp": datetime.now().isoformat()
                    })
                pbar.update(1)
    
    return results

def save_batch_results(results: list, output_file: str):
    """
    保存批量推理结果到文件
    
    Args:
        results: 推理结果列表
        output_file: 输出文件路径
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def vllm_call(system_prompt: str, user_prompt: str, temperature=0.7, model="qwen-turbo-1101") -> str:
    '''
    https://qwen.readthedocs.io/en/latest/deployment/vllm.html#parsing-thinking-content
    注意: 这个函数使用全局的vllm_api_base配置
    '''
    vllm_client = get_vllm_client()
    chat_response = vllm_client.chat.completions.create(
        model="Qwen/Qwen3-8B",
        messages=[
            {"role": "user", "content": "Give me a short introduction to large language models."},
        ],
        max_tokens=8192,
        temperature=0.7,
        top_p=0.8,
        presence_penalty=1.5,
        extra_body={
            "top_k": 20, 
            "chat_template_kwargs": {"enable_thinking": False},
        },
    )
    print("Chat response:", chat_response)

if __name__ == "__main__":
    #测试check_vllm_service_status()
    resposne = call_vllm(system_prompt="You are a helpful assistant.", user_prompt="What is the capital of France?", enable_thinking=True,model="mdagent-v1")
    print(resposne)
    resposne2 = call_vllm(system_prompt="You are a helpful assistant.", user_prompt="What is the capital of France?", enable_thinking=False,model="mdagent-v1")
    print(resposne2)
    # #测试一下openai
    # system_prompt = """
    # You are a LAMMPS expert. Given a user request describing a molecular dynamics task, 
    # generate a minimal, working LAMMPS input script (.in file) in plain text. 
    # The script should:
    # 1) include units, atom_style, lattice, region, create_box, create_atoms, mass,
    # 2) define suitable pair_style and pair_coeff using the given potential,
    # 3) apply velocity and fix (e.g., nve or nvt), and
    # 4) run for the given number of steps, writing log and dump outputs to file.
    # """
    # user_prompt = """
    # Simulate the diffusion process of a single-component gas molecule using LAMMPS.
    # """
    # response = call_openai(system_prompt, user_prompt)
    # print(response)
    
    # # 测试批量推理
    # test_prompts = [
    #     "用lammps实现Cu的建模",
    #     "用lammps计算Al的平衡晶格常数", 
    #     "用lammps实现金刚石三棱锥刀具的建模"
    # ]
    
    # print("\n开始批量推理测试...")
    # batch_results = batch_call_openai(system_prompt, test_prompts, max_workers=3)
    
    # # 保存结果
    # save_batch_results(batch_results, "batch_results.json")
    # print(f"批量推理完成，结果已保存到 batch_results.json")