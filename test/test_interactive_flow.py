# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.interactive_flow import run_stage_1, run_stage_2, run_stage_3
from scripts.compile import load_project_config


def test_stage_writers_create_missing_parent_directories(tmp_path):
    # Prepare a minimal source file
    input_file = tmp_path / "source.md"
    input_file.write_text("# 测试\n这里是测试内容。", encoding="utf-8")

    # Determine deep nested outputs
    stage1_out = tmp_path / "nested" / "deep" / "stage1.md"
    stage2_out = tmp_path / "nested" / "deep" / "stage2.md"
    stage3_out = tmp_path / "nested" / "deep" / "stage3_wechat.html"

    # Run stage 1 -> should create parent dirs and write file
    ok1 = run_stage_1(str(input_file), str(stage1_out), None, None)
    assert ok1 is True
    assert stage1_out.exists()

    # Run stage 2 using stage1 output
    ok2 = run_stage_2(str(stage1_out), str(stage2_out), None)
    assert ok2 is True
    assert stage2_out.exists()

    # Load project config for stage 3 and run it
    pack_dir = PROJECT_ROOT / "packs" / "danke"
    project_config = load_project_config(str(pack_dir))
    ok3 = run_stage_3(str(stage2_out), str(stage3_out), project_config)
    assert ok3 is True
    assert stage3_out.exists()
