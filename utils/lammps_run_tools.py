import tempfile
import os
from lammps import lammps
import shutil
import uuid
import tempfile
import os
import shutil
import uuid
import time
import multiprocessing
import os
import shutil
from multiprocessing import Queue
from typing import Optional, List, Dict, Any
from utils.lammps_vis_eval_utils.lammps_evaluator_api import evaluate_log_quality

def _run_lammps_worker(
    lammps_code: str,
    tmpdir: str,
    max_return_length: int,
    result_queue: Queue,
    checkout_filename_list: Optional[List[str]] = None,
    max_files: int = 5,
    is_use_evaluator_tool: bool = True,
    is_delete_tmpdir: bool = False
):
    """
    在子进程中执行LAMMPS代码并返回结构化结果
    
    参数:
        lammps_code: 要执行的LAMMPS输入脚本代码
        tmpdir: 临时工作目录路径
        max_return_length: 输出文件内容的最大返回长度
        result_queue: 用于返回结果的进程间通信队列
        checkout_filename_list: 指定要检查的输出文件名列表，默认为None时自动选择
        max_files: 最大输出文件数量限制
        is_use_evaluator_tool: 是否使用日志质量评估工具
        is_delete_tmpdir: 是否在完成后删除临时目录
    
    返回:
        通过result_queue返回包含status、summary、outputs、errors等字段的字典
    """
    #先检查是否有tmpdir，没有则创建
    if not os.path.exists(tmpdir):
        os.makedirs(tmpdir)
    input_path = os.path.join(tmpdir, "in.generated.lmp")
    result = {
        "status": "success",
        "summary": "",
        "outputs": {},#[{filename:content}]
        "errors": [],
        "extra_info": {}
    }

    with open(input_path, "w", encoding="utf-8") as f:
        f.write(lammps_code)
    try:
        lmp = lammps(cmdargs=["-log", "none","-screen", "none",
"-nocite"])  # 推荐加 -log 明确日志输出
        # lmp = lammps()
        lmp.file(input_path)
        lmp.close()
        del lmp
    except Exception as e:
        result["status"] = "error"
        result["summary"] = f"❌ LAMMPS Runtime Error: {str(e)}"
        result_queue.put(result)
        return
    if checkout_filename_list is None:
        output_priority = ["log.lammps", "dump.lammpstrj"]
        all_files = [f for f in os.listdir(tmpdir) if f != "in.generated.lmp"]
        sorted_files = sorted(all_files, key=lambda x: (output_priority.index(x) if x in output_priority else 99, x))
        target_files = sorted_files[:max_files]
        if len(sorted_files) > max_files:
            result["summary"] += f"\n⚠️ 输出文件超过 {max_files} 个，仅展示前 {max_files} 个。"
    else:
        target_files = checkout_filename_list

    for fname in target_files:
        fpath = os.path.join(tmpdir, fname)
        if os.path.isfile(fpath):
            if is_use_evaluator_tool and fname == "log.lammps":
                evaluator_result = evaluate_log_quality(fpath)
                result["extra_info"][fname] = evaluator_result
            #排除掉图片和gif文件
            if fname.endswith(".png") or fname.endswith(".jpg") or fname.endswith(".gif"):
                continue
            try:
                with open(fpath, "r", errors="ignore") as f:
                    content = f.read()
                    if len(content) > max_return_length:
                        content_summary = (
                            f"📄 [{fname}]\n"
                            f"前{max_return_length//2}字符：\n{content[:max_return_length//2].strip()}\n"
                            f"...\n"
                            f"后{max_return_length//2}字符：\n{content[-max_return_length//2:].strip()}"
                        )
                    else:
                        content_summary = f"📄 [{fname}]\n{content.strip()}"
                    result["outputs"][fname] = content_summary  # ✅ 正确
            except Exception as read_err:
                result["errors"].append(f"📄 [{fname}] 读取失败: {str(read_err)}")

    if not result["outputs"]:
        result["summary"] = (
            "⚠️ LAMMPS 脚本执行成功，但未产生任何输出文件。请检查是否缺少 log、dump、print 等输出命令。"
        )
    if is_delete_tmpdir:
        shutil.rmtree(tmpdir)
    result_queue.put(result)


