---
name: Pr-controls-skill
version: 1.0.0
description: |
  Adobe Premiere Pro 智能管理与控制技能。核心能力：Pr工程解析、生成、修改、
  特效迁移、模板管理、与剪映工程互转。与 ai-video-editor、jianying-editor、
  Comfyui-controls-skill、Blender-controls-skill、anysearch-skill 为姊妹项目。
  Use when asked to 管理Premiere、控制Pr、Pr工程、prproj解析、Pr特效、Pr模板、Pr转剪映。
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - Grep
triggers:
  - premiere
  - pr
  - prproj
  - premiere pro
  - Pr工程
  - Pr特效
  - Pr模板
  - Pr转剪映
metadata:
  license: MIT
  requires:
    bins:
      - python
      - git
---

# Pr Controls Skill

> **Adobe Premiere Pro 智能管理与控制框架** —— 让 Pr 工程从二进制变成可程序化操作的对象。工程解析 + 生成 + 修改 + 特效迁移 + 模板管理，全链路自动化。

## 姊妹项目（航空母舰战斗群）

| 项目 | 定位 | 角色 |
|------|------|------|
| **ai-video-editor** | AI视频剪辑框架 | 🚢 航空母舰（集成平台） |
| **jianying-editor** | 剪映工程控制 | 🎬 主剪辑台 |
| **Pr-controls-skill** | Premiere Pro控制（本项目） | 🎞️ 专业剪辑台 |
| **Comfyui-controls-skill** | ComfyUI智能管理 | 🚀 AI算力生成 |
| **Blender-controls-skill** | Blender智能管理 | 🎨 3D合成特效 |
| **anysearch-skill** | 深度搜索技能 | 📡 情报搜索 |

> 单体都能干活，任意组合互相增强。

## 核心能力

| 能力 | 说明 | 状态 |
|------|------|------|
| **Pr工程解析** | 解析.prproj文件（gzip压缩XML），提取序列/轨道/片段/特效/转场/关键帧 | ✅ |
| **Pr工程生成** | 从零生成.prproj工程文件，支持序列设置/多轨道/片段/特效 | ✅ |
| **Pr工程修改** | 修改现有Pr工程，替换素材/调整参数/添加特效 | ✅ |
| **特效映射迁移** | Pr特效→剪映特效映射表（50+种），支持跨平台迁移 | ✅ |
| **转场映射迁移** | Pr转场→剪映转场映射表（50+种） | ✅ |
| **关键帧迁移** | Pr关键帧→剪映关键帧，支持位置/缩放/旋转/透明度 | ✅ |
| **文字字幕迁移** | Pr文字/字幕→剪映文字，保留内容/字体/颜色/位置 | ✅ |
| **速度变速迁移** | Pr速度/变速→剪映速度调整 | ✅ |
| **模板管理** | Pr模板版本管理、参数化修改、批量生成 | 🚧 |
| **Pr→剪映转换** | 完整Pr工程→剪映工程端到端转换 | ✅ |
| **剪映→Pr转换** | 剪映工程→Pr工程转换（规划中） | 📋 |

## 快速开始

```bash
# 1. 解析Pr工程
python scripts/prproj_parser.py input.prproj --output parsed.json

# 2. Pr转剪映
python scripts/prproj_to_jianying.py input.prproj -o output_draft

# 3. 生成Pr工程
python scripts/prproj_generator.py --config config.json -o output.prproj
```

## 项目架构

```
Pr-controls-skill/
├── capabilities/              # 能力模块（可插拔）
│   ├── cap_prproj_parser/         # Pr工程解析
│   ├── cap_prproj_generator/      # Pr工程生成
│   └── cap_pr_executor/           # Pr执行器
├── scripts/                   # 工具脚本
│   ├── prproj_parser.py           # Pr工程解析器
│   ├── prproj_generator.py        # Pr工程生成器
│   ├── prproj_modifier.py         # Pr工程修改器
│   ├── prproj_template_modifier.py # Pr模板修改器
│   └── prproj_to_jianying.py      # Pr→剪映转换器
├── SKILL.md                   # 本文件
└── README.md                  # 项目说明
```

## Pr工程格式说明

- `.prproj` 文件是 gzip 压缩的 XML
- 时间单位：1秒 = 254016000000 tick
- 轨道类型基于媒体文件扩展名判断（.mp3/.wav为音频，.mp4/.mov为视频）
- 特效存储在 ClipItem 的 Effects 节点中
- 关键帧存储在 Effect 的 Parameter 节点中

## 特效映射表（v1.2）

已支持50+种Pr特效映射到剪映：
- 基础变换：位置/缩放/旋转/锚点
- 模糊锐化：高斯模糊/方向模糊/锐化
- 颜色校正：亮度对比度/色阶/曲线/色彩平衡
- 抠像透明：色度键/亮度键/非红色键
- 扭曲变形：位移/镜像/球面化/波纹
- 光效：镜头光晕/漏光/渐变
- 噪点颗粒：噪波/杂色
- 风格化：查找表/马赛克/浮雕
- 时间：抽帧/色调分离
- 转场：交叉溶解/叠加溶解/黑场过渡/白场过渡等50+种

## License

[MIT](LICENSE)
