import re
from .my_utils import parse_log_file
import numpy as np
from typing import Dict, Any, Optional, Tuple
    
def evaluate_log_quality(log_path: str) -> Dict[str, Any]:
    '''
    Evaluate the quality of a LAMMPS log file with comprehensive analysis.
    Args:
        log_path: str, path to the log file (只接受lammps的log文件)
    Returns:
        report: dict, comprehensive evaluation report
    '''
    report = {
        # 基础状态
        "finished": False,
        "timesteps": 0,
        "has_nan": False,
        "has_warning_lines": False,
        
        # 能量相关
        "energy_stable": False,
        "thermal_equilibrium": False,
        "energy_trend": None,
        
        # 温度相关
        "temperature_stable": False,
        "temperature_converged": False,
        "temperature_trend": None,
        
        # 压力相关
        "pressure_reasonable": False,
        "pressure_stable": False,
        
        # 体积/密度相关
        "volume_stable": False,
        "density_stable": False,
        
        # 动力学相关
        "kinetic_energy_stable": False,
        "potential_energy_stable": False,
        
        # 系统参数
        "dangerous_builds": None,
        "neighs_per_atom": None,
        "atoms_count": None,
        "box_dimensions": None,
        
        # 模拟类型和质量等级
        "simulation_type": None,  # "NVE" | "NVT" | "NPT" | "minimize" | "deform" | "mixed"
        "ensemble_info": {},       # 系综详细信息
        "quality_grade": None,    # "Excellent" | "Good" | "Fair" | "Poor"
        "grade_reason": "",       # 分级原因说明
        "quick_diagnostic": {},   # 快速诊断卡片
        
        # 性能信息
        "performance_info": {},
        "timing_info": {},
        
        # 诊断信息
        "warnings": [],
        "recommendations": [],
        "summary": ""
    }

    # 解析日志数据
    try:
        df = parse_log_file(log_path)
        report["timesteps"] = len(df)
    except Exception as e:
        report["summary"] = f"❌ 无法解析 thermo 数据: {e}"
        return _convert_to_strings(report)

    # 读取原始日志内容
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        report["summary"] = f"❌ 无法读取 log 文件: {e}"
        return _convert_to_strings(report)

    # 1. 基础检查：模拟完成状态
    _check_simulation_completion(content, report)
    
    # 2. 系统参数提取
    _extract_system_parameters(content, report)
    
    # 3. 模拟类型识别
    _identify_simulation_type(content, report)
    
    # 4. 能量分析（总能量、动能、势能）
    _analyze_energy_properties(df, report)
    
    # 5. 温度分析
    _analyze_temperature_properties(df, report)
    
    # 6. 压力分析
    _analyze_pressure_properties(df, report)
    
    # 7. 体积/密度分析
    _analyze_volume_density_properties(df, report)
    
    # 8. 数值稳定性检查
    _check_numerical_stability(df, content, report)
    
    # 9. 特化评估（根据模拟类型）
    sim_type = report.get("simulation_type", "unknown")
    if sim_type == "minimize":
        _evaluate_minimization_quality(df, report)
    elif sim_type == "deform":
        _evaluate_deformation_quality(df, content, report)
    
    # 10. 性能分析
    _analyze_performance(content, report)
    
    # 11. 生成诊断建议
    _generate_recommendations(report)
    
    # 12. 计算质量等级
    _calculate_quality_grade(report)
    
    # 13. 生成快速诊断卡片
    _generate_quick_diagnostic_card(report)
    
    # 14. 生成总结
    _generate_summary(report)
    
    return _convert_to_strings(report)


def _check_simulation_completion(content: str, report: Dict[str, Any]) -> None:
    """检查模拟是否正常完成"""
    if "Loop time of" in content:
        report["finished"] = True
    else:
        report["warnings"].append("未检测到模拟完成标志 (Loop time)")
        report["recommendations"].append("检查模拟是否正常结束，可能需要增加运行时间")


