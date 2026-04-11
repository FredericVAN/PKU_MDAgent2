
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.animation import FuncAnimation
from .my_utils import parse_log_file, read_lammps_dump
import os
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

def save_thermo_curves(log_file):
    df = parse_log_file(log_file)
    for col in df.columns:
        if col.lower() != "step":
            plt.plot(df["Step"], df[col], label=col)
    plt.xlabel("Timestep")
    plt.ylabel("Thermo Quantities")
    plt.legend()
    plt.title(f"Thermo data from {log_file}")
    plt.grid(True)
    plt.tight_layout()
    # 生成保存路径
    dir_path = os.path.dirname(os.path.abspath(log_file))
    base_name = os.path.splitext(os.path.basename(log_file))[0]
    save_path = os.path.join(dir_path, f"{base_name}_thermo.png")
    plt.savefig(save_path, dpi=150)
    plt.close()
    return save_path

def plot_thermo_curves(log_file):
    df = parse_log_file(log_file)
    for col in df.columns:
        if col.lower() != "step":
            plt.plot(df["Step"], df[col], label=col)
    plt.xlabel("Timestep")
    plt.ylabel("Thermo Quantities")
    plt.legend()
    plt.title(f"Thermo data from {log_file}")
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def plot_dump_frame(dump_file, frame_index=0):
    frames = read_lammps_dump(dump_file)
    timestep, x, y, z = frames[frame_index]
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


def save_dump_as_gif(dump_file, interval=None, dpi=100):
    frames = read_lammps_dump(dump_file)
    num_frames = len(frames)

    if num_frames == 0:
        print("❌ dump 文件无帧内容，无法生成 GIF。请确认 dump.lammpstrj 格式或模拟是否成功。")
        return None

    # 自动计算合理 interval（保证播放时间 5~10 秒）
    if interval is None or interval <= 0:
        target_duration_sec = 6
        try:
            interval = int((target_duration_sec * 1000) / num_frames)
            interval = max(50, interval)
        except ZeroDivisionError:
            interval = 200  # 安全兜底值

    fps = max(1, 1000 // interval)  # 避免 fps = 0

    # 自动生成 gif 路径
    dump_dir = os.path.dirname(dump_file)
    dump_name = os.path.splitext(os.path.basename(dump_file))[0]
    gif_path = os.path.join(dump_dir, dump_name + ".gif")

    print(f"🎞️ 共 {num_frames} 帧，将以 {fps} FPS 保存 GIF，输出路径：{gif_path}")

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    def update(frame):
        timestep, x, y, z = frame
        ax.clear()
        ax.set_title(f"Timestep {timestep}")
        ax.scatter(x, y, z, s=10)
        return ax,

    ani = FuncAnimation(fig, update, frames=frames, blit=False, interval=interval)
    ani.save(gif_path, writer=PillowWriter(fps=fps), dpi=dpi)
    plt.close()

    gif_path = os.path.abspath(gif_path)
    print(f"✅ GIF 已保存到: {gif_path}")
    return gif_path