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
# os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
from langgraph.graph import START
import shutil
from langchain_core.messages import AnyMessage, HumanMessage, AIMessage
from tqdm import tqdm
import datetime
from utils.lammps_check_systax_tools import check_can_run_lammps
# Load environment variables
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
            print("Error: Please create a .env file in the working directory and set OPENAI_API_KEY.")
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
        raise ValueError(f"Unsupported provider: {provider}")
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
    State dictionary containing:
    - user_input: user requirement
    - lammps_code: generated LAMMPS script
    - run_result: LAMMPS run result
    - eval_result: evaluator score (JSON string)
    - generate_time: current iteration count
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
    potential_check_message: str  # Potential file check result
    potential_all_ready: bool    # Whether all potential files are ready
    syntax_check_result: str      # Syntax check result
    syntax_errors: str           # Syntax error details
    last_node_source: str        # Previous node source
    is_can_run: bool             # Whether the script can run

MAX_GENERATE_CODE_TIME = 5
MAX_RECURSION_LIMIT = 30
PASS_REWARD = 1 # Range: 0~1

def node_init(state: LammpsState):
    generate_dir = generate_random_dirname()
    # Create temporary directory (will be deleted later)
    os.makedirs(generate_dir)
    # Get absolute path
    abs_generate_dir = os.path.abspath(generate_dir)
    state["abs_generate_dir"] = abs_generate_dir
    state["generate_dir"] = generate_dir
    state["llm_name"] = code_llm.model_name
    state["generate_time"] = 0
    state["user_input"] = state["messages"][-1].content

    # Set initial node source
    state["last_node_source"] = "init"

    return state

# Node 1: Generate LAMMPS script
def node_generate(state: LammpsState):
    """
    Generate or fix LAMMPS code.
    Determines generation strategy based on the previous node source.
    """
    # Determine the previous node source
    last_node_source = state.get("last_node_source", "init")
    lammps_code = state.get("lammps_code", "")
    penalty_detail = state.get("penalty_detail", "")
    eval_result = state.get("eval_result", "")
    print(f"Generate node - previous node source: {last_node_source}")
    log_to_file(f"Generate node - previous node source: {last_node_source}", LOG_FILE)

    if last_node_source == "init":
        # First generation: from init node, generate from scratch
        prompt = f"""System prompt:
        {generate_lammps_script_prompt(state["generate_dir"])}

        User task:
        {state["user_input"]}
        """
        print("First-time LAMMPS script generation")

    elif last_node_source == "check_syntax":
        # From syntax check node: syntax errors found, need to fix
        syntax_errors = state.get("syntax_errors", "")
        syntax_check_result = state.get("syntax_check_result", "")
        prompt = f"""System prompt:
        {generate_lammps_script_prompt(state["generate_dir"])}

        # User task:
        {state["user_input"]}

        ## Previously generated script:
        {lammps_code}

        ## Previous syntax check result: {syntax_check_result}
        ### Detailed check info
        {syntax_errors}

        Please fix the errors in the code based on the syntax check results.
        """
        print("Fixing syntax errors")

    elif last_node_source == "check_potentials":
        # From potential check node: potential file errors, need to fix
        potential_check_message = state.get("potential_check_message", "")
        prompt = f"""System prompt:
        {generate_lammps_script_prompt(state["generate_dir"])}
        # Previous potential file check result:
        {potential_check_message}

        ## Previously generated script:
        {lammps_code}

        Please fix the errors in the code based on the potential file check results.
        """
        print("Fixing potential file errors")

    elif last_node_source == "eval":
        # From evaluation node: code has issues, need improvement
        prompt = f"""System prompt:
        {generate_lammps_script_prompt(state["generate_dir"])}

        # User task:
        {state["user_input"]}

        ## The previously generated LAMMPS script has issues. Please identify its shortcomings based on the evaluation results below, and **modify or rewrite** the code accordingly:
        - Fix errors or unreasonable parts in the code in a targeted manner
        - Retain the correct parts from the previous code
        - Ensure the new script meets the task requirements and avoids previous errors

        ## Previously generated script:
        {lammps_code}

        ## Previous evaluation result:
        {eval_result}
        """
        print("Improving code based on evaluation results")

    else:
        # Unknown source, default handling
        prompt = f"""System prompt:
        {generate_lammps_script_prompt(state["generate_dir"])}

        User task:
        {state["user_input"]}
        """
        print(f"Unknown node source: {last_node_source}, using default generation strategy")

    res = code_llm.invoke(prompt)
    res_json = json_repair.loads(extract_jsonstr_from_outputstr(res.content.strip()))
    code_str = res_json["code"]
    code_str = extract_codestr_from_outputstr(code_str).strip()
    state["lammps_code"] = code_str
    state["checkout_filename_list"] = res_json["checkout_filename_list"]

    # Add generated message
    state["messages"].append(AIMessage(content=res.content.strip()))
    state["generate_time"] = state.get("generate_time", 0) + 1

    # Set current node source for the next node
    state["last_node_source"] = "generate"

    print("Code generation complete")
    log_to_file("Code generation complete", LOG_FILE)
    return state