def _identify_simulation_type(content: str, report: Dict[str, Any]) -> None:
    """识别模拟类型"""
    simulation_types = []
    ensemble_info = {}
    
    # 检测系综类型
    nve_pattern = r'fix\s+\S+\s+\S+\s+nve'
    nvt_pattern = r'fix\s+\S+\s+\S+\s+nvt'
    npt_pattern = r'fix\s+\S+\s+\S+\s+npt'
    
    if re.search(nve_pattern, content, re.IGNORECASE):
        simulation_types.append("NVE")
        ensemble_info["NVE"] = True
    
    if re.search(nvt_pattern, content, re.IGNORECASE):
        simulation_types.append("NVT")
        # 提取NVT参数
        nvt_match = re.search(r'fix\s+\S+\s+\S+\s+nvt\s+temp\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)', content, re.IGNORECASE)
        if nvt_match:
            ensemble_info["NVT"] = {
                "temp_start": float(nvt_match.group(1)),
                "temp_end": float(nvt_match.group(2)),
                "damp": float(nvt_match.group(3))
            }
    
    if re.search(npt_pattern, content, re.IGNORECASE):
        simulation_types.append("NPT")
        # 提取NPT参数
        npt_match = re.search(r'fix\s+\S+\s+\S+\s+npt\s+temp\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)\s+iso\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)', content, re.IGNORECASE)
        if npt_match:
            ensemble_info["NPT"] = {
                "temp_start": float(npt_match.group(1)),
                "temp_end": float(npt_match.group(2)),
                "temp_damp": float(npt_match.group(3)),
                "press_start": float(npt_match.group(4)),
                "press_end": float(npt_match.group(5)),
                "press_damp": float(npt_match.group(6))
            }
    
    # 检测结构优化
    minimize_pattern = r'minimize\s+'
    if re.search(minimize_pattern, content, re.IGNORECASE):
        simulation_types.append("minimize")
        # 提取minimize参数
        min_match = re.search(r'minimize\s+([\d.e-]+)\s+([\d.e-]+)\s+(\d+)\s+(\d+)', content, re.IGNORECASE)
        if min_match:
            ensemble_info["minimize"] = {
                "etol": float(min_match.group(1)),
                "ftol": float(min_match.group(2)),
                "maxiter": int(min_match.group(3)),
                "maxeval": int(min_match.group(4))
            }
    
    # 检测形变模拟
    deform_pattern = r'fix\s+\S+\s+\S+\s+deform'
    if re.search(deform_pattern, content, re.IGNORECASE):
        simulation_types.append("deform")
        # 提取deform参数
        deform_match = re.search(r'fix\s+\S+\s+\S+\s+deform\s+(\d+)\s+(\w+)\s+([\d.-]+)\s+([\d.-]+)', content, re.IGNORECASE)
        if deform_match:
            ensemble_info["deform"] = {
                "direction": int(deform_match.group(1)),
                "style": deform_match.group(2),
                "rate": float(deform_match.group(3)),
                "final_value": float(deform_match.group(4))
            }
    
    # 检测其他特殊fix
    special_fixes = []
    shake_pattern = r'fix\s+\S+\s+\S+\s+shake'
    rigid_pattern = r'fix\s+\S+\s+\S+\s+rigid'
    
    if re.search(shake_pattern, content, re.IGNORECASE):
        special_fixes.append("shake")
    if re.search(rigid_pattern, content, re.IGNORECASE):
        special_fixes.append("rigid")
    
    if special_fixes:
        ensemble_info["special_fixes"] = special_fixes
    
    # 确定主要模拟类型
    if len(simulation_types) == 0:
        report["simulation_type"] = "unknown"
    elif len(simulation_types) == 1:
        report["simulation_type"] = simulation_types[0]
    else:
        # 多种类型，选择主要类型
        if "minimize" in simulation_types:
            report["simulation_type"] = "minimize"  # 优化优先
        elif "deform" in simulation_types:
            report["simulation_type"] = "deform"    # 形变次之
        elif "NPT" in simulation_types:
            report["simulation_type"] = "NPT"       # NPT比NVT/NVE更复杂
        else:
            report["simulation_type"] = "mixed"      # 混合类型
    
    report["ensemble_info"] = ensemble_info


