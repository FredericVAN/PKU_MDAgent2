import uuid
import time

import re

def cal_reward(add_score:int,penalty_score:int,MAX_SCORE:int = 1)->float:
    '''
    计算reward并且放缩到[0,MAX_SCORE]
    :param add_score: 加分
    :param penalty_score: 扣分
    :return: 奖励
    '''
    MIN_RAW_SCORE = -10  # 允许负分数
    MAX_RAW_SCORE = 30
    raw_score = add_score - abs(penalty_score)
    raw_score = max(MIN_RAW_SCORE,raw_score) #防止过小负数
    raw_score = min(raw_score,MAX_RAW_SCORE) #防止超限
    #放缩到0~MAX_SCORE，使用线性映射
    reward = (raw_score - MIN_RAW_SCORE) / (MAX_RAW_SCORE - MIN_RAW_SCORE) * MAX_SCORE
    return reward

def extract_codestr_from_outputstr(output_str: str) -> str:
    # 优先顺序：```lammps > ```json > ```
    patterns = [
        r"```lammps\s*([\s\S]+?)```",
        r"```json\s*([\s\S]+?)```",
        r"```\s*([\s\S]+?)```"
    ]

    for pattern in patterns:
        match = re.search(pattern, output_str)
        if match:
            return match.group(1).strip()
    
    # fallback: return full string if no match found
    return output_str


def extract_jsonstr_from_outputstr(output_str):
    if "```json" in output_str:
        output_str = output_str.split("```json")[-1].strip()
        output_str = output_str.split("```")[0].strip()
    if "```" in output_str:
        output_str = output_str.split("```")[-1].strip()
        output_str = output_str.split("```")[0].strip()
    return output_str

def generate_random_dirname():
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    return f"lammps_run_{timestamp}_{str(uuid.uuid4())[:4]}"

def generate_random_dirname_without_timestamp():
    return f"lammps_run_{str(uuid.uuid4())[:8]}"

import json

def json_to_jsonl(json_path: str, jsonl_path: str):
    """
    将标准 JSON 文件（list[dict]）转换为 JSONL 文件（每行一个 JSON）。
    
    参数：
    - json_path: 输入 JSON 文件路径
    - jsonl_path: 输出 JSONL 文件路径
    """
    with open(json_path, 'r', encoding='utf-8') as fin:
        data = json.load(fin)

    if not isinstance(data, list):
        raise ValueError("输入 JSON 文件必须是一个包含多个对象的列表")

    with open(jsonl_path, 'w', encoding='utf-8') as fout:
        for item in data:
            fout.write(json.dumps(item, ensure_ascii=False) + '\n')

    print(f"✅ 已将 {json_path} 转换为 {jsonl_path}")

if __name__ == "__main__":
    text = """{\n  \"code\": \"\n    # 使用 BCC 结构 Ge，势函数 Ge_Zuo_JPCA2020.quadratic.snapparam\n    units metal\n    atom_style atomic\n    lattice bcc 3.96\n    region box block 0 5 0 5 0 5\n    create_box 1 box\n    create_atoms 1 box\n    mass 1 72.64\n    pair_style eam\n    pair_coeff * * potentials/Ge_Zuo_JPCA2020.quadratic.snapparam\n    velocity all create 172.0 12345\n    log lammps_run_20250708_164103_0b22/log.lammps\n    dump 1 all atom 10 lammps_run_20250708_164103_0b22/dump.lammpstrj\n    dump_modify 1 sort id\n    thermo 10\n    fix 1 all nvt temp 172.0 172.0 0.1\n    run 5000\n    \",\n  \"checkout_filename_list\": [\n    \"log.lammps\",\n    \"dump.lammpstrj\"\n  ]\n}"""

    print(extract_codestr_from_outputstr(text))
    #json_to_jsonl(r"D:\mycoding\python\Lammps-GRPO\datasets\Lammps_Code_DATASET\自己生成的\test_dataset copy.json", r"D:\mycoding\python\Lammps-GRPO\datasets\Lammps_Code_DATASET\自己生成的\test_dataset copy.jsonl")