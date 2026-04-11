import os
from dotenv import load_dotenv
from utils.lammps_potential_tools import check_lammps_potentials_tool
from utils.lammps_run_tools import run_lammps_in_process
from prompt import lammps_evaluator_system_prompt, generate_lammps_script_prompt, lammps_syntax_check_prompt
from utils.lammps_potential_utils.lammps_potential_api import check_lammps_potentials, get_similar_potentials_recommendation
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from utils.log_utils import log_to_file
import json
import json_repair
from utils.common_utils import extract_jsonstr_from_outputstr, extract_codestr_from_outputstr, generate_random_dirname,cal_reward
import csv
import os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
print("已设置Hugging Face镜像源为:", os.environ.get('HF_ENDPOINT', '默认源'))
from langgraph.graph import START
import shutil
from langchain_core.messages import AnyMessage, HumanMessage, AIMessage
from tqdm import tqdm
import datetime
from utils.lammps_check_systax_tools import check_can_run_lammps
# 加载环境变量
load_dotenv()


def get_chat_llm(provider:str="ollama",model_name:str="qwen3:8b"):
    if provider == "ollama":
        from langchain_ollama import ChatOllama
        llm = ChatOllama(
            model=model_name,
            temperature=0,
            # other params...
        )
    elif provider == "huggingface":
        from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
        llm_hf = HuggingFaceEndpoint(
            repo_id=model_name,
            task="text-generation",
            max_new_tokens=4096,
            do_sample=False,
        )
        llm = ChatHuggingFace(llm=llm_hf, verbose=True)
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        api_base = os.getenv("OPENAI_API_BASE")
        if api_key is None:
            print("错误：请在工作目录下创建一个 .env 文件，并设置 OPENAI_API_KEY。")
            exit()
        llm_kwargs = {"model": model_name, "api_key": api_key}
        llm = ChatOpenAI(
            **llm_kwargs
        )
    elif provider == "tongyi":
        from langchain_community.chat_models.tongyi import ChatTongyi
        llm = ChatTongyi(
            model=model_name,
            streaming=True
        )
    else:
        raise ValueError(f"不支持的provider: {provider}")
    return llm

AVAILABLE_PROVIDERS = {"ollama":["qwen3:8b"], "huggingface":["Qwen/Qwen3-8B"], "openai":["gpt-4-turbo","o4-mini"], "tongyi":["qwen3-8b","qwen3-14b","qwen3-32b","qwen-turbo-2025-02-11"]}
code_llm = get_chat_llm("tongyi","qwen3-8b")
judge_llm = get_chat_llm("tongyi","qwen-flash")

CHECK_SYNTAX_METHOD = "TOOL"
LOG_FILE = "lammps.log"
from typing import Annotated
from typing_extensions import TypedDict
from langchain_core.messages import AnyMessage,HumanMessage
from langgraph.graph.message import add_messages
class LammpsState(TypedDict):
    """
    状态字典，包含：
    - user_input: 用户需求
    - lammps_code: 生成的lammps脚本
    - run_result: lammps运行结果
    - eval_result: 评估器评分（json字符串）
    - generate_time: 当前轮数
    """
    messages: Annotated[list, add_messages]
    user_input: str
    checkout_filename_list: list[str]
    lammps_code: str
    run_result: str
    eval_result: str
    final_score: int
    reward:float
    generate_time: int
    generate_dir: str
    llm_name: str
    abs_generate_dir: str
    penalty_detail: str
    reward :float
    potential_check_message: str  # 势函数检查结果
    potential_all_ready: bool    # 势函数检查是否所有文件都就绪
    syntax_check_result: str      # 语法检查结果
    syntax_errors: str           # 语法错误详细信息
    last_node_source: str        # 上一个节点来源
    is_can_run: bool             # 是否可以运行

MAX_GENERATE_CODE_TIME = 5
MAX_RECURSION_LIMIT = 30
PASS_REWARD = 1#范围在0~1之间

def node_init(state: LammpsState):
    generate_dir = generate_random_dirname()
    #需要生成临时文件夹最后又删除
    os.makedirs(generate_dir)
    #获取绝对路径
    abs_generate_dir = os.path.abspath(generate_dir)
    state["abs_generate_dir"] = abs_generate_dir
    state["generate_dir"] = generate_dir
    state["llm_name"] = code_llm.model_name
    state["generate_time"] = 0
    state["user_input"] = state["messages"][-1].content
    
    # 设置初始节点来源
    state["last_node_source"] = "init"
    
    return state

# 节点1：生成lammps脚本
def node_generate(state: LammpsState):
    """
    生成或修正LAMMPS代码
    根据上一个节点的来源决定生成策略
    """
    # 判断上一个节点的来源
    last_node_source = state.get("last_node_source", "init")
    lammps_code = state.get("lammps_code", "")
    penalty_detail = state.get("penalty_detail", "")
    eval_result = state.get("eval_result", "")
    print(f"🔄 生成节点 - 上一个节点来源: {last_node_source}")
    log_to_file(f"生成节点 - 上一个节点来源: {last_node_source}", LOG_FILE)
    
    if last_node_source == "init":
        # 首次生成：从init节点来，全新生成
        prompt = f"""系统提示:
        {generate_lammps_script_prompt(state["generate_dir"])}

        用户输入的任务:
        {state["user_input"]}
        """
        print("📝 首次生成LAMMPS脚本")
        
    elif last_node_source == "check_syntax":
        # 从语法检查节点来：有语法错误，需要修正
        syntax_errors = state.get("syntax_errors", "")
        syntax_check_result = state.get("syntax_check_result", "")
        prompt = f"""系统提示:
        {generate_lammps_script_prompt(state["generate_dir"])}

        # 用户输入的任务:
        {state["user_input"]}

        ## 上一次生成的脚本:
        {lammps_code}

        ## 上一次语法审查结果: {syntax_check_result}
        ### 审查的具体Info
        {syntax_errors}

        请根据语法检查结果修正代码中的错误。
        """
        print("🔧 修正语法错误")

    elif last_node_source == "check_potentials":
        # 从势函数检查节点来：有势函数错误，需要修正
        potential_check_message = state.get("potential_check_message", "")
        prompt = f"""系统提示:
        {generate_lammps_script_prompt(state["generate_dir"])}
        # 上一次的势函数检查结果:
        {potential_check_message}

        ## 上一次生成的脚本:
        {lammps_code}

        请根据势函数检查结果修正代码中的错误。
        """
        print("🔧 修正势函数错误")

    elif last_node_source == "eval":
        # 从评估节点来：代码运行有问题，需要改进
        prompt = f"""系统提示:
        {generate_lammps_script_prompt(state["generate_dir"])}

        # 用户输入的任务:
        {state["user_input"]}

        ## 上一次生成的 LAMMPS 脚本存在问题，请你根据以下评估结果判断其不足之处，并在此基础上 **修改或重写** 代码：
        - 有针对性地修正代码中存在的错误或不合理之处
        - 保留上一次代码中已经正确的部分
        - 生成新脚本后，请确保其符合任务要求，并避免原有的错误

        ## 上一次生成的脚本:
        {lammps_code}

        ## 上一次的评估结果:
        {eval_result}
        """
        print("🔄 根据评估结果改进代码")
        
    else:
        # 未知来源，默认处理
        prompt = f"""系统提示:
        {generate_lammps_script_prompt(state["generate_dir"])}

        用户输入的任务:
        {state["user_input"]}
        """
        print(f"⚠️ 未知节点来源: {last_node_source}，使用默认生成策略")
    
    res = code_llm.invoke(prompt)
    res_json = json_repair.loads(extract_jsonstr_from_outputstr(res.content.strip()))
    code_str = res_json["code"]
    code_str = extract_codestr_from_outputstr(code_str).strip()
    state["lammps_code"] = code_str
    state["checkout_filename_list"] = res_json["checkout_filename_list"]
    
    # 添加生成消息
    state["messages"].append(AIMessage(content=res.content.strip()))
    state["generate_time"] = state.get("generate_time", 0) + 1
    
    # 设置当前节点来源，供下一个节点使用
    state["last_node_source"] = "generate"
    
    print("✅ 代码生成完成")
    log_to_file("代码生成完成", LOG_FILE)
    return state