def _extract_system_parameters(content: str, report: Dict[str, Any]) -> None:
    """提取系统参数"""
    # 原子数量
    atoms_match = re.search(r"(\d+)\s+atoms", content)
    if atoms_match:
        report["atoms_count"] = int(atoms_match.group(1))
    
    # 盒子尺寸
    box_match = re.search(r"xlo xhi\s+([\d.-]+)\s+([\d.-]+)", content)
    if box_match:
        xlo, xhi = float(box_match.group(1)), float(box_match.group(2))
        report["box_dimensions"] = {"x": xhi - xlo}
        
        # 尝试获取y和z维度
        y_match = re.search(r"ylo yhi\s+([\d.-]+)\s+([\d.-]+)", content)
        z_match = re.search(r"zlo zhi\s+([\d.-]+)\s+([\d.-]+)", content)
        if y_match:
            ylo, yhi = float(y_match.group(1)), float(y_match.group(2))
            report["box_dimensions"]["y"] = yhi - ylo
        if z_match:
            zlo, zhi = float(z_match.group(1)), float(z_match.group(2))
            report["box_dimensions"]["z"] = zhi - zlo


def _analyze_energy_properties(df, report: Dict[str, Any]) -> None:
    """分析能量相关属性"""
    # 总能量分析
    if "TotEng" in df.columns:
        energy = df["TotEng"].values
        if np.any(np.isnan(energy)) or np.any(np.isinf(energy)):
            report["has_nan"] = True
            report["warnings"].append("TotEng 出现 nan/inf，模拟可能发散")
        else:
            # 动态阈值调整
            threshold = _get_dynamic_threshold(len(energy), report.get("atoms_count", 1000), report.get("simulation_type", "unknown"))
            
            std_ratio = np.std(energy) / (np.abs(np.mean(energy)) + 1e-8)
            report["energy_stable"] = std_ratio < threshold
            if not report["energy_stable"]:
                report["warnings"].append(f"总能量波动较大（>{threshold*100:.1f}%）")

            # 热平衡判断（尾部能量稳定性）
            tail_size = max(3, int(len(energy) * 0.2))
            tail_energy = energy[-tail_size:]
            std_tail = np.std(tail_energy) / (np.abs(np.mean(tail_energy)) + 1e-8)
            report["thermal_equilibrium"] = std_tail < 0.05
            if not report["thermal_equilibrium"]:
                report["warnings"].append("后期能量仍有明显波动，可能尚未达到热平衡")
            
            # 能量趋势分析
            report["energy_trend"] = _analyze_trend(energy)
    else:
        report["warnings"].append("log 中不包含 TotEng 列")

    # 动能分析
    if "KinEng" in df.columns:
        kin_eng = df["KinEng"].values
        if not (np.any(np.isnan(kin_eng)) or np.any(np.isinf(kin_eng))):
            std_ratio = np.std(kin_eng) / (np.abs(np.mean(kin_eng)) + 1e-8)
            report["kinetic_energy_stable"] = std_ratio < 0.3
            if not report["kinetic_energy_stable"]:
                report["warnings"].append("动能波动较大，可能温度控制有问题")
    
    # 势能分析
    if "PotEng" in df.columns:
        pot_eng = df["PotEng"].values
        if not (np.any(np.isnan(pot_eng)) or np.any(np.isinf(pot_eng))):
            std_ratio = np.std(pot_eng) / (np.abs(np.mean(pot_eng)) + 1e-8)
            report["potential_energy_stable"] = std_ratio < 0.2
            if not report["potential_energy_stable"]:
                report["warnings"].append("势能波动较大，可能势函数参数有问题")


