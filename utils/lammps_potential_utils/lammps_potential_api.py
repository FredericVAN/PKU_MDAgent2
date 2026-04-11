"""
LAMMPS势函数管理器 - 大模型API接口
简化版本，专门为大模型调用设计
"""

from utils.lammps_potential_utils.lammps_potential_manager import LAMMPSPotentialManager
from typing import Dict, List, Optional
from pathlib import Path
from difflib import SequenceMatcher
import re
import os


class LAMMPSPotentialAPI:
    """LAMMPS势函数API - 大模型专用接口"""
    
    def __init__(self, potentials_dir: str = "potentials"):
        self.manager = LAMMPSPotentialManager(potentials_dir)
    
    def check_lammps_potential_files(self, potential_files: List[str], top_k: int = 10) -> Dict[str, any]:
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
            if not potential_files:
                return {
                    "status": "success",
                    "summary": "未提供势函数文件列表",
                    "details": {},
                    "all_ready": True,
                    "message": "未提供势函数文件列表",
                    "recommendations": {}
                }
            
            details = {}
            recommendations = {}
            missing_files = []
            existing_files = []
            
            # 检查每个文件
            for potential_file in potential_files:
                # 提取纯文件名（去掉路径）
                filename = os.path.basename(potential_file.strip())
                
                # 获取文件信息
                file_info = self.get_potential_info(filename)
                exists = file_info.get("exists_locally", False)
                
                details[potential_file] = {
                    "filename": filename,
                    "exists": exists,
                    "local_path": file_info.get("local_path", ""),
                    "file_size": file_info.get("file_size", 0) if exists else 0,
                    "is_valid": file_info.get("is_valid", False) if exists else False
                }
                
                if exists:
                    existing_files.append(filename)
                else:
                    missing_files.append(filename)
                    # 为不存在的文件推荐相似文件
                    similar_result = self.find_similar_potentials(filename, top_k=top_k)
                    recommendations[filename] = {
                        "original_file": filename,
                        "similar_potentials": similar_result.get("similar_potentials", []),
                        "total_found": similar_result.get("total_found", 0),
                        "message": similar_result.get("message", "")
                    }
            
            # 统计结果
            total_files = len(potential_files)
            existing_count = len(existing_files)
            missing_count = len(missing_files)
            
            # 生成摘要
            if missing_count == 0:
                summary = f"检查了 {total_files} 个势函数文件，全部存在"
            else:
                summary = f"检查了 {total_files} 个势函数文件，{existing_count} 个存在，{missing_count} 个不存在"
            
            # 生成简洁易读的消息
            message_parts = []
            
            # 存在的文件列表
            if existing_files:
                if len(existing_files) == 1:
                    message_parts.append(f"✅ 存在: {existing_files[0]}")
                else:
                    files_list = ", ".join(existing_files)
                    message_parts.append(f"✅ 存在 ({existing_count}个): {files_list}")
            
            # 不存在的文件及推荐
            if missing_files:
                for missing_file in missing_files:
                    rec_info = recommendations.get(missing_file, {})
                    similar_pots = rec_info.get("similar_potentials", [])
                    
                    if similar_pots:
                        # 只显示前3个最相似的
                        top_similar = similar_pots[:top_k]
                        similar_names = [f"{pot['filename']}({pot['similarity']:.2f})" for pot in top_similar]
                        similar_str = ", ".join(similar_names)
                        message_parts.append(f"❌ 不存在: {missing_file} → 推荐: {similar_str}")
                    else:
                        message_parts.append(f"❌ 不存在: {missing_file} (无相似文件)")
            
            message = "\n".join(message_parts) if message_parts else "未检查到任何文件"
            
            return {
                "status": "success",
                "summary": summary,
                "details": details,
                "all_ready": missing_count == 0,
                "message": message,
                "recommendations": recommendations,
                "existing_files": existing_files,
                "missing_files": missing_files
            }
            
        except Exception as e:
            return {
                "status": "error",
                "summary": f"检查失败: {str(e)}",
                "details": {},
                "all_ready": False,
                "message": f"势函数文件检查失败: {str(e)}",
                "recommendations": {},
                "error": str(e)
            }

    def check_lammps_potentials(self, lammps_code: str, top_k: int = 10) -> Dict[str, any]:
        """
        检查LAMMPS代码中的势函数依赖,如果有某个文件无法使用会推荐相似文件
        
        Args:
            lammps_code: LAMMPS输入脚本内容
            top_k: 推荐相似的势函数文件数量，默认为10
            
        Returns:
            Dict包含检查结果和下载状态
                - status: "success" 或 "error"
                - summary: 检查摘要
                - details: 每个文件的检查详情
                - all_ready: 是否所有文件都就绪
                - message: 用户友好的消息
                - recommendations: 失败文件的推荐信息
                - existing_files: 成功获取的文件列表
                - failed_files: 失败的文件列表
        """
        try:
            results = self.manager.check_and_fetch_potentials(lammps_code)
            
            # 统计结果
            total_files = len(results)
            success_statuses = ["local_valid", "local_exists", "downloaded_official", "downloaded_github"]
            success_count = sum(1 for status in results.values() if status in success_statuses)
            failed_count = sum(1 for status in results.values() if status == "download_failed")
            
            # 分类文件
            existing_files = [fname for fname, status in results.items() if status in success_statuses]
            failed_files = [fname for fname, status in results.items() if status == "download_failed"]
            
            # 为失败的文件推荐相似文件
            recommendations = {}
            if failed_files:
                for failed_file in failed_files:
                    similar_result = self.find_similar_potentials(failed_file, top_k=top_k)
                    recommendations[failed_file] = {
                        "original_file": failed_file,
                        "similar_potentials": similar_result.get("similar_potentials", []),
                        "total_found": similar_result.get("total_found", 0),
                        "message": similar_result.get("message", "")
                    }
            
            # 生成摘要
            if failed_count == 0:
                summary = f"检查了 {total_files} 个势函数文件，全部就绪"
            else:
                summary = f"检查了 {total_files} 个势函数文件，{success_count} 个可用，{failed_count} 个下载失败"
            
            # 生成简洁易读的消息
            message_parts = []
            
            # 存在的文件列表
            if existing_files:
                if len(existing_files) == 1:
                    message_parts.append(f"✅ 就绪: {existing_files[0]}")
                else:
                    files_list = ", ".join(existing_files)
                    message_parts.append(f"✅ 就绪 ({success_count}个): {files_list}")
            
            # 失败的文件及推荐
            if failed_files:
                for failed_file in failed_files:
                    rec_info = recommendations.get(failed_file, {})
                    similar_pots = rec_info.get("similar_potentials", [])
                    
                    if similar_pots:
                        # 显示前top_k个最相似的
                        top_similar = similar_pots[:top_k]
                        similar_names = [f"{pot['filename']}({pot['similarity']:.2f})" for pot in top_similar]
                        similar_str = ", ".join(similar_names)
                        message_parts.append(f"❌ 不存在或无法使用: {failed_file} → 相似的可用文件: {similar_str}")
                    else:
                        message_parts.append(f"❌ 不存在或无法使用: {failed_file} (无相似文件)")
            
            message = "\n".join(message_parts) if message_parts else "未检查到任何文件"
            
            return {
                "status": "success",
                "summary": summary,
                "details": results,
                "all_ready": failed_count == 0,
                "message": message,
                "recommendations": recommendations,
                "existing_files": existing_files,
                "failed_files": failed_files
            }
            
        except Exception as e:
            return {
                "status": "error", 
                "summary": f"检查失败: {str(e)}",
                "details": {},
                "all_ready": False,
                "message": f"势函数检查失败: {str(e)}",
                "recommendations": {},
                "existing_files": [],
                "failed_files": [],
                "error": str(e)
            }
    
    def get_potential_info(self, filename: str) -> Dict[str, any]:
        """
        获取势函数文件信息
        
        Args:
            filename: 势函数文件名
            
        Returns:
            文件信息字典
        """
        local_path = self.manager.potentials_dir / filename
        
        info = {
            "filename": filename,
            "exists_locally": local_path.exists(),
            "local_path": str(local_path),
            "has_md5": filename in self.manager.md5_registry,
            "md5_value": self.manager.md5_registry.get(filename, "unknown")
        }
        
        if local_path.exists():
            info["file_size"] = local_path.stat().st_size
            info["is_valid"] = self.manager._verify_file_integrity(
                local_path, 
                self.manager.md5_registry.get(filename)
            )
        
        return info
    
    def _calculate_similarity_score(self, query: str, filename: str) -> float:
        """
        计算查询字符串与文件名的相似度分数
        
        Args:
            query (str): 查询的势函数名称
            filename (str): 本地文件名
            
        Returns:
            float: 相似度分数 (0-1)
        """
        # 转换为小写进行比较
        query_lower = query.lower()
        filename_lower = filename.lower()
        
        # 1. 精确匹配得分最高
        if query_lower == filename_lower:
            return 1.0
        
        # 2. 包含关系得分
        if query_lower in filename_lower or filename_lower in query_lower:
            return 0.8
        
        # 3. 使用SequenceMatcher计算编辑距离相似度
        sequence_similarity = SequenceMatcher(None, query_lower, filename_lower).ratio()
        
        # 4. 提取元素符号进行匹配
        query_elements = re.findall(r'[A-Z][a-z]?', query)
        filename_elements = re.findall(r'[A-Z][a-z]?', filename)
        
        element_score = 0.0
        if query_elements and filename_elements:
            # 计算元素符号的Jaccard相似度
            query_set = set(query_elements)
            filename_set = set(filename_elements)
            intersection = len(query_set & filename_set)
            union = len(query_set | filename_set)
            if union > 0:
                element_score = intersection / union
        
        # 5. 提取数字进行匹配
        query_numbers = re.findall(r'\d+', query)
        filename_numbers = re.findall(r'\d+', filename)
        
        number_score = 0.0
        if query_numbers and filename_numbers:
            query_num_set = set(query_numbers)
            filename_num_set = set(filename_numbers)
            intersection = len(query_num_set & filename_num_set)
            union = len(query_num_set | filename_num_set)
            if union > 0:
                number_score = intersection / union
        
        # 6. 综合评分
        # 序列相似度权重0.4，元素匹配权重0.4，数字匹配权重0.2
        final_score = (sequence_similarity * 0.4 + 
                       element_score * 0.4 + 
                       number_score * 0.2)
        
        return final_score
    
    def find_similar_potentials(self, query_name: str, top_k: int = 10) -> Dict[str, any]:
        """
        根据势函数名称（可能错误）在本地potentials文件夹中查找最相关的势函数
        
        Args:
            query_name (str): 要搜索的势函数名称（可能包含拼写错误）
            top_k (int): 返回最相关的前k个结果，默认为10
            
        Returns:
            Dict[str, any]: 搜索结果字典
        """
        try:
            potentials_dir = Path(self.manager.potentials_dir)
            if not potentials_dir.exists():
                return {
                    "similar_potentials": [],
                    "total_found": 0,
                    "query_name": query_name,
                    "message": "potentials目录不存在"
                }
            
            # 复用manager中的势函数文件扩展名
            potential_extensions = self.manager.potential_extensions
            
            # 收集所有势函数文件
            potential_files = []
            for file_path in potentials_dir.iterdir():
                if file_path.is_file():
                    filename = file_path.name
                    ext = file_path.suffix.lower()
                    
                    # 检查是否是势函数文件
                    if ext in potential_extensions or any(filename.endswith(e) for e in potential_extensions):
                        potential_files.append(filename)
            
            # 计算相似度并排序
            similarity_scores = []
            for filename in potential_files:
                similarity = self._calculate_similarity_score(query_name, filename)
                if similarity > 0.1:  # 只保留相似度大于0.1的结果
                    similarity_scores.append({
                        "filename": filename,
                        "similarity": similarity,
                        "local_path": str(potentials_dir / filename)
                    })
            
            # 按相似度降序排序
            similarity_scores.sort(key=lambda x: x["similarity"], reverse=True)
            
            # 返回前top_k个结果
            top_results = similarity_scores[:top_k]
            
            return {
                "similar_potentials": top_results,
                "total_found": len(top_results),
                "query_name": query_name,
                "message": f"'{query_name}' 相似的势函数检索结果: {top_results}"
            }
            
        except Exception as e:
            return {
                "similar_potentials": [],
                "total_found": 0,
                "query_name": query_name,
                "error": str(e),
                "message": f"搜索势函数时出错: {str(e)}"
            }
    
    def extract_potential_files_from_code(self, lammps_code: str) -> List[str]:
        """
        从LAMMPS代码中提取势函数文件名 - 复用manager的功能
        
        Args:
            lammps_code (str): LAMMPS输入脚本内容
            
        Returns:
            List[str]: 势函数文件名列表
        """
        return list(self.manager._extract_potential_files_from_code(lammps_code))
    
    def get_potential_extensions(self) -> set:
        """
        获取势函数文件扩展名集合
        
        Returns:
            set: 势函数文件扩展名集合
        """
        return self.manager.potential_extensions
    
    def get_similar_potentials_recommendation(self, lammps_code: str, top_k_per_file: int = 40, max_total: int = 40) -> Dict[str, any]:
        """
        当势函数检查失败时，从LAMMPS代码中提取势函数文件名并推荐相似的势函数文件
        
        Args:
            lammps_code (str): LAMMPS输入脚本内容
            top_k_per_file (int): 为每个势函数文件搜索的相似文件数量，默认为40
            max_total (int): 返回的最大推荐数量，默认为40
            
        Returns:
            Dict[str, any]: 包含推荐信息的字典
                - similar_potentials_info (str): 格式化的推荐信息字符串
                - similar_potentials (list): 相似文件列表
                - total_found (int): 找到的相似文件总数
                - potential_files (list): 从代码中提取的势函数文件名列表
        """
        try:
            # 从LAMMPS代码中提取势函数文件名
            potential_files = self.extract_potential_files_from_code(lammps_code)
            
            if not potential_files:
                return {
                    "similar_potentials_info": "\n\n未检测到势函数文件名",
                    "similar_potentials": [],
                    "total_found": 0,
                    "potential_files": [],
                    "message": "未检测到势函数文件名"
                }
            
            # 为每个失败的势函数文件搜索相似文件
            all_similar = []
            for potential_file in potential_files:
                try:
                    similar_result = self.find_similar_potentials(potential_file, top_k=top_k_per_file)
                    if similar_result.get("similar_potentials"):
                        all_similar.extend(similar_result["similar_potentials"])
                except Exception as search_error:
                    # 单个文件搜索失败不影响整体流程
                    continue
            
            # 去重并按相似度排序
            if all_similar:
                # 使用字典去重，保留相似度最高的
                unique_similar = {}
                for item in all_similar:
                    filename = item["filename"]
                    if filename not in unique_similar or item["similarity"] > unique_similar[filename]["similarity"]:
                        unique_similar[filename] = item
                
                # 按相似度排序，取前max_total个
                sorted_similar = sorted(unique_similar.values(), key=lambda x: x["similarity"], reverse=True)[:max_total]
                
                # 格式化推荐信息
                similar_potentials_info = f"""
                    
相似势函数文件建议（共{len(sorted_similar)}个）：
"""
                for i, pot in enumerate(sorted_similar, 1):
                    similar_potentials_info += f"{i:2d}. {pot['filename']} (相似度: {pot['similarity']:.3f})\n"
                
                return {
                    "similar_potentials_info": similar_potentials_info,
                    "similar_potentials": sorted_similar,
                    "total_found": len(sorted_similar),
                    "potential_files": potential_files,
                    "message": f"找到 {len(sorted_similar)} 个相似势函数文件"
                }
            else:
                return {
                    "similar_potentials_info": "\n\n未找到相似的势函数文件",
                    "similar_potentials": [],
                    "total_found": 0,
                    "potential_files": potential_files,
                    "message": "未找到相似的势函数文件"
                }
                
        except Exception as e:
            return {
                "similar_potentials_info": f"\n\n相似性搜索失败: {str(e)}",
                "similar_potentials": [],
                "total_found": 0,
                "potential_files": [],
                "message": f"相似性搜索失败: {str(e)}",
                "error": str(e)
            }


