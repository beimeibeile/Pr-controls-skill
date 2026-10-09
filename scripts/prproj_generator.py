"""
PRPROJ 工程生成器
生成剪映可导入的 Premiere Pro 工程文件 (.prproj)

.prproj = gzip压缩的XML
剪映专业版3.6+支持导入，兼容能力：
  ✅ 视频/音频片段、多轨道、倍速、旋转缩放
  ❌ 文本样式、关键帧转场、PR特效控件

参考：Premiere Pro 2022 工程格式
"""

import logging
logger = logging.getLogger(__name__)


import os
import gzip
import uuid
from typing import List, Dict, Any
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom


class PRPROJGenerator:
    """PRPROJ工程生成器"""

    def __init__(self, width=1080, height=1920, fps=30):
        self.width = width
        self.height = height
        self.fps = fps
        self.video_clips: List[Dict] = []
        self.audio_clips: List[Dict] = []
        self._object_id = 10

    def _next_id(self) -> int:
        self._object_id += 1
        return self._object_id

    def add_video_clip(self, path: str, start_frame: int, duration_frames: int,
                       track: int = 0, name: str = None):
        """添加视频片段"""
        self.video_clips.append({
            "path": os.path.abspath(path),
            "name": name or os.path.basename(path),
            "start": start_frame,
            "duration": duration_frames,
            "track": track,
        })

    def add_audio_clip(self, path: str, start_frame: int, duration_frames: int,
                       track: int = 0, name: str = None):
        """添加音频片段"""
        self.audio_clips.append({
            "path": os.path.abspath(path),
            "name": name or os.path.basename(path),
            "start": start_frame,
            "duration": duration_frames,
            "track": track,
        })

    def _frames_to_ticks(self, frames: int) -> int:
        """帧转tick（Pr内部时间基，1秒=254016000000 tick）"""
        return int(frames * (254016000000 / self.fps))

    def _build_file_object(self, clip: Dict, is_audio=False) -> Element:
        """构建素材文件对象"""
        obj_id = self._next_id()
        file_elem = Element("File")
        file_elem.set("ObjectID", str(obj_id))
        file_elem.set("ClassID", "ea12d27c-3bd0-470a-8e34-0e0c0a0e0c0a")
        file_elem.set("Version", "20")

        name_elem = SubElement(file_elem, "Name")
        name_elem.text = clip["name"]

        path_elem = SubElement(file_elem, "Path")
        path_elem.text = clip["path"].replace("\\", "/")

        # 媒体特性
        media = SubElement(file_elem, "Media")
        if not is_audio:
            video = SubElement(media, "Video")
            sample = SubElement(video, "SampleCharacteristics")
            SubElement(sample, "Width").text = str(self.width)
            SubElement(sample, "Height").text = str(self.height)
            rate = SubElement(sample, "Rate")
            SubElement(rate, "Timebase").text = str(self.fps)
            SubElement(rate, "NTSC").text = "FALSE"
            SubElement(sample, "PixelAspectRatio").text = "square"
        else:
            audio = SubElement(media, "Audio")
            sample = SubElement(audio, "SampleCharacteristics")
            SubElement(sample, "SampleRate").text = "48000"
            SubElement(sample, "BitDepth").text = "16"

        return file_elem, obj_id

    def _build_clipitem(self, clip: Dict, file_id: int, is_audio=False) -> Element:
        """构建轨道片段对象"""
        clipitem = Element("ClipItem")
        clipitem.set("ObjectID", str(self._next_id()))
        clipitem.set("ClassID", "ea12d27c-3bd0-470a-8e34-0e0c0a0e0c0b")
        clipitem.set("Version", "20")

        SubElement(clipitem, "Name").text = clip["name"]
        SubElement(clipitem, "Enabled").text = "TRUE"

        # 时间信息
        start_ticks = self._frames_to_ticks(clip["start"])
        dur_ticks = self._frames_to_ticks(clip["duration"])
        SubElement(clipitem, "Start").text = str(start_ticks)
        SubElement(clipitem, "End").text = str(start_ticks + dur_ticks)
        SubElement(clipitem, "In").text = "0"
        SubElement(clipitem, "Out").text = str(dur_ticks)

        # 引用素材
        file_ref = SubElement(clipitem, "File")
        file_ref.set("ObjectID", str(file_id))

        return clipitem

    def generate_xml(self) -> str:
        """生成PRPROJ XML字符串"""
        root = Element("PremiereData")
        root.set("Version", "3")

        # 关键：PremiereData下第一个节点是Project ObjectRef引用
        project_ref = SubElement(root, "Project")
        project_ref.set("ObjectRef", "1")

        # Project定义
        project = SubElement(root, "Project")
        project.set("ObjectID", "1")
        project.set("ClassID", "62ad66dd-0dcd-42da-a660-6d8fbde94876")
        project.set("Version", "36")

        proj_node = SubElement(project, "Node")
        proj_node.set("Version", "1")

        proj_props = SubElement(proj_node, "Properties")
        proj_props.set("Version", "1")

        # 工程名称
        SubElement(proj_props, "Name").text = "Generated Project"

        # Children
        children = SubElement(proj_node, "Children")
        children.set("Version", "1")

        # Sequence
        sequence = SubElement(children, "Sequence")
        seq_id = self._next_id()
        sequence.set("ObjectID", str(seq_id))
        sequence.set("ClassID", "62ad66dd-0dcd-42da-a660-6d8fbde94877")
        sequence.set("Version", "36")

        seq_node = SubElement(sequence, "Node")
        seq_node.set("Version", "1")

        seq_props = SubElement(seq_node, "Properties")
        seq_props.set("Version", "1")
        SubElement(seq_props, "Name").text = "Sequence 01"

        # 序列设置
        seq_data = SubElement(seq_props, "SequenceData")
        seq_data.set("Version", "1")
        SubElement(seq_data, "Timebase").text = str(self.fps)
        SubElement(seq_data, "NTSC").text = "FALSE"

        video_format = SubElement(seq_data, "VideoFormat")
        SubElement(video_format, "Width").text = str(self.width)
        SubElement(video_format, "Height").text = str(self.height)
        SubElement(video_format, "PixelAspectRatio").text = "square"
        rate = SubElement(video_format, "Rate")
        SubElement(rate, "Timebase").text = str(self.fps)
        SubElement(rate, "NTSC").text = "FALSE"

        # 序列Children（轨道）
        seq_children = SubElement(seq_node, "Children")
        seq_children.set("Version", "1")

        # 视频轨道
        max_video_track = max([c["track"] for c in self.video_clips], default=0)
        for track_idx in range(max_video_track + 1):
            track_elem = SubElement(seq_children, "Track")
            track_elem.set("ObjectID", str(self._next_id()))
            track_elem.set("ClassID", "62ad66dd-0dcd-42da-a660-6d8fbde94878")
            track_elem.set("Version", "20")
            SubElement(track_elem, "Name").text = f"Video {track_idx + 1}"

            track_children = SubElement(track_elem, "Children")
            track_children.set("Version", "1")

            # 该轨道上的片段
            track_clips = [c for c in self.video_clips if c["track"] == track_idx]
            for clip in track_clips:
                file_obj, file_id = self._build_file_object(clip, is_audio=False)
                # 文件对象放在Project的Children中
                children.append(file_obj)
                track_children.append(self._build_clipitem(clip, file_id, is_audio=False))

        # 音频轨道
        if self.audio_clips:
            max_audio_track = max([c["track"] for c in self.audio_clips], default=0)
            for track_idx in range(max_audio_track + 1):
                track_elem = SubElement(seq_children, "Track")
                track_elem.set("ObjectID", str(self._next_id()))
                track_elem.set("ClassID", "62ad66dd-0dcd-42da-a660-6d8fbde94879")
                track_elem.set("Version", "20")
                SubElement(track_elem, "Name").text = f"Audio {track_idx + 1}"

                track_children = SubElement(track_elem, "Children")
                track_children.set("Version", "1")

                track_clips = [c for c in self.audio_clips if c["track"] == track_idx]
                for clip in track_clips:
                    file_obj, file_id = self._build_file_object(clip, is_audio=True)
                    children.append(file_obj)
                    track_children.append(self._build_clipitem(clip, file_id, is_audio=True))

        # 美化XML
        rough = tostring(root, encoding="unicode")
        pretty = minidom.parseString(rough).toprettyxml(indent="  ", encoding="UTF-8")
        return pretty.decode("utf-8") if isinstance(pretty, bytes) else pretty

    def save(self, filepath: str):
        """保存为.prproj文件（gzip压缩XML）"""
        xml_content = self.generate_xml()

        # gzip压缩
        with gzip.open(filepath, "wb", compresslevel=9) as f:
            f.write(xml_content.encode("utf-8"))

        size = os.path.getsize(filepath)
        logger.info(f"✅ 已保存: {filepath} ({size} bytes)")
        return filepath


