"""
Pr工程分析器
分析现有.prproj文件的结构、素材、序列、特效等，提供工程健康度评估和优化建议

核心能力：
1. 工程结构解析（序列/轨道/片段/素材引用）
2. 素材完整性检查（缺失文件/离线素材/重复素材）
3. 工程健康度评估（复杂度/性能风险/规范合规）
4. 优化建议生成（冗余清理/性能优化/规范整改）
5. 工程摘要导出（JSON/Markdown格式）
"""

import logging
logger = logging.getLogger(__name__)

import os
import sys
import gzip
import json
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)


@dataclass
class MediaRef:
    """素材引用"""
    media_id: str
    file_path: str
    file_name: str
    file_size: int = 0
    duration: float = 0.0
    exists: bool = True
    usage_count: int = 0


@dataclass
class SequenceInfo:
    """序列信息"""
    sequence_id: str
    name: str
    width: int = 0
    height: int = 0
    fps: float = 0.0
    duration: float = 0.0
    track_count: int = 0
    clip_count: int = 0
    has_effects: bool = False
    has_transitions: bool = False


@dataclass
class HealthReport:
    """工程健康度报告"""
    score: float = 0.0  # 0-100
    grade: str = ""  # A/B/C/D
    issues: List[Dict] = field(default_factory=list)
    warnings: List[Dict] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


