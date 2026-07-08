# -*- coding: utf-8 -*-
import os
import sys
import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.interactive_flow import run_stage_1, run_stage_2, run_stage_3, main
from scripts.compile import load_project_config


class TestInteractiveFlow(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_stage_writers_create_missing_parent_directories(self):
        # Prepare a minimal source file
        input_file = self.tmp_path / "source.md"
        input_file.write_text("# 测试\n这里是测试内容。", encoding="utf-8")

        # Determine deep nested outputs
        stage1_out = self.tmp_path / "nested" / "deep" / "stage1.md"
        stage2_out = self.tmp_path / "nested" / "deep" / "stage2.md"
        stage3_out = self.tmp_path / "nested" / "deep" / "stage3_wechat.html"

        # Run stage 1 -> should create parent dirs and write file
        ok1 = run_stage_1(str(input_file), str(stage1_out), None, None)
        self.assertTrue(ok1)
        self.assertTrue(stage1_out.exists())

        # Run stage 2 using stage1 output
        ok2 = run_stage_2(str(stage1_out), str(stage2_out), None)
        self.assertTrue(ok2)
        self.assertTrue(stage2_out.exists())

        # Load project config for stage 3 and run it
        pack_dir = PROJECT_ROOT / "packs" / "danke"
        project_config = load_project_config(str(pack_dir))
        ok3 = run_stage_3(str(stage2_out), str(stage3_out), project_config)
        self.assertTrue(ok3)
        self.assertTrue(stage3_out.exists())

    @patch('scripts.interactive_flow.publish_draft')
    def test_non_interactive_flow_success(self, mock_publish_draft):
        # Prepare a minimal source file
        input_file = self.tmp_path / "source.md"
        input_file.write_text("# 测试\n这里是测试内容。", encoding="utf-8")

        # Mock sys.argv with non-interactive flag -y
        test_args = ["interactive_flow.py", str(input_file), "--pack", str(PROJECT_ROOT / "packs" / "danke"), "-y"]
        
        # Patch credentials to avoid setup_interactive_config call
        with patch.dict(os.environ, {"WECHAT_APPID": "mock_id", "WECHAT_APPSECRET": "mock_secret"}):
            with patch('sys.argv', test_args):
                main()
                
        # Verify publish_draft was called once
        mock_publish_draft.assert_called_once()

    @patch('scripts.interactive_flow.setup_interactive_config')
    def test_non_interactive_flow_aborts_on_missing_credentials(self, mock_setup_config):
        # Prepare a minimal source file
        input_file = self.tmp_path / "source.md"
        input_file.write_text("# 测试\n这里是测试内容。", encoding="utf-8")

        # Mock sys.argv with non-interactive flag -y
        test_args = ["interactive_flow.py", str(input_file), "--pack", str(PROJECT_ROOT / "packs" / "danke"), "-y"]

        # Ensure environment lacks credentials
        with patch.dict(os.environ, {}):
            with patch('scripts.interactive_flow.load_config', return_value={}):
                with patch('sys.argv', test_args):
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    self.assertEqual(cm.exception.code, 1)
                    
        # Ensure setup_interactive_config was NOT called
        mock_setup_config.assert_not_called()


if __name__ == "__main__":
    unittest.main()