# 全局实例
potential_api = LAMMPSPotentialAPI()

import requests
import json

def check_potential_real_exists(potential_name: str) -> bool:
    """
    根据势函数名称调用 Search LLM (或任意 Web 搜索 API) 判断势函数是否真实存在。
    只有当确定不存在时才返回 False；只要有可能存在就返回 True。

    参数:
        potential_name (str): 势函数名称，如 "Al_zhou.eam.alloy"

    返回:
        bool: True -> 可能存在 / 搜索到；False -> 搜索确认不存在
    """

    # ====== 你需要在这里替换成你自己的 Search API 接口 =======
    SEARCH_API_URL = "https://your-search-api-endpoint.com/search"

    # 搜索参数
    query = {
        "query": f"{potential_name} LAMMPS potential file"
    }

    try:
        # 调用 Web/LLM 搜索
        resp = requests.post(SEARCH_API_URL, json=query, timeout=10)
        resp.raise_for_status()

        data = resp.json()


        hits = data.get("results", [])
        if not hits:
            return False

        for item in hits:
            text = json.dumps(item).lower()
            if potential_name.lower() in text:
                return True
        return True

    except Exception as e:
        print(f"[WARNING] Search API 调用失败: {e}")
        # 保守策略：除非确认不存在，否则返回 True
        return True


