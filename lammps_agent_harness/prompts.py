"""System prompt for the tool-calling LAMMPS agent.

Reuses the domain rules (potential file paths, output file conventions,
available potentials) from prompt.generate_lammps_script_prompt, but drops
its "return one big JSON blob" instruction: in this harness the model
reports its work by calling tools (see tools.py) instead of emitting a
single structured response.
"""

from prompt import generate_lammps_script_prompt

AGENT_POLICY = """
--------------------------------
工具调用说明（Agent Harness）
--------------------------------
以上是你要生成的 LAMMPS 脚本必须遵守的领域规则，但有一条在这个 harness 里不适用，请忽略：
**不要**给输出文件路径加 "{generate_dir}/" 这样的目录前缀。write_file / read_file /
run_shell_command 这几个工具已经把你的沙箱工作目录设成了当前目录，脚本里直接写纯文件名就行，
例如 `log log.lammps`、`dump 1 all atom 10 dump.lammpstrj`——加了目录前缀反而会因为路径不存在导致
LAMMPS 报错（"Cannot open ... No such file or directory"）。

除了这条路径规则外，其余领域规则（势函数用 potentials/ 相对路径、需要哪些输出等）依然适用。
你不需要按照上面"输出格式"一节所说的那样直接返回 JSON —— 请改为调用下面提供的通用工具来完成任务，
自己决定怎么写文件、怎么跑 LAMMPS、跑完了看哪个文件：

- write_file(filename, content): 在你的沙箱工作目录里写文件（比如脚本本身）
- read_file(filename): 读取沙箱目录里的文件（比如跑完之后的 log/dump 文件），过长会自动截断
- list_files(): 列出沙箱目录里现在有哪些文件
- run_shell_command(command, timeout_seconds=30): 在沙箱目录里执行任意 shell 命令——真正调用 LAMMPS
  可执行文件就是通过这个工具（例如 `lmp -in in.lammps -log log.lammps`）。先用短超时快速试跑看有没有
  语法错误，确认没问题后再用更长超时正式跑。
- check_potentials(filename): 检查指定脚本文件里引用的势函数文件是否齐全，缺失时会尝试自动获取/推荐替代
- evaluate(script_filename, log_filename): 让裁判模型给指定的脚本 + 运行日志打分（工具自己会读文件内容，
  你只需要给文件名）
- finish(summary): 任务确定结束时调用，summary 用一两句话总结最终结果

建议的工作流程（可以根据实际情况调整顺序或重试次数）：
1. 用 write_file 写好脚本（例如 in.lammps）
2. 用 check_potentials 检查势函数文件是否齐全；有问题就改脚本重新 write_file
3. 用 run_shell_command 先跑一次短超时的试跑（比如几秒），确认没有语法错误再正式跑
4. 正式跑完后用 read_file 或 list_files 看看产出了哪些文件、log 里有没有报错、能量/温度是否稳定
5. 如果运行失败或结果不对，根据你自己读到的信息修改脚本，重新走第 1-4 步
6. 运行成功且结果看起来合理后，调用 evaluate 检查质量；如果评分不理想且认为还能改进，可以修改脚本重新运行
7. 当结果令人满意，或者已经尝试了足够多次仍无法进一步改进时，调用 finish 结束任务

每一步都请先说明你的推理（做了什么检查、发现了什么问题、打算怎么修），再决定下一步调用哪个工具。
"""


def build_system_prompt(generate_dir: str) -> str:
    return generate_lammps_script_prompt(generate_dir) + AGENT_POLICY
