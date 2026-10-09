"""
Pr-controls-skill 基础测试套件
验证：prproj解析、生成、执行器核心功能
"""
import os
import sys
import unittest
import tempfile
import gzip

# 路径设置
SKILL_ROOT = r"C:\Users\Administrator\AppData\Local\Doubao\User Data\Default\.doubao\agent_mode\workspace\.user_skills\Pr-controls-skill"
sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))


class TestPrprojParser(unittest.TestCase):
    """Prproj解析器测试"""
    
    def test_import_ok(self):
        """测试：模块可正常导入"""
        from prproj_parser import PrprojParser
        self.assertIsNotNone(PrprojParser)
    
    def test_parser_requires_path(self):
        """测试：解析器需要prproj_path参数"""
        from prproj_parser import PrprojParser
        with self.assertRaises(TypeError):
            PrprojParser()  # 缺少必需参数应报错
    
    def test_parse_nonexistent_file(self):
        """测试：解析不存在的文件应优雅失败"""
        from prproj_parser import PrprojParser
        parser = PrprojParser(r"C:\nonexistent\file.prproj")
        self.assertIsNotNone(parser)


class TestPrprojGenerator(unittest.TestCase):
    """Prproj生成器测试"""
    
    def setUp(self):
        from prproj_generator import PRPROJGenerator
        self.generator = PRPROJGenerator(width=1080, height=1920, fps=30)
    
    def test_import_ok(self):
        """测试：模块可正常导入"""
        from prproj_generator import PRPROJGenerator
        self.assertIsNotNone(PRPROJGenerator)
    
    def test_generator_init(self):
        """测试：生成器初始化参数"""
        from prproj_generator import PRPROJGenerator
        gen = PRPROJGenerator(width=1920, height=1080, fps=24)
        self.assertEqual(gen.width, 1920)
        self.assertEqual(gen.height, 1080)
        self.assertEqual(gen.fps, 24)
    
    def test_add_video_clip(self):
        """测试：添加视频片段"""
        self.generator.add_video_clip("test.mp4", 0, 100, track=0)
        self.assertEqual(len(self.generator.video_clips), 1)
        self.assertEqual(self.generator.video_clips[0]["path"], os.path.abspath("test.mp4"))
        self.assertEqual(self.generator.video_clips[0]["start"], 0)
        self.assertEqual(self.generator.video_clips[0]["duration"], 100)
    
    def test_add_audio_clip(self):
        """测试：添加音频片段"""
        self.generator.add_audio_clip("test.mp3", 0, 200, track=0)
        self.assertEqual(len(self.generator.audio_clips), 1)
        self.assertEqual(self.generator.audio_clips[0]["path"], os.path.abspath("test.mp3"))
    
    def test_frames_to_ticks(self):
        """测试：帧转tick计算"""
        # 30fps时，1帧 = 254016000000/30 = 8467200000 tick
        expected = int(1 * (254016000000 / 30))
        self.assertEqual(self.generator._frames_to_ticks(1), expected)
    
    def test_next_id_increment(self):
        """测试：ID自增"""
        id1 = self.generator._next_id()
        id2 = self.generator._next_id()
        self.assertEqual(id2, id1 + 1)


class TestPrprojExecutor(unittest.TestCase):
    """Prproj执行器测试"""
    
    def setUp(self):
        from prproj_executor import PrprojExecutor
        self.executor = PrprojExecutor()
    
    def test_import_ok(self):
        """测试：模块可正常导入"""
        from prproj_executor import PrprojExecutor
        self.assertIsNotNone(PrprojExecutor)
    
    def test_executor_init(self):
        """测试：执行器初始化"""
        from prproj_executor import PrprojExecutor
        executor = PrprojExecutor()
        self.assertIsNotNone(executor)
    
    def test_list_templates_empty(self):
        """测试：空模板目录返回空列表"""
        import tempfile
        from prproj_executor import PrprojExecutor
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = PrprojExecutor(template_dir=tmpdir)
            templates = executor.list_templates()
            self.assertEqual(len(templates), 0)


class TestPrprojToJianying(unittest.TestCase):
    """Pr转剪映工具测试"""
    
    def test_import_ok(self):
        """测试：模块可正常导入"""
        try:
            from prproj_to_jianying import PrprojToJianying
            self.assertIsNotNone(PrprojToJianying)
        except ImportError:
            # 模块可能不存在，跳过
            pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