def _analyze_temperature_properties(df, report: Dict[str, Any]) -> None:
    """分析温度相关属性"""
    if "Temp" in df.columns:
        temp = df["Temp"].values
        if np.any(np.isnan(temp)) or np.any(np.isinf(temp)):
            report["has_nan"] = True
            report["warnings"].append("温度出现 nan/inf")
        else:
            # 温度稳定性
            std_ratio = np.std(temp) / (np.mean(temp) + 1e-8)
            report["temperature_stable"] = std_ratio < 0.3
            if not report["temperature_stable"]:
                report["warnings"].append("温度波动较大（>30%）")

            # 温度收敛判断
            final_temp = temp[-1]
            init_temp = temp[0]
            temp_change_ratio = abs(final_temp - init_temp) / (init_temp + 1e-8)
            report["temperature_converged"] = temp_change_ratio < 0.1
            if not report["temperature_converged"]:
                report["warnings"].append(f"温度未收敛（初值 {init_temp:.2f} → 末值 {final_temp:.2f}）")
            
            # 温度趋势分析
            report["temperature_trend"] = _analyze_trend(temp)
            
            # 温度合理性检查
            if final_temp < 0:
                report["warnings"].append("温度出现负值，物理上不合理")
            elif final_temp > 10000:  # 10K K
                report["warnings"].append("温度过高，可能数值不稳定")
    else:
        report["warnings"].append("log 中不包含 Temp 列")


def _analyze_pressure_properties(df, report: Dict[str, Any]) -> None:
    """分析压力相关属性"""
    if "Press" in df.columns:
        press = df["Press"].values
        if np.any(np.isnan(press)) or np.any(np.isinf(press)):
            report["has_nan"] = True
            report["warnings"].append("压力出现 nan/inf")
        else:
            # 压力合理性
            max_press = np.max(np.abs(press))
            report["pressure_reasonable"] = max_press < 1e6
            if not report["pressure_reasonable"]:
                report["warnings"].append(f"压力超过 ±1e6（最大 {max_press:.2e}），数值可能不稳定")
            
            # 压力稳定性
            std_ratio = np.std(press) / (np.abs(np.mean(press)) + 1e-8)
            report["pressure_stable"] = std_ratio < 0.5
            if not report["pressure_stable"]:
                report["warnings"].append("压力波动较大，可能系统未达到力学平衡")
    else:
        report["warnings"].append("log 中不包含 Press 列")


def _analyze_volume_density_properties(df, report: Dict[str, Any]) -> None:
    """分析体积和密度相关属性"""
    # 体积分析
    if "Volume" in df.columns:
        volume = df["Volume"].values
        if not (np.any(np.isnan(volume)) or np.any(np.isinf(volume))):
            std_ratio = np.std(volume) / np.mean(volume)
            report["volume_stable"] = std_ratio < 0.1
            if not report["volume_stable"]:
                report["warnings"].append("体积波动较大，可能系统未达到力学平衡")
            
            # 体积合理性检查
            if np.any(volume <= 0):
                report["warnings"].append("体积出现非正值，物理上不合理")
    
    # 密度分析（如果有原子数信息）
    if "Volume" in df.columns and report.get("atoms_count"):
        volume = df["Volume"].values
        density = report["atoms_count"] / volume
        if not (np.any(np.isnan(density)) or np.any(np.isinf(density))):
            std_ratio = np.std(density) / np.mean(density)
            report["density_stable"] = std_ratio < 0.1
            if not report["density_stable"]:
                report["warnings"].append("密度波动较大")


