import subprocess
import tempfile
import os
import sys
import platform
import time
import re

def _extract_error_info(output: str) -> str:
    """
    从 LAMMPS 输出中提取关键错误信息，格式化为对 LLM 友好的格式。
    
    参数:
        output: LAMMPS 的完整输出
    
    返回:
        格式化后的错误信息字符串
    """
    lines = output.split('\n')
    error_lines = []
    last_command_line = None
    error_context = []
    
    # 提取关键信息
    for i, line in enumerate(lines):
        line_upper = line.upper()
        
        # 提取 ERROR 行
        if 'ERROR' in line_upper and ('ERROR:' in line_upper or 'ERROR ON PROC' in line_upper):
            error_lines.append(line.strip())
            # 提取错误行前后的上下文（最多前后各2行）
            start = max(0, i - 2)
            end = min(len(lines), i + 3)
            error_context = [l.strip() for l in lines[start:end] if l.strip()]
        
        # 提取 LAST COMMAND 行
        if 'LAST COMMAND:' in line_upper:
            last_command_line = line.strip()
    
    # 构建格式化的错误信息
    error_info_parts = []
    
    if error_lines:
        error_info_parts.append("错误信息:")
        for err_line in error_lines:
            error_info_parts.append(f"  - {err_line}")
    
    if last_command_line:
        error_info_parts.append(f"\n最后执行的命令: {last_command_line}")
    
    # 如果有错误上下文，添加关键上下文（只包含命令相关的行）
    if error_context:
        # 过滤出可能是命令的行（匹配常见的 LAMMPS 命令）
        command_pattern = re.compile(r'^\s*(units|atom_style|lattice|region|create_box|create_atoms|mass|pair_style|pair_coeff|velocity|thermo|fix|run|minimize|dump|log|dump_modify)', re.IGNORECASE)
        relevant_context = [line for line in error_context if command_pattern.search(line) or 'ERROR' in line.upper() or 'LAST COMMAND' in line.upper()]
        
        if relevant_context:
            error_info_parts.append("\n相关命令上下文:")
            for ctx_line in relevant_context[-5:]:  # 最多显示5行上下文
                if ctx_line.strip():
                    error_info_parts.append(f"  {ctx_line}")
    
    if error_info_parts:
        return "\n".join(error_info_parts)
    else:
        # 如果没有提取到关键信息，返回简化的输出（只包含包含 ERROR 的行）
        error_only = [line.strip() for line in lines if 'ERROR' in line.upper() and line.strip()]
        if error_only:
            return "错误信息:\n  - " + "\n  - ".join(error_only)
        return "发现错误，但无法提取详细信息"

def check_can_run_lammps(code: str, timeout: float = 3.0, lammps_cmd: str = None) -> tuple[bool,str]:
    """
    检查 LAMMPS 脚本是否能成功通过语法检查并开始运行。
    只要 LAMMPS 能启动（不报 ERROR），就返回 True。
    不等待模拟结束。
    
    参数:
        code: LAMMPS 脚本代码字符串
        timeout: 超时时间（秒），默认 3.0 秒
                 - 语法错误通常在 0.5-2 秒内就能检测到
                 - 正常代码启动通常需要 1-3 秒
                 - 如果代码需要读取大文件，可能需要 3-5 秒
                 - 建议范围：2-5 秒（简单代码用 2-3 秒，复杂代码用 3-5 秒）
        lammps_cmd: LAMMPS 可执行文件命令，默认为 None 时自动检测
                    Windows 上可能是 "lmp" 或 "lammps"
                    Linux/Mac 上可能是 "lmp" 或 "lammps"
    
    返回:
        tuple[bool,str]: 是否可以运行，错误信息
    """
    # 自动检测 LAMMPS 命令
    if lammps_cmd is None:
        # 常见的 LAMMPS 可执行文件名
        possible_cmds = ["lmp", "lammps", "lmp_serial", "lmp_mpi"]
        lammps_cmd = None
        for cmd in possible_cmds:
            try:
                # 检查命令是否存在
                result = subprocess.run(
                    [cmd, "-help"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=2.0
                )
                if result.returncode == 0 or "LAMMPS" in result.stdout.decode().upper():
                    lammps_cmd = cmd
                    break
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                continue
        
        if lammps_cmd is None:
            print("❌ 错误: 未找到 LAMMPS 可执行文件。请确保 LAMMPS 已安装并在 PATH 中。")
            info = "未找到 LAMMPS 可执行文件。请确保 LAMMPS 已安装并在 PATH 中。"
            return False, info
    
    # 1. 将 LAMMPS 代码写入临时文件
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".in", encoding='utf-8') as tmp_file:
        tmp_path = tmp_file.name
        tmp_file.write(code)
        tmp_file.flush()
    
    try:
        # 2. 使用 subprocess 启动 LAMMPS
        #    -in tmp_path   -> 指定输入文件
        #    -log none      -> 避免写 log 文件（更快）
        #    -echo screen   -> 让输出更快返回
        cmd = [lammps_cmd, "-in", tmp_path, "-log", "none", "-echo", "screen"]
        
        # 创建 subprocess
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # 合并 stderr 到 stdout
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        
        try:
            # 3. 最多等 timeout 秒看是否抛出错误
            stdout, _ = process.communicate(timeout=timeout)
            output = stdout
            
        except subprocess.TimeoutExpired:
            # 超时：表示至少已经启动了，没有立即的语法错误（否则会提前退出）
            # 终止进程
            try:
                if platform.system() == "Windows":
                    # Windows 上使用 taskkill
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], 
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                else:
                    # Unix/Linux/Mac 上使用 kill
                    process.terminate()
                    try:
                        process.wait(timeout=1.0)
                    except subprocess.TimeoutExpired:
                        process.kill()
            except Exception:
                pass  # 忽略终止进程时的错误
            
            return True, ""
        
        # 4. 检查是否含 ERROR（LAMMPS 的错误标识）
        # 常见 LAMMPS 错误：ERROR: Invalid atom style...
        # 也检查常见的错误关键词
        output_upper = output.upper()
        error_keywords = ["ERROR", "FATAL ERROR", "UNKNOWN COMMAND", "INVALID"]
        
        for keyword in error_keywords:
            if keyword in output_upper:
                # 进一步检查是否是真正的错误（排除一些误报）
                # 例如 "ERROR" 可能在正常输出中出现，但 "ERROR:" 更可能是真正的错误
                if "ERROR:" in output_upper or "FATAL ERROR" in output_upper:
                    error_info = _extract_error_info(output)
                    return False, error_info
        
        # 5. 检查返回码
        if process.returncode != 0:
            # 非零返回码通常表示有错误
            # 但如果输出中没有 ERROR 关键词，可能是其他问题
            if "ERROR" in output_upper:
                error_info = _extract_error_info(output)
                return False, error_info
        
        # 没报错即认为能运行
        return True, ""
        
    except FileNotFoundError:
        print("   请确保 LAMMPS 已安装并在 PATH 中，或使用 lammps_cmd 参数指定路径。")
        return False, "未找到 LAMMPS 可执行文件: " + lammps_cmd
    except Exception as e:
        print(f"❌ 运行 LAMMPS 时发生异常: {e}")
        return False, "运行 LAMMPS 时发生异常: " + str(e)
    finally:
        # 清理临时文件
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


