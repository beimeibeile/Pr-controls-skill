"""
PRPROJ模板修改器 v1 - 概念验证
将真实PR模板中的所有媒体路径替换为指定文件，
验证剪映导入后能否正常渲染。
"""

import logging
logger = logging.getLogger(__name__)

import gzip
import re
import os

TEMPLATE = r'D:\DobaoWork_Project\Ai_Video_Editor\prxml_test\real_template.prproj'
OUTPUT = r'D:\DobaoWork_Project\Ai_Video_Editor\prxml_test\test_modified.prproj'
REPLACEMENT_MEDIA = r'C:\temp\prtest\test.png'

def main():
    # 读取模板
    with gzip.open(TEMPLATE, 'rt', encoding='utf-8') as f:
        content = f.read()

    logger.info(f"模板原始大小: {len(content)} 字符")

    # 找所有FilePath
    file_paths = re.findall(r'<FilePath>([^<]+)</FilePath>', content)
    logger.info(f"找到 {len(file_paths)} 个FilePath:")
    for fp in file_paths:
        if len(fp) > 10:  # 跳过数字类型的
            logger.info(f"  {fp}")

    # 替换所有实际文件路径（包含\或/的路径）
    replaced = 0
    for fp in file_paths:
        if '\\' in fp or '/' in fp:
            # 替换FilePath内容
            content = content.replace(f'<FilePath>{fp}</FilePath>', f'<FilePath>{REPLACEMENT_MEDIA}</FilePath>')
            replaced += 1

    logger.info(f"\n已替换 {replaced} 个媒体路径为: {REPLACEMENT_MEDIA}")

    # 同时替换ClipProjectItem中的Name（保持一致性）
    # 找到所有媒体名称
    media_names = re.findall(r'<Name>([^<]+\.(?:mov|png|jpg|mp4|avi))</Name>', content)
    logger.info(f"\n找到 {len(media_names)} 个媒体名称:")
    for name in set(media_names):
        logger.info(f"  {name}")

    # 写入输出
    with gzip.open(OUTPUT, 'wt', encoding='utf-8') as f:
        f.write(content)

    logger.info(f"\n已保存修改后的工程: {OUTPUT}")
    logger.info(f"输出大小: {os.path.getsize(OUTPUT)} bytes")
    logger.info("\n请在剪映中导入测试: test_modified.prproj")

if __name__ == '__main__':
    main()
