#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P2-6阶段3-4：Pr工程(.prproj) → 剪映工程 端到端转换工具
支持简单工程格式（Node>Children>Track>Children>ClipItem）
转换内容：序列设置、视频轨道、片段、特效、转场、关键帧
"""
import logging
import gzip
import json
import os
import sys
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# 路径配置
SKILL_ROOT = r"C:\Users\Administrator\AppData\Local\Doubao\User Data\Default\.doubao\agent_mode\workspace\.user_skills"
JY_SKILL = os.path.join(SKILL_ROOT, "jianying-editor")
AVE_SKILL = os.path.join(SKILL_ROOT, "ai-video-editor")
sys.path.insert(0, os.path.join(JY_SKILL, "scripts"))
sys.path.insert(0, os.path.join(AVE_SKILL, "scripts"))

from jy_wrapper import JyProject
from jianying_effect_api import JianyingEffectAPI

# Pr时间单位：1秒 = 254016000000 tick
PR_TICK_PER_SECOND = 254016000000

# Pr→剪映特效映射（v1.2扩展版）
PR_TO_JIANYING_EFFECTS = {
    # 基础变换
    "0": None,           # 变换 - 剪映用关键帧实现
    "1": "裁剪",          # Crop
    "2": "画面稳定",      # Stabilize
    # 模糊与锐化
    "7": "模糊",          # Gaussian Blur
    "8": "方向模糊",      # Directional Blur
    "9": "径向模糊",      # Radial Blur
    "10": "锐化",         # Sharpen
    # 颜色校正
    "11": None,           # 亮度对比度 - 剪映用调节实现
    "13": None,           # 色彩平衡 - 剪映用调节实现
    "14": None,           # 色相饱和度 - 剪映用调节实现
    "15": None,           # 曲线 - 剪映用调节实现
    "16": "黑白",         # Black & White
    "17": "反色",         # Invert
    "19": "复古",         # Vintage
    "20": "胶片",         # Film
    # 抠像与透明
    "30": None,           # 色度键 - 剪映用色度抠图
    "31": None,           # 亮度键 - 剪映用亮度抠图
    "32": None,           # 差异遮罩 - 剪映用智能抠图
    # 扭曲与变形
    "40": "球面化",       # Spherize
    "41": "镜像",         # Mirror
    "42": "扭曲",         # Twirl
    "43": "波纹",         # Ripple
    "44": "挤压",         # Pinch
    "45": "膨胀",         # Bulge
    # 光效
    "50": "光晕",         # Lens Flare
    "51": "光斑",         # Light Leak
    "52": "辉光",         # Glow
    "53": "镜头光晕",     # Camera Lens Blur
    "54": "光晕",         # Lens Flare (重复)
    "55": "闪电",         # Lightning
    "56": "炫光",         # Glare
    # 噪点与颗粒
    "60": "噪点",         # Noise
    "61": "颗粒",         # Grain
    "62": "灰尘",         # Dust
    "63": "划痕",         # Scratches
    # 风格化
    "70": "卡通",         # Cartoon
    "71": "油画",         # Oil Paint
    "72": "水彩",         # Watercolor
    "73": "素描",         # Sketch
    "74": "像素化",       # Pixelate
    "75": "马赛克",       # Mosaic
    "76": "浮雕",         # Emboss
    "77": "查找边缘",     # Find Edges
    "78": "阈值",         # Threshold
    "79": "海报化",       # Posterize
    # 时间
    "80": None,           # 时间重映射 - 剪映用变速实现
    "81": None,           # 抽帧 - 剪映用变速实现
    # 转场（在特效中也可能出现）
    "90": "溶解",         # Block Dissolve
    "92": "擦除",         # Linear Wipe
    "94": "百叶窗",       # Venetian Blinds
    "96": "圆形展开",     # Iris Round
    "98": "菱形展开",     # Iris Diamond
    # 其他
    "100": "故障",        # Glitch
    "101": "色差",        # Chromatic Aberration
    "102": "暗角",        # Vignette
    "103": "边框",        # Border
    "104": "阴影",        # Drop Shadow
}


def tick_to_seconds(tick_str: str) -> float:
    """Pr tick → 秒"""
    try:
        return int(tick_str) / PR_TICK_PER_SECOND
    except (ValueError, TypeError):
        return 0.0


def parse_prproj(filepath: str) -> Dict[str, Any]:
    """解析.prproj文件，返回结构化数据"""
    result = {
        "project_name": "",
        "sequences": [],
        "media_files": [],
        "effects_found": set(),
        "transitions_found": set(),
    }

    with gzip.open(filepath, 'rb') as f:
        root = ET.fromstring(f.read())

    # 项目名称
    project_name_elem = root.find(".//ProjectName")
    if project_name_elem is not None and project_name_elem.text:
        result["project_name"] = project_name_elem.text

    # 解析所有序列
    for seq_elem in root.iter("Sequence"):
        seq_data = parse_sequence(seq_elem)
        if seq_data and seq_data.get("tracks"):
            result["sequences"].append(seq_data)

    # 收集特效/转场类型
    for vft in root.iter("VideoFilterType"):
        if vft.text:
            result["effects_found"].add(vft.text.strip())
    for vtt in root.iter("VideoTransitionType"):
        if vtt.text:
            result["transitions_found"].add(vtt.text.strip())

    result["effects_found"] = list(result["effects_found"])
    result["transitions_found"] = list(result["transitions_found"])

    return result


def parse_sequence(seq_elem: ET.Element) -> Optional[Dict[str, Any]]:
    """解析单个序列"""
    seq_data = {
        "name": "",
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "tracks": [],
    }

    # 序列名称
    name_elem = seq_elem.find(".//Name")
    if name_elem is not None and name_elem.text:
        seq_data["name"] = name_elem.text

    # 分辨率
    width_elem = seq_elem.find(".//Width")
    height_elem = seq_elem.find(".//Height")
    if width_elem is not None and width_elem.text:
        seq_data["width"] = int(width_elem.text)
    if height_elem is not None and height_elem.text:
        seq_data["height"] = int(height_elem.text)

    # 帧率（Timebase可能是fps值，也可能是每帧tick数）
    timebase_elem = seq_elem.find(".//Timebase")
    if timebase_elem is not None and timebase_elem.text:
        try:
            timebase = int(timebase_elem.text)
            if timebase < 1000:
                # Timebase直接是fps值（如30）
                seq_data["fps"] = timebase
            else:
                # Timebase是每帧tick数
                seq_data["fps"] = int(PR_TICK_PER_SECOND / timebase)
        except (ValueError, ZeroDivisionError):
            pass

    # 解析轨道（旧格式：Node > Children > Track）
    node_elem = seq_elem.find("Node")
    if node_elem is not None:
        children_elem = node_elem.find("Children")
        if children_elem is not None:
            for track_elem in children_elem.findall("Track"):
                track_data = parse_track(track_elem)
                if track_data:
                    seq_data["tracks"].append(track_data)

    return seq_data if seq_data["tracks"] else None


def parse_track(track_elem: ET.Element) -> Optional[Dict[str, Any]]:
    """解析单个轨道"""
    track_data = {
        "track_type": "video",
        "clips": [],
    }

    # 解析片段
    children_elem = track_elem.find("Children")
    if children_elem is not None:
        for clip_elem in children_elem.findall("ClipItem"):
            clip_data = parse_clip(clip_elem)
            if clip_data:
                track_data["clips"].append(clip_data)

    # 根据媒体文件扩展名判断轨道类型（Pr工程Track无Class属性）
    audio_exts = ('.mp3', '.wav', '.aac', '.m4a', '.flac', '.ogg', '.wma', '.aiff', '.au')
    video_exts = ('.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v')
    if track_data["clips"]:
        first_media = track_data["clips"][0].get("media_path", "").lower()
        if any(first_media.endswith(ext) for ext in audio_exts):
            track_data["track_type"] = "audio"
        elif any(first_media.endswith(ext) for ext in video_exts):
            track_data["track_type"] = "video"
        # 图片/其他默认video

    return track_data if track_data["clips"] else None


def parse_clip(clip_elem: ET.Element) -> Dict[str, Any]:
    """解析单个片段"""
    clip_data = {
        "name": "",
        "start": 0.0,
        "end": 0.0,
        "duration": 0.0,
        "in_point": 0.0,
        "out_point": 0.0,
        "media_path": "",
        "effects": [],
        "transitions": [],
        "keyframes": [],
        "texts": [],
        "speed": 1.0,
    }

    # 片段名称
    name_elem = clip_elem.find("Name")
    if name_elem is not None and name_elem.text:
        clip_data["name"] = name_elem.text

    # 时间（单位tick）
    for field in ["Start", "End", "In", "Out"]:
        elem = clip_elem.find(field)
        if elem is not None and elem.text:
            seconds = tick_to_seconds(elem.text)
            if field == "Start":
                clip_data["start"] = seconds
            elif field == "End":
                clip_data["end"] = seconds
            elif field == "In":
                clip_data["in_point"] = seconds
            elif field == "Out":
                clip_data["out_point"] = seconds

    clip_data["duration"] = clip_data["end"] - clip_data["start"]

    # 媒体文件路径
    file_elem = clip_elem.find(".//File")
    if file_elem is not None:
        path_url = file_elem.find("PathURL")
        if path_url is not None and path_url.text:
            clip_data["media_path"] = path_url.text

    # 特效
    for filter_elem in clip_elem.iter("VideoFilterComponent"):
        effect_data = parse_effect(filter_elem)
        if effect_data:
            clip_data["effects"].append(effect_data)

    # 转场
    for trans_elem in clip_elem.iter("VideoTransitionComponent"):
        trans_data = parse_transition(trans_elem)
        if trans_data:
            clip_data["transitions"].append(trans_data)

    # 关键帧（从特效参数中提取）
    for filter_elem in clip_elem.iter("VideoFilterComponent"):
        kfs = parse_keyframes(filter_elem)
        clip_data["keyframes"].extend(kfs)

    # 文字/字幕（Pr Title或Text元素）
    for title_elem in clip_elem.iter("Title"):
        text_data = parse_text(title_elem)
        if text_data:
            clip_data["texts"].append(text_data)
    for text_elem in clip_elem.iter("Text"):
        text_data = parse_text(text_elem)
        if text_data:
            clip_data["texts"].append(text_data)

    # 速度/变速（Pr Speed元素）
    speed_elem = clip_elem.find("Speed")
    if speed_elem is not None and speed_elem.text:
        try:
            clip_data["speed"] = float(speed_elem.text)
        except (ValueError, TypeError):
            pass

    return clip_data


def parse_text(text_elem: ET.Element) -> Optional[Dict[str, Any]]:
    """解析文字/字幕节点"""
    text_data = {
        "content": "",
        "font_size": 48,
        "font_color": "#FFFFFF",
        "position_x": 0.5,
        "position_y": 0.8,
        "alignment": "center",
    }

    # 文字内容
    for tag in ["Text", "Content", "String", "Value"]:
        elem = text_elem.find(tag)
        if elem is not None and elem.text:
            text_data["content"] = elem.text.strip()
            break

    # 字体大小
    size_elem = text_elem.find(".//FontSize")
    if size_elem is not None and size_elem.text:
        try:
            text_data["font_size"] = int(float(size_elem.text))
        except (ValueError, TypeError):
            pass

    # 字体颜色
    color_elem = text_elem.find(".//FillColor")
    if color_elem is not None:
        r = color_elem.find("Red")
        g = color_elem.find("Green")
        b = color_elem.find("Blue")
        if r is not None and g is not None and b is not None:
            try:
                ri = int(float(r.text) * 255) if r.text else 255
                gi = int(float(g.text) * 255) if g.text else 255
                bi = int(float(b.text) * 255) if b.text else 255
                text_data["font_color"] = f"#{ri:02X}{gi:02X}{bi:02X}"
            except (ValueError, TypeError):
                pass

    # 位置
    pos_elem = text_elem.find(".//Position")
    if pos_elem is not None and pos_elem.text:
        try:
            parts = pos_elem.text.split(",")
            if len(parts) >= 2:
                text_data["position_x"] = float(parts[0].strip())
                text_data["position_y"] = float(parts[1].strip())
        except (ValueError, TypeError):
            pass

    return text_data if text_data["content"] else None


def parse_effect(filter_elem: ET.Element) -> Optional[Dict[str, Any]]:
    """解析特效节点"""
    effect_data = {
        "filter_type": "",
        "name": "",
        "params": [],
        "is_transition": False,
    }

    # 特效类型
    type_elem = filter_elem.find("VideoFilterType")
    if type_elem is not None and type_elem.text:
        effect_data["filter_type"] = type_elem.text.strip()

    # 特效名称
    name_elem = filter_elem.find("Name")
    if name_elem is not None and name_elem.text:
        effect_data["name"] = name_elem.text

    # 判断是否为转场
    if filter_elem.tag == "VideoTransitionComponent":
        effect_data["is_transition"] = True

    return effect_data if effect_data["filter_type"] else None


def parse_transition(trans_elem: ET.Element) -> Optional[Dict[str, Any]]:
    """解析转场节点"""
    trans_data = {
        "transition_type": "",
        "name": "",
        "duration": 0.0,
    }

    # 转场类型
    type_elem = trans_elem.find("VideoTransitionType")
    if type_elem is not None and type_elem.text:
        trans_data["transition_type"] = type_elem.text.strip()

    # 转场名称
    name_elem = trans_elem.find("Name")
    if name_elem is not None and name_elem.text:
        trans_data["name"] = name_elem.text

    # 转场时长
    duration_elem = trans_elem.find("Duration")
    if duration_elem is not None and duration_elem.text:
        trans_data["duration"] = tick_to_seconds(duration_elem.text)

    return trans_data if trans_data["transition_type"] else None


# Pr→剪映转场映射（v1.2扩展版）
PR_TO_JIANYING_TRANSITIONS = {
    # 溶解类
    "0": "叠化",          # Cross Dissolve
    "1": "淡入淡出",       # Dip to Black
    "2": "白场过渡",       # Dip to White
    "3": "叠加溶解",       # Additive Dissolve
    "4": "非叠加溶解",     # Non-Additive Dissolve
    "5": "随机反转",       # Random Invert
    "6": "抖动溶解",       # Dither Dissolve
    # 擦除类
    "10": "擦除",         # Band Wipe
    "11": "擦除",         # Wipe
    "12": "径向擦除",      # Radial Wipe
    "13": "渐变擦除",      # Gradient Wipe
    "14": "百叶窗",        # Venetian Blinds (重复)
    "15": "棋盘擦除",      # Checker Wipe
    "16": "插入擦除",      # Insert Wipe
    "17": "油漆飞溅",      # Paint Splatter
    "18": "螺旋框",        # Spiral Boxes
    "19": "楔形擦除",      # Wedge Wipe
    "20": "Z形擦除",       # Zig-Zag Blocks
    # 3D运动
    "30": "翻页",         # Flip Over
    "31": "折叠",         # Fold Up
    "32": "滚动",         # Roll Away
    "33": "旋转",         # Spin
    "34": "旋转离开",      # Spin Away
    "35": "立方体旋转",    # Cube Spin
    "36": "门",           # Doors
    "37": "翻转入",        # Flip In
    "38": "翻转出",        # Flip Out
    # 划像类
    "40": "圆形展开",      # Iris Round
    "41": "菱形展开",      # Iris Diamond
    "42": "十字展开",      # Iris Cross
    "43": "星形展开",      # Iris Star
    "44": "形状展开",      # Iris Shapes
    "45": "斜角展开",      # Iris Points
    # 滑动类
    "50": "滑动",         # Sliding Boxes
    "51": "带状滑动",      # Band Slide
    "52": "中心合并",      # Center Merge
    "53": "中心分割",      # Center Split
    "54": "多旋转",        # Multi-Spin
    "55": "推",           # Push
    "56": "斜线滑动",      # Slash Slide
    "57": "滑动",         # Slide
    "58": "分割",         # Split
    "59": "交换",         # Swap
    "60": "漩涡",         # Swirl
    # 缩放类
    "70": "交叉缩放",      # Cross Zoom
    "71": "缩放",         # Zoom
    "72": "缩放轨迹",      # Zoom Trails
    "73": "缩放框",        # Zoom Boxes
    "74": "连续缩放",      # Continuous Zoom
    # 特殊效果
    "90": "溶解",         # Block Dissolve
    "91": "抖动溶解",      # Dither Dissolve (重复)
    "92": "擦除",         # Linear Wipe
    "93": "径向擦除",      # Radial Wipe (重复)
    "94": "百叶窗",        # Venetian Blinds
    "95": "渐变擦除",      # Gradient Wipe (重复)
    "96": "圆形展开",      # Iris Round (重复)
    "97": "菱形展开",      # Iris Diamond (重复)
    "98": "菱形展开",      # Iris Diamond (重复)
    "99": "故障",         # Glitch
}


def parse_keyframes(filter_elem: ET.Element) -> List[Dict[str, Any]]:
    """从特效参数中提取关键帧数据"""
    keyframes = []
    # Pr关键帧存储在Parameter > Keyframe中
    for param_elem in filter_elem.iter("Parameter"):
        param_name = param_elem.get("Name", "")
        # 映射Pr参数名到剪映关键帧属性
        prop_map = {
            "Position": "position",
            "Scale": "scale",
            "Rotation": "rotation",
            "Opacity": "alpha",
            "Anchor Point": "position",
        }
        jy_prop = prop_map.get(param_name, "")
        if not jy_prop:
            continue

        for kf_elem in param_elem.iter("Keyframe"):
            time_elem = kf_elem.find("Time")
            value_elem = kf_elem.find("Value")
            if time_elem is not None and time_elem.text:
                kf_data = {
                    "property": jy_prop,
                    "time": tick_to_seconds(time_elem.text),
                    "value": 0.0,
                }
                if value_elem is not None and value_elem.text:
                    try:
                        # Pr值可能是"x, y"格式或单值
                        val_str = value_elem.text.strip()
                        if "," in val_str:
                            kf_data["value"] = float(val_str.split(",")[0].strip())
                        else:
                            kf_data["value"] = float(val_str)
                    except (ValueError, TypeError):
                        pass
                keyframes.append(kf_data)

    return keyframes


def create_placeholder_image(path: str, width: int = 1920, height: int = 1080, label: str = "") -> str:
    """创建占位图片（当Pr工程媒体文件不存在时使用）"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        # 生成基于label的颜色
        color_hash = hash(label) % 360
        img = Image.new('RGB', (width, height), (
            int(128 + 64 * (color_hash % 3)),
            int(128 + 64 * ((color_hash // 3) % 3)),
            int(128 + 64 * ((color_hash // 9) % 3))
        ))
        draw = ImageDraw.Draw(img)
        if label:
            try:
                font = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 48)
            except:
                font = ImageFont.load_default()
            text = f"[Pr导入占位]\n{label[:30]}"
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text(((width-tw)//2, (height-th)//2), text, fill=(255,255,255), font=font)
        img.save(path)
        return path
    except Exception as e:
        logger.error(f"    创建占位图失败: {e}")
        return None


def convert_to_jianying(pr_data: Dict[str, Any], output_name: str = None, use_placeholder: bool = True) -> str:
    """将解析后的Pr数据转换为剪映工程"""
    if not pr_data["sequences"]:
        raise ValueError("Pr工程中没有可转换的序列")

    # 使用第一个序列
    seq = pr_data["sequences"][0]
    draft_name = output_name or f"pr_import_{seq['name'][:20]}"

    logger.info(f"\n=== 转换为剪映工程: {draft_name} ===")
    logger.info(f"  序列: {seq['name']}")
    logger.info(f"  分辨率: {seq['width']}x{seq['height']}")
    logger.info(f"  帧率: {seq['fps']}fps")
    logger.info(f"  轨道数: {len(seq['tracks'])}")

    # 创建剪映工程
    project = JyProject(project_name=draft_name, width=seq['width'], height=seq['height'])
    api = JianyingEffectAPI()

    total_clips = 0
    total_effects = 0
    total_transitions = 0
    total_keyframes = 0
    total_texts = 0
    prev_segment = None  # 用于转场（转场添加在前一个片段上）

    # 转换每个轨道
    for track_idx, track in enumerate(seq["tracks"]):
        track_type = track["track_type"]
        clips = track["clips"]
        logger.info(f"\n  轨道{track_idx+1} ({track_type}): {len(clips)}个片段")

        for clip in clips:
            # 音频片段：添加到音频轨道
            if track_type == "audio":
                media_path = clip["media_path"]
                if not media_path or not os.path.exists(media_path):
                    logger.warning(f"    [SKIP] 音频片段 '{clip['name']}': 媒体文件不存在")
                    continue
                try:
                    seg = project.add_media_safe(
                        media_path,
                        start_time=clip["start"],
                        duration=clip["duration"],
                        track_name="AudioTrack"
                    )
                    if seg:
                        total_clips += 1
                        logger.info(f"    [OK] 音频: {clip['name']}")
                except Exception as e:
                    logger.warning(f"    [SKIP] 音频 {clip['name']}: {e}")
                continue

            # 检查媒体文件是否存在
            media_path = clip["media_path"]
            if not media_path or not os.path.exists(media_path):
                if use_placeholder:
                    # 创建占位图片
                    placeholder_dir = os.path.join(
                        r"C:\Users\Administrator\AppData\Local\JianyingPro\User Data\Projects\com.lveditor.draft",
                        draft_name, "materials"
                    )
                    os.makedirs(placeholder_dir, exist_ok=True)
                    placeholder_name = f"placeholder_{abs(hash(clip['name'])) % 10000}.png"
                    placeholder_path = os.path.join(placeholder_dir, placeholder_name)
                    if create_placeholder_image(placeholder_path, seq['width'], seq['height'], clip['name']):
                        media_path = placeholder_path
                        logger.info(f"    [占位] '{clip['name']}' -> {placeholder_name}")
                    else:
                        continue
                else:
                    logger.warning(f"    [SKIP] 片段 '{clip['name']}': 媒体文件不存在")
                    continue

            # 添加视频片段（每个Pr轨道映射到不同的剪映轨道）
            track_name = f"VideoTrack_{track_idx+1}" if track_idx > 0 else "VideoTrack"
            seg = project.add_media_safe(
                media_path,
                start_time=clip["start"],
                duration=clip["duration"],
                track_name=track_name
            )
            if seg:
                total_clips += 1
                # 应用特效
                for effect in clip["effects"]:
                    pr_type = effect["filter_type"]
                    jy_effect_name = PR_TO_JIANYING_EFFECTS.get(pr_type)
                    if jy_effect_name:
                        try:
                            api.apply_scene_effect(
                                project, jy_effect_name,
                                start=clip["start"],
                                duration=clip["duration"]
                            )
                            total_effects += 1
                            logger.info(f"    [OK] 特效: {jy_effect_name} (Pr类型{pr_type})")
                        except Exception as e:
                            logger.warning(f"    [SKIP] 特效 {jy_effect_name}: {e}")

                # 应用转场（添加在前一个片段上）
                for transition in clip.get("transitions", []):
                    pr_type = transition["transition_type"]
                    jy_trans_name = PR_TO_JIANYING_TRANSITIONS.get(pr_type)
                    if jy_trans_name and prev_segment:
                        try:
                            from pyJianYingDraft import TransitionType
                            trans_enum = TransitionType.from_name(jy_trans_name)
                            trans_dur = int(transition.get("duration", 0.5) * 1000000)
                            prev_segment.add_transition(trans_enum, duration=trans_dur)
                            total_transitions += 1
                            logger.info(f"    [OK] 转场: {jy_trans_name} (Pr类型{pr_type})")
                        except Exception as e:
                            logger.warning(f"    [SKIP] 转场 {jy_trans_name}: {e}")

                # 应用关键帧
                for kf in clip.get("keyframes", []):
                    try:
                        from pyJianYingDraft.keyframe import KeyframeProperty
                        t_us = int(kf.get("time", 0) * 1000000)
                        val = float(kf.get("value", 0))
                        prop = kf.get("property", "")
                        kf_prop = None
                        if prop == "scale":
                            kf_prop = KeyframeProperty.uniform_scale
                        elif prop == "position":
                            kf_prop = KeyframeProperty.position_x
                        elif prop == "rotation":
                            kf_prop = KeyframeProperty.rotation
                        elif prop == "alpha":
                            kf_prop = KeyframeProperty.alpha
                        if kf_prop and val != 0:
                            seg.add_keyframe(kf_prop, t_us, val)
                            total_keyframes += 1
                    except Exception as e:
                        pass

                # 应用文字/字幕
                for text in clip.get("texts", []):
                    try:
                        text_seg = project.add_text(
                            text=text.get("content", ""),
                            start_time=clip["start"],
                            duration=clip["duration"],
                            font_size=text.get("font_size", 48),
                            color=text.get("font_color", "#FFFFFF"),
                        )
                        if text_seg:
                            total_texts += 1
                            logger.info(f"    [OK] 文字: {text.get('content', '')[:20]}")
                    except Exception as e:
                        logger.warning(f"    [SKIP] 文字: {e}")

                prev_segment = seg

    # 保存工程
    project.save()
    logger.info(f"\n=== 转换完成 ===")
    logger.info(f"  工程名: {draft_name}")
    logger.info(f"  转换片段: {total_clips}个")
    logger.info(f"  应用特效: {total_effects}个")
    logger.info(f"  应用转场: {total_transitions}个")
    logger.info(f"  应用关键帧: {total_keyframes}个")
    logger.info(f"  应用文字: {total_texts}个")
    logger.info(f"  发现Pr特效类型: {pr_data['effects_found']}")
    logger.info(f"  发现Pr转场类型: {pr_data['transitions_found']}")

    return draft_name


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Pr工程(.prproj) → 剪映工程 转换工具")
    parser.add_argument("prproj_file", help="输入的.prproj文件路径")
    parser.add_argument("-o", "--output", help="输出剪映工程名称（可选）")
    parser.add_argument("--parse-only", action="store_true", help="仅解析不转换")
    args = parser.parse_args()

    if not os.path.exists(args.prproj_file):
        logger.error(f"错误: 文件不存在 - {args.prproj_file}")
        return

    logger.info("=" * 60)
    logger.info("Pr工程 → 剪映工程 转换工具 v1.0")
    logger.info("=" * 60)

    # 解析Pr工程
    logger.info(f"\n=== 解析Pr工程: {os.path.basename(args.prproj_file)} ===")
    pr_data = parse_prproj(args.prproj_file)

    logger.info(f"  项目名: {pr_data['project_name']}")
    logger.info(f"  序列数: {len(pr_data['sequences'])}")
    for i, seq in enumerate(pr_data['sequences']):
        logger.info(f"    序列{i+1}: {seq['name']} ({seq['width']}x{seq['height']}@{seq['fps']}fps, {len(seq['tracks'])}轨道)")
    logger.info(f"  特效类型: {pr_data['effects_found']}")
    logger.info(f"  转场类型: {pr_data['transitions_found']}")

    if args.parse_only:
        # 保存解析结果为JSON
        json_path = args.prproj_file.replace(".prproj", "_parsed.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(pr_data, f, ensure_ascii=False, indent=2)
        logger.info(f"\n解析结果已保存: {json_path}")
        return

    # 转换为剪映工程
    if pr_data["sequences"]:
        convert_to_jianying(pr_data, args.output)
    else:
        logger.error("\n错误: Pr工程中没有可转换的序列（可能使用了复杂对象引用格式）")
        logger.info("建议: 使用--parse-only查看解析结果，或使用简单格式的Pr工程测试")


if __name__ == "__main__":
    main()