# 节点1.2：检查语法错误
def node_check_syntax(state: LammpsState):
    """
    专门检查LAMMPS代码的语法错误，只负责指出问题，不修正代码
    """
    print("🔧 检查语法错误...")
    log_to_file("🔧 开始检查语法错误", LOG_FILE)
    
    generate_dir = state.get("generate_dir", "")
    lammps_code = state.get("lammps_code", "")
    if not lammps_code:
        print("⚠️ 没有LAMMPS代码需要检查")
        log_to_file("⚠️ 没有LAMMPS代码需要检查", LOG_FILE)
        state["syntax_check_result"] = "没有LAMMPS代码需要检查"
        state["syntax_errors"] = ""
        return state

    if CHECK_SYNTAX_METHOD == "TOOL":
        ok,info = check_can_run_lammps(lammps_code)
        if ok:
            state["syntax_check_result"] = True
            state["syntax_errors"] = "语法检查通过,未发现错误"
            state["is_can_run"] = True
            state["messages"].append(AIMessage(content=f"语法检查通过,未发现错误"))
        else:
            state["syntax_check_result"] = False
            state["syntax_errors"] = f"语法检查不通过: {info}"
            state["is_can_run"] = False
            state["messages"].append(AIMessage(content=f"语法检查不通过: {info}"))
    else:
        try:
            syntax_prompt = lammps_syntax_check_prompt(lammps_code, generate_dir)
            
            syntax_response = code_llm.invoke(syntax_prompt)
            syntax_content = syntax_response.content.strip()
            
            # 解析LLM响应
            try:
                syntax_json = json_repair.loads(extract_jsonstr_from_outputstr(syntax_content))
                
                has_errors = syntax_json.get("has_errors", False)
                error_description = syntax_json.get("error_description", "")
                error_list = syntax_json.get("error_list", [])
                suggestions = syntax_json.get("suggestions", "")
                
                if has_errors:
                    print(f"❌ 发现语法错误: {error_description}")
                    log_to_file(f"发现语法错误: {error_description}", LOG_FILE)
                    
                    # 构建详细的错误信息
                    error_details = f"""
                    语法检查发现以下错误：
                    - 错误描述: {error_description}
                    - 具体错误列表: {', '.join(error_list) if error_list else '无'}
                    - 修正建议: {suggestions}
                    """
                    
                    state["syntax_check_result"] = False
                    state["syntax_errors"] = f"ERROR摘要: {error_description}\n ERROR具体信息: {error_details}"
                    
                    # 添加语法检查结果到消息历史
                    state["messages"].append(AIMessage(content=f"语法检查结果: {error_details}"))
                    
                else:
                    print("✅ 语法检查通过，未发现错误")
                    log_to_file("语法检查通过，未发现错误", LOG_FILE)
                    state["syntax_check_result"] = True
                    state["syntax_errors"] = ""
                    
                    # 添加检查结果到消息历史
                    check_message = "语法检查结果：语法检查通过，未发现错误"
                    state["messages"].append(AIMessage(content=check_message))
                    
            except Exception as parse_error:
                print(f"⚠️ 语法检查响应解析失败: {parse_error}")
                log_to_file(f"语法检查响应解析失败: {parse_error}", LOG_FILE)
                state["syntax_check_result"] = False
                state["syntax_errors"] = f"语法检查响应解析失败: {str(parse_error)}"
                
                # 添加原始响应到消息历史
                state["messages"].append(AIMessage(content=f"语法检查原始响应: {syntax_content}"))
                
        except Exception as e:
            print(f"❌ 语法检查失败: {e}")
            log_to_file(f"语法检查失败: {e}", LOG_FILE)
            state["syntax_check_result"] = False
            state["syntax_errors"] = f"语法检查失败: {str(e)}"
            state["messages"].append(AIMessage(content=f"语法检查失败: {str(e)}"))
    
    # 设置当前节点来源，供下一个节点使用
    state["last_node_source"] = "check_syntax"
    
    print("✅ 语法检查完成")
    log_to_file("✅ 语法检查完成", LOG_FILE)
    return state

