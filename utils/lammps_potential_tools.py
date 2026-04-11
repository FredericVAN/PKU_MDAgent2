"""
LAMMPS势函数检查工具 - LangGraph Tool
为LangGraph提供势函数检查和下载功能
"""

from typing import Dict, Any, List, Optional
from utils.lammps_potential_utils.lammps_potential_api import (
    check_lammps_potentials, 
    get_potential_info,
    find_similar_potentials,
    get_potential_extensions,
    check_lammps_potential_files
)
from pathlib import Path

def check_lammps_potential_files_tool( potential_files: List[str], top_k: int = 10) -> Dict[str, any]:
        """
        检查势函数文件是否存在,如果有不存在的文件则需要推荐相似的势函数文件
        
        Args:
            potential_files: 势函数文件名列表('potentials/Al99.eam.alloy' 或者 'Al99.eam.alloy')
            top_k: 推荐相似的势函数文件数量，默认为10
            
        Returns:
            Dict[str, any]: 包含检查结果的字典
                - status: "success" 或 "error"
                - summary: 检查摘要
                - details: 每个文件的检查详情
                - all_ready: 是否所有文件都存在
                - message: 用户友好的消息
                - recommendations: 不存在的文件的推荐信息
        """
        try:
            result = check_lammps_potential_files(potential_files, top_k=top_k)
            return result
        except Exception as e:
            return {
                "status": "error",
                "summary": f"势函数文件检查失败: {str(e)}",
                "details": {},
                "all_ready": False,
                "message": f"势函数文件检查工具出错: {str(e)}"
            }
def check_lammps_potentials_tool(lammps_code: str, top_k: int = 10) -> Dict[str, Any]:
    """
    检查LAMMPS代码中的势函数依赖，尝试下载确实的文件，如果下载失败，则推荐相似的势函数文件。
    
    Args:
        lammps_code: LAMMPS输入脚本内容
        top_k: 推荐相似的势函数文件数量，默认为10
        
    Returns:
        Dict[str, any]: 包含检查结果的字典
                - status: "success" 或 "error"
                - summary: 检查摘要
                - details: 每个文件的检查详情
                - all_ready: 是否所有文件都存在
                - message: 用户友好的消息
                - recommendations: 不存在的文件的推荐信息
                - existing_files: 成功获取的文件列表
                - failed_files: 失败的文件列表
    """
    try:
        result = check_lammps_potentials(lammps_code, top_k=top_k)
        return result
    except Exception as e:
        return {
            "status": "error",
            "summary": f"势函数检查失败: {str(e)}",
            "details": {},
            "all_ready": False,
            "message": f"势函数检查工具出错: {str(e)}"
        }


def get_potential_file_info_tool(filename: str) -> Dict[str, Any]:
    """
    获取指定势函数文件的详细信息。
    
    Args:
        filename (str): 势函数文件名（如 "Al99.eam.alloy"）
        
    Returns:
        Dict[str, Any]: 文件信息字典
        - filename: 文件名
        - exists_locally: 本地是否存在
        - local_path: 本地路径
        - has_md5: 是否有MD5校验值
        - md5_value: MD5值
        - file_size: 文件大小（bytes，仅当文件存在时）
        - is_valid: 文件是否有效（仅当文件存在时）
        
    Example:
        ```python
        info = get_potential_file_info_tool("Al99.eam.alloy")
        print(f"文件存在: {info['exists_locally']}")
        ```
    """
    try:
        info = get_potential_info(filename)
        return info
    except Exception as e:
        return {
            "filename": filename,
            "exists_locally": False,
            "local_path": "",
            "has_md5": False,
            "md5_value": "unknown",
            "error": str(e)
        }



def list_available_potentials_tool() -> Dict[str, Any]:
    """
    列出本地可用的势函数文件。
    
    Returns:
        Dict[str, Any]: 可用势函数文件列表
        - available_files: 本地存在的势函数文件列表
        - total_count: 总文件数
        - file_types: 按类型分组的文件统计
        - message: 消息
        
    """
    try:
        potentials_dir = Path("potentials")
        if not potentials_dir.exists():
            return {
                "available_files": [],
                "total_count": 0,
                "file_types": {},
                "message": "potentials目录不存在"
            }
        
        # 从API获取势函数文件扩展名（统一数据源）
        potential_extensions = get_potential_extensions()
        
        available_files = []
        file_types = {}
        
        for file_path in potentials_dir.iterdir():
            if file_path.is_file():
                filename = file_path.name
                ext = file_path.suffix.lower()
                
                # 检查是否是势函数文件
                if ext in potential_extensions or any(filename.endswith(e) for e in potential_extensions):
                    available_files.append(filename)
                    
                    # 统计文件类型
                    if ext in file_types:
                        file_types[ext] += 1
                    else:
                        file_types[ext] = 1
        
        return {
            "available_files": sorted(available_files),
            "total_count": len(available_files),
            "file_types": file_types,
            "message": f"找到 {len(available_files)} 个势函数文件"
        }
        
    except Exception as e:
        return {
            "available_files": [],
            "total_count": 0,
            "file_types": {},
            "error": str(e),
            "message": f"列出势函数文件时出错: {str(e)}"
        }



