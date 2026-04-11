"""
Decode answer fields in MD-EvalBench benchmark files.
User-facing script: restores base64-encoded answer fields back to plaintext.

Usage:  python decrypt_benchmark.py
  (no password needed)
"""

import json
import sys
import base64
from pathlib import Path

# ── files to process (relative to repo root) ──────────────────────────
# Each entry: (file_path, list_of_fields_to_decode)
BENCHMARK_TARGETS = [
    ("MD_Benchmark/EN/Code_Eval/LammpsCodeGenEval_sub.json",  ["standrd_code"]),
    ("MD_Benchmark/EN/QA_Eval/LAMMPS-SyntaxEval_total.jsonl",  ["answer", "answer_text"]),
    ("MD_Benchmark/EN/QA_Eval/MD-KnowledgeEval_total.jsonl",   ["answer", "answer_text"]),
    ("MD_Benchmark/ZH/Code_Eval/LammpsCodeGenEval_sub.json",  ["standrd_code"]),
    ("MD_Benchmark/ZH/QA_Eval/LAMMPS-SyntaxEval_total.jsonl",  ["answer", "answer_text"]),
    ("MD_Benchmark/ZH/QA_Eval/MD-KnowledgeEval_total.jsonl",   ["answer", "answer_text"]),
]

ENC_PREFIX = "BASE64:"


def decode_value(enc_str):
    """Decode a 'BASE64:<data>' string and return the original JSON value."""
    if not isinstance(enc_str, str) or not enc_str.startswith(ENC_PREFIX):
        return enc_str  # not encoded, return as-is
    raw = base64.b64decode(enc_str[len(ENC_PREFIX):])
    return json.loads(raw.decode("utf-8"))


def decode_fields_in_record(record: dict, fields: list[str]) -> dict:
    out = dict(record)
    for field in fields:
        if field in out and out[field] is not None:
            out[field] = decode_value(out[field])
    return out


def process_jsonl(filepath: Path, fields: list[str]):
    lines = filepath.read_text(encoding="utf-8").strip().splitlines()
    decoded_lines = []
    for line in lines:
        record = json.loads(line)
        decoded_lines.append(
            json.dumps(decode_fields_in_record(record, fields),
                       ensure_ascii=False)
        )
    filepath.write_text("\n".join(decoded_lines) + "\n", encoding="utf-8")
    print(f"  [OK]   {filepath}  (decoded fields: {fields})")


def process_json(filepath: Path, fields: list[str]):
    data = json.loads(filepath.read_text(encoding="utf-8"))
    decoded = [decode_fields_in_record(rec, fields) for rec in data]
    filepath.write_text(
        json.dumps(decoded, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"  [OK]   {filepath}  (decoded fields: {fields})")


def main():
    root = Path(__file__).parent

    print("\nDecoding answer fields in benchmark files...")
    for rel_path, fields in BENCHMARK_TARGETS:
        fp = root / rel_path
        if not fp.exists():
            print(f"  [SKIP] {fp} not found")
            continue
        if fp.suffix == ".jsonl":
            process_jsonl(fp, fields)
        else:
            process_json(fp, fields)

    print("\nDone. Answer fields have been decoded in-place.")


if __name__ == "__main__":
    main()