def _check_numerical_stability(df, content: str, report: Dict[str, Any]) -> None:
    """检查数值稳定性"""
    # Dangerous builds
    match = re.search(r"Dangerous builds\s+=\s+(\d+)", content)
    if match:
        db = int(match.group(1))
        report["dangerous_builds"] = db
        if db > 0:
            report["warnings"].append(f"Dangerous builds = {db}，可能邻居表不稳定")
            report["recommendations"].append("考虑调整 neighbor 命令参数或减小时间步长")
    
    # neighs/atom
    match = re.search(r"Ave neighs/atom\s+=\s+([\d.]+)", content)
    if match:
        neighs = float(match.group(1))
        report["neighs_per_atom"] = neighs
        if neighs < 3:
            report["warnings"].append(f"平均邻居数为 {neighs}，可能过少")
            report["recommendations"].append("检查势函数截断半径设置")
        elif neighs > 200:
            report["warnings"].append(f"平均邻居数为 {neighs}，可能过多")
            report["recommendations"].append("考虑减小势函数截断半径以提高效率")
    
    # 检测Lost atoms
    lost_atoms_match = re.search(r"Lost atoms:\s+(\d+)", content)
    if lost_atoms_match:
        lost_count = int(lost_atoms_match.group(1))
        report["warnings"].append(f"Lost atoms: {lost_count}，原子丢失")
        report["recommendations"].append("检查边界条件设置或减小时间步长")
    
    # 检测Bond atoms missing
    if "Bond atoms missing" in content:
        report["warnings"].append("Bond atoms missing，键连原子缺失")
        report["recommendations"].append("检查分子结构或键连设置")
    
    # 检测Out of range atoms
    if "Out of range atoms" in content:
        report["warnings"].append("Out of range atoms，原子超出范围")
        report["recommendations"].append("检查盒子尺寸或边界条件")
    
    # 统计ERROR和WARNING数量
    error_count = len(re.findall(r"ERROR", content, re.IGNORECASE))
    warning_count = len(re.findall(r"WARNING", content, re.IGNORECASE))
    
    if error_count > 0:
        report["warnings"].append(f"检测到 {error_count} 个ERROR，请检查具体内容")
    if warning_count > 0:
        report["has_warning_lines"] = True
        report["warnings"].append(f"检测到 {warning_count} 个WARNING，请注意数值稳定性或参数设置")


def _analyze_performance(content: str, report: Dict[str, Any]) -> None:
    """分析性能信息"""
    # 性能摘要
    perf_match = re.search(r"Performance:\s+([^\n]+)", content)
    if perf_match:
        report["performance_info"]["summary"] = perf_match.group(1).strip()

    # 时间信息
    loop_time_match = re.search(r"Loop time of\s+([\d.]+)\s+on\s+(\d+)\s+procs", content)
    if loop_time_match:
        loop_time = float(loop_time_match.group(1))
        num_procs = int(loop_time_match.group(2))
        report["timing_info"]["loop_time"] = loop_time
        report["timing_info"]["num_procs"] = num_procs
        report["timing_info"]["time_per_proc"] = loop_time / num_procs if num_procs > 0 else loop_time
    
    # 原子/秒性能
    atoms_per_sec_match = re.search(r"([\d.]+)\s+atoms/sec", content)
    if atoms_per_sec_match:
        atoms_per_sec = float(atoms_per_sec_match.group(1))
        report["performance_info"]["atoms_per_second"] = atoms_per_sec


def _generate_recommendations(report: Dict[str, Any]) -> None:
    """生成改进建议"""
    if not report["finished"]:
        report["recommendations"].append("增加模拟运行时间或检查输入脚本")
    
    if not report["thermal_equilibrium"]:
        report["recommendations"].append("延长平衡时间或调整温度控制参数")
    
    if not report["temperature_converged"]:
        report["recommendations"].append("检查初始温度设置和温度控制算法")
    
    if report["dangerous_builds"] and report["dangerous_builds"] > 0:
        report["recommendations"].append("调整 neighbor 命令的 skin 参数")
    
    if report.get("neighs_per_atom", 0) > 200:
        report["recommendations"].append("考虑减小势函数截断半径以提高计算效率")