def find_similar_potentials_tool(query_name: str, top_k: int = 10) -> Dict[str, Any]:
    """
    根据势函数名称（可能错误）在本地potentials文件夹中查找最相似的势函数。
    
    这个工具使用多种相似度算法来匹配势函数名称，包括：
    - 字符串编辑距离相似度
    - 元素符号匹配
    - 数字匹配
    - 包含关系检查
    
    Args:
        query_name (str): 要搜索的势函数名称（可能包含拼写错误）
        top_k (int): 返回最相关的前k个结果，默认为10
        
    Returns:
        Dict[str, Any]: 搜索结果字典
        - similar_potentials: 按相似度排序的势函数列表
        - total_found: 找到的相关势函数总数
        - query_name: 原始查询名称
        - message: 用户友好的消息
        
    Example:
        ```python
        result = find_similar_potentials_tool("Al99.eam")
        print(f"找到 {len(result['similar_potentials'])} 个相关势函数")
        for pot in result['similar_potentials']:
            print(f"{pot['filename']} (相似度: {pot['similarity']:.3f})")
        ```
    """
    try:
        # 直接调用API层的功能，避免重复实现
        result = find_similar_potentials(query_name, top_k)
        return result
    except Exception as e:
        return {
            "similar_potentials": [],
            "total_found": 0,
            "query_name": query_name,
            "error": str(e),
            "message": f"搜索势函数时出错: {str(e)}"
        }


# 工具列表，供LangGraph使用
LAMMPS_POTENTIAL_TOOLS = [
    check_lammps_potential_files_tool,
    check_lammps_potentials_tool,
    get_potential_file_info_tool,
    list_available_potentials_tool,
    find_similar_potentials_tool
]


def get_potential_tools() -> List:
    """
    获取所有势函数相关的工具列表
    
    Returns:
        List: LangGraph工具列表
    """
    return LAMMPS_POTENTIAL_TOOLS


# 示例用法
if __name__ == "__main__":
    # 测试工具功能
    print("测试势函数检查工具...")
    
    # 测试代码
    test_code = """
    units metal
    atom_style atomic
    
    lattice fcc 3.52
    region box block 0 4 0 4 0 4
    create_box 1 box
    create_atoms 1 box
    
    pair_style eam/alloy
    pair_coeff * * Al99.eam.alloy Al
    
    thermo 10
    run 100
    """
    
    # 测试势函数检查
    result = check_lammps_potentials_tool(test_code)
    print(f"检查结果: {result['message']}")
    print(f"摘要: {result['summary']}")
    
    # 测试文件信息获取
    info = get_potential_file_info_tool("Al99.eam.alloy")
    print(f"\n文件信息: {info['filename']}")
    print(f"本地存在: {info['exists_locally']}")
    
    # 测试列出可用文件
    available = list_available_potentials_tool()
    print(f"\n可用文件数: {available['total_count']}")
    print(f"文件类型: {available['file_types']}")
    
    # 测试相似势函数搜索
    print("\n测试相似势函数搜索...")
    similar = find_similar_potentials_tool("Al99.eam", 5)
    print(f"搜索结果: {similar['message']}")
    for pot in similar['similar_potentials']:
        print(f"  {pot['filename']} (相似度: {pot['similarity']:.3f})")
    
    # 测试错误拼写的搜索
    print("\n测试错误拼写搜索...")
    similar_error = find_similar_potentials_tool("Ta6.8x.mgpt", 3)
    print(f"搜索结果: {similar_error['message']}")
    for pot in similar_error['similar_potentials']:
        print(f"  {pot['filename']} (相似度: {pot['similarity']:.3f})")

    code_1 = '''
        # 使用 FCC 铝，EAM 力场
    units metal
    atom_style atomic
    lattice fcc 4.05
    region box block 0 10 0 10 0 10
    create_box 1 box
    create_atoms 1 box
    mass 1 26.9815
    pair_style eam
    pair_coeff * * potentials/Al99.eam.alloy
    log lammps_run_20251119_160505_257c/log.lammps
    dump 1 all atom 10 lammps_run_20251119_160505_257c/dump.lammpstrj
    dump_modify 1 sort id
    minimize 1.0e-4 1.0e-6 1000 10000
    ",
  "checkout_filename_list": [
    "log.lammps",
    "dump.lammpstrj"
    '''
    result = check_lammps_potentials_tool(code_1)
    print("="*100+"测试势函数检查和推荐相似势函数"+"="*100)
    print(result)
    code_2 ='''
        # 使用 FCC 铝，EAM 力场
    units metal
    atom_style atomic
    lattice fcc 4.05
    region box block 0 10 0 10 0 10
    create_box 1 box
    create_atoms 1 box
    mass 1 26.9815
    pair_style eam
    pair_coeff * * potentials/Al99.eam
    log lammps_run_20251119_160505_257c/log.lammps
    dump 1 all atom 10 lammps_run_20251119_160505_257c/dump.lammpstrj
    dump_modify 1 sort id
    minimize 1.0e-4 1.0e-6 1000 10000
    '''
    # 测试势函数检查和推荐相似势函数
    result = check_lammps_potentials_tool(test_code)
    print("="*100+"测试势函数检查和推荐相似势函数"+"="*100)
    print(result)

    query_name = ["Al99.eam", "Al99.eam.alloy", "Al99.eam.fs", "Al99.eam.fs.alloy"]
    result = check_lammps_potential_files_tool(query_name)
    print("="*100+"测试相似势函数搜索"+"="*100)
    print(result['message'])