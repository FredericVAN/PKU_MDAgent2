# Utils 工具模块说明

> 本目录包含了 LAMMPS-GRPO 项目中使用的各种工具函数和辅助模块，涵盖了 LAMMPS 代码处理、LLM 调用、数据统计、可视化等功能。

## 📋 目录

- [概述](#概述)
- [核心工具文件](#核心工具文件)
- [子模块说明](#子模块说明)
  - [lammps_potential_utils](#lammps_potential_utils)
  - [lammps_vis_eval_utils](#lammps_vis_eval_utils)
- [使用示例](#使用示例)

---

## 概述

`utils` 目录提供了项目所需的各种工具函数，主要分为以下几类：

| 类别 | 功能 | 主要文件 |
|------|------|----------|
| **通用工具** | 奖励计算、代码提取、文件转换 | `common_utils.py` |
| **GRPO 工具** | 强化学习奖励计算、LAMMPS 运行评估 | `grpo_utils.py` |
| **LAMMPS 工具** | 语法检查、势函数管理、代码执行 | `lammps_*.py` |
| **LLM 调用** | OpenAI、Qwen、VLLM 接口封装 | `llm_call.py` |
| **数据处理** | 数据集统计、HuggingFace 上传 | `statistics_datasets.py`, `upload_huggingface.py` |
| **可视化评估** | LAMMPS 结果可视化、质量评估 | `lammps_vis_eval_utils/` |

---

## 核心工具文件

### `common_utils.py`

**功能：** 提供通用的工具函数

**主要函数：**

- `cal_reward(add_score, penalty_score, MAX_SCORE=1)` - 计算奖励分数并缩放到 [0, MAX_SCORE] 范围
- `extract_codestr_from_outputstr(output_str)` - 从 LLM 输出中提取 LAMMPS 代码（支持 ```lammps、```json、``` 等格式）
- `extract_jsonstr_from_outputstr(output_str)` - 从输出中提取 JSON 字符串
- `generate_random_dirname()` - 生成带时间戳的随机目录名（用于 LAMMPS 运行）
- `generate_random_dirname_without_timestamp()` - 生成不带时间戳的随机目录名
- `json_to_jsonl(json_path, jsonl_path)` - 将标准 JSON 文件转换为 JSONL 格式

**使用场景：**
- 奖励计算（GRPO 训练）
- 代码提取（从 LLM 输出中解析代码）
- 文件格式转换

---

### `grpo_utils.py`

**功能：** GRPO（Group Relative Policy Optimization）相关的工具函数

**主要函数：**

- `call_qwen(system_prompt, user_prompt, ...)` - 调用阿里云 Qwen API（支持流式输出和 thinking 模式）
- `get_reward_by_llm_eval_lammps(lammps_code, checkout_filename_list, user_input, ...)` - 使用 LLM 评估 LAMMPS 代码并计算奖励
  - 支持两种模式：
    - `is_with_run_result=True`: 结合 LAMMPS 运行结果进行评估（方式2）
    - `is_with_run_result=False`: 仅使用代码进行评估（方式1）
  - 支持标准答案对比评估（`standard_answer` 参数）
- `run_lammps_via_api(lammps_code, ...)` - 通过 FastAPI 接口运行 LAMMPS 代码

**使用场景：**
- GRPO 训练中的奖励计算
- LAMMPS 代码质量评估
- 远程 LAMMPS 服务调用

---

### `lammps_check_systax_tools.py`

**功能：** LAMMPS 语法检查工具

**主要函数：**

- `check_can_run_lammps(code, timeout=3.0, lammps_cmd=None)` - 快速检查 LAMMPS 代码是否能成功运行
  - 自动检测 LAMMPS 可执行文件（支持 `lmp`, `lammps`, `lmp_serial`, `lmp_mpi`）
  - 在超时时间内快速检测语法错误
  - 返回格式化的错误信息（对 LLM 友好）
  - 支持 Windows/Linux/Mac 多平台

**特点：**
- 快速检测（默认 3 秒超时）
- 智能错误提取（提取 ERROR 行、最后执行的命令、相关上下文）
- 不等待模拟完成，只检查能否启动

**使用场景：**
- 代码生成后的语法验证
- 快速错误检测
- LangGraph 工具集成

---

### `lammps_potential_tools.py`

**功能：** LAMMPS 势函数检查工具（LangGraph 工具接口）

**主要工具函数：**

- `check_lammps_potentials_tool(lammps_code, top_k=10)` - 检查 LAMMPS 代码中的势函数依赖
  - 自动检测缺失的势函数文件
  - 尝试从 LAMMPS 官方源下载
  - 下载失败时推荐相似的势函数文件
- `check_lammps_potential_files_tool(potential_files, top_k=10)` - 检查势函数文件列表是否存在
- `get_potential_file_info_tool(filename)` - 获取势函数文件的详细信息
- `list_available_potentials_tool()` - 列出本地可用的势函数文件
- `find_similar_potentials_tool(query_name, top_k=10)` - 根据名称查找相似的势函数文件

**返回格式：**
```python
{
    "status": "success" | "error",
    "summary": "检查摘要",
    "details": {...},  # 每个文件的检查详情
    "all_ready": bool,  # 是否所有文件都存在
    "message": "用户友好的消息",
    "recommendations": {...}  # 不存在的文件的推荐信息
}
```

**使用场景：**
- LangGraph Agent 工具集成
- 势函数依赖检查
- 相似势函数推荐

---

### `lammps_run_tools.py`

**功能：** LAMMPS 代码执行工具（多进程安全）

**主要函数：**

- `run_lammps_in_process(lammps_code, max_return_length=20000, tmpdir=None, checkout_filename_list=None, timeout=1200)` - 在独立进程中执行 LAMMPS 代码
  - 支持超时控制（默认 1200 秒）
  - 多进程安全（使用 `multiprocessing`）
  - 自动提取输出文件内容
  - 支持日志质量评估（`is_use_evaluator_tool`）
  - 可指定要检查的输出文件列表
- `create_lammps_script(tmpdir)` - 创建标准的 LAMMPS 测试脚本
- `test_run_lammps_in_process()` - 测试多进程并发运行功能

**返回格式：**
```python
{
    "status": "success" | "error" | "timeout",
    "summary": "执行摘要",
    "outputs": {filename: content},  # 输出文件内容字典
    "errors": [...],  # 错误信息列表
    "extra_info": {...}  # 额外信息（如日志质量评估结果）
}
```

**特点：**
- 进程隔离，避免崩溃影响主程序
- 自动清理临时文件
- 支持并发执行多个 LAMMPS 实例

**使用场景：**
- 代码执行验证
- 批量代码运行
- GRPO 训练中的代码执行

---

### `lammps_vis_eval_tools.py`

**功能：** LAMMPS 可视化和评估工具（高级接口）

**主要函数：**

- `evaluate_log_quality_tool(log_path)` - 评估 log 文件的质量
- `auto_visualize_eval_lammps_files(folder_path)` - 自动可视化文件夹中的 LAMMPS 文件
  - 自动处理 `log.lammps` 文件（生成热力学曲线图）
  - 自动处理 `dump.lammpstrj` 文件（生成 GIF 动画）
  - 同时进行质量评估

**使用场景：**
- 批量结果可视化
- 结果质量评估
- 报告生成

---

### `llm_call.py`

**功能：** LLM 调用工具（支持多种 API）

**主要函数：**

- `call_vllm(system_prompt, user_prompt, temperature=0.7, model="Qwen/Qwen3-8B", enable_thinking=True)` - 调用 VLLM 服务
  - 支持 thinking 模式（Qwen3 推理解析）
  - 自动重试机制（最多 5 次）
  - 错误诊断（检查服务状态、列出可用模型）
  - 配置通过环境变量：`VLLM_API_BASE`, `VLLM_API_KEY`
- `call_qwen(system_prompt, user_prompt, ...)` - 调用阿里云 Qwen API
  - 支持流式输出
  - 支持 thinking 模式
- `call_openai(system_prompt, user_prompt, ...)` - 调用 OpenAI API
- `batch_call_openai(system_prompt, user_prompts, ...)` - 批量调用 OpenAI API（并发）
- `check_vllm_service_status()` - 检查 VLLM 服务状态和可用模型

**配置：**
- OpenAI: 从环境变量 `OPENAI_API_KEY` 读取
- Qwen: 从环境变量 `DASHSCOPE_API_KEY` 读取
- VLLM: 从环境变量 `VLLM_API_BASE`（默认 `http://172.31.1.132:8000/v1`）和 `VLLM_API_KEY` 读取

**使用场景：**
- 代码生成
- 代码评估
- 批量推理

---

### `log_utils.py`

**功能：** 日志工具

**主要函数：**

- `log_to_file(msg, filename="lammps_log.txt")` - 将日志信息写入文件，自动添加时间戳

**使用场景：**
- 调试日志记录
- 运行日志保存

---

### `statistics_datasets.py`

**功能：** 数据集统计工具

**主要函数：**

- `read_json_or_jsonl(filepath)` - 读取 JSON 或 JSONL 文件
- `count_tokens(text, encoding_name="cl100k_base")` - 使用 tiktoken 统计文本的 token 数
- `analyze_token_stats(data)` - 统计数据集中每一列的 token 数
- `plot_token_stats(token_stats, output_dir, filename)` - 绘制所有列的 token 分布直方图（拼接成一张大图）
- `print_token_range(token_stats)` - 打印每一列的 token 数范围（min, max, mean, count）

**使用场景：**
- 数据集分析
- Token 统计
- 数据质量检查

**命令行使用：**
```bash
python statistics_datasets.py --filepath data.jsonl --output_dir ./token_stats_plots
```

---

### `upload_huggingface.py`

**功能：** HuggingFace 数据集上传工具

**主要函数：**

- `upload_json_to_hf(json_path, repo_id, token=None, split="train", auto_split=False, test_size=0.1, seed=42, private=False)` - 上传本地 JSON 文件到 HuggingFace Hub
  - 支持自动划分训练集和测试集（`auto_split=True`）
  - 支持私有数据集上传（`private=True`）
- `push_to_huggingface_dataset(train_dataset, valid_dataset, repo_id, token)` - 将训练集和验证集一起上传

**使用场景：**
- 数据集发布
- 模型训练数据管理

---

## 子模块说明

### `lammps_potential_utils/`

势函数管理相关工具。

#### `lammps_potential_manager.py`

**功能：** LAMMPS 势函数管理器（核心实现）

**主要功能：**

- 自动检测 LAMMPS 代码中使用的势函数
- 从 LAMMPS 官方源（`https://download.lammps.org/potentials`）下载缺失的势函数文件
- MD5 校验文件完整性
- 支持多种势函数格式（EAM、Tersoff、SNAP、MEAM 等 50+ 种格式）
- 文件验证和完整性检查

**主要类：**

- `LAMMPSPotentialManager` - 势函数管理器类

**使用场景：**
- 势函数依赖管理
- 自动下载缺失文件
- 文件完整性验证

---

#### `lammps_potential_api.py`

**功能：** 势函数 API 接口（大模型专用）

**主要类：**

- `LAMMPSPotentialAPI` - 势函数 API 类

**主要方法：**

- `check_lammps_potential_files(potential_files, top_k=10)` - 检查势函数文件列表
- `check_lammps_potentials(lammps_code, top_k=10)` - 检查代码中的势函数
- `get_potential_info(filename)` - 获取文件信息
- `find_similar_potentials(query_name, top_k=10)` - 查找相似势函数
- `get_potential_extensions()` - 获取支持的势函数扩展名列表

**特点：**
- 简化接口，专门为大模型调用设计
- 自动推荐相似文件（使用多种相似度算法）
- 友好的错误消息

---

### `lammps_vis_eval_utils/`

LAMMPS 结果可视化和评估工具。

#### `my_utils.py`

**功能：** 基础工具函数

**主要函数：**

- `parse_log_file(filename)` - 解析 LAMMPS log 文件，提取 thermo 数据为 pandas DataFrame
- `read_lammps_dump(filename)` - 读取 LAMMPS dump 文件，返回帧列表 `[(timestep, x, y, z), ...]`
  - 支持 `x/y/z` 和 `xs/ys/zs` 坐标格式
  - 自动处理坐标转换

**使用场景：**
- 数据解析
- 可视化预处理

---

#### `lammps_evaluator_api.py`

**功能：** LAMMPS 日志质量评估 API

**主要函数：**

- `evaluate_log_quality(log_path)` - 全面评估 LAMMPS log 文件质量

**评估内容：**

- **基础状态：** 模拟是否完成、时间步数、是否有 NaN、是否有警告
- **能量分析：** 能量稳定性、热平衡、能量趋势
- **温度分析：** 温度稳定性、收敛性、温度趋势
- **压力分析：** 压力合理性、稳定性
- **体积/密度分析：** 体积稳定性、密度稳定性
- **动力学分析：** 动能稳定性、势能稳定性
- **系统参数：** 原子数、盒子尺寸、邻居数等
- **模拟类型识别：** NVE、NVT、NPT、minimize、deform 等
- **质量等级：** Excellent、Good、Fair、Poor

**返回格式：**
```python
{
    "finished": bool,
    "timesteps": int,
    "has_nan": bool,
    "energy_stable": bool,
    "temperature_stable": bool,
    "quality_grade": "Excellent" | "Good" | "Fair" | "Poor",
    "summary": str,
    "warnings": [...],
    "recommendations": [...],
    ...
}
```

**使用场景：**
- 代码质量评估
- 模拟结果诊断
- 自动报告生成

---

#### `lammps_visualizer_api.py`

**功能：** LAMMPS 可视化 API

**主要函数：**

- `save_thermo_curves(log_file)` - 保存热力学曲线图（温度、能量、压力等）
  - 自动保存到 log 文件同目录，文件名：`{log_name}_thermo.png`
- `plot_thermo_curves(log_file)` - 绘制热力学曲线图（显示）
- `plot_dump_frame(dump_file, frame_index=0)` - 绘制 dump 文件的单帧 3D 图
- `save_dump_as_gif(dump_file, interval=None, dpi=100)` - 将 dump 文件保存为 GIF 动画
  - 自动计算合理的播放速度（目标 5-10 秒）
  - 自动保存到 dump 文件同目录，文件名：`{dump_name}.gif`

**使用场景：**
- 结果可视化
- 报告生成
- 动画制作

---

#### `plot_dump.py`

**功能：** dump 文件可视化脚本（独立工具）

**主要功能：**

- 读取 dump 文件
- 绘制单帧或生成 GIF 动画
- 命令行工具

**使用场景：**
- 独立使用
- 批量处理

---

#### `plot_log.py`

**功能：** log 文件可视化脚本（独立工具）

**主要功能：**

- 解析 log 文件
- 绘制热力学曲线
- 命令行工具

**使用场景：**
- 独立使用
- 快速查看结果

---

## 使用示例

### 示例 1：检查 LAMMPS 代码语法

```python
from utils.lammps_check_systax_tools import check_can_run_lammps

code = """
units metal
atom_style atomic
lattice fcc 3.615
region box block 0 5 0 5 0 5
create_box 1 box
create_atoms 1 box
run 10
"""

can_run, error_info = check_can_run_lammps(code, timeout=3.0)
if can_run:
    print("✅ 代码可以运行")
else:
    print(f"❌ 代码有错误：\n{error_info}")
```

### 示例 2：检查势函数依赖

```python
from utils.lammps_potential_tools import check_lammps_potentials_tool

code = """
pair_style eam
pair_coeff * * potentials/Al99.eam.alloy
"""

result = check_lammps_potentials_tool(code, top_k=5)
print(result["message"])
if not result["all_ready"]:
    print("推荐文件：", result["recommendations"])
```

### 示例 3：运行 LAMMPS 代码

```python
from utils.lammps_run_tools import run_lammps_in_process

code = """
units lj
atom_style atomic
lattice fcc 0.8442
region box block 0 10 0 10 0 10
create_box 1 box
create_atoms 1 box
mass 1 1.0
pair_style lj/cut 2.5
pair_coeff 1 1 1.0 1.0 2.5
thermo 10
log log.lammps
dump 1 all atom 10 dump.lammpstrj
fix 1 all nve
run 50
"""

result = run_lammps_in_process(
    code,
    checkout_filename_list=["log.lammps", "dump.lammpstrj"],
    timeout=60
)

if result["status"] == "success":
    print("✅ 运行成功")
    print("输出文件：", list(result["outputs"].keys()))
else:
    print("❌ 运行失败：", result["summary"])
```

### 示例 4：评估日志质量

```python
from utils.lammps_vis_eval_utils.lammps_evaluator_api import evaluate_log_quality

report = evaluate_log_quality("log.lammps")
print(f"质量等级：{report['quality_grade']}")
print(f"摘要：{report['summary']}")
print(f"警告：{report['warnings']}")
```

### 示例 5：可视化结果

```python
from utils.lammps_vis_eval_utils.lammps_visualizer_api import save_thermo_curves, save_dump_as_gif

# 生成热力学曲线图
save_thermo_curves("log.lammps")

# 生成 dump 动画
save_dump_as_gif("dump.lammpstrj")
```

### 示例 6：调用 LLM

```python
from utils.llm_call import call_vllm

response = call_vllm(
    system_prompt="You are a LAMMPS expert.",
    user_prompt="Generate a LAMMPS script for Cu simulation.",
    model="mdagent-v5",
    enable_thinking=True
)
print(response)
```

### 示例 7：统计数据集 Token

```python
from utils.statistics_datasets import read_json_or_jsonl, analyze_token_stats, print_token_range

data = read_json_or_jsonl("dataset.jsonl")
token_stats = analyze_token_stats(data)
print_token_range(token_stats)
```

---

## 📝 注意事项

1. **环境变量配置：**
   - `OPENAI_API_KEY`: OpenAI API 密钥
   - `DASHSCOPE_API_KEY`: 阿里云 Qwen API 密钥
   - `VLLM_API_BASE`: VLLM 服务地址（默认：`http://172.31.1.132:8000/v1`）
   - `VLLM_API_KEY`: VLLM API 密钥（可选）
   - `HF_TOKEN`: HuggingFace 访问令牌

2. **LAMMPS 安装：**
   - 部分工具需要本地安装 LAMMPS
   - 支持通过 API 调用远程 LAMMPS 服务

3. **依赖安装：**
   - 大部分工具需要安装项目依赖（见项目根目录 `requirements.txt` 或 `uv.lock`）

4. **多进程安全：**
   - `lammps_run_tools.py` 使用多进程执行，确保进程隔离
   - 注意临时文件清理

---

## 🔗 相关文档

- [项目主 README](../README.md)
- [势函数管理器说明](../README_potential_manager.md)
- [PostTrain 代码说明](../PostTrain代码/README.md)

---

> 💡 **提示**：如有问题或建议，请查看相关工具的代码注释或提交 Issue。
