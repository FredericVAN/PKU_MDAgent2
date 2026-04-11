import os
from datetime import datetime

def log_to_file(msg: str, filename: str = "lammps_log.txt"):
    """
    将日志信息写入指定文件，自动添加时间戳。
    :param msg: 日志内容
    :param filename: 日志文件名，默认为lammps_log.txt
    """
    log_dir = os.path.dirname(filename)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(filename, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {msg}\n") 