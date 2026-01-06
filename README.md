
# IoDResearch: Deep Research on Private Heterogeneous Data via the Internet of Data

<p align="center">
  <img src="./assets/IoDResearch-total-1.png" alt="logo" width="100%"/>
</p>

`<a href="https://arxiv.org/pdf/2510.01553">`![arXiv](https://img.shields.io/badge/arXiv-2510.01553-b31b1b) `</a>`
`<a href="https://huggingface.co/collections/FredericFan/iodresearch">`![Datasets](https://img.shields.io/badge/Hugging%20Face-FFD21E?logo=huggingface&logoColor=white) `</a>`
`<a href="https://fredericvan.github.io/PKU_IoDResearch/">`![website](https://img.shields.io/badge/website-PKU_IoDResearch-blue) `</a>`

> **Note:** Code and Datasets will be released upon paper acceptance.

## 💡 Introduction

- We propose **IoDResearch** (Internet of Data Research), a **private data-centric** Deep Research framework that operationalizes the Internet of Data paradigm for heterogeneous scientific data.
- IoDResearch encapsulates heterogeneous resources as **FAIR-compliant digital objects**, and further refines them into atomic knowledge units and knowledge graphs, forming a heterogeneous graph index for multi-granularity retrieval.
- We establish a **multi-agent system** that supports both reliable question answering and structured scientific report generation on top of the heterogeneous graph representation.
- We establish the **IoD DeepResearch Benchmark** to systematically evaluate both data representation and Deep Research capabilities in IoD scenarios. Experimental results show that IoDResearch consistently surpasses representative RAG and Deep Research baselines.

## Benchmark

**IoD DeepResearch Benchmark** is established to systematically evaluate both data representation and Deep Research capabilities in IoD scenarios. The benchmark includes:

- **Retrieval tasks**: Multi-granularity retrieval on heterogeneous graph index
- **Question Answering (QA) tasks**: Reliable question answering on private heterogeneous data
- **Report Writing tasks**: Structured scientific report generation

Experimental results on retrieval, QA, and report-writing tasks show that IoDResearch consistently surpasses representative RAG and Deep Research baselines.

## 🚀 Performance

<p align="center">
  <img src="assets\ScreenShot_2025-12-16_103550_864.png" alt="logo" width="80%"/>
</p>
<p align="center">
  <img src="assets\ScreenShot_2025-12-16_103500_066.png" alt="logo" width="80%"/>
</p>
<p align="center">
  <img src="assets\ScreenShot_2025-12-16_103510_951.png" alt="logo" width="80%"/>
</p>

## 🔍 IoDResearch Features

### FAIR-Compliant Data Representation

<p align="center">
  <img src="./assets\IoDRearch-EN-threeLayer-202508.drawio-1.png" alt="logo" width="80%"/>
</p>

IoDResearch encapsulates heterogeneous resources as **FAIR-compliant digital objects**, ensuring Findability, Accessibility, Interoperability, and Reusability of scientific data. These digital objects are further refined into:

- **Atomic knowledge units**: Fine-grained knowledge representation for precise retrieval
- **Knowledge graphs**: Structured representation of relationships between entities
- **Heterogeneous graph index**: Multi-granularity retrieval infrastructure

<p align="center">
  <img src="assets\IoDResearch-EN-example-202508.drawio-1.png" alt="logo" width="80%"/>
</p>

### Multi-Agent System

<p align="center">
  <img src="assets\IoDResearch-EN-MultiAgents-202508.drawio-1.png" alt="logo" width="80%"/>
</p>

On top of the heterogeneous graph representation, IoDResearch employs a multi-agent system that supports:

- **Reliable Question Answering**: Accurate QA on private heterogeneous data
- **Structured Scientific Report Generation**: Automated generation of well-structured research reports

### Internet of Data Paradigm

IoDResearch operationalizes the Internet of Data paradigm, enabling:

- **Private data-centric Deep Research**: Focus on local private data rather than web search
- **Heterogeneous data integration**: Unified representation of multi-source, multimodal scientific data
- **Trustworthy and reusable scientific discovery**: FAIR principles compliance for better data management

## 📑 Citation

If this work is helpful, please kindly cite as:

```bibtex
@misc{shi2025iodresearchdeepresearchprivate,
      title={IoDResearch: Deep Research on Private Heterogeneous Data via the Internet of Data}, 
      author={Zhuofan Shi and Zijie Guo and Xinjian Ma and Gang Huang and Yun Ma and Xiang Jing},
      year={2025},
      eprint={2510.01553},
      archivePrefix={arXiv},
      primaryClass={cs.IR},
      url={https://arxiv.org/abs/2510.01553}, 
}
```
