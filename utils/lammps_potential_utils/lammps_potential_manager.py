#!/usr/bin/env python3
"""
LAMMPS势函数管理器 - 基于官方Fetch.sh方法
自动检查LAMMPS代码中使用的势函数，缺失时从官方源下载
"""

import os
import re
import hashlib
import urllib.request
import urllib.error
import json
import tempfile
from typing import List, Dict, Tuple, Optional, Set
from pathlib import Path


class LAMMPSPotentialManager:
    """LAMMPS势函数管理器"""
    
    def __init__(self, potentials_dir: str = "potentials"):
        """
        初始化势函数管理器
        
        Args:
            potentials_dir: 势函数文件存储目录
        """
        self.potentials_dir = Path(potentials_dir)
        self.potentials_dir.mkdir(exist_ok=True)
        
        # LAMMPS官方下载源
        self.base_url = "https://download.lammps.org/potentials"
        
        # 势函数文件扩展名
        self.potential_extensions = {
            '.eam', '.eam.alloy', '.eam.fs', '.eam.he',
            '.tersoff', '.tersoff.zbl', '.tersoff.mod', '.tersoff.modc',
            '.sw', '.sw.mod', '.sw.zbl',
            '.bop', '.bop.table',
            '.rebo', '.airebo', '.airebo-m',
            '.meam', '.msmeam', '.meam.spline', '.meam.sw.spline',
            '.adp', '.uf3', '.uf4', '.uf5',
            '.gw', '.gw.zbl',
            '.edip', '.extep', '.drip',
            '.lcbop', '.comb', '.comb3', '.eim',
            '.reax', '.ffield', '.ffield.reax', '.ffield.comb',
            '.snap', '.snapcoeff', '.snapparam',
            '.mliap', '.mliap.descriptor', '.mliap.model',
            '.agni', '.ace', '.rann', '.cgdna',
            '.ILP', '.nb3b', '.nb3b.harmonic', '.nb3b.screened',
            '.vashishta', '.ctip', '.poly', '.table',
            '.cmap', '.water', '.2dm', '.KC', '.KC-full',
            '.Lebedeva', '.mgpt', '.mgpt.parmin', '.mgpt.potin',
            '.pod', '.quadratic', '.smtbq', '.rebomos',
            '.mesocnt', '.uf3', '.uf4', '.uf5'
        }
        
        # 从known_potentials.json加载MD5信息（如果存在）
        self.md5_registry = self._load_md5_registry()
    
    def _load_md5_registry(self) -> Dict[str, str]:
        """加载MD5注册表"""
        md5_file = Path("known_potentials_md5.json")
        if md5_file.exists():
            try:
                with open(md5_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ 加载MD5注册表失败: {e}")
        return {}
    
    def _save_md5_registry(self):
        """保存MD5注册表"""
        md5_file = Path("known_potentials_md5.json")
        try:
            with open(md5_file, 'w', encoding='utf-8') as f:
                json.dump(self.md5_registry, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ 保存MD5注册表失败: {e}")
    
    def _calculate_md5(self, file_path: Path) -> str:
        """计算文件MD5值"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return ""
    
    def _verify_file_integrity(self, file_path: Path, expected_md5: str = None) -> bool:
        """验证文件完整性"""
        if not file_path.exists():
            return False
        
        if expected_md5:
            actual_md5 = self._calculate_md5(file_path)
            return actual_md5 == expected_md5
        
        return True
    
    def _extract_potential_files_from_code(self, lammps_code: str) -> Set[str]:
        """从LAMMPS代码中提取势函数文件名"""
        potential_files = set()
        
        # 转义扩展名中的点号，用于正则表达式
        # 按长度降序排序，优先匹配较长的扩展名（如 .eam.alloy 优先于 .eam）
        sorted_extensions = sorted(self.potential_extensions, key=lambda x: len(x), reverse=True)
        escaped_extensions = [re.escape(ext[1:]) for ext in sorted_extensions]
        extensions_pattern = '|'.join(escaped_extensions)
        
        # 匹配各种势函数文件引用模式
        patterns = [
            # pair_coeff 命令中的文件引用（最常见）
            # 匹配: pair_coeff * * file.eam.alloy 或 pair_coeff * * path/file.eam.alloy
            r'pair_coeff\s+\S+\s+\S+\s+([^\s]+)',
            # pair_style 命令中的文件引用
            r'pair_style\s+\S+\s+([^\s]+)',
            # 直接的文件名引用（在引号中）
            r'["\']([^"\']+)["\']',
            # 变量引用中的文件名
            r'\$\{?(\w+)\}?.*?',
        ]
        
        # 收集所有可能的文件名候选
        candidates = []
        for pattern in patterns:
            matches = re.findall(pattern, lammps_code, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                candidate = match.strip()
                if candidate:
                    candidates.append(candidate)
        
        # 对每个候选文件名，尝试匹配所有扩展名，选择最长的匹配
        for candidate in candidates:
            # 移除路径，只保留文件名部分
            filename_with_path = candidate
            filename_only = os.path.basename(filename_with_path)
            
            # 尝试匹配所有扩展名，选择最长的匹配
            best_match = None
            best_match_len = 0
            
            for ext in sorted_extensions:
                ext_without_dot = ext[1:]  # 去掉开头的点
                # 检查文件名是否以该扩展名结尾（不区分大小写）
                if filename_only.lower().endswith(ext.lower()):
                    if len(ext) > best_match_len:
                        best_match = filename_only
                        best_match_len = len(ext)
            
            # 如果找到匹配，添加到结果集
            if best_match:
                potential_files.add(best_match)
        
        return potential_files
    
    def _download_potential_file(self, filename: str, expected_md5: str = None) -> bool:
        """下载势函数文件"""
        url = f"{self.base_url}/{filename}"
        if expected_md5:
            url += f".{expected_md5}"
        
        local_path = self.potentials_dir / filename
        
        try:
            print(f"正在下载势函数文件: {filename}")
            print(f"   来源: {url}")
            
            # 使用urllib下载
            urllib.request.urlretrieve(url, local_path)
            
            # 验证下载的文件
            if expected_md5:
                if self._verify_file_integrity(local_path, expected_md5):
                    print(f"成功下载并验证: {filename}")
                    return True
                else:
                    print(f"文件校验失败: {filename}")
                    local_path.unlink(missing_ok=True)
                    return False
            else:
                print(f"成功下载: {filename}")
                return True
                
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print(f"文件不存在: {filename}")
            else:
                print(f"下载失败: {filename}, HTTP错误: {e.code}")
            return False
        except Exception as e:
            print(f"下载失败: {filename}, 错误: {e}")
            return False
    
    def _try_alternative_sources(self, filename: str) -> bool:
        """尝试从备用源下载"""
        # GitHub备用源
        github_url = f"https://raw.githubusercontent.com/lammps/lammps/develop/potentials/{filename}"
        local_path = self.potentials_dir / filename
        
        try:
            print(f"尝试从GitHub下载: {filename}")
            urllib.request.urlretrieve(github_url, local_path)
            print(f"从GitHub成功下载: {filename}")
            return True
        except Exception as e:
            print(f"GitHub下载也失败: {filename}, 错误: {e}")
            return False
    
    def check_and_fetch_potentials(self, lammps_code: str, 
                                  use_md5_verification: bool = True) -> Dict[str, str]:
        """
        检查并下载LAMMPS代码中需要的势函数文件
        
        Args:
            lammps_code: LAMMPS输入脚本内容
            use_md5_verification: 是否使用MD5验证
            
        Returns:
            Dict[filename, status]: 文件名和下载状态的映射
        """
        print("扫描LAMMPS代码中的势函数文件...")
        
        # 提取势函数文件名
        potential_files = self._extract_potential_files_from_code(lammps_code)
        
        if not potential_files:
            print("未发现势函数文件引用")
            return {}
        
        print(f"发现 {len(potential_files)} 个势函数文件:")
        for f in sorted(potential_files):
            print(f"   - {f}")
        
        results = {}
        
        for filename in potential_files:
            local_path = self.potentials_dir / filename
            
            # 检查本地文件是否存在且有效
            if local_path.exists():
                if use_md5_verification and filename in self.md5_registry:
                    expected_md5 = self.md5_registry[filename]
                    if self._verify_file_integrity(local_path, expected_md5):
                        print(f"本地文件完整: {filename}")
                        results[filename] = "local_valid"
                        continue
                    else:
                        print(f"本地文件损坏: {filename}")
                else:
                    print(f"本地文件存在: {filename}")
                    results[filename] = "local_exists"
                    continue
            
            # 尝试下载
            print(f"下载缺失文件: {filename}")
            
            # 首先尝试官方源
            expected_md5 = self.md5_registry.get(filename) if use_md5_verification else None
            success = self._download_potential_file(filename, expected_md5)
            
            if success:
                results[filename] = "downloaded_official"
            else:
                # 尝试备用源
                success = self._try_alternative_sources(filename)
                if success:
                    results[filename] = "downloaded_github"
                else:
                    results[filename] = "download_failed"
        
        return results
    
    def create_potentials_txt(self, lammps_code: str, output_file: str = "potentials.txt"):
        """创建potentials.txt文件（LAMMPS官方格式）"""
        potential_files = self._extract_potential_files_from_code(lammps_code)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# list of potential files to be fetched when this package is installed\n")
            f.write("# potential file  md5sum\n")
            
            for filename in sorted(potential_files):
                md5 = self.md5_registry.get(filename, "unknown")
                f.write(f"{filename} {md5}\n")
        
        print(f"已创建potentials.txt文件: {output_file}")
    
    def update_md5_registry(self, filename: str, md5_value: str):
        """更新MD5注册表"""
        self.md5_registry[filename] = md5_value
        self._save_md5_registry()
        print(f"已更新MD5注册表: {filename} -> {md5_value}")


def main():
    """主函数 - 命令行接口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="LAMMPS势函数管理器")
    parser.add_argument("input_file", help="LAMMPS输入文件")
    parser.add_argument("--potentials-dir", default="potentials", help="势函数目录")
    parser.add_argument("--no-md5", action="store_true", help="跳过MD5验证")
    parser.add_argument("--create-txt", action="store_true", help="创建potentials.txt文件")
    
    args = parser.parse_args()
    
    # 读取LAMMPS代码
    with open(args.input_file, 'r', encoding='utf-8') as f:
        lammps_code = f.read()
    
    # 创建管理器
    manager = LAMMPSPotentialManager(args.potentials_dir)
    
    # 检查并下载势函数
    results = manager.check_and_fetch_potentials(lammps_code, not args.no_md5)
    
    # 输出结果
    print("\n📊 处理结果:")
    for filename, status in results.items():
        status_map = {
            "local_valid": "✅ 本地文件完整",
            "local_exists": "✅ 本地文件存在", 
            "downloaded_official": "📥 从官方源下载",
            "downloaded_github": "📥 从GitHub下载",
            "download_failed": "❌ 下载失败"
        }
        print(f"   {filename}: {status_map.get(status, status)}")
    
    # 创建potentials.txt文件
    if args.create_txt:
        manager.create_potentials_txt(lammps_code)


if __name__ == "__main__":
    main()
