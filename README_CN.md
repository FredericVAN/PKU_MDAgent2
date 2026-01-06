
# MDAgent2: 用于分子动力学代码生成与知识问答的大语言模型

<p align="center">
  <img src="./pics/MDAgent2-System.png" alt="logo" width="100%"/>
</p>

<a href="https://arxiv.org/abs/2601.02075">![arXiv](https://img.shields.io/badge/arXiv-2601.02075-b31b1b)</a>
<a href="https://github.com/your-repo/PKU_MDAgent2">![GitHub](https://img.shields.io/badge/GitHub-PKU_MDAgent2-blue)</a>
<a href="https://your-username.github.io/PKU_MDAgent2/">![website](https://img.shields.io/badge/website-MDAgent2-blue)</a>

> **注意：** 代码和数据集将在论文接收后发布。

## 💡 简介

- 我们提出了 **MDAgent2**，这是第一个能够在分子动力学（MD）领域同时执行知识问答和代码生成的端到端框架。
- 我们构建了一个领域特定的数据构建管道，产生了三个高质量数据集，涵盖MD知识、问答和代码生成。
- 我们采用三阶段后训练策略——继续预训练（CPT）、监督微调（SFT）和强化学习（RL）——训练了两个领域适应模型：**MD-Instruct** 和 **MD-Code**。
- 我们引入了 **MD-GRPO**，一种闭环强化学习方法，利用仿真结果作为奖励信号，并回收低奖励轨迹进行持续优化。
- 我们构建了 **MDAgent2-RUNTIME**，一个可部署的多智能体系统，集成了代码生成、执行、评估和自我纠正。
- 我们提出了 **MD-EvalBench**，这是第一个用于LAMMPS代码生成和问答的基准测试。

## 🚀 性能表现

我们的模型和系统在MD-EvalBench上取得了超越多个强基线的性能，展示了大语言模型在工业仿真任务中的适应性和泛化能力。

<p align="center">
  <img src="pics/Exp1-table1.png" alt="性能对比表格" width="100%"/>
</p>

<p align="center">
  <img src="pics/EXP2-figure_combined.png" alt="性能结果" width="80%"/>
</p>

## 🔍 MDAgent2 特性

### 三阶段训练策略

<p align="center">
  <img src="./pics/MDAgent2-System.png" alt="MDAgent2系统" width="80%"/>
</p>

MDAgent2采用全面的三阶段后训练策略：

- **继续预训练（CPT）**：通过在MD特定语料库上继续预训练进行领域适应
- **监督微调（SFT）**：在高质量的指令跟随和代码生成数据集上进行微调
- **强化学习（RL）**：使用MD-GRPO方法通过仿真反馈优化代码生成

### MD-GRPO：闭环强化学习

<p align="center">
  <img src="./pics/MDAgent2-MDGRPO.drawio.png" alt="MD-GRPO" width="80%"/>
</p>

**MD-GRPO** 是一种新颖的闭环强化学习方法，具有以下特点：

- 利用仿真结果作为代码质量评估的奖励信号
- 回收低奖励轨迹进行持续优化
- 实现生成LAMMPS脚本的迭代改进

### MDAgent2-RUNTIME：多智能体系统

<p align="center">
  <img src="./pics/MDAgent2-RUNTIME.png" alt="MDAgent2-RUNTIME" width="80%"/>
</p>

**MDAgent2-RUNTIME** 是一个可部署的多智能体系统，集成了：

- **代码生成**：从自然语言描述自动生成LAMMPS脚本
- **代码执行**：在仿真环境中运行生成的脚本
- **评估**：评估代码正确性和仿真结果
- **自我纠正**：基于执行反馈进行迭代优化

### 领域特定数据集

我们构建了三个高质量数据集：

- **MD知识数据集**：分子动力学的综合知识库
- **问答数据集**：MD领域知识的问答对
- **代码生成数据集**：带有自然语言描述的LAMMPS脚本示例

## 📊 MD-EvalBench

**MD-EvalBench** 是第一个用于LAMMPS代码生成和问答的基准测试，系统评估：

- **代码生成任务**：从自然语言生成可执行的LAMMPS脚本
- **问答任务**：回答关于分子动力学的领域特定问题
- **代码可执行性**：确保生成的代码能够在仿真环境中成功运行

实验结果表明，MDAgent2在MD-EvalBench上持续超越代表性基线方法。

## 🎯 主要贡献

1. **第一个端到端框架**：MDAgent2是第一个在MD领域同时支持知识问答和代码生成的框架
2. **领域特定数据管道**：用于MD领域的高质量数据集构建管道
3. **三阶段训练**：结合CPT、SFT和RL的全面训练策略
4. **MD-GRPO方法**：利用仿真反馈的新颖闭环强化学习方法
5. **可部署系统**：用于实际部署的MDAgent2-RUNTIME
6. **第一个基准测试**：用于系统评估的MD-EvalBench

## 📑 引用

如果您觉得我们的工作对您的研究有帮助或启发，请引用：

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

## 📝 许可证

本项目遵循LICENSE文件中指定的许可证条款。

## 🙏 致谢

我们衷心感谢所有参与本研究的贡献者和机构。