def _calculate_quality_grade(report: Dict[str, Any]) -> None:
    """计算质量等级"""
    grade = "Poor"
    reasons = []
    
    # 基础检查
    if not report["finished"]:
        reasons.append("模拟未完成")
        report["quality_grade"] = "Poor"
        report["grade_reason"] = "；".join(reasons)
        return
    
    if report["has_nan"]:
        reasons.append("存在NaN值")
        report["quality_grade"] = "Poor"
        report["grade_reason"] = "；".join(reasons)
        return
    
    # 优秀等级检查
    excellent_conditions = [
        report["energy_stable"],
        report["temperature_stable"],
        report["thermal_equilibrium"],
        report["temperature_converged"],
        report["pressure_reasonable"],
        report["dangerous_builds"] == 0 or report["dangerous_builds"] is None,
        len(report["warnings"]) == 0
    ]
    
    if all(excellent_conditions):
        grade = "Excellent"
        reasons.append("所有指标均达到优秀标准")
    else:
        # 良好等级检查
        good_conditions = [
            report["energy_stable"] or report["temperature_stable"],
            len(report["warnings"]) <= 2
        ]
        
        if all(good_conditions):
            grade = "Good"
            reasons.append("主要指标良好，警告较少")
        else:
            # 一般等级检查
            fair_conditions = [
                len(report["warnings"]) <= 5
            ]
            
            if all(fair_conditions):
                grade = "Fair"
                reasons.append("基本完成，存在一些警告")
            else:
                grade = "Poor"
                reasons.append("存在较多问题")
    
    # 根据模拟类型调整等级
    sim_type = report.get("simulation_type", "unknown")
    if sim_type == "minimize":
        # 结构优化不要求温度稳定
        if grade == "Poor" and not report["has_nan"] and report["finished"]:
            if report["energy_stable"] or len(report["warnings"]) <= 3:
                grade = "Fair"
                reasons.append("结构优化模拟，放宽温度要求")
    
    elif sim_type == "NPT":
        # NPT允许体积波动
        if grade == "Poor" and not report["has_nan"] and report["finished"]:
            if report["pressure_reasonable"] and len(report["warnings"]) <= 4:
                grade = "Fair"
                reasons.append("NPT模拟，允许体积波动")
    
    report["quality_grade"] = grade
    report["grade_reason"] = "；".join(reasons)


def _generate_quick_diagnostic_card(report: Dict[str, Any]) -> None:
    """生成快速诊断卡片"""
    diagnostic = {}
    
    # 状态
    if report["finished"]:
        diagnostic["status"] = "✅完成"
    else:
        diagnostic["status"] = "❌未完成"
    
    # 稳定性
    if report["energy_stable"] and report["temperature_stable"]:
        diagnostic["stability"] = "✅稳定"
    elif report["energy_stable"] or report["temperature_stable"]:
        diagnostic["stability"] = "⚠️部分稳定"
    else:
        diagnostic["stability"] = "❌不稳定"
    
    # 错误状态
    if report["has_nan"]:
        diagnostic["errors"] = "❌NaN检测到"
    elif "Lost atoms" in str(report["warnings"]):
        diagnostic["errors"] = "❌Lost atoms"
    elif len(report["warnings"]) > 0:
        diagnostic["errors"] = f"⚠️{len(report['warnings'])}个警告"
    else:
        diagnostic["errors"] = "✅无错误"
    
    # 质量等级
    grade_map = {
        "Excellent": "优秀",
        "Good": "良好", 
        "Fair": "一般",
        "Poor": "差"
    }
    diagnostic["grade"] = grade_map.get(report["quality_grade"], "未知")
    
    # 关键指标
    key_metrics = {}
    
    if report.get("energy_trend"):
        key_metrics["能量趋势"] = report["energy_trend"]
    
    if report.get("temperature_trend"):
        key_metrics["温度趋势"] = report["temperature_trend"]
    
    if report.get("timesteps", 0) > 0:
        key_metrics["时间步数"] = f"{report['timesteps']}"
    
    if report.get("atoms_count"):
        key_metrics["原子数"] = f"{report['atoms_count']}"
    
    if report.get("dangerous_builds") is not None:
        key_metrics["Dangerous builds"] = f"{report['dangerous_builds']}"
    
    diagnostic["key_metrics"] = key_metrics
    
    report["quick_diagnostic"] = diagnostic