# Node 1.2: Check syntax errors
def node_check_syntax(state: LammpsState):
    """
    Check LAMMPS code for syntax errors. Only identifies issues, does not fix code.
    """
    print("Checking syntax errors...")
    log_to_file("Starting syntax check", LOG_FILE)

    generate_dir = state.get("generate_dir", "")
    lammps_code = state.get("lammps_code", "")
    if not lammps_code:
        print("No LAMMPS code to check")
        log_to_file("No LAMMPS code to check", LOG_FILE)
        state["syntax_check_result"] = "No LAMMPS code to check"
        state["syntax_errors"] = ""
        return state

    if CHECK_SYNTAX_METHOD == "TOOL":
        ok,info = check_can_run_lammps(lammps_code)
        if ok:
            state["syntax_check_result"] = True
            state["syntax_errors"] = "Syntax check passed, no errors found"
            state["is_can_run"] = True
            state["messages"].append(AIMessage(content="Syntax check passed, no errors found"))
        else:
            state["syntax_check_result"] = False
            state["syntax_errors"] = f"Syntax check failed: {info}"
            state["is_can_run"] = False
            state["messages"].append(AIMessage(content=f"Syntax check failed: {info}"))
    else:
        try:
            syntax_prompt = lammps_syntax_check_prompt(lammps_code, generate_dir)

            syntax_response = code_llm.invoke(syntax_prompt)
            syntax_content = syntax_response.content.strip()

            # Parse LLM response
            try:
                syntax_json = json_repair.loads(extract_jsonstr_from_outputstr(syntax_content))

                has_errors = syntax_json.get("has_errors", False)
                error_description = syntax_json.get("error_description", "")
                error_list = syntax_json.get("error_list", [])
                suggestions = syntax_json.get("suggestions", "")

                if has_errors:
                    print(f"Syntax errors found: {error_description}")
                    log_to_file(f"Syntax errors found: {error_description}", LOG_FILE)

                    # Build detailed error information
                    error_details = f"""
                    Syntax check found the following errors:
                    - Error description: {error_description}
                    - Error list: {', '.join(error_list) if error_list else 'None'}
                    - Suggestions: {suggestions}
                    """

                    state["syntax_check_result"] = False
                    state["syntax_errors"] = f"ERROR summary: {error_description}\n ERROR details: {error_details}"

                    # Add syntax check result to message history
                    state["messages"].append(AIMessage(content=f"Syntax check result: {error_details}"))

                else:
                    print("Syntax check passed, no errors found")
                    log_to_file("Syntax check passed, no errors found", LOG_FILE)
                    state["syntax_check_result"] = True
                    state["syntax_errors"] = ""

                    # Add check result to message history
                    check_message = "Syntax check result: passed, no errors found"
                    state["messages"].append(AIMessage(content=check_message))

            except Exception as parse_error:
                print(f"Syntax check response parse failed: {parse_error}")
                log_to_file(f"Syntax check response parse failed: {parse_error}", LOG_FILE)
                state["syntax_check_result"] = False
                state["syntax_errors"] = f"Syntax check response parse failed: {str(parse_error)}"

                # Add raw response to message history
                state["messages"].append(AIMessage(content=f"Syntax check raw response: {syntax_content}"))

        except Exception as e:
            print(f"Syntax check failed: {e}")
            log_to_file(f"Syntax check failed: {e}", LOG_FILE)
            state["syntax_check_result"] = False
            state["syntax_errors"] = f"Syntax check failed: {str(e)}"
            state["messages"].append(AIMessage(content=f"Syntax check failed: {str(e)}"))

    # Set current node source for the next node
    state["last_node_source"] = "check_syntax"

    print("Syntax check complete")
    log_to_file("Syntax check complete", LOG_FILE)
    return state