# 节点1.5：检查势函数依赖
def node_check_potentials(state: LammpsState):
    """
    检查LAMMPS代码中的势函数依赖
    """
    print("🔍 检查势函数依赖...")
    log_to_file("🔍 开始检查势函数依赖", LOG_FILE)
    
    lammps_code = state.get("lammps_code", "")
    if not lammps_code:
        print("⚠️ 没有LAMMPS代码需要检查")
        state["potential_check_message"] = "没有LAMMPS代码需要检查"
        return state
    
    # 检查势函数依赖
    print("📋 检查势函数依赖...")
    try:
        potential_result = check_lammps_potentials_tool(lammps_code, top_k=10)
        potential_all_ready = potential_result.get("all_ready", False)
        potential_check_message = f"势函数检查结果: {potential_result['message']}"
        state["potential_all_ready"] = potential_all_ready
        state["potential_check_message"] = potential_check_message
        print(potential_check_message)
        log_to_file(potential_check_message, LOG_FILE)
        # 添加势函数检查结果到消息历史
        state["messages"].append(AIMessage(content=potential_check_message))
        
    except Exception as e:
        potential_check_message = f"势函数检查工具异常: {e}"
        state["potential_check_message"] = potential_check_message
        print(potential_check_message)
        log_to_file(potential_check_message, LOG_FILE)
        state["messages"].append(AIMessage(content=potential_check_message))
    
    # 设置当前节点来源，供下一个节点使用
    state["last_node_source"] = "check_potentials"
    
    print("✅ 势函数检查完成")
    log_to_file("势函数检查完成", LOG_FILE)
    return state

# 节点2：运行lammps脚本
def node_run(state: LammpsState):
    code = state.get("lammps_code", "")
    print("---开始运行code---")
    log_to_file(f"---开始运行code---",LOG_FILE)
    result = run_lammps_in_process(code, tmpdir=state["generate_dir"], checkout_filename_list=state["checkout_filename_list"])
    state["run_result"] = result
    state["messages"].append(AIMessage(content=str(result)))
    #通过result来看是否运行成功
    state["is_can_run"] = result.get("status", "failed") == "success"
    # 设置当前节点来源，供下一个节点使用
    state["last_node_source"] = "run"
    
    print("✅ 代码运行完成")
    log_to_file("代码运行完成", LOG_FILE)
    return state


# 节点3：评估lammps脚本
def node_eval(state: LammpsState):
    # 评估内容为lammps_code
    #如果是第一次评估   
    if state.get("eval_result", None) is None:
        prompt = f"""{lammps_evaluator_system_prompt}
                # 输入
                ## user_input:
                {state["user_input"]}
                
                ## lammps_code:
                {state["lammps_code"]}

                ## run_result:
                {state["run_result"]}
                """
    else:
        prompt = f"""{lammps_evaluator_system_prompt}
        # 输入
        ## user_input:
        {state["user_input"]}

        ## 上一次给过一版lammps_code随后你进行了一次评估
        ## 上一次的评估结果:
        {state["eval_result"]}

        ## 在经过上一次评估后，对方已经对代码进行了修改，请重新评估。
        ## 经过修改后的lammps_code:
        {state["lammps_code"]}

        ## 经过修改后的run_result:
        {state["run_result"]}
        """
    eval_msg = judge_llm.invoke(prompt)
    # 解析分数
    try:
        # 去除markdown包裹
        content = eval_msg.content.strip()
        content = extract_jsonstr_from_outputstr(content)
        state["eval_result"] = content
        state["messages"].append(AIMessage(content=eval_msg.content.strip()))
        score_obj = json.loads(content)
        state['penalty_detail'] = str(score_obj.get("penalty_detail", ""))
        state["final_score"] = score_obj.get("final_score", 0)
        module_score = score_obj.get("module_score", 0)
        penalty_score = score_obj.get("penalty_score", 0)
        reward = cal_reward(module_score,penalty_score)
        state["reward"] = reward

    except Exception:
        state["eval_result"] = "评估失败"
        state["messages"].append(AIMessage(content=state["eval_result"]))
        state["final_score"] = 0
        state["reward"] = 0
        print(f"评估失败: {eval_msg.content.strip()}")
    
    # 设置当前节点来源，供下一个节点使用
    state["last_node_source"] = "eval"
    
    return state