def _generate_summary(report: Dict[str, Any]) -> None:
    """生成总结"""
    sim_type = report.get("simulation_type", "unknown")
    grade = report.get("quality_grade", "Poor")
    
    if grade == "Excellent":
        report["summary"] = f"✅ {sim_type}模拟完成，质量优秀：{report.get('grade_reason', '')}"
    elif grade == "Good":
        report["summary"] = f"✅ {sim_type}模拟完成，质量良好：{report.get('grade_reason', '')}"
    elif grade == "Fair":
        report["summary"] = f"⚠️ {sim_type}模拟完成，质量一般：{report.get('grade_reason', '')}"
    else:
        warning_count = len(report["warnings"])
        if warning_count > 0:
            report["summary"] = f"❌ {sim_type}模拟存在问题：{report.get('grade_reason', '')}；警告：{';'.join(report['warnings'][:3])}"
            if warning_count > 3:
                report["summary"] += f" 等共{warning_count}个问题"
        else:
            report["summary"] = f"❌ {sim_type}模拟存在问题：{report.get('grade_reason', '')}"


def _get_dynamic_threshold(timesteps: int, atoms_count: int, simulation_type: str = "unknown") -> float:
    """根据系统大小、时间步数和模拟类型动态调整阈值"""
    base_threshold = 0.2
    
    # 根据模拟类型调整
    if simulation_type == "minimize":
        base_threshold *= 0.5  # 结构优化要求更严格
    elif simulation_type == "NPT":
        base_threshold *= 1.2  # NPT允许更大波动
    elif simulation_type == "deform":
        base_threshold *= 1.5  # 形变模拟允许更大波动
    elif simulation_type == "NVE":
        base_threshold *= 0.8  # NVE要求较严格
    
    # 根据原子数调整
    if atoms_count < 100:
        base_threshold *= 1.5  # 小系统允许更大波动
    elif atoms_count > 10000:
        base_threshold *= 0.7  # 大系统要求更严格
    
    # 根据时间步数调整
    if timesteps < 1000:
        base_threshold *= 1.3  # 短时间模拟允许更大波动
    elif timesteps > 10000:
        base_threshold *= 0.8  # 长时间模拟要求更严格
    
    return min(base_threshold, 0.5)  # 最大不超过50%