# 测试代码
if __name__ == "__main__":
    # 测试用例 1: 正确的代码
    code1 = """
units metal
atom_style atomic
lattice fcc 3.615
region box block 0 5 0 5 0 5
create_box 1 box
create_atoms 1 box
mass 1 63.546
pair_style eam
pair_coeff * * potentials/Cu_u3.eam
velocity all create 300.0 12345
thermo 10
fix 1 all nve
run 10
"""
    
    # 测试用例 2: 有语法错误的代码
    code2 = """
units metal
atom_style atomic
invalid_command  # 这是一个不存在的命令
run 10
"""
    
    # 测试用例 3: 需要长时间运行的代码（验证快速检查功能）
    code3 = """
units metal
atom_style atomic
lattice fcc 3.615
region box block 0 5 0 5 0 5
create_box 1 box
create_atoms 1 box
mass 1 63.546
pair_style lj/cut 2.5
pair_coeff 1 1 1.0 1.0 2.5
velocity all create 300.0 12345
thermo 1000
fix 1 all nve
run 1000000
"""
    
    # print("=" * 60)
    # print("测试用例 1: 正确的代码（短时间运行）")
    # print("=" * 60)
    # start_time = time.time()
    # ok1, info1 = check_can_run_lammps(code1, timeout=3.0)
    # elapsed = time.time() - start_time
    # print(f"结果: {'✅ 可以运行' if ok1 else '❌ 不能运行'}, Info: {info1}")
    # print(f"耗时: {elapsed:.2f} 秒\n")
    
    # print("=" * 60)
    # print("测试用例 2: 有语法错误的代码")
    # print("=" * 60)
    # start_time = time.time()
    # ok2, info2 = check_can_run_lammps(code2, timeout=3.0)
    # elapsed = time.time() - start_time
    # print(f"结果: {'✅ 可以运行' if ok2 else '❌ 不能运行'}, Info: {info2}")
    # print(f"耗时: {elapsed:.2f} 秒\n")
    
    # print("=" * 60)
    # print("测试用例 3: 需要长时间运行的代码（run 1000000 步）")
    # print("=" * 60)
    # print("说明: 这个代码需要运行很长时间，但函数应该能在 timeout 时间内快速返回")
    # start_time = time.time()
    # ok3, info3 = check_can_run_lammps(code3, timeout=3.0)
    # elapsed = time.time() - start_time
    # print(f"结果: {'✅ 可以运行' if ok3 else '❌ 不能运行'}, Info: {info3}")
    # print(f"耗时: {elapsed:.2f} 秒")
    # if elapsed < 4.0:
    #     print("✅ 验证通过: 函数在超时时间内快速返回，没有等待模拟完成")
    # else:
    #     print("⚠️ 警告: 函数耗时较长，可能存在问题")
    # print()
    
    # print("=" * 60)
    # print("测试完成")
    # print("=" * 60)
    code_4 = """
\n    # 使用 FCC 铝，EAM 力场\n    units metal\n    atom_style atomic\n    lattice fcc 4.05\n    region box block 0 5 0 5 0 5\n    create_box 1 box\n    create_atoms 1 box\n    mass 1 26.98\n    pair_style eam\n    pair_coeff * * potentials/Al99.eam.alloy\n    velocity all create 300.0 12345\n    log lammps_run_20251119_214222_e23a/log.lammps\n    dump 1 all atom 10 lammps_run_20251119_214222_e23a/dump.lammpstrj\n    dump_modify 1 sort id\n    thermo 10\n    minimize 1.0e-4 1.0e-6 1000 10000\n    run 0\n
    """
    ok4, info4 = check_can_run_lammps(code_4, timeout=3.0)
    print(f"结果: {'✅ 可以运行' if ok4 else '❌ 不能运行'}, Info: {info4}")
    
    print("=" * 60)
    print("测试完成")
    print("=" * 60)