def decide_syntax_next(state: LammpsState):
    """
    决定语法检查后的下一步
    """
    syntax_errors = state.get("syntax_errors", "")
    syntax_check_result = state.get("syntax_check_result", True) # True表示语法检查通过，False表示语法检查失败
    
    # 检查循环次数限制
    if state.get("generate_time", 1) >= MAX_GENERATE_CODE_TIME:
        print(f"{state['generate_time']}轮尝试次数已达上限，终止流程。")
        state["messages"].append(AIMessage(content=f"{state['generate_time']}轮尝试次数已达上限，终止流程。"))
        return END
    
    # 如果有语法错误，需要重新生成代码
    if syntax_check_result == False:
        print("🔄 语法检查不通过，需要重新生成代码")
        state["messages"].append(AIMessage(content="语法检查不通过，需要重新生成代码"))
        return "generate"
    
    # 如果没有语法错误，继续检查势函数
    print("✅ 语法检查通过，继续检查势函数")
    state["messages"].append(AIMessage(content="语法检查通过，继续检查势函数"))
    return "run"


def decide_potentials_next(state: LammpsState):
    """
    决定势函数检查后的下一步
    """
    potential_check_message = state.get("potential_check_message", "")
    all_ready = state.get("potential_all_ready", False)
    
    # 检查循环次数限制
    if state.get("generate_time", 1) >= MAX_GENERATE_CODE_TIME:
        print(f"{state['generate_time']}轮尝试次数已达上限，终止流程。")
        state["messages"].append(AIMessage(content=f"{state['generate_time']}轮尝试次数已达上限，终止流程。"))
        return END
    
    # 如果势函数检查失败，需要重新生成代码
    if not all_ready:
        print("🔄 势函数检查失败，需要重新生成代码")
        state["messages"].append(AIMessage(content="势函数检查失败，需要重新生成代码"))
        return "generate"
    
    # 如果势函数检查通过，继续运行代码
    print("✅ 势函数检查通过，继续运行代码")
    state["messages"].append(AIMessage(content="势函数检查通过，继续运行代码"))
    return "check_syntax"


def decide_next(state: LammpsState):
    if state.get("reward", 0) >= PASS_REWARD:
        print(f"{state['generate_time']}轮分数合格，流程完成 ✅")
        state["messages"].append(AIMessage(content="分数合格，流程完成 ✅"))
        return END
    
    if state.get("generate_time", 1) >= MAX_GENERATE_CODE_TIME:
        print(f"{state['generate_time']}轮尝试次数已达上限，终止流程。")
        state["messages"].append(AIMessage(content=f"{state['generate_time']}轮尝试次数已达上限，终止流程。"))
        return END
    
    if state.get("eval_result", None) is None or state.get("eval_result", None) == "评估失败":
        state["messages"].append(AIMessage(content=f"{state['generate_time']}轮评估失败，重新执行评估"))
        return "eval"

    # 否则继续生成
    state["messages"].append(AIMessage(content=f"{state['generate_time']}轮生成的代码经过评估,没有达到合格分数，继续生成"))
    return "generate"

from langgraph.errors import GraphRecursionError
# 构建LangGraph流程
graph = StateGraph(LammpsState)
graph.add_edge(START, "init")
graph.add_node("init", node_init)
graph.add_node("generate", node_generate)
graph.add_node("check_syntax", node_check_syntax)
graph.add_node("check_potentials", node_check_potentials)
graph.add_node("run", node_run)
graph.add_node("eval", node_eval)

graph.add_edge("init", "generate")
graph.add_edge("generate", "check_potentials")
graph.add_conditional_edges("check_syntax", decide_syntax_next, {"generate": "generate", "run": "run", END: END})
graph.add_conditional_edges("check_potentials", decide_potentials_next, {"generate": "generate", "check_syntax": "check_syntax", END: END})
graph.add_edge("run", "eval")
graph.add_conditional_edges("eval", decide_next, {"generate": "generate", END: END})
# graph.set_entry_point("init")
workflow = graph.compile(checkpointer=MemorySaver())
def run_lammps_agents(user_input:str, is_delete_dir:bool=False) -> LammpsState:
    '''
    运行lammps agents
    :param user_input: 用户输入
    :param is_delete_dir: 是否删除临时文件夹
    :return: LammpsState
    '''
    final_state = None
    config = {
        "recursion_limit": MAX_RECURSION_LIMIT,
        "configurable": {
            "thread_id": "demo"
        }
    }
    input_dict = {
        "messages": [{
            "role": "human",
            "content": user_input
        }]
    }
    try:
        for output in workflow.stream(input_dict, config):
            for key, value in output.items():
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                final_state = value
                generate_time = final_state.get("generate_time", 0)
                msg = f"[{timestamp}] ---------generate_time {generate_time} --- NODE '{key}': ---------\n{value['messages'][-1].content}\n--------------------------------"
                print(msg)
                log_to_file(msg, "lammps.log")
        print("流程结束")
    except GraphRecursionError as e:
        print(f"❌ 递归轮数超限，流程被强制终止: {e}")
        log_to_file(f"❌ 递归轮数超限，流程被强制终止: {e}", "lammps.log")
    except Exception as e:
        print(f"❌ 运行过程中发生异常: {e}")
        log_to_file(f"❌ 运行过程中发生异常: {e}", "lammps.log")
    finally:
        if is_delete_dir and final_state is not None:
            generate_dir = final_state.get("generate_dir", None)
            if generate_dir:
                shutil.rmtree(generate_dir, ignore_errors=True)
    return final_state

