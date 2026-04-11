# MDAgent2: 用于分子动力学代码生成与知识问答的大语言模型

<p align="center">
  <img src="./pics/MDAgent2-System.png" alt="MDAgent2 系统概览" width="100%"/>
</p>

[![arXiv](https://img.shields.io/badge/arXiv-2601.02075-b31b1b)](https://arxiv.org/abs/2601.02075)
[![GitHub](https://img.shields.io/badge/GitHub-PKU__MDAgent2-blue)](https://github.com/FredericVAN/PKU_MDAgent2)
[![website](https://img.shields.io/badge/website-MDAgent2-blue)](https://fredericvan.github.io/PKU_MDAgent2/)
[![Leaderboard](https://img.shields.io/badge/%F0%9F%8F%86%20Leaderboard-MD--Benchmark-orange)](https://huggingface.co/spaces/PKU-JX-LAB/Molecular-Dynamics-Benchmark)
[![Dataset](https://img.shields.io/badge/%F0%9F%A4%97%20HuggingFace-MD--EvalBench-yellow)](https://huggingface.co/datasets/FredericFan/MD-EvalBench)

[English](README.md)

## 新闻

- **[2026-04-11]** 我们公开了代码与部分 Benchmark，欢迎体验！

> **注意：** 完整代码与完整 Benchmark 将于论文录用后公开。

## 简介

我们提出了 **MDAgent2**，这是第一个在分子动力学（MD）领域同时支持知识问答和代码生成的端到端框架。主要贡献包括：

- 构建了领域特定的数据构建管道，产生三个高质量数据集，涵盖 MD 知识、问答和代码生成。
- 采用三阶段后训练策略——继续预训练（CPT）、监督微调（SFT）和强化学习（RL）——训练了两个领域适应模型：**MD-Instruct** 和 **MD-Code**。
- 引入 **MD-GRPO**，一种闭环强化学习方法，利用仿真结果作为奖励信号，并回收低奖励轨迹进行持续优化。
- 构建了 **MDAgent2-RUNTIME**，一个可部署的多智能体系统，集成代码生成、执行、评估和自我纠正。
- 提出了 **MD-EvalBench**，第一个用于 LAMMPS 代码生成和问答的基准测试。

## 性能表现

我们的模型和系统在 MD-EvalBench 上取得了超越多个强基线的性能，展示了大语言模型在工业仿真任务中的适应性和泛化能力。

<p align="center">
  <img src="pics/Exp1-table1.png" alt="性能对比表格" width="100%"/>
</p>

<p align="center">
  <img src="pics/EXP2-figure_combined.png" alt="性能结果" width="80%"/>
</p>

## 架构

### 三阶段训练策略

<p align="center">
  <img src="./pics/MDAgent2-System.png" alt="MDAgent2 系统" width="80%"/>
</p>

- **CPT**：在 MD 专用语料库上继续预训练，实现领域适应
- **SFT**：在高质量指令跟随和代码生成数据集上微调
- **RL（MD-GRPO）**：闭环强化学习，利用仿真反馈作为奖励信号，回收低奖励轨迹持续优化

### MD-GRPO

<p align="center">
  <img src="./pics/MDAgent2-MDGRPO.drawio.png" alt="MD-GRPO" width="80%"/>
</p>

### MDAgent2-RUNTIME

<p align="center">
  <img src="./pics/MDAgent2-RUNTIME.png" alt="MDAgent2-RUNTIME" width="80%"/>
</p>

可部署的多智能体系统，将代码生成、执行、评估和自我纠正集成在闭环中。

## MD-EvalBench

**MD-EvalBench** 是第一个用于 LAMMPS 代码生成和问答的基准测试，系统评估：

- **代码生成**：从自然语言生成可执行的 LAMMPS 脚本
- **知识问答**：回答关于分子动力学的领域特定问题
- **代码可执行性**：确保生成的代码能在仿真环境中成功运行

### 基准数据解密

为防止基准测试数据被爬取用于大语言模型训练，`MD_Benchmark/` 中的答案字段以 base64 编码形式分发。

解码答案字段用于评测：

```bash
python decrypt_benchmark.py
```

无需密码。该脚本会原地还原 `answer` 和 `answer_text` 字段，文件始终保持有效的 JSON/JSONL 格式。

> **注意：** 请勿公开传播解码后的基准数据。

## 使用方法

### 两种 Agent 实现

**LangGraph 版本**：

```python
from LammpsAgents_by_langgraph import run_lammps_agents

final_state = run_lammps_agents("我想模拟铜的热膨胀", is_delete_dir=True)
```

**Autogen 版本**：

```python
from LammpsAgents_by_autogen import run_lammps_agents

final_state = run_lammps_agents("我想模拟铜的热膨胀", is_delete_dir=True)
```

### 环境配置

#### Linux（推荐）

1. 推荐 Python 3.11（建议使用 conda 虚拟环境）

2. 安装 CUDA：

   ```bash
   conda install cudatoolkit cuda-version=11
   ```

3. 安装 LAMMPS：

   - **方式 A** — conda（简单但功能有限）：

     ```bash
     conda install lammps -c conda-forge
     conda install openkim-models -c conda-forge
     ```

   - **方式 B** — 源码编译（完全控制）：

     ```bash
     git clone https://github.com/lammps/lammps.git
     cd lammps && mkdir build && cd build
     cmake ../cmake \
       -DCMAKE_BUILD_TYPE=Release \
       -DBUILD_MPI=ON \
       -DBUILD_SHARED_LIBS=ON \
       -DPKG_MISC=ON \
       -DPKG_KSPACE=ON \
       -DPKG_MOLECULE=ON \
       -DPKG_USER-MISC=ON \
       -DPKG_EAM=ON \
       -DPKG_MANYBODY=ON
     make -j$(nproc)
     ```

4. 安装 Python 依赖：

   ```bash
   pip install uv
   uv pip install -r requirements.txt
   ```

5. 配置环境变量：

   ```bash
   cp .env-EXAMPLE .env
   # 编辑 .env，设置 OPENAI_API_KEY=...
   ```

6. （可选）安装 PyTorch 以使用本地模型：

   ```bash
   pip3 install torch torchvision torchaudio
   ```

#### Windows

1. 推荐 Python 3.11（建议使用 conda 虚拟环境）

2. 安装 CUDA：

   ```bash
   conda install cudatoolkit cuda-version=11
   ```

3. 按照 [LAMMPS 官方指南](https://docs.lammps.org/Install.html) 安装 LAMMPS

4. 安装 Python 依赖：

   ```bash
   pip install uv
   uv pip install -r requirements.txt
   ```

5. 配置环境变量：

   ```bash
   cp .env-EXAMPLE .env
   # 编辑 .env，设置 OPENAI_API_KEY=...
   ```

6. （可选）安装 PyTorch：

   ```bash
   pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
   ```

### 方式一：前端 + 后端

- **后端**：基于 FastAPI，负责 Agent 推理、文件管理和可视化
- **前端**：基于 Vue3 + Vite，提供交互式 Web 界面

```bash
# 启动后端（默认端口 8000）
python app.py

# 启动前端
cd lammps-frontend
npm install
npm run dev
```

前端：<http://localhost:5173> | 后端 API 文档：<http://localhost:8000/docs>

### 方式二：Docker

```bash
# 构建镜像
docker build -t lammps-grpo:latest .

# 运行
docker run -d --restart=always -p 8000:8000 \
  --env-file .env \
  --name lammps-grpo \
  lammps-grpo:latest
```

> 默认镜像基于 `python:3.11-slim`，不包含 GPU/CUDA。如需在容器内使用 LAMMPS + CUDA，请自行扩展 Dockerfile。

## 示例

**输入**：

> 我想模拟铜在 300K 下等压等温（NPT）条件下的热膨胀系数变化过程，并输出其体积变化数据。

**生成的 LAMMPS 脚本**：

```lammps
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
log log.lammps
dump 1 all atom 10 dump.lammpstrj
dump_modify 1 sort id
thermo 10
fix 1 all npt temp 300.0 300.0 0.1 iso 0 0 1.0
run 1000
```

## 目录结构

```text
├── LammpsAgents_by_langgraph.py   # 基于 LangGraph 的 Agent 工作流
├── app.py                         # FastAPI 后端服务
├── prompt.py                      # LAMMPS 生成系统提示词
├── encrypt_benchmark.py           # 编码基准答案字段（base64）
├── decrypt_benchmark.py           # 解码基准答案字段
├── potentials/                    # LAMMPS 势函数文件
├── train_dataset/                 # 训练数据集（仅示例）
│   ├── MD-CodeGen/
│   ├── MD-InstructQA/
│   └── MD-Knowledge/
├── MD_Benchmark/                  # 评测基准
│   ├── ZH/                       # 中文版
│   │   ├── Code_Eval/
│   │   └── QA_Eval/
│   └── EN/                       # 英文版
│       ├── Code_Eval/
│       └── QA_Eval/
├── utils/                         # 工具和 API
├── lammps-frontend/               # Vue3 前端
├── lammps_run_example/            # LAMMPS 运行示例
├── pics/                          # 图片
├── demo_video/                    # 演示视频
├── requirements.txt               # Python 依赖
├── requirements_grpo.txt          # GRPO 训练依赖
├── Dockerfile                     # Docker 配置
├── .env-EXAMPLE                   # 环境变量模板
├── README.md                      # 文档（英文）
├── README_CN.md                   # 文档（中文）
└── LICENSE                        # 许可证
```

## 引用

如果您觉得我们的工作对您的研究有帮助，请引用：

```bibtex
@misc{shi2026mdagent2large,
      title={MDAgent2: Large Language Model for Code Generation and Knowledge Q&A in Molecular Dynamics}, 
      author={Zhuofan Shi and Hubao A and Yufei Shao and Mengyan Dai and Yadong Yu and Pan Xiang and Dongliang Huang and Hongxu An and Chunxiao Xin and Haiyang Shen and Zhenyu Wang and Yunshan Na and Gang Huang and Xiang Jing},
      year={2026},
      eprint={2601.02075},
      archivePrefix={arXiv},
      primaryClass={cs.CE},
      url={https://arxiv.org/abs/2601.02075}
}
```

## 许可证

本项目遵循 [LICENSE](LICENSE) 文件中指定的许可证条款。

## 致谢

我们衷心感谢所有参与本研究的贡献者和机构。
