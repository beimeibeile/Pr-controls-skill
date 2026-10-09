# Pr Controls Skill

Adobe Premiere Pro 智能管理与控制框架。

## 核心能力

- Pr工程解析（.prproj gzip压缩XML）
- Pr工程生成与修改
- Pr→剪映工程转换（50+特效/转场映射）
- 关键帧/文字/速度迁移

## 快速开始

\\\ash
python scripts/prproj_parser.py input.prproj --output parsed.json
python scripts/prproj_to_jianying.py input.prproj -o output_draft
\\\

## License

MIT
