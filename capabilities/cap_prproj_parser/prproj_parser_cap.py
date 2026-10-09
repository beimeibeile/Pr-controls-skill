"""
Pr工程解析能力模块
封装prproj_parser.py的PrprojParser类，提供高层解析接口
"""
import os
import sys
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# 导入scripts目录
_SCRIPT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from prproj_parser import PrprojParser, PrProject


class PrprojParseCapability:
    """Pr工程解析能力

    能力清单：
    - parse_prproj: 解析.prproj文件为结构化对象
    - get_summary: 获取工程摘要信息
    - list_sequences: 列出所有序列
    - list_tracks: 列出指定序列的轨道
    - list_effects: 列出所有特效
    - list_transitions: 列出所有转场
    - list_media: 列出所有媒体文件
    - to_dict: 导出为字典
    - to_json: 导出为JSON文件
    """

    CAPABILITY_ID = "prproj_parser"
    CAPABILITY_NAME = "Pr工程解析"
    CAPABILITY_VERSION = "1.0.0"

    def __init__(self):
        self._parser = None
        self._project = None

    def parse_prproj(self, prproj_path: str) -> PrProject:
        """解析.prproj文件

        Args:
            prproj_path: .prproj文件路径

        Returns:
            PrProject结构化对象
        """
        if not os.path.exists(prproj_path):
            raise FileNotFoundError(f"文件不存在: {prproj_path}")

        logger.info(f"解析Pr工程: {prproj_path}")
        self._parser = PrprojParser(prproj_path)
        self._project = self._parser.parse()
        logger.info(f"解析完成: {len(self._project.sequences)}个序列, "
                    f"{len(self._project.media_files)}个媒体文件")
        return self._project

    def get_summary(self) -> Dict[str, Any]:
        """获取工程摘要"""
        if not self._project:
            return {"error": "未解析工程"}
        return {
            "project_name": self._project.info.name if self._project.info else "unknown",
            "version": self._project.info.version if self._project.info else "unknown",
            "sequences_count": len(self._project.sequences),
            "media_count": len(self._project.media_files),
            "effects_count": len(self._project.effects),
            "transitions_count": len(self._project.transitions),
        }

    def list_sequences(self) -> list:
        """列出所有序列"""
        if not self._project:
            return []
        return [{"id": seq.id, "name": seq.name,
                 "duration": seq.duration,
                 "tracks_count": len(seq.tracks)}
                for seq in self._project.sequences]

    def list_tracks(self, sequence_index: int = 0) -> list:
        """列出指定序列的轨道"""
        if not self._project or sequence_index >= len(self._project.sequences):
            return []
        seq = self._project.sequences[sequence_index]
        return [{"id": track.id, "type": track.track_type,
                 "items_count": len(track.items)}
                for track in seq.tracks]

    def list_effects(self) -> list:
        """列出所有特效"""
        if not self._project:
            return []
        return [{"name": eff.name, "type": eff.effect_type,
                 "params_count": len(eff.params)}
                for eff in self._project.effects]

    def list_transitions(self) -> list:
        """列出所有转场"""
        if not self._project:
            return []
        return [{"name": trans.name, "duration": trans.duration}
                for trans in self._project.transitions]

    def list_media(self) -> list:
        """列出所有媒体文件"""
        if not self._project:
            return []
        return [{"id": media.id, "name": media.name,
                 "path": media.path, "type": media.media_type}
                for media in self._project.media_files]

    def to_dict(self) -> Dict[str, Any]:
        """导出为字典"""
        if not self._project:
            return {}
        return self._parser.to_dict()

    def to_json(self, output_path: str) -> str:
        """导出为JSON文件"""
        if not self._project:
            raise RuntimeError("未解析工程")
        return self._parser.save_json(output_path)

    def print_summary(self):
        """打印工程摘要"""
        if self._parser:
            self._parser.print_summary()


# 便捷函数
def parse_prproj(prproj_path: str) -> Dict[str, Any]:
    """快速解析.prproj文件并返回字典"""
    cap = PrprojParseCapability()
    cap.parse_prproj(prproj_path)
    return cap.to_dict()


def get_prproj_summary(prproj_path: str) -> Dict[str, Any]:
    """快速获取工程摘要"""
    cap = PrprojParseCapability()
    cap.parse_prproj(prproj_path)
    return cap.get_summary()