def check_lammps_potential_files(potential_files: List[str], top_k: int = 10) -> Dict[str, any]:
    """
    检查势函数文件是否存在,如果有不存在的文件则需要推荐相似的势函数文件 - 全局函数
    
    Args:
        potential_files: 势函数文件名列表('potentials/Al99.eam.alloy' 或者 'Al99.eam.alloy')
        top_k: 推荐相似的势函数文件数量，默认为10
        
    Returns:
        Dict[str, any]: 包含检查结果的字典
    """
    return potential_api.check_lammps_potential_files(potential_files, top_k=top_k)

def check_lammps_potentials(lammps_code: str, top_k: int = 10) -> Dict[str, any]:
    """
    检查LAMMPS代码中的势函数依赖 - 全局函数
    
    Args:
        lammps_code: LAMMPS输入脚本内容
        top_k: 推荐相似的势函数文件数量，默认为10
        
    Returns:
        检查结果字典
    """
    return potential_api.check_lammps_potentials(lammps_code, top_k=top_k)


def get_potential_info(filename: str) -> Dict[str, any]:
    """
    获取势函数文件信息 - 全局函数
    
    Args:
        filename: 势函数文件名
        
    Returns:
        文件信息字典
    """
    return potential_api.get_potential_info(filename)


def find_similar_potentials(query_name: str, top_k: int = 10) -> Dict[str, any]:
    """
    根据势函数名称（可能错误）在本地potentials文件夹中查找最相关的势函数 - 全局函数
    
    Args:
        query_name (str): 要搜索的势函数名称（可能包含拼写错误）
        top_k (int): 返回最相关的前k个结果，默认为10
        
    Returns:
        Dict[str, any]: 搜索结果字典
    """
    return potential_api.find_similar_potentials(query_name, top_k)


