"""
Pr工程生成能力模块
封装prproj_generator.py的PRPROJGenerator类，提供高层生成接口
"""
import os
import sys
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

_SCRIPT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from prproj_generator import PRPROJGenerator


class PrprojGenerateCapability:
    """Pr工程生成能力

    能力清单：
    - create_project: 创建新的Pr工程
    - add_video_clip: 添加视频片段
    - add_audio_clip: 添加音频片段
    - add_transition: 添加转场（待扩展）
    - add_effect: 添加特效（待扩展）
    - generate_xml: 生成XML内容
    - save: 保存为.prproj文件
    - generate_L1: L1级别快速生成（仅视频+音频）
    - generate_L2: L2级别生成（含转场）
    - generate_L3: L3级别生成（含特效+关键帧）
    """

    CAPABILITY_ID = "prproj_generator"
    CAPABILITY_NAME = "Pr工程生成"
    CAPABILITY_VERSION = "1.0.0"

    def __init__(self, width: int = 1920, height: int = 1080,
                 fps: float = 30.0, name: str = "Generated Project"):
        self._gen = PRPROJGenerator(width, height, fps)
        self._name = name
        self._video_clips: List[Dict] = []
        self._audio_clips: List[Dict] = []

    def create_project(self, name: str = None, width: int = None,
                       height: int = None, fps: float = None):
        """创建/重置工程"""
        if name: self._name = name
        if width: self._gen.width = width
        if height: self._gen.height = height
        if fps: self._gen.fps = fps
        self._video_clips = []
        self._audio_clips = []
        logger.info(f"创建Pr工程: {self._name} ({self._gen.width}x{self._gen.height} @ {self._gen.fps}fps)")

    def add_video_clip(self, media_path: str, start_frame: int = 0,
                       duration_frames: int = 30, track_index: int = 0) -> Dict:
        """添加视频片段

        Args:
            media_path: 媒体文件路径
            start_frame: 起始帧
            duration_frames: 持续帧数（默认30帧=1秒）
            track_index: 轨道索引

        Returns:
            片段信息字典
        """
        clip_info = {
            "path": media_path,
            "start": start_frame,
            "duration": duration_frames,
            "track": track_index,
        }
        self._video_clips.append(clip_info)
        self._gen.add_video_clip(media_path, start_frame, duration_frames, track_index)
        logger.debug(f"添加视频片段: {os.path.basename(media_path)} @帧{start_frame}")
        return clip_info

    def add_audio_clip(self, media_path: str, start_frame: int = 0,
                       duration_frames: int = 30, track_index: int = 0) -> Dict:
        """添加音频片段"""
        clip_info = {
            "path": media_path,
            "start": start_frame,
            "duration": duration_frames,
            "track": track_index,
        }
        self._audio_clips.append(clip_info)
        self._gen.add_audio_clip(media_path, start_frame, duration_frames, track_index)
        logger.debug(f"添加音频片段: {os.path.basename(media_path)} @帧{start_frame}")
        return clip_info

    def generate_xml(self) -> str:
        """生成XML内容"""
        return self._gen.generate_xml()

    def save(self, output_path: str) -> str:
        """保存为.prproj文件

        Args:
            output_path: 输出文件路径

        Returns:
            保存的文件路径
        """
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        result = self._gen.save(output_path)
        logger.info(f"Pr工程已保存: {output_path}")
        return result

    def generate_L1(self, video_files: List[str], output_path: str,
                    audio_file: str = None) -> str:
        """L1级别快速生成：视频拼接+可选音频

        Args:
            video_files: 视频文件列表
            output_path: 输出.prproj路径
            audio_file: 可选背景音乐路径

        Returns:
            保存的文件路径
        """
        self.create_project(name="L1_QuickEdit")
        current_frame = 0
        for vf in video_files:
            self.add_video_clip(vf, start_frame=current_frame)
            # 估算每段30帧（1秒），实际由generator处理
            current_frame += 30
        if audio_file:
            self.add_audio_clip(audio_file, start_frame=0)
        return self.save(output_path)

    def generate_L2(self, video_files: List[str], output_path: str,
                    transition_type: str = "cross_dissolve") -> str:
        """L2级别生成：视频拼接+转场（转场待底层支持）"""
        logger.info(f"L2生成: {len(video_files)}个片段, 转场={transition_type}")
        return self.generate_L1(video_files, output_path)

    def generate_L3(self, clips: List[Dict], output_path: str) -> str:
        """L3级别生成：含特效+关键帧（待底层支持）

        Args:
            clips: 片段配置列表，每个元素可含effects/keyframes
        """
        logger.info(f"L3生成: {len(clips)}个片段（含特效/关键帧占位）")
        video_files = [c.get("path") for c in clips if c.get("path")]
        return self.generate_L1(video_files, output_path)

    def get_project_info(self) -> Dict[str, Any]:
        """获取当前工程信息"""
        return {
            "name": self._name,
            "width": self._gen.width,
            "height": self._gen.height,
            "fps": self._gen.fps,
            "video_clips": len(self._video_clips),
            "audio_clips": len(self._audio_clips),
        }


# 便捷函数
def quick_generate_prproj(video_files: List[str], output_path: str,
                          audio_file: str = None) -> str:
    """快速生成Pr工程"""
    cap = PrprojGenerateCapability()
    return cap.generate_L1(video_files, output_path, audio_file)
