"""
Encode answer fields in MD-EvalBench benchmark files for distribution.

Only the answer-related fields are base64-encoded; all other fields remain
in plaintext so the files stay as valid JSON/JSONL for HuggingFace hosting.

This is NOT cryptographic encryption — it is an obfuscation layer to prevent
LLM crawlers from directly reading benchmark answers.  Users can run
decrypt_benchmark.py (no password needed) to restore the original fields.
"""

import json
import sys
import base64
from pathlib import Path

# ── files to process (relative to repo root) ──────────────────────────
# Each entry: (file_path, list_of_fields_to_encode)
BENCHMARK_TARGETS = [
    ("MD_Benchmark/EN/Code_Eval/LammpsCodeGenEval_sub.json",  ["standrd_code"]),
    ("MD_Benchmark/EN/QA_Eval/LAMMPS-SyntaxEval_total.jsonl",  ["answer", "answer_text"]),
    ("MD_Benchmark/EN/QA_Eval/MD-KnowledgeEval_total.jsonl",   ["answer", "answer_text"]),
    ("MD_Benchmark/ZH/Code_Eval/LammpsCodeGenEval_sub.json",  ["standrd_code"]),
    ("MD_Benchmark/ZH/QA_Eval/LAMMPS-SyntaxEval_total.jsonl",  ["answer", "answer_text"]),
    ("MD_Benchmark/ZH/QA_Eval/MD-KnowledgeEval_total.jsonl",   ["answer", "answer_text"]),
]


def encode_value(value) -> str:
    """Base64-encode a JSON-serialisable value."""
    plaintext = json.dumps(value, ensure_ascii=False).encode("utf-8")
    encoded = base64.b64encode(plaintext).decode("ascii")
    return f"{ENC_PREFIX}{encoded}"


def encode_fields_in_record(record: dict, fields: list[str]) -> dict:
    out = dict(record)
    for field in fields:
        if field in out and out[field] is not None:
            out[field] = encode_value(out[field])
    return out


def process_jsonl(filepath: Path, fields: list[str]):
    lines = filepath.read_text(encoding="utf-8").strip().splitlines()
    encoded_lines = []
    for line in lines:
        record = json.loads(line)
        encoded_lines.append(
            json.dumps(encode_fields_in_record(record, fields),
                       ensure_ascii=False)
        )
    filepath.write_text("\n".join(encoded_lines) + "\n", encoding="utf-8")
    print(f"  [OK]   {filepath}  (encoded fields: {fields})")


def process_json(filepath: Path, fields: list[str]):
    data = json.loads(filepath.read_text(encoding="utf-8"))
    encoded = [encode_fields_in_record(rec, fields) for rec in data]
    filepath.write_text(
        json.dumps(encoded, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"  [OK]   {filepath}  (encoded fields: {fields})")


def main():
    root = Path(__file__).parent

    print("\nEncoding answer fields in benchmark files...")
    for rel_path, fields in BENCHMARK_TARGETS:
        fp = root / rel_path
        if not fp.exists():
            print(f"  [SKIP] {fp} not found")
            continue
        if fp.suffix == ".jsonl":
            process_jsonl(fp, fields)
        else:
            process_json(fp, fields)

    print("\nDone. Answer fields have been base64-encoded in-place.")
    print("The files are still valid JSON/JSONL and can be pushed to HuggingFace.")
    print("Users can run 'python decrypt_benchmark.py' to decode (no password needed).")


if __name__ == "__main__":
    main()