# ============= 分级测试工程生成 =============

def generate_prproj_L1(output_dir: str, video_path: str):
    """L1: 单视频片段"""
    gen = PRPROJGenerator()
    gen.add_video_clip(video_path, 0, 150, track=0)
    return gen.save(os.path.join(output_dir, "test_L1_single_video.prproj"))


def generate_prproj_L2(output_dir: str, video_path: str, audio_path: str):
    """L2: 视频+音频"""
    gen = PRPROJGenerator()
    gen.add_video_clip(video_path, 0, 150, track=0)
    gen.add_audio_clip(audio_path, 0, 150, track=0)
    return gen.save(os.path.join(output_dir, "test_L2_video_audio.prproj"))


def generate_prproj_L3(output_dir: str, video1: str, video2: str):
    """L3: 多轨道（画中画）"""
    gen = PRPROJGenerator()
    gen.add_video_clip(video1, 0, 150, track=0, name="background")
    gen.add_video_clip(video2, 30, 90, track=1, name="pip")
    return gen.save(os.path.join(output_dir, "test_L3_multitrack.prproj"))


if __name__ == "__main__":
    output_dir = r"D:\DobaoWork_Project\Ai_Video_Editor\prxml_test"
    os.makedirs(output_dir, exist_ok=True)

    test_video = r"D:\DobaoWork_Project\Ai_Video_Editor\material\jianying out\1006-01.png"
    test_audio = r"D:\DobaoWork_Project\Ai_Video_Editor\doubao_hit_v3\sfx\弹弓发射.mp3"

    logger.info("=" * 60)
    logger.info("PRPROJ 分级兼容性测试工程生成")
    logger.info("=" * 60)

    generate_prproj_L1(output_dir, test_video)
    if os.path.exists(test_audio):
        generate_prproj_L2(output_dir, test_video, test_audio)
    generate_prproj_L3(output_dir, test_video, test_video)

    logger.info(f"\n✅ 测试工程已生成到: {output_dir}")
    logger.info("请在剪映中导入测试（导入工程 → 选择.prproj文件）")
