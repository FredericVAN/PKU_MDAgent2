
import re
import numpy as np
import pandas as pd

def parse_log_file(filename):
    import re
    import pandas as pd

    with open(filename, 'r') as f:
        lines = f.readlines()

    thermo_data = []
    columns = []

    for i, line in enumerate(lines):
        if re.match(r"\s*Step\s+", line):
            columns = re.findall(r"\S+", line.strip())
            for j in range(i + 1, len(lines)):
                if lines[j].strip() == "" or "Loop time" in lines[j] or not re.match(r"\s*\d+", lines[j]):
                    break
                row = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", lines[j].strip())
                if len(row) == len(columns):
                    thermo_data.append([float(x) for x in row])
            break

    if not columns or not thermo_data:
        raise ValueError("未能解析出 thermo 数据")

    df = pd.DataFrame(thermo_data, columns=columns)
    return df


def read_lammps_dump(filename):
    frames = []
    with open(filename, 'r') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        if "ITEM: TIMESTEP" in lines[i]:
            timestep = int(lines[i+1].strip())
            num_atoms = int(lines[i+3].strip())
            box_bounds = [list(map(float, lines[i+5+j].split())) for j in range(3)]
            header_line = lines[i+8].strip()
            assert header_line.startswith("ITEM: ATOMS")
            header = header_line.split()[2:]

            data_lines = lines[i+9:i+9+num_atoms]
            data = np.array([list(map(float, line.split())) for line in data_lines])

            data_dict = {key: data[:, idx] for idx, key in enumerate(header)}

            # 支持 x/y/z 或 xs/ys/zs
            if "xs" in header:
                x = data_dict["xs"] * (box_bounds[0][1] - box_bounds[0][0]) + box_bounds[0][0]
                y = data_dict["ys"] * (box_bounds[1][1] - box_bounds[1][0]) + box_bounds[1][0]
                z = data_dict["zs"] * (box_bounds[2][1] - box_bounds[2][0]) + box_bounds[2][0]
            else:
                x = data_dict.get("x", np.zeros(num_atoms))
                y = data_dict.get("y", np.zeros(num_atoms))
                z = data_dict.get("z", np.zeros(num_atoms))

            frames.append((timestep, x, y, z))
            i += 9 + num_atoms
        else:
            i += 1

    return frames