def _run_lammps_worker_v1(lammps_code: str, tmpdir: str, max_return_length: int, result_queue):
    """
    在子进程中运行LAMMPS代码的旧版本实现（已废弃）
    
    参数:
        lammps_code: 要执行的LAMMPS输入脚本代码
        tmpdir: 临时工作目录路径
        max_return_length: 输出文件内容的最大返回长度
        result_queue: 用于返回结果的进程间通信队列
    
    注意:
        此函数会切换工作目录到临时目录，可能导致路径问题，建议使用_run_lammps_worker
    """
    result_text = ""
    input_path = os.path.join(tmpdir, "in.generated.lmp")
    try:
        with open(input_path, "w") as f:
            f.write(lammps_code)
        cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            lmp = lammps()
            lmp.file("in.generated.lmp")
            lmp.close()
            del lmp
            # time.sleep(0.5)  # 可以去掉，避免无谓等待
        except Exception as e:
            result_queue.put(f"❌ Runtime Error: {str(e)}")
            return
        finally:
            os.chdir(cwd)
        for fname in os.listdir(tmpdir):
            if fname == "in.generated.lmp":
                continue
            else:
                if result_text == "":
                    result_text += (
                        "以下是 LAMMPS 模拟运行生成的输出文件及其内容节选\n\n"
                    )
                fpath = os.path.join(tmpdir, fname)
                if os.path.isfile(fpath):
                    try:
                        with open(fpath, "r", errors="ignore") as f:
                            content = f.read()
                            if len(content) > max_return_length:
                                result_text += f"\n📄 [{fname}]\n前{max_return_length//2}字符：\n" + content[:(max_return_length//2)].strip()
                                result_text += f"\n...\n后{max_return_length//2}字符：\n" + content[-(max_return_length//2):].strip()
                            else:
                                result_text += f"\n📄 [{fname}]\n" + content.strip()
                    except Exception as read_err:
                        result_text += f"\n📄 [{fname}] 无法读取: {read_err}"
        if not result_text:
            result_text = (
                "⚠️ LAMMPS 脚本执行成功，但未产生任何输出文件。请检查你的脚本中是否包含诸如 "
                "`log`, `dump`, `write_data`, `print` 等文件输出指令。"
            )
    finally:
        try:
            shutil.rmtree(tmpdir)  # 清理临时目录
        except:
            pass  # 忽略清理过程中的任何错误
    result_queue.put(result_text)


def run_lammps_in_process(
    lammps_code: str,
    max_return_length: int = 20000,
    tmpdir: str = None,
    checkout_filename_list: Optional[List[str]] = None,
    timeout: int = 1200  # 单位s
) -> Dict[str, Any]:
    """
    在独立进程中安全执行LAMMPS代码，支持超时控制和并发执行
    
    参数:
        lammps_code: 要执行的LAMMPS输入脚本代码
        max_return_length: 输出文件内容的最大返回长度，默认20000字符
        tmpdir: 临时工作目录路径，为None时自动创建
        checkout_filename_list: 指定要检查的输出文件名列表
        timeout: 执行超时时间（秒），默认1200秒
    
    返回:
        Dict[str, Any]: 包含以下字段的结果字典
            - status: 执行状态（"success", "error", "timeout"）
            - summary: 执行摘要信息
            - outputs: 输出文件内容字典
            - errors: 错误信息列表
            - extra_info: 额外信息（如日志质量评估结果）
    """
    result_queue = multiprocessing.Queue()
    p = multiprocessing.Process(
        target=_run_lammps_worker,
        args=(lammps_code, tmpdir, max_return_length, result_queue, checkout_filename_list)
    )
    p.start()
    try:
        result = result_queue.get(timeout=timeout)
    except multiprocessing.queues.Empty:
        p.terminate()
        result = {
            "status": "timeout",
            "summary": f"⏰ 超过 {timeout} 秒仍未完成，已中止执行。",
            "outputs": {},
            "errors": ["进程执行超时"]
        }
    p.join()
    return result


def create_lammps_script(tmpdir: str) -> str:
    """
    创建一个标准的LAMMPS测试脚本
    
    参数:
        tmpdir: 临时目录路径，用于指定输出文件位置
    
    返回:
        str: 完整的LAMMPS输入脚本字符串
        
    脚本内容:
        使用LJ势能函数模拟FCC晶格结构的简单分子动力学模拟
    """
    return f"""
    units lj
    atom_style atomic
    lattice fcc 0.8442
    region box block 0 10 0 10 0 10
    create_box 1 box
    create_atoms 1 box

    mass 1 1.0
    velocity all create 1.44 87287 loop geom
    pair_style lj/cut 2.5
    pair_coeff 1 1 1.0 1.0 2.5

    neighbor 0.3 bin
    neigh_modify delay 5

    thermo 10
    log {tmpdir}/log.lammps
    dump 1 all atom 10 {tmpdir}/dump.lammpstrj
    fix 1 all nve

    run 50
    """

def run_one_lammps_instance(instance_id: int) -> dict:
    """
    运行单个LAMMPS实例的测试函数
    
    参数:
        instance_id: 实例标识符
    
    返回:
        dict: 包含执行结果和实例ID的字典
        
    功能:
        创建临时目录，生成测试脚本，执行LAMMPS模拟，并返回结果
    """
    tmpdir = tempfile.mkdtemp(prefix=f"lammps_{instance_id}_" + str(uuid.uuid4())[:8] + "_")
    lammps_code = create_lammps_script(tmpdir)
    checkout_files = ["log.lammps", "dump.lammpstrj"]
    result = run_lammps_in_process(
        lammps_code=lammps_code,
        tmpdir=tmpdir,
        checkout_filename_list=checkout_files,
        timeout=60
    )
    result["instance_id"] = instance_id
    return result

from concurrent.futures import ProcessPoolExecutor, as_completed
def test_run_lammps_in_process():
    """
    测试多进程并发运行LAMMPS的功能
    
    功能:
        使用进程池并行执行多个LAMMPS实例，验证多进程安全性
        默认运行4个并发实例，每个实例执行独立的LAMMPS模拟
    
    输出:
        打印每个实例的执行结果和状态信息
    """
    num_instances = 4  # 并行运行的 LAMMPS 数量
    results: List[dict] = []

    with ProcessPoolExecutor(max_workers=num_instances) as executor:
        futures = [executor.submit(run_one_lammps_instance, i) for i in range(num_instances)]
        for future in as_completed(futures):
            try:
                result = future.result()
                print(f"\n=== LAMMPS Instance #{result['instance_id']} ===")
                print(result)
            except Exception as e:
                print(f"❌ Error in one instance: {e}")

if __name__ == "__main__":
    tmpdir = tempfile.mkdtemp(dir=".", prefix="lammps_run_" + str(uuid.uuid4())[:8] + "_")
    lammps_script = f"""
    units lj
    atom_style atomic
    lattice fcc 0.8442
    region box block 0 10 0 10 0 10
    create_box 1 box
    create_atoms 1 box

    mass 1 1.0
    velocity all create 1.44 87287 loop geom
    pair_style lj/cut 2.5
    pair_coeff 1 1 1.0 1.0 2.5

    neighbor 0.3 bin
    neigh_modify delay 5

    thermo 10
    log {tmpdir}/log.lammps
    dump 1 all atom 10 {tmpdir}/dump.lammpstrj
    fix 1 all nve

    run 50
    """
    lammps_script="""
    \n    # 使用 FCC 铜，EAM 力场\n    units metal\n    atom_style atomic\n    lattice fcc 3.615\n    region box block 0 5 0 5 0 5\n    create_box 1 box\n    create_atoms 1 box\n    mass 1 63.546\n    pair_style eam\n    pair_coeff * * potentials/Cu_u3.eam\n    velocity all create 300.0 12345\n    log lammps_run_20250717_163929_8395/log.lammps\n    dump 1 all atom 10 lammps_run_20250717_163929_8395/dump.lammpstrj\n    dump_modify 1 sort id\n    thermo 10\n    fix 1 all nve\n    run 10000\n
    """
    checkout_filename_list = ["log.lammps", "dump.lammpstrj"]
    output = run_lammps_in_process(lammps_script.strip(), tmpdir=tmpdir, checkout_filename_list=checkout_filename_list)
    print(output)
    # test_run_lammps_in_process()