def _analyze_trend(data: np.ndarray) -> str:
    """分析数据趋势"""
    if len(data) < 10:
        return "数据点不足，无法分析趋势"
    
    # 计算线性趋势
    x = np.arange(len(data))
    coeffs = np.polyfit(x, data, 1)
    slope = coeffs[0]
    
    # 计算趋势强度
    trend_strength = abs(slope) / (np.std(data) + 1e-8)
    
    # 检测周期性（简单的自相关检测）
    if len(data) > 20:
        # 计算自相关
        autocorr = np.correlate(data - np.mean(data), data - np.mean(data), mode='full')
        autocorr = autocorr[autocorr.size // 2:]
        autocorr = autocorr / autocorr[0]
        
        # 寻找周期性峰值
        peaks = []
        for i in range(1, min(len(autocorr), len(data)//4)):
            if autocorr[i] > 0.3 and autocorr[i] > autocorr[i-1] and autocorr[i] > autocorr[i+1]:
                peaks.append(i)
        
        if peaks:
            period = min(peaks)
            return f"周期性振荡（周期≈{period}步，强度: {trend_strength:.2f}）"
    
    # 检测突变点（简单的梯度变化检测）
    if len(data) > 10:
        gradients = np.diff(data)
        gradient_changes = np.abs(np.diff(gradients))
        max_change_idx = np.argmax(gradient_changes)
        
        if gradient_changes[max_change_idx] > 2 * np.std(gradient_changes):
            return f"存在突变点（第{max_change_idx}步，强度: {trend_strength:.2f}）"
    
    # 基本趋势判断
    if trend_strength < 0.1:
        return "稳定"
    elif slope > 0:
        return f"上升趋势（强度: {trend_strength:.2f}）"
    else:
        return f"下降趋势（强度: {trend_strength:.2f}）"


def _evaluate_minimization_quality(df, report: Dict[str, Any]) -> None:
    """评估结构优化质量"""
    if "TotEng" not in df.columns:
        return
    
    energy = df["TotEng"].values
    if len(energy) < 2:
        return
    
    # 检查能量是否单调下降
    energy_diff = np.diff(energy)
    decreasing_steps = np.sum(energy_diff < 0)
    total_steps = len(energy_diff)
    
    if decreasing_steps / total_steps > 0.8:
        report["warnings"].append("结构优化：能量单调下降良好")
    elif decreasing_steps / total_steps < 0.5:
        report["warnings"].append("结构优化：能量下降不充分，可能未收敛")
    
    # 检查最终能量稳定性
    if len(energy) > 10:
        final_energy = energy[-10:]
        energy_std = np.std(final_energy)
        energy_mean = np.abs(np.mean(final_energy))
        
        if energy_std / (energy_mean + 1e-8) < 0.01:
            report["warnings"].append("结构优化：最终能量非常稳定")
        elif energy_std / (energy_mean + 1e-8) > 0.1:
            report["warnings"].append("结构优化：最终能量波动较大，可能未完全收敛")


def _evaluate_deformation_quality(df, content: str, report: Dict[str, Any]) -> None:
    """评估形变模拟质量"""
    # 形变模拟允许体积变化
    if "Volume" in df.columns:
        volume = df["Volume"].values
        if len(volume) > 1:
            volume_change = (volume[-1] - volume[0]) / volume[0]
            if abs(volume_change) > 0.5:  # 体积变化超过50%
                report["warnings"].append(f"形变模拟：体积变化 {volume_change*100:.1f}%，检查是否合理")
    
    # 检查应力-应变关系
    if "Press" in df.columns and "Volume" in df.columns:
        press = df["Press"].values
        volume = df["Volume"].values
        
        # 简单的应力-应变相关性检查
        if len(press) > 10 and len(volume) > 10:
            correlation = np.corrcoef(press, volume)[0, 1]
            if abs(correlation) > 0.7:
                report["warnings"].append("形变模拟：压力-体积相关性良好")
            elif abs(correlation) < 0.3:
                report["warnings"].append("形变模拟：压力-体积相关性较弱，检查形变设置")


def _detect_simulation_phases(df) -> Dict[str, Any]:
    """检测模拟阶段"""
    phases = {}
    
    if len(df) < 20:
        return phases
    
    # 简单的阶段检测：基于能量变化
    if "TotEng" in df.columns:
        energy = df["TotEng"].values
        
        # 寻找能量变化最小的区域（平衡阶段）
        window_size = max(10, len(energy) // 10)
        min_variance_idx = 0
        min_variance = float('inf')
        
        for i in range(len(energy) - window_size):
            window_energy = energy[i:i+window_size]
            variance = np.var(window_energy)
            if variance < min_variance:
                min_variance = variance
                min_variance_idx = i
        
        # 如果最小方差区域在后期，认为是平衡阶段
        if min_variance_idx > len(energy) * 0.5:
            phases["equilibration_end"] = min_variance_idx
            phases["production_start"] = min_variance_idx
    
    return phases


def _convert_to_strings(report: Dict[str, Any]) -> Dict[str, str]:
    """将所有值转换为字符串"""
    result = {}
    for key, value in report.items():
        if isinstance(value, dict):
            result[key] = str(value)
        elif isinstance(value, list):
            result[key] = str(value)
        else:
            result[key] = str(value)
    return result

