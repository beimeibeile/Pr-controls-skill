"""
Pr执行器能力模块
封装prproj_executor.py的PrprojExecutor类，提供高层执行接口
"""
import os
import sys
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

_SCRIPT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from prproj_executor import PrprojExecutor


class PrExecutorCapability:
    """Pr执行器能力

    能力清单：
    - list_templates: 列出可用模板
    - get_template_info: 获取模板详细信息
    - create_project: 从模板创建项目
    - create_from_instructions: 从指令序列创建项目
    - create_prproj_project: 创建完整Pr工程
    - validate_project: 验证工程完整性
    - export_project_info: 导出工程信息
    """

    CAPABILITY_ID = "pr_executor"
    CAPABILITY_NAME = "Pr执行器"
    CAPABILITY_VERSION = "1.0.0"

    def __init__(self, templates_dir: str = None, output_dir: str = None):
        self._executor = PrprojExecutor(templates_dir)
        self._output_dir = output_dir
        self._last_project: Dict[str, Any] = None

    def list_templates(self) -> List[Dict[str, Any]]:
        """列出可用模板

        Returns:
            模板列表，每个元素含name/path/description
        """
        templates = self._executor.list_templates()
        logger.info(f"找到{len(templates)}个Pr模板")
        return templates

    def get_template_info(self, template_name: str) -> Optional[Dict[str, Any]]:
        """获取模板详细信息"""
        info = self._executor.get_template_info(template_name)
        if info:
            logger.info(f"模板信息: {template_name}")
        else:
            logger.warning(f"模板不存在: {template_name}")
        return info

    def create_project(self, template_name: str, output_name: str = None,
                       replacements: Dict[str, str] = None) -> Dict[str, Any]:
        """从模板创建项目

        Args:
            template_name: 模板名称
            output_name: 输出项目名称
            replacements: 文本替换字典（占位符→实际值）

        Returns:
            项目创建结果
        """
        result = self._executor.create_project(template_name, output_name, replacements)
        self._last_project = result
        logger.info(f"项目创建: {result.get('status', 'unknown')} - {result.get('output_path', '')}")
        return result

    def create_from_instructions(self, instructions: Dict[str, Any],
                                  output_name: str = None) -> Dict[str, Any]:
        """从指令序列创建项目

        Args:
            instructions: 指令序列JSON，格式：
                {
                    "template": "模板名",
                    "clips": [{"path": "...", "start": 0, "duration": 30}],
                    "replacements": {"TITLE": "我的视频"},
                    "effects": [...],
                    "transitions": [...]
                }
            output_name: 输出名称

        Returns:
            项目创建结果
        """
        result = self._executor.create_from_instructions(instructions, output_name)
        self._last_project = result
        logger.info(f"指令创建: {result.get('status', 'unknown')}")
        return result

    def create_prproj_project(self, name: str, width: int = 1920,
                               height: int = 1080, fps: float = 30.0,
                               clips: List[Dict] = None) -> Dict[str, Any]:
        """创建完整Pr工程

        Args:
            name: 项目名称
            width/height: 分辨率
            fps: 帧率
            clips: 片段列表

        Returns:
            项目创建结果
        """
        result = self._executor.create_prproj_project(name, width, height, fps, clips)
        self._last_project = result
        logger.info(f"Pr工程创建: {name} - {result.get('status', 'unknown')}")
        return result

    def validate_project(self, prproj_path: str) -> Dict[str, Any]:
        """验证工程完整性

        Args:
            prproj_path: .prproj文件路径

        Returns:
            验证结果 {valid, errors, warnings, info}
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "info": {},
        }

        if not os.path.exists(prproj_path):
            result["valid"] = False
            result["errors"].append(f"文件不存在: {prproj_path}")
            return result

        # 检查文件大小
        size = os.path.getsize(prproj_path)
        result["info"]["file_size"] = size
        if size < 1000:
            result["warnings"].append(f"文件过小: {size}字节（可能不完整）")

        # 尝试解析
        try:
            from cap_prproj_parser.prproj_parser_cap import PrprojParseCapability
            parser = PrprojParseCapability()
            project = parser.parse_prproj(prproj_path)
            result["info"]["sequences"] = len(project.sequences)
            result["info"]["media_files"] = len(project.media_files)
            if len(project.sequences) == 0:
                result["warnings"].append("工程中没有序列")
        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"解析失败: {e}")

        logger.info(f"工程验证: {'通过' if result['valid'] else '失败'} - {prproj_path}")
        return result

    def export_project_info(self, prproj_path: str,
                             output_json: str = None) -> Dict[str, Any]:
        """导出工程信息为JSON

        Args:
            prproj_path: .prproj文件路径
            output_json: 输出JSON路径（可选）

        Returns:
            工程信息字典
        """
        from cap_prproj_parser.prproj_parser_cap import PrprojParseCapability
        parser = PrprojParseCapability()
        parser.parse_prproj(prproj_path)
        info = {
            "summary": parser.get_summary(),
            "sequences": parser.list_sequences(),
            "effects": parser.list_effects(),
            "transitions": parser.list_transitions(),
            "media": parser.list_media(),
        }

        if output_json:
            os.makedirs(os.path.dirname(output_json) or ".", exist_ok=True)
            with open(output_json, 'w', encoding='utf-8') as f:
                json.dump(info, f, ensure_ascii=False, indent=2)
            logger.info(f"工程信息已导出: {output_json}")

        return info

    def get_last_project(self) -> Optional[Dict[str, Any]]:
        """获取最后创建的项目信息"""
        return self._last_project


# 便捷函数
def create_from_template(template_name: str, output_path: str,
                          replacements: Dict[str, str] = None) -> Dict[str, Any]:
    """从模板快速创建Pr项目"""
    cap = PrExecutorCapability()
    return cap.create_project(template_name, os.path.basename(output_path), replacements)