if __name__ == "__main__":

    # 读取json文件作为测试用例
    import os
    from tqdm import tqdm
    import json

    # 增加一个参数，可以指定从第几个 index 开始处理
    input_dataset_file = r""
    start_index = 0  # 可以在这里指定起始 index，例如 10 表示从第 10 个开始

    with open(input_dataset_file, 'r', encoding='utf-8') as f:
        test_case = json.load(f)
    test_case = [item["task"] for item in test_case]
    # #简单测试
    test_case = [
        # "用lammps模拟计算FCC-Al的平衡晶格常数",
        "帮我生成Lammps代码，我想模拟一个铜在300K下进行等压等温（npt）热膨胀系数的变化过程，输出其体积变化数据。",
        "使用 LAMMPS 对 FCC 晶格结构的 Lennard-Jones 原子系统进行 NVE 系综模拟，模拟区域为 10×10×10，温度初始化为 1.44，总共运行 50 步，并输出 log 和 dump 文件。",
    ]
    
    # 设置jsonl输出文件
    jsonl_file = f"lammps_results_{code_llm.model_name}_MAX_GENERATE_TIME_{MAX_GENERATE_CODE_TIME}.jsonl"
    
    # 只处理从 start_index 开始的部分
    for idx, task in enumerate(tqdm(test_case[start_index:], desc=f"从第{start_index}条开始")):
        real_idx = idx + start_index  # 记录真实的 index
        final_state = run_lammps_agents(task, is_delete_dir=True)
        
        # 检查final_state是否有效
        if final_state is None:
            print(f"⚠️ 警告: final_state为None (index: {real_idx})，跳过保存")
            log_to_file(f"警告: final_state为None (index: {real_idx})，跳过保存", LOG_FILE)
            continue
        
        # 构建结果数据
        result = {
            "index": real_idx,
            "user_input": final_state.get("user_input", ""),
            "lammps_code": final_state.get("lammps_code", ""),
            "potential_check_message": final_state.get("potential_check_message", {}),
            "syntax_check_result": final_state.get("syntax_check_result", False),
            "run_result": final_state.get("run_result", ""),
            "is_can_run": final_state.get("is_can_run", False),
            "eval_result": final_state.get("eval_result", ""),
            "final_score": final_state.get("final_score", 0),
            "reward": final_state.get("reward", 0),
            "generate_time": final_state.get("generate_time", 1),
            # "messages": final_state.get("messages", []),
            "generate_dir": final_state.get("generate_dir", "")
        }
        log_to_file(f"index: {real_idx} \n----------result: {result}----------\n", LOG_FILE)
        log_to_file(f"index: {real_idx} \n----------messages: {final_state.get('messages', [])}----------\n", LOG_FILE)
        # 立即追加到jsonl文件（追加模式）
        try:
            with open(jsonl_file, "a", encoding="utf-8") as jf:
                jf.write(json.dumps(result, ensure_ascii=False) + "\n")
            print(f"✅ 结果已追加到文件: {jsonl_file} (index: {real_idx})")
        except Exception as e:
            print(f"❌ 保存结果失败 (index: {real_idx}): {e}")
            log_to_file(f"保存结果失败 (index: {real_idx}): {e}", LOG_FILE)
    
    print(f"✅ 所有结果已保存到: {jsonl_file}")
