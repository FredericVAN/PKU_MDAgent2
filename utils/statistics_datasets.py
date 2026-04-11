import os
import json
import matplotlib.pyplot as plt
from collections import defaultdict
from typing import List, Dict, Any, Tuple
import tiktoken
try:
    from tqdm import tqdm
except ImportError:
    tqdm = lambda x: x

def count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """
    用 tiktoken 统计文本的 token 数。
    默认使用 OpenAI cl100k_base 编码（适用于gpt-3.5/4）。
    """

    if not isinstance(text, str):
        return 0
    enc = tiktoken.get_encoding(encoding_name)
    return len(enc.encode(text))

def read_json_or_jsonl(filepath: str) -> List[Dict[str, Any]]:
    """
    读取json或jsonl文件，返回数据列表
    """
    data = []
    if filepath.endswith('.jsonl'):
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    data.append(json.loads(line))
    elif filepath.endswith('.json'):
        with open(filepath, 'r', encoding='utf-8') as f:
            obj = json.load(f)
            if isinstance(obj, list):
                data = obj
            else:
                data = [obj]
    else:
        raise ValueError("只支持json或jsonl文件")
    return data

def analyze_token_stats(data: List[Dict[str, Any]]) -> Dict[str, List[int]]:
    """
    统计每一列的token数
    """
    token_stats = defaultdict(list)
    for item in data:
        for key, value in item.items():
            token_stats[key].append(count_tokens(str(value)))
    return token_stats

import math

def plot_token_stats(token_stats: Dict[str, List[int]], output_dir: str = "./token_stats_plots", filename: str = "all_token_hist.png"):
    """
    将所有列的token分布直方图拼成一张大图保存
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    keys = list(token_stats.keys())
    n = len(keys)
    if n == 0:
        print("没有可绘制的列")
        return
    # 自动计算行列数（尽量接近正方形）
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(cols*6, rows*4))
    axes = axes.flatten() if n > 1 else [axes]
    for idx, key in enumerate(keys):
        tokens = token_stats[key]
        ax = axes[idx]
        ax.hist(tokens, bins=30, color='skyblue', edgecolor='black')
        ax.set_title(f"Token分布: {key}")
        ax.set_xlabel("Token数")
        ax.set_ylabel("样本数")
        ax.grid(True, linestyle='--', alpha=0.5)
    # 多余的子图隐藏
    for j in range(idx+1, len(axes)):
        axes[j].set_visible(False)
    plt.tight_layout()
    save_path = os.path.join(output_dir, filename)
    plt.savefig(save_path)
    plt.close()
    print(f"所有直方图已拼接保存为: {save_path}")
    
def print_token_range(token_stats: Dict[str, List[int]]):
    """
    打印每一列的token数范围
    """
    for key, tokens in token_stats.items():
        if tokens:
            print(f"{key}: min={min(tokens)}, max={max(tokens)}, mean={sum(tokens)/len(tokens):.2f}, count={len(tokens)}")
        else:
            print(f"{key}: 无数据")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="统计json/jsonl文件每一列的token数范围并画图")
    parser.add_argument("--filepath", type=str, help="输入的json或jsonl文件路径", default=r"D:\mycoding\python\Lammps-GRPO\datasets\Lammps_Code_DATASET\自己生成的\codeGen_train.jsonl")
    parser.add_argument("--output_dir", type=str, default="./token_stats_plots", help="图片输出目录")
    args = parser.parse_args()
    filename = os.path.basename(args.filepath)
    save_dir = os.path.join(args.output_dir, filename)
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    print(f"正在读取数据: {args.filepath}")
    data = read_json_or_jsonl(args.filepath)
    print(f"共读取到{len(data)}条数据")
    token_stats = analyze_token_stats(data)
    print("每一列的token数范围如下：")
    print_token_range(token_stats)
    print(f"正在绘制直方图，图片保存在: {save_dir}")
    plot_token_stats(token_stats, save_dir)
    print("完成！")
