
import argparse
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

def read_lammps_dump(filename):
    with open(filename, 'r') as f:
        lines = f.readlines()

    frames = []
    i = 0
    while i < len(lines):
        if "ITEM: TIMESTEP" in lines[i]:
            timestep = int(lines[i+1].strip())
            num_atoms = int(lines[i+3].strip())
            box_bounds = [list(map(float, lines[i+5+j].split())) for j in range(3)]
            header = lines[i+9].strip().split()[2:]
            data = np.array([
                list(map(float, lines[i+10+k].split()))
                for k in range(num_atoms)
            ])
            i += 10 + num_atoms

            xs = data[:, header.index("xs")]
            ys = data[:, header.index("ys")]
            zs = data[:, header.index("zs")]
            x = xs * (box_bounds[0][1] - box_bounds[0][0]) + box_bounds[0][0]
            y = ys * (box_bounds[1][1] - box_bounds[1][0]) + box_bounds[1][0]
            z = zs * (box_bounds[2][1] - box_bounds[2][0]) + box_bounds[2][0]
            frames.append((timestep, x, y, z))
        else:
            i += 1
    return frames

def plot_frame(x, y, z, timestep):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    ax.scatter(x, y, z, s=10, alpha=0.6)
    ax.set_title(f"Atoms at timestep {timestep}")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    ax.set_box_aspect([1, 1, 1])
    plt.tight_layout()
    plt.show()

def save_gif(frames, filename="trajectory.gif"):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    def update(frame):
        ax.clear()
        timestep, x, y, z = frame
        ax.scatter(x, y, z, s=10, alpha=0.6)
        ax.set_title(f"Timestep {timestep}")
        ax.set_xlim([min(x), max(x)])
        ax.set_ylim([min(y), max(y)])
        ax.set_zlim([min(z), max(z)])
        ax.set_box_aspect([1, 1, 1])

    ani = FuncAnimation(fig, update, frames, interval=500)
    ani.save(filename, writer='pillow')
    print(f"已保存 gif 动画至 {filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dump_file", type=str)
    parser.add_argument("--frame", type=int, default=0, help="显示指定帧")
    parser.add_argument("--gif", action="store_true", help="是否输出 gif 动画")
    args = parser.parse_args()

    frames = read_lammps_dump(args.dump_file)
    if args.gif:
        save_gif(frames)
    else:
        timestep, x, y, z = frames[args.frame]
        plot_frame(x, y, z, timestep)
