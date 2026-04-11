# Training Dataset

This directory contains training datasets for the MDAgent2 system, organized into three main categories:

## Directory Structure

### MD-CodeGen/

Contains datasets for training code generation capabilities, specifically for generating LAMMPS input scripts.

- **codeGen_train.jsonl**: Training dataset for LAMMPS code generation
- **codeGen_valid.jsonl**: Validation dataset for LAMMPS code generation
- **example.jsonl**: Example entries showing the format of code generation tasks

Each entry includes:

- Problem description (user request for MD simulation)
- Solution (generated LAMMPS script)
- System prompts and user messages for instruction following

### MD-InstructQA/

Contains datasets for training instruction-following and question-answering capabilities in the context of molecular dynamics and materials science.

- **think_mdagent.jsonl**: Training data with reasoning/thinking process included
- **nothink_mdagent.jsonl**: Training data without explicit reasoning process
- **example.jsonl**: Example entries showing the format of QA tasks

Each entry contains conversational data with system prompts, user questions, and assistant responses, covering topics such as optimization, computational chemistry, and related interdisciplinary fields.

### MD-Knowledge/

Contains knowledge base datasets for training the system's understanding of molecular dynamics concepts and terminology.

- **cpt.jsonl**: Knowledge corpus containing MD-related text passages
- **example.jsonl**: Example entries showing the format of knowledge data

Each entry contains text passages about classical molecular dynamics simulation, interatomic potentials, and related scientific concepts.

## Data Format

All datasets use JSONL (JSON Lines) format, where each line is a valid JSON object. The specific structure varies by dataset type:

- **CodeGen**: Contains problem-solution pairs with prompt templates
- **InstructQA**: Contains multi-turn conversation messages with role-based formatting
- **Knowledge**: Contains text passages for knowledge embedding and retrieval