# Node 1.5: Check potential file dependencies
def node_check_potentials(state: LammpsState):
    """
    Check potential file dependencies in LAMMPS code.
    """
    print("Checking potential file dependencies...")
    log_to_file("Starting potential file check", LOG_FILE)

    lammps_code = state.get("lammps_code", "")
    if not lammps_code:
        print("No LAMMPS code to check")
        state["potential_check_message"] = "No LAMMPS code to check"
        return state

    # Check potential file dependencies
    print("Checking potential file dependencies...")
    try:
        potential_result = check_lammps_potentials_tool(lammps_code, top_k=10)
        potential_all_ready = potential_result.get("all_ready", False)
        potential_check_message = f"Potential file check result: {potential_result['message']}"
        state["potential_all_ready"] = potential_all_ready
        state["potential_check_message"] = potential_check_message
        print(potential_check_message)
        log_to_file(potential_check_message, LOG_FILE)
        # Add potential check result to message history
        state["messages"].append(AIMessage(content=potential_check_message))

    except Exception as e:
        potential_check_message = f"Potential file check tool error: {e}"
        state["potential_check_message"] = potential_check_message
        print(potential_check_message)
        log_to_file(potential_check_message, LOG_FILE)
        state["messages"].append(AIMessage(content=potential_check_message))

    # Set current node source for the next node
    state["last_node_source"] = "check_potentials"

    print("Potential file check complete")
    log_to_file("Potential file check complete", LOG_FILE)
    return state

# Node 2: Run LAMMPS script
def node_run(state: LammpsState):
    code = state.get("lammps_code", "")
    print("--- Running code ---")
    log_to_file("--- Running code ---",LOG_FILE)
    result = run_lammps_in_process(code, tmpdir=state["generate_dir"], checkout_filename_list=state["checkout_filename_list"])
    state["run_result"] = result
    state["messages"].append(AIMessage(content=str(result)))
    # Check if run was successful
    state["is_can_run"] = result.get("status", "failed") == "success"
    # Set current node source for the next node
    state["last_node_source"] = "run"

    print("Code execution complete")
    log_to_file("Code execution complete", LOG_FILE)
    return state


# Node 3: Evaluate LAMMPS script
def node_eval(state: LammpsState):
    # Evaluate the lammps_code
    # If this is the first evaluation
    if state.get("eval_result", None) is None:
        prompt = f"""{lammps_evaluator_system_prompt}
                # Input
                ## user_input:
                {state["user_input"]}

                ## lammps_code:
                {state["lammps_code"]}

                ## run_result:
                {state["run_result"]}
                """
    else:
        prompt = f"""{lammps_evaluator_system_prompt}
        # Input
        ## user_input:
        {state["user_input"]}

        ## A previous version of lammps_code was evaluated
        ## Previous evaluation result:
        {state["eval_result"]}

        ## After the previous evaluation, the code has been modified. Please re-evaluate.
        ## Modified lammps_code:
        {state["lammps_code"]}

        ## Modified run_result:
        {state["run_result"]}
        """
    eval_msg = judge_llm.invoke(prompt)
    # Parse score
    try:
        # Remove markdown wrapping
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
        state["eval_result"] = "Evaluation failed"
        state["messages"].append(AIMessage(content=state["eval_result"]))
        state["final_score"] = 0
        state["reward"] = 0
        print(f"Evaluation failed: {eval_msg.content.strip()}")

    # Set current node source for the next node
    state["last_node_source"] = "eval"

    return state


def decide_syntax_next(state: LammpsState):
    """
    Decide the next step after syntax check.
    """
    syntax_errors = state.get("syntax_errors", "")
    syntax_check_result = state.get("syntax_check_result", True) # True = passed, False = failed

    # Check iteration limit
    if state.get("generate_time", 1) >= MAX_GENERATE_CODE_TIME:
        print(f"Iteration {state['generate_time']}: max attempts reached, terminating.")
        state["messages"].append(AIMessage(content=f"Iteration {state['generate_time']}: max attempts reached, terminating."))
        return END

    # If syntax errors exist, regenerate code
    if syntax_check_result == False:
        print("Syntax check failed, regenerating code")
        state["messages"].append(AIMessage(content="Syntax check failed, regenerating code"))
        return "generate"

    # If no syntax errors, proceed to run
    print("Syntax check passed, proceeding to run")
    state["messages"].append(AIMessage(content="Syntax check passed, proceeding to run"))
    return "run"