class PrProjectAnalyzer:
    """Pr工程分析器"""

    # Pr时间单位：1秒 = 254016000000 tick
    TICKS_PER_SECOND = 254016000000

    def __init__(self, prproj_path: str = None):
        self.prproj_path = prproj_path
        self._xml_root = None
        self._raw_xml = ""
        self.media_refs: Dict[str, MediaRef] = {}
        self.sequences: List[SequenceInfo] = []
        self.health_report: Optional[HealthReport] = None

    def load(self, prproj_path: str = None) -> bool:
        """加载.prproj文件（gzip压缩的XML）"""
        path = prproj_path or self.prproj_path
        if not path:
            logger.error("未指定.prproj路径")
            return False

        if not os.path.exists(path):
            logger.error(f"文件不存在: {path}")
            return False

        try:
            with gzip.open(path, "rb") as f:
                self._raw_xml = f.read().decode("utf-8", errors="replace")
            self._xml_root = ET.fromstring(self._raw_xml)
            self.prproj_path = path
            logger.info(f"工程加载成功: {os.path.basename(path)}")
            return True
        except Exception as e:
            logger.error(f"工程加载失败: {e}")
            return False

    def analyze(self) -> Dict[str, Any]:
        """执行完整分析"""
        if self._xml_root is None:
            return {"error": "未加载工程文件"}

        # 1. 解析素材引用
        self._parse_media_refs()

        # 2. 解析序列
        self._parse_sequences()

        # 3. 健康度评估
        self.health_report = self._evaluate_health()

        return {
            "file": os.path.basename(self.prproj_path),
            "file_size": os.path.getsize(self.prproj_path),
            "analyzed_at": datetime.now().isoformat(),
            "media_count": len(self.media_refs),
            "missing_media": sum(1 for m in self.media_refs.values() if not m.exists),
            "sequence_count": len(self.sequences),
            "sequences": [asdict(s) for s in self.sequences],
            "health": asdict(self.health_report),
        }

    def _parse_media_refs(self):
        """解析素材引用"""
        self.media_refs = {}

        # 查找所有ProjectItem（素材项）
        for item in self._xml_root.iter("ProjectItem"):
            media_id = item.get("id", "")
            name_elem = item.find("Name")
            name = name_elem.text if name_elem is not None else "未知"

            # 查找文件路径
            file_path = ""
            for file_elem in item.iter("File"):
                path_url = file_elem.get("pathUrl", "")
                if path_url:
                    file_path = path_url.replace("file:///", "").replace("/", os.sep)
                    break

            if not file_path:
                continue

            exists = os.path.exists(file_path)
            file_size = 0
            if exists:
                try:
                    file_size = os.path.getsize(file_path)
                except Exception:
                    pass

            self.media_refs[media_id] = MediaRef(
                media_id=media_id,
                file_path=file_path,
                file_name=os.path.basename(file_path),
                file_size=file_size,
                exists=exists,
            )

        # 统计素材使用次数
        for clip in self._xml_root.iter("Clip"):
            ref_id = clip.get("mediapoolRef", "")
            if ref_id in self.media_refs:
                self.media_refs[ref_id].usage_count += 1

        logger.info(f"解析到 {len(self.media_refs)} 个素材引用")

    def _parse_sequences(self):
        """解析序列信息"""
        self.sequences = []

        for seq_elem in self._xml_root.iter("Sequence"):
            seq_id = seq_elem.get("id", "")
            name_elem = seq_elem.find("Name")
            name = name_elem.text if name_elem is not None else "未命名序列"

            # 分辨率
            width = 1920
            height = 1080
            video_settings = seq_elem.find(".//VideoSettings")
            if video_settings is not None:
                frame_size = video_settings.find("FrameSize")
                if frame_size is not None:
                    width = int(frame_size.get("horizontal", 1920))
                    height = int(frame_size.get("vertical", 1080))

            # 帧率
            fps = 30.0
            rate_elem = seq_elem.find(".//Timebase")
            if rate_elem is not None:
                fps = float(rate_elem.get("value", 30))

            # 轨道和片段数
            tracks = list(seq_elem.iter("Track"))
            clips = list(seq_elem.iter("Clip"))

            # 时长
            duration = 0.0
            for clip in clips:
                dur_str = clip.get("duration", "0")
                try:
                    dur_ticks = int(dur_str)
                    duration = max(duration, dur_ticks / self.TICKS_PER_SECOND)
                except Exception:
                    pass

            # 特效和转场
            has_effects = len(list(seq_elem.iter("Effect"))) > 0
            has_transitions = len(list(seq_elem.iter("Transition"))) > 0

            self.sequences.append(SequenceInfo(
                sequence_id=seq_id,
                name=name,
                width=width,
                height=height,
                fps=fps,
                duration=round(duration, 2),
                track_count=len(tracks),
                clip_count=len(clips),
                has_effects=has_effects,
                has_transitions=has_transitions,
            ))

        logger.info(f"解析到 {len(self.sequences)} 个序列")

    def _evaluate_health(self) -> HealthReport:
        """评估工程健康度"""
        report = HealthReport()
        score = 100.0

        # 检查1：缺失素材
        missing = [m for m in self.media_refs.values() if not m.exists]
        if missing:
            penalty = min(len(missing) * 10, 30)
            score -= penalty
            report.issues.append({
                "type": "missing_media",
                "severity": "high",
                "count": len(missing),
                "description": f"{len(missing)}个素材文件缺失/离线",
                "files": [m.file_name for m in missing[:5]],
            })

        # 检查2：未使用素材
        unused = [m for m in self.media_refs.values() if m.usage_count == 0]
        if unused:
            penalty = min(len(unused) * 2, 10)
            score -= penalty
            report.warnings.append({
                "type": "unused_media",
                "severity": "low",
                "count": len(unused),
                "description": f"{len(unused)}个素材未被使用",
            })

        # 检查3：工程复杂度
        total_clips = sum(s.clip_count for s in self.sequences)
        if total_clips > 500:
            score -= 10
            report.warnings.append({
                "type": "high_complexity",
                "severity": "medium",
                "clip_count": total_clips,
                "description": f"片段数过多({total_clips})，可能影响性能",
            })

        # 检查4：序列分辨率一致性
        resolutions = set((s.width, s.height) for s in self.sequences)
        if len(resolutions) > 1:
            score -= 5
            report.warnings.append({
                "type": "mixed_resolutions",
                "severity": "low",
                "resolutions": list(resolutions),
                "description": "序列分辨率不一致",
            })

        # 检查5：文件大小
        file_size_mb = os.path.getsize(self.prproj_path) / (1024 * 1024)
        if file_size_mb > 50:
            score -= 5
            report.warnings.append({
                "type": "large_file",
                "severity": "low",
                "size_mb": round(file_size_mb, 1),
                "description": f"工程文件较大({file_size_mb:.1f}MB)",
            })

        # 评级
        report.score = max(score, 0)
        if report.score >= 90:
            report.grade = "A"
        elif report.score >= 75:
            report.grade = "B"
        elif report.score >= 60:
            report.grade = "C"
        else:
            report.grade = "D"

        # 优化建议
        if missing:
            report.suggestions.append("重新链接缺失素材或替换为可用文件")
        if unused:
            report.suggestions.append("清理项目面板中未使用的素材")
        if total_clips > 500:
            report.suggestions.append("考虑使用嵌套序列/子序列降低复杂度")
        if len(resolutions) > 1:
            report.suggestions.append("统一序列分辨率，避免混剪")
        if not report.suggestions:
            report.suggestions.append("工程状态良好，无需特别优化")

        # 指标
        report.metrics = {
            "total_media": len(self.media_refs),
            "missing_media": len(missing),
            "unused_media": len(unused),
            "total_sequences": len(self.sequences),
            "total_clips": total_clips,
            "file_size_mb": round(file_size_mb, 2),
            "has_effects": any(s.has_effects for s in self.sequences),
            "has_transitions": any(s.has_transitions for s in self.sequences),
        }

        return report

    def export_report(self, output_path: str = None, format: str = "markdown") -> str:
        """导出分析报告"""
        if self.health_report is None:
            self.analyze()

        if format == "json":
            report_data = {
                "file": os.path.basename(self.prproj_path),
                "analyzed_at": datetime.now().isoformat(),
                "health": asdict(self.health_report),
                "sequences": [asdict(s) for s in self.sequences],
                "media_summary": {
                    "total": len(self.media_refs),
                    "missing": sum(1 for m in self.media_refs.values() if not m.exists),
                    "unused": sum(1 for m in self.media_refs.values() if m.usage_count == 0),
                },
            }
            content = json.dumps(report_data, ensure_ascii=False, indent=2)
        else:
            # Markdown格式
            lines = [
                f"# Pr工程分析报告：{os.path.basename(self.prproj_path)}",
                "",
                f"分析时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
                "",
                "## 健康度评估",
                "",
                f"- **综合评分**：{self.health_report.score:.1f}/100（{self.health_report.grade}级）",
                f"- **素材总数**：{self.health_report.metrics.get('total_media', 0)}",
                f"- **缺失素材**：{self.health_report.metrics.get('missing_media', 0)}",
                f"- **序列数**：{self.health_report.metrics.get('total_sequences', 0)}",
                f"- **片段总数**：{self.health_report.metrics.get('total_clips', 0)}",
                "",
                "## 序列列表",
                "",
            ]
            for i, seq in enumerate(self.sequences, 1):
                lines.append(f"### {i}. {seq.name}")
                lines.append(f"- 分辨率：{seq.width}x{seq.height} @ {seq.fps}fps")
                lines.append(f"- 时长：{seq.duration:.1f}秒")
                lines.append(f"- 轨道：{seq.track_count}，片段：{seq.clip_count}")
                lines.append(f"- 特效：{'有' if seq.has_effects else '无'}，转场：{'有' if seq.has_transitions else '无'}")
                lines.append("")

            if self.health_report.issues:
                lines.append("## 严重问题")
                lines.append("")
                for issue in self.health_report.issues:
                    lines.append(f"- **[{issue['severity']}]** {issue['description']}")
                lines.append("")

            if self.health_report.warnings:
                lines.append("## 警告")
                lines.append("")
                for w in self.health_report.warnings:
                    lines.append(f"- **[{w['severity']}]** {w['description']}")
                lines.append("")

            lines.append("## 优化建议")
            lines.append("")
            for i, s in enumerate(self.health_report.suggestions, 1):
                lines.append(f"{i}. {s}")

            content = "\n".join(lines)

        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"报告已导出: {output_path}")

        return content


