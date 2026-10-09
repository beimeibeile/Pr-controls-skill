#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P2-6 阶段1: Pr工程(.prproj)解析器
===================================
解析gzip压缩的XML格式.prproj文件，提取：
- 项目元信息
- 序列结构（轨道/片段/时间线）
- 特效信息（VideoFilterComponent）
- 转场信息（VideoTransitionTrackItem）
- 关键帧数据
- 媒体素材引用

输出结构化JSON，为后续Pr→剪映映射转换提供数据基础。
"""

import gzip
import json
import os
import sys
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from collections import Counter


# ============ 数据结构 ============

@dataclass
class PrProjectInfo:
    """项目元信息"""
    name: str = ""
    version: str = ""
    object_count: int = 0
    sequence_count: int = 0
    file_count: int = 0


@dataclass
class PrTrackItem:
    """轨道项（片段）"""
    object_id: str = ""
    class_id: str = ""
    start: int = 0  # 帧
    duration: int = 0  # 帧
    end: int = 0  # 帧
    in_point: int = 0
    out_point: int = 0
    name: str = ""
    has_video: bool = False
    has_audio: bool = False
    effects: List[Dict] = field(default_factory=list)
    transitions: List[Dict] = field(default_factory=list)


@dataclass
class PrTrack:
    """轨道"""
    object_id: str = ""
    class_id: str = ""
    track_type: str = ""  # video / audio
    is_muted: bool = False
    is_locked: bool = False
    items: List[PrTrackItem] = field(default_factory=list)


@dataclass
class PrSequence:
    """序列"""
    object_id: str = ""
    class_id: str = ""
    name: str = ""
    frame_rate: float = 30.0
    width: int = 1920
    height: int = 1080
    duration: int = 0
    tracks: List[PrTrack] = field(default_factory=list)


@dataclass
class PrEffect:
    """特效"""
    object_id: str = ""
    class_id: str = ""
    filter_type: str = ""
    params: List[Dict] = field(default_factory=list)
    has_keyframes: bool = False
    bypass: bool = False


@dataclass
class PrTransition:
    """转场"""
    object_id: str = ""
    class_id: str = ""
    transition_type: str = ""
    duration: int = 0


@dataclass
class PrMediaFile:
    """媒体文件引用"""
    object_id: str = ""
    class_id: str = ""
    name: str = ""
    path: str = ""
    file_type: str = ""  # video / audio / image
    duration: int = 0
    width: int = 0
    height: int = 0


@dataclass
class PrProject:
    """完整Pr工程数据"""
    info: PrProjectInfo = field(default_factory=PrProjectInfo)
    sequences: List[PrSequence] = field(default_factory=list)
    effects: List[PrEffect] = field(default_factory=list)
    transitions: List[PrTransition] = field(default_factory=list)
    media_files: List[PrMediaFile] = field(default_factory=list)
    node_stats: Dict[str, int] = field(default_factory=dict)


# ============ 解析器 ============

class PrprojParser:
    """Pr工程解析器"""

    # ClassID映射
    CLASS_ID_MAP = {
        "62ad66dd-0dcd-42da-a660-6d8fbde94878": "video_track",
        "62ad66dd-0dcd-42da-a660-6d8fbde94879": "audio_track",
        "d10da199-beea-4dd1-b941-ed3a78766d50": "video_filter",
        "3eeaed31-f78e-4144-b8e8-077656517181": "video_transition",
        "8c1e5682-780b-4f9d-9b4a-9b3e4e8c1a2b": "sequence",
        "ea13d5b2-8a09-48e9-9b4a-9b3e4e8c1a2b": "file",
    }

    def __init__(self, prproj_path: str):
        self.prproj_path = prproj_path
        self.root = None
        self.project = PrProject()
        self._object_cache: Dict[str, ET.Element] = {}

    def parse(self) -> PrProject:
        """解析完整工程"""
        # 1. 解压并解析XML
        self.root = self._load_xml()

        # 2. 统计节点
        self._count_nodes()

        # 3. 构建对象缓存
        self._build_object_cache()

        # 4. 解析项目信息
        self._parse_project_info()

        # 5. 解析序列
        self._parse_sequences()

        # 6. 解析特效
        self._parse_effects()

        # 7. 解析转场
        self._parse_transitions()

        # 8. 解析媒体文件
        self._parse_media_files()

        return self.project

    def _load_xml(self) -> ET.Element:
        """加载.prproj文件（gzip+XML）"""
        with gzip.open(self.prproj_path, 'rb') as f:
            xml_content = f.read()
        return ET.fromstring(xml_content)

    def _count_nodes(self):
        """统计所有节点类型"""
        counter = Counter()
        for elem in self.root.iter():
            counter[elem.tag] += 1
        self.project.node_stats = dict(counter.most_common(30))

    def _build_object_cache(self):
        """构建ObjectID到元素的映射"""
        for elem in self.root.iter():
            obj_id = elem.get("ObjectID")
            if obj_id:
                self._object_cache[obj_id] = elem

    def _get_text(self, elem: Optional[ET.Element], tag: str, default: str = "") -> str:
        """安全获取子元素文本"""
        if elem is None:
            return default
        child = elem.find(tag)
        return child.text if child is not None and child.text else default

    def _get_int(self, elem: Optional[ET.Element], tag: str, default: int = 0) -> int:
        """安全获取子元素整数值"""
        val = self._get_text(elem, tag)
        try:
            return int(val) if val else default
        except (ValueError, TypeError):
            return default

    def _get_bool(self, elem: Optional[ET.Element], tag: str, default: bool = False) -> bool:
        """安全获取子元素布尔值"""
        val = self._get_text(elem, tag)
        if val.lower() in ("true", "1", "yes"):
            return True
        if val.lower() in ("false", "0", "no"):
            return False
        return default

    def _parse_project_info(self):
        """解析项目元信息"""
        project_elem = self.root.find("Project")
        if project_elem is None:
            return

        node_elem = project_elem.find("Node")
        if node_elem is not None:
            props = node_elem.find("Properties")
            self.project.info.name = self._get_text(props, "Name", "Unnamed")

        self.project.info.object_count = len(self._object_cache)
        self.project.info.sequence_count = len([
            e for e in self.root.iter("Sequence")
        ])
        self.project.info.file_count = len([
            e for e in self.root.iter("File")
        ])

    # Pr时间单位：tick，1秒=254016000000 tick
    TICK_PER_SECOND = 254016000000

    def _tick_to_seconds(self, tick: int) -> float:
        """tick转换为秒"""
        return tick / self.TICK_PER_SECOND if tick else 0.0

    def _tick_to_frames(self, tick: int, fps: float = 30.0) -> int:
        """tick转换为帧"""
        return int(round(tick / self.TICK_PER_SECOND * fps)) if tick else 0

    def _parse_sequences(self):
        """解析所有序列（只解析有Node子元素的真正序列定义，跳过空引用）"""
        for seq_elem in self.root.iter("Sequence"):
            # 跳过空引用（没有ObjectID且没有子元素）
            if not seq_elem.get("ObjectID") and len(list(seq_elem)) == 0:
                continue
            # 必须有Node子元素才是真正的序列定义
            node_elem = seq_elem.find("Node")
            if node_elem is None:
                continue
            seq = PrSequence()
            seq.object_id = seq_elem.get("ObjectID", "")
            seq.class_id = seq_elem.get("ClassID", "")

            # 序列属性在 Node > Properties 下
            node_elem = seq_elem.find("Node")
            props_elem = node_elem.find("Properties") if node_elem is not None else None

            seq.name = self._get_text(props_elem, "Name", "Sequence")

            # 帧率：Node > Properties > SequenceData > Timebase
            seq_data = props_elem.find("SequenceData") if props_elem is not None else None
            if seq_data is not None:
                timebase = self._get_text(seq_data, "Timebase")
                if timebase:
                    try:
                        seq.frame_rate = float(timebase)
                    except ValueError:
                        pass
                # 分辨率：SequenceData > VideoFormat > Width/Height
                video_format = seq_data.find("VideoFormat")
                if video_format is not None:
                    seq.width = self._get_int(video_format, "Width", 1920)
                    seq.height = self._get_int(video_format, "Height", 1080)

            # 解析轨道（在 Node > Children > Track 下）
            children_elem = node_elem.find("Children") if node_elem is not None else None
            if children_elem is not None:
                self._parse_tracks_from_children(children_elem, seq)
            else:
                # 兼容：直接在Sequence下找Track
                self._parse_tracks(seq_elem, seq)

            self.project.sequences.append(seq)

    def _parse_tracks_from_children(self, children_elem: ET.Element, seq: PrSequence):
        """从Children元素解析轨道"""
        for track_elem in children_elem.findall("Track"):
            track = self._parse_single_track(track_elem)
            seq.tracks.append(track)

    def _parse_tracks(self, seq_elem: ET.Element, seq: PrSequence):
        """解析序列中的轨道（兼容模式）"""
        for track_elem in seq_elem.iter("Track"):
            track = self._parse_single_track(track_elem)
            seq.tracks.append(track)

    def _parse_single_track(self, track_elem: ET.Element) -> PrTrack:
        """解析单个轨道"""
        track = PrTrack()
        track.object_id = track_elem.get("ObjectID", "")
        track.class_id = track_elem.get("ClassID", "")
        track.name = self._get_text(track_elem, "Name", "")

        # 判断轨道类型：通过ClassID最后几位
        class_id = track.class_id.lower()
        if class_id.endswith("4878") or "4d37a0c" in class_id:
            track.track_type = "video"
        elif class_id.endswith("4879"):
            track.track_type = "audio"
        else:
            # 通过子元素判断
            if track_elem.find(".//VideoComponent") is not None:
                track.track_type = "video"
            elif track_elem.find(".//AudioComponent") is not None:
                track.track_type = "audio"
            elif track.name.lower().startswith("video") or "视频" in track.name:
                track.track_type = "video"
            elif track.name.lower().startswith("audio") or "音频" in track.name:
                track.track_type = "audio"
            else:
                track.track_type = "unknown"

        track.is_muted = self._get_bool(track_elem, "IsMuted")
        track.is_locked = self._get_bool(track_elem, "IsLocked")

        # 解析轨道项（在 Track > Children > ClipItem 下）
        children_elem = track_elem.find("Children")
        if children_elem is not None:
            self._parse_clip_items(children_elem, track)
        else:
            # 兼容：直接找ClipItem
            self._parse_clip_items(track_elem, track)

        return track

    def _parse_clip_items(self, parent_elem: ET.Element, track: PrTrack):
        """解析轨道中的片段项（ClipItem）"""
        for item_elem in parent_elem.iter("ClipItem"):
            # 跳过嵌套的ClipItem
            if item_elem.find(".//ClipItem") is not None:
                continue

            item = PrTrackItem()
            item.object_id = item_elem.get("ObjectID", "")
            item.class_id = item_elem.get("ClassID", "")
            item.name = self._get_text(item_elem, "Name", "")

            # 时间信息（单位：tick）
            start_tick = self._get_int(item_elem, "Start")
            end_tick = self._get_int(item_elem, "End")
            in_tick = self._get_int(item_elem, "In")
            out_tick = self._get_int(item_elem, "Out")

            # 转换为帧（基于30fps，后续可根据序列帧率调整）
            item.start = self._tick_to_frames(start_tick)
            item.end = self._tick_to_frames(end_tick)
            item.duration = item.end - item.start
            item.in_point = self._tick_to_frames(in_tick)
            item.out_point = self._tick_to_frames(out_tick)

            # 组件检测
            item.has_video = item_elem.find(".//VideoComponent") is not None
            item.has_audio = item_elem.find(".//AudioComponent") is not None

            # 解析片段上的特效
            self._parse_item_effects(item_elem, item)

            # 解析转场
            self._parse_item_transitions(item_elem, item)

            track.items.append(item)

    def _parse_item_effects(self, item_elem: ET.Element, item: PrTrackItem):
        """解析片段上的特效"""
        for filter_elem in item_elem.iter("VideoFilterComponent"):
            effect = self._parse_single_effect(filter_elem)
            item.effects.append(asdict(effect))

    def _parse_item_transitions(self, item_elem: ET.Element, item: PrTrackItem):
        """解析片段上的转场"""
        for trans_elem in item_elem.iter("VideoTransitionTrackItem"):
            trans = PrTransition()
            trans.object_id = trans_elem.get("ObjectID", "")
            trans.class_id = trans_elem.get("ClassID", "")
            trans.transition_type = self._get_text(trans_elem, "TransitionType", "unknown")
            trans.duration = self._get_int(trans_elem, "Duration")
            item.transitions.append(asdict(trans))

    def _parse_single_effect(self, filter_elem: ET.Element) -> PrEffect:
        """解析单个特效节点"""
        effect = PrEffect()
        effect.object_id = filter_elem.get("ObjectID", "")
        effect.class_id = filter_elem.get("ClassID", "")
        effect.filter_type = self._get_text(filter_elem, "VideoFilterType", "unknown")
        effect.bypass = self._get_bool(filter_elem, "Bypass")

        # 解析参数
        params_elem = filter_elem.find("Params")
        if params_elem is not None:
            for param_elem in params_elem.findall("Parameter"):
                param = {
                    "id": self._get_text(param_elem, "ParameterID"),
                    "control_type": self._get_text(param_elem, "ParameterControlType"),
                    "current_value": self._get_text(param_elem, "CurrentValue"),
                    "upper_bound": self._get_text(param_elem, "UpperBound"),
                    "lower_bound": self._get_text(param_elem, "LowerBound"),
                    "is_time_varying": self._get_bool(param_elem, "IsTimeVarying"),
                    "has_keyframe": param_elem.find("Keyframes") is not None,
                }
                effect.params.append(param)
                if param["is_time_varying"] or param["has_keyframe"]:
                    effect.has_keyframes = True

        return effect

    def _parse_effects(self):
        """解析全局特效（不在片段上的独立特效节点）"""
        # 已经在_parse_item_effects中解析了片段上的特效
        # 这里统计全局特效数量
        all_filters = list(self.root.iter("VideoFilterComponent"))
        self.project.info.object_count  # 已统计

    def _parse_transitions(self):
        """解析全局转场"""
        for trans_elem in self.root.iter("VideoTransitionTrackItem"):
            # 只处理直接的转场项（不在TrackItem内部的）
            parent = trans_elem
            # 简单收集所有转场
            trans = PrTransition()
            trans.object_id = trans_elem.get("ObjectID", "")
            trans.class_id = trans_elem.get("ClassID", "")
            trans.transition_type = self._get_text(trans_elem, "TransitionType", "unknown")
            trans.duration = self._get_int(trans_elem, "Duration")
            self.project.transitions.append(trans)

    def _parse_media_files(self):
        """解析媒体文件引用"""
        for file_elem in self.root.iter("File"):
            media = PrMediaFile()
            media.object_id = file_elem.get("ObjectID", "")
            media.class_id = file_elem.get("ClassID", "")
            media.name = self._get_text(file_elem, "Name", "")
            media.path = self._get_text(file_elem, "Path", "")
            media.duration = self._get_int(file_elem, "Duration")
            media.width = self._get_int(file_elem, ".//Width")
            media.height = self._get_int(file_elem, ".//Height")

            # 判断文件类型
            if file_elem.find(".//VideoComponent") is not None:
                media.file_type = "video"
            elif file_elem.find(".//AudioComponent") is not None:
                media.file_type = "audio"
            else:
                media.file_type = "unknown"

            self.project.media_files.append(media)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于JSON序列化）"""
        return {
            "info": asdict(self.project.info),
            "sequences": [asdict(s) for s in self.project.sequences],
            "effects": [asdict(e) for e in self.project.effects],
            "transitions": [asdict(t) for t in self.project.transitions],
            "media_files": [asdict(m) for m in self.project.media_files],
            "node_stats": self.project.node_stats,
        }

    def to_json(self, indent: int = 2) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def save_json(self, output_path: str):
        """保存为JSON文件"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(self.to_json())

    def print_summary(self):
        """打印解析摘要"""
        info = self.project.info
        print(f"=== Pr工程解析摘要 ===")
        print(f"项目名称: {info.name}")
        print(f"对象总数: {info.object_count}")
        print(f"序列数: {info.sequence_count}")
        print(f"媒体文件数: {info.file_count}")
        print(f"特效数: {len(self.project.effects)}")
        print(f"转场数: {len(self.project.transitions)}")
        print()

        for i, seq in enumerate(self.project.sequences):
            print(f"序列[{i}]: {seq.name} ({seq.width}x{seq.height}, {seq.frame_rate}fps)")
            video_tracks = [t for t in seq.tracks if t.track_type == "video"]
            audio_tracks = [t for t in seq.tracks if t.track_type == "audio"]
            total_items = sum(len(t.items) for t in seq.tracks)
            print(f"  视频轨道: {len(video_tracks)}, 音频轨道: {len(audio_tracks)}, 片段总数: {total_items}")

            for j, track in enumerate(seq.tracks):
                if track.items:
                    effects_count = sum(len(item.effects) for item in track.items)
                    transitions_count = sum(len(item.transitions) for item in track.items)
                    print(f"    轨道[{j}] {track.track_type}: {len(track.items)}片段, {effects_count}特效, {transitions_count}转场")

        print()
        print(f"节点统计 TOP15:")
        for node, count in sorted(self.project.node_stats.items(), key=lambda x: -x[1])[:15]:
            print(f"  {node}: {count}")


# ============ 命令行入口 ============

def main():
    if len(sys.argv) < 2:
        print("用法: python prproj_parser.py <prproj文件路径> [输出JSON路径]")
        print("示例: python prproj_parser.py test.prproj output.json")
        sys.exit(1)

    prproj_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    if not os.path.exists(prproj_path):
        print(f"错误: 文件不存在 - {prproj_path}")
        sys.exit(1)

    print(f"正在解析: {prproj_path}")
    parser = PrprojParser(prproj_path)
    project = parser.parse()
    parser.print_summary()

    if output_path:
        parser.save_json(output_path)
        print(f"\n已保存JSON: {output_path}")
    else:
        # 默认保存到同目录
        default_output = os.path.splitext(prproj_path)[0] + "_parsed.json"
        parser.save_json(default_output)
        print(f"\n已保存JSON: {default_output}")


if __name__ == "__main__":
    main()
