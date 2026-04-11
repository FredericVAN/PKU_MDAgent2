
import sys
import re
import pandas as pd
import matplotlib.pyplot as plt

def parse_log_file(filename):
    with open(filename, 'r') as f:
        lines = f.readlines()

    thermo_data = []
    columns = []
    for i, line in enumerate(lines):
        if re.match(r"^Step", line):
            columns = line.strip().split()
            data_start = i + 1
            for j in range(data_start, len(lines)):
                if lines[j].strip() == "" or "Loop time" in lines[j]:
                    break
                thermo_data.append([float(x) for x in lines[j].strip().split()])
            break

    if not columns or not thermo_data:
        raise ValueError("未能解析出 thermo 数据")

    df = pd.DataFrame(thermo_data, columns=columns)
    return df

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python plot_log.py log.lammps")
        sys.exit(1)

    log_file = sys.argv[1]
    df = parse_log_file(log_file)

    for col in df.columns:
        if col.lower() not in ["step"]:
            plt.plot(df["Step"], df[col], label=col)

    plt.xlabel("Timestep")
    plt.ylabel("Thermo Quantities")
    plt.legend()
    plt.title(f"Thermo data from {log_file}")
    plt.grid(True)
    plt.tight_layout()
    plt.show()