def extract_potential_files_from_code(lammps_code: str) -> List[str]:
    """
    从LAMMPS代码中提取势函数文件名 - 全局函数
    
    Args:
        lammps_code (str): LAMMPS输入脚本内容
        
    Returns:
        List[str]: 势函数文件名列表
    """
    return potential_api.extract_potential_files_from_code(lammps_code)


def get_potential_extensions() -> set:
    """
    获取势函数文件扩展名集合 - 全局函数
    
    Returns:
        set: 势函数文件扩展名集合
    """
    return potential_api.get_potential_extensions()


def get_similar_potentials_recommendation(lammps_code: str, top_k_per_file: int = 40, max_total: int = 40) -> Dict[str, any]:
    """
    当势函数检查失败时，从LAMMPS代码中提取势函数文件名并推荐相似的势函数文件 - 全局函数
    
    Args:
        lammps_code (str): LAMMPS输入脚本内容
        top_k_per_file (int): 为每个势函数文件搜索的相似文件数量，默认为40
        max_total (int): 返回的最大推荐数量，默认为40
        
    Returns:
        Dict[str, any]: 包含推荐信息的字典
    """
    return potential_api.get_similar_potentials_recommendation(lammps_code, top_k_per_file, max_total)


# 示例用法
if __name__ == "__main__":
    # 测试代码
    test_lammps_code = """
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
    
    result = check_lammps_potentials(test_lammps_code)
    print("检查结果:")
    print(f"状态: {result['status']}")
    print(f"摘要: {result['summary']}")
    print(f"消息: {result['message']}")
    print(f"所有文件就绪: {result['all_ready']}")
    
    if result['details']:
        print("\n详细信息:")
        for filename, status in result['details'].items():
            print(f"  {filename}: {status}")
    
    # 测试势函数提取
    print("\n" + "="*50)
    print("测试势函数提取功能:")
    extracted_files = extract_potential_files_from_code(test_lammps_code)
    print(f"提取到的势函数文件: {extracted_files}")
    
    # 测试相似性搜索
    print("\n" + "="*50)
    print("测试相似性搜索功能:")
    
    test_queries = ["Al99.eam", "Si.tersoff", "Cu.eam"]
    for query in test_queries:
        print(f"\n搜索: '{query}'")
        similar_result = find_similar_potentials(query, top_k=3)
        print(f"结果: {similar_result['message']}")
        if similar_result['similar_potentials']:
            for i, pot in enumerate(similar_result['similar_potentials'], 1):
                print(f"  {i}. {pot['filename']} (相似度: {pot['similarity']:.3f})")

    api = LAMMPSPotentialAPI()
    result = api.check_lammps_potential_files(
    potential_files=['potentials/Al99.eam.alloy', 'Si.tersoff', 'Cu.eam'],
    top_k=5
    )
    print("="*100+"测试check_lammps_potential_files"+"="*100)
    print(result)
    print("="*100+"Message部分"+"="*100)
    print(result['message'])  # 查看检查结果和推荐信息

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
    result = check_lammps_potentials(code_1, top_k=5)
    print("="*100+"测试check_lammps_potentials"+"="*100)
    print(result)
    print("="*100+"Message部分"+"="*100)
    print(result['message'])  # 查看检查结果和推荐信息

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

    #测试check_lammps_potentials
    result = check_lammps_potentials(code_2, top_k=5)
    print("="*100+"测试check_lammps_potentials"+"="*100)
    print(result)
    print("="*100+"Message部分"+"="*100)
    print(result['message'])  # 查看检查结果和推荐信息

    # print(result['all_ready'])  # 是否所有文件都存在