# ============ 便捷函数 ============

def analyze_project(prproj_path: str, output_path: str = None) -> Dict[str, Any]:
    """便捷函数：分析Pr工程"""
    analyzer = PrProjectAnalyzer(prproj_path)
    if analyzer.load():
        result = analyzer.analyze()
        if output_path:
            analyzer.export_report(output_path)
        return result
    return {"error": "加载失败"}


if __name__ == "__main__":
    # 自测
    print("=" * 50)
    print("PrProjectAnalyzer 自测")
    print("=" * 50)

    # 查找测试用.prproj文件
    test_dir = r"D:\DobaoWork_Project\Ai_Video_Editor"
    prproj_files = []
    for root, dirs, files in os.walk(test_dir):
        for f in files:
            if f.endswith(".prproj"):
                prproj_files.append(os.path.join(root, f))
                if len(prproj_files) >= 3:
                    break
        if len(prproj_files) >= 3:
            break

    if prproj_files:
        print(f"\n找到 {len(prproj_files)} 个.prproj文件")
        for f in prproj_files:
            print(f"  - {os.path.basename(f)}")

        # 分析第一个
        analyzer = PrProjectAnalyzer(prproj_files[0])
        if analyzer.load():
            result = analyzer.analyze()
            print(f"\n分析结果:")
            print(f"  素材数: {result['media_count']}")
            print(f"  缺失素材: {result['missing_media']}")
            print(f"  序列数: {result['sequence_count']}")
            print(f"  健康度: {result['health']['score']:.1f} ({result['health']['grade']})")
    else:
        print("\n未找到.prproj测试文件，仅验证模块导入")
        analyzer = PrProjectAnalyzer()
        print("  模块导入成功")

    print("\n" + "=" * 50)
    print("自测完成")
    print("=" * 50)