def decide_potentials_next(state: LammpsState):
    """
    Decide the next step after potential file check.
    """
    potential_check_message = state.get("potential_check_message", "")
    all_ready = state.get("potential_all_ready", False)

    # Check iteration limit
    if state.get("generate_time", 1) >= MAX_GENERATE_CODE_TIME:
        print(f"Iteration {state['generate_time']}: max attempts reached, terminating.")
        state["messages"].append(AIMessage(content=f"Iteration {state['generate_time']}: max attempts reached, terminating."))
        return END

    # If potential check failed, regenerate code
    if not all_ready:
        print("Potential file check failed, regenerating code")
        state["messages"].append(AIMessage(content="Potential file check failed, regenerating code"))
        return "generate"

    # If potential check passed, proceed to syntax check
    print("Potential file check passed, proceeding to syntax check")
    state["messages"].append(AIMessage(content="Potential file check passed, proceeding to syntax check"))
    return "check_syntax"


def decide_next(state: LammpsState):
    if state.get("reward", 0) >= PASS_REWARD:
        print(f"Iteration {state['generate_time']}: score passed, workflow complete")
        state["messages"].append(AIMessage(content="Score passed, workflow complete"))
        return END

    if state.get("generate_time", 1) >= MAX_GENERATE_CODE_TIME:
        print(f"Iteration {state['generate_time']}: max attempts reached, terminating.")
        state["messages"].append(AIMessage(content=f"Iteration {state['generate_time']}: max attempts reached, terminating."))
        return END

    if state.get("eval_result", None) is None or state.get("eval_result", None) == "Evaluation failed":
        state["messages"].append(AIMessage(content=f"Iteration {state['generate_time']}: evaluation failed, re-evaluating"))
        return "eval"

    # Otherwise continue generating
    state["messages"].append(AIMessage(content=f"Iteration {state['generate_time']}: code did not reach passing score, continuing generation"))
    return "generate"

from langgraph.errors import GraphRecursionError
# Build LangGraph workflow
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
    Run LAMMPS agents workflow.
    :param user_input: user input
    :param is_delete_dir: whether to delete temporary directory
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
        print("Workflow finished")
    except GraphRecursionError as e:
        print(f"Recursion limit exceeded, workflow forcefully terminated: {e}")
        log_to_file(f"Recursion limit exceeded, workflow forcefully terminated: {e}", "lammps.log")
    except Exception as e:
        print(f"Exception during execution: {e}")
        log_to_file(f"Exception during execution: {e}", "lammps.log")
    finally:
        if is_delete_dir and final_state is not None:
            generate_dir = final_state.get("generate_dir", None)
            if generate_dir:
                shutil.rmtree(generate_dir, ignore_errors=True)
    return final_state

if __name__ == "__main__":

    # Read JSON file as test cases
    import os
    from tqdm import tqdm
    import json

    # Specify starting index for processing
    input_dataset_file = r""
    start_index = 0  # Specify starting index here, e.g. 10 to start from the 10th entry

    with open(input_dataset_file, 'r', encoding='utf-8') as f:
        test_case = json.load(f)
    test_case = [item["task"] for item in test_case]
    # Quick test
    test_case = [
        "Generate LAMMPS code to simulate the thermal expansion coefficient change of copper at 300K under NPT conditions, and output its volume change data.",
        "Use LAMMPS to perform an NVE ensemble simulation on a Lennard-Jones atomic system with FCC lattice structure, simulation region 10x10x10, initial temperature 1.44, run for 50 steps, and output log and dump files.",
    ]

    # Set JSONL output file
    jsonl_file = f"lammps_results_{code_llm.model_name}_MAX_GENERATE_TIME_{MAX_GENERATE_CODE_TIME}.jsonl"

    # Process from start_index onward
    for idx, task in enumerate(tqdm(test_case[start_index:], desc=f"Starting from index {start_index}")):
        real_idx = idx + start_index  # Record the actual index
        final_state = run_lammps_agents(task, is_delete_dir=True)

        # Check if final_state is valid
        if final_state is None:
            print(f"Warning: final_state is None (index: {real_idx}), skipping save")
            log_to_file(f"Warning: final_state is None (index: {real_idx}), skipping save", LOG_FILE)
            continue

        # Build result data
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
        # Append to JSONL file immediately
        try:
            with open(jsonl_file, "a", encoding="utf-8") as jf:
                jf.write(json.dumps(result, ensure_ascii=False) + "\n")
            print(f"Result appended to file: {jsonl_file} (index: {real_idx})")
        except Exception as e:
            print(f"Failed to save result (index: {real_idx}): {e}")
            log_to_file(f"Failed to save result (index: {real_idx}): {e}", LOG_FILE)

    print(f"All results saved to: {jsonl_file}")
