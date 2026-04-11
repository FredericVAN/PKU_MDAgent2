from utils.lammps_vis_eval_utils import lammps_evaluator_api, lammps_visualizer_api

def evaluate_log_quality_tool(log_path: str):
    """
    评估log文件的质量
    """
    return lammps_evaluator_api.evaluate_log_quality(log_path)

def auto_visualize_eval_lammps_files(folder_path: str):
    """
    自动可视化文件夹中的LAMMPS文件
    
    Args:
        folder_path (str): 文件夹路径
    """
    import os
    
    # 检查文件夹是否存在
    if not os.path.exists(folder_path):
        print(f"错误：文件夹 {folder_path} 不存在")
        return
    
    if not os.path.isdir(folder_path):
        print(f"错误：{folder_path} 不是一个文件夹")
        return
    
    # 遍历文件夹中的所有文件
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        
        # 检查是否为文件
        if not os.path.isfile(file_path):
            continue
            
        try:
            # 处理 log.lammps 文件
            if filename == "log.lammps":
                print(f"正在处理 log.lammps 文件: {file_path}")
                lammps_visualizer_api.save_thermo_curves(file_path)
                print(f"✅ 已保存 log.lammps 热力学曲线图")
                
                # 同时进行质量评估
                report = lammps_evaluator_api.evaluate_log_quality(file_path)
                print(f"📊 评估结果: {report['summary']}")
                
            # 处理 dump.lammpstrj 文件
            elif filename == "dump.lammpstrj":
                print(f"正在处理 dump.lammpstrj 文件: {file_path}")
                lammps_visualizer_api.save_dump_as_gif(file_path)
                print(f"✅ 已保存 dump.lammpstrj 动画文件")
                
        except Exception as e:
            print(f"❌ 处理文件 {filename} 时出错: {str(e)}")
            continue
    
    print("🎉 文件夹可视化处理完成！")