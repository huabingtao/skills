import contextlib
import csv
import datetime
import importlib.util
import io
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, skill, script):
    spec = importlib.util.spec_from_file_location(name, ROOT / "skills" / skill / "scripts" / script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


calendar = load("calendar_skill", "danke-calendar-skill", "generate_reminder.py")
redeem = load("redeem_skill", "danke-redeem-skill", "redeem.py")
sync = load("sync_skill", "danke-strategy-sync", "sync.py")


class CalendarTests(unittest.TestCase):
    def data(self, **fields):
        return {"date": "2026-09-30", "items": [{"name": "玩法", "statusText": "还剩 2 天", **fields}]}

    def test_wrong_date_rejected(self):
        with self.assertRaises(ValueError):
            calendar.validate_digest(self.data(), "2026-10-01")

    def test_invalid_field_types_rejected(self):
        for fields in ({"name": " "}, {"statusText": ""}, {"digestNote": 4},
                       {"daysRemaining": "2"}, {"daysRemaining": True},
                       {"daysRemaining": float("nan")}, {"isRedeemDay": "false"}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                calendar.validate_digest(self.data(**fields), "2026-09-30")

    def test_null_days_sort_last_without_highlight(self):
        data = self.data(daysRemaining=None)
        data["items"].append({"name": "紧急", "statusText": "还剩 1 天", "daysRemaining": 1})
        article = calendar.build_reminder_article(data)
        self.assertLess(article.index("- 紧急"), article.index("- 玩法"))
        self.assertIn("- 玩法：还剩 2 天", article)

    def test_multiline_notes_remain_one_list_item(self):
        article = calendar.build_reminder_article(self.data(digestNote="第一行\n第二行"))
        self.assertIn("（第一行 第二行）", article)

    def test_rng_does_not_modify_global_state(self):
        before = random.getstate()
        calendar.build_reminder_article(self.data())
        self.assertEqual(before, random.getstate())

    def test_empty_items_do_not_fallback_to_old_reminders(self):
        data = {"date": "2026-09-30", "items": [], "reminders": [{"name": "旧活动"}]}
        self.assertNotIn("旧活动", calendar.build_reminder_article(data))

    def test_explicit_source_required(self):
        with patch("sys.argv", ["calendar"]), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            calendar.main()
        self.assertEqual(caught.exception.code, 2)

    def test_offline_output_and_overwrite_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "article"
            digest = Path(tmp) / "digest.json"
            digest.write_text(json.dumps(self.data()), encoding="utf-8")
            args = ["calendar", "--date", "2026-09-30", "--digest-file", str(digest),
                    "--output-dir", str(out), "--skip-covers", "--no-auto-tag"]
            with patch("sys.argv", args), patch.object(calendar, "fetch_daily_digest") as fetch:
                calendar.main()
                fetch.assert_not_called()
                original = (out / "26.9.30.md").read_bytes()
                with self.assertRaises(FileExistsError):
                    calendar.main()
                self.assertEqual(original, (out / "26.9.30.md").read_bytes())

    def test_cover_failure_keeps_existing_article(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            article = out / "26.9.30.md"
            article.write_text("original")
            digest = out / "digest.json"
            digest.write_text(json.dumps(self.data()))
            args = ["calendar", "--date", "2026-09-30", "--digest-file", str(digest),
                    "--output-dir", str(out), "--no-auto-tag", "--force"]
            with patch("sys.argv", args), patch.object(calendar, "generate_covers", side_effect=RuntimeError("cover")):
                with self.assertRaises(RuntimeError):
                    calendar.main()
            self.assertEqual(article.read_text(), "original")

    def test_cover_success_requires_both_files(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(calendar.subprocess, "run"):
            with self.assertRaises(RuntimeError):
                calendar.generate_covers(Path(tmp), datetime.date(2026, 9, 30))

    def test_auto_tag_uses_existing_sibling_script(self):
        with patch.object(calendar.subprocess, "run") as run:
            calendar.auto_tag_file(Path("article.md"))
        self.assertTrue(Path(run.call_args.args[0][1]).is_file())


class RedeemTests(unittest.TestCase):
    def test_excel_ids_and_report_round_trip(self):
        try:
            import pandas as pd
            import openpyxl
        except ImportError:
            self.skipTest("Excel integration requires pandas/openpyxl")
        with tempfile.TemporaryDirectory() as tmp:
            source, report = Path(tmp) / "ids.xlsx", Path(tmp) / "report.xlsx"
            pd.DataFrame({"ID": ["00123", "12345678901234567890", "123.0", ""]}).to_excel(source, index=False)
            self.assertEqual(redeem.load_player_ids(source), ["00123", "12345678901234567890", "123"])
            rows = [{"玩家ID": "00123", "兑换状态": "待兑换", "结果说明": "test", "验证码尝试次数": 0}]
            redeem.save_report(rows, report)
            actual = pd.read_excel(report, dtype=str)
            self.assertEqual(actual.iloc[0]["玩家ID"], "00123")

    def test_txt_bom_comments_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ids.txt"
            path.write_text("# comment\n用户-00123\n00123\n456\n", encoding="utf-8-sig")
            self.assertEqual(redeem.load_player_ids(path), ["00123", "456"])

    def test_csv_preserves_long_and_leading_zero_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ids.csv"
            path.write_text("玩家ID,备注\n00123,甲\n12345678901234567890,乙\n123.0,丙\n,空\n", encoding="utf-8-sig")
            self.assertEqual(redeem.load_player_ids(path), ["00123", "12345678901234567890", "123"])

    def test_invalid_ids_rejected(self):
        for value in ("abc", "-123", "1e10", "123.5", "１２３"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                redeem.normalize_player_id(value, spreadsheet=True)

    def test_empty_table_rejected(self):
        with self.assertRaises(ValueError):
            redeem.select_id_column([])

    def test_column_matching(self):
        self.assertEqual(redeem.select_id_column(["备注", " USERID "]), " USERID ")

    def test_bad_delay_and_output_rejected(self):
        for option in (["--delay", "-1"], ["--delay", "nan"], ["--output", "report.xls"]):
            with patch("sys.argv", ["redeem", "-f", "ids.txt", "-c", "code"] + option), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                redeem.parse_args()

    def test_dry_run_does_not_construct_network_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "ids.txt"
            source.write_text("00123\n456")
            report = Path(tmp) / "dist/result.csv"
            with patch("sys.argv", ["redeem", "-f", str(source), "-c", "example", "-o", str(report), "--dry-run"]), patch.object(redeem, "DankRedeemer") as client:
                redeem.main()
                client.assert_not_called()
            with report.open(encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([r["玩家ID"] for r in rows], ["00123", "456"])
            self.assertTrue(all(r["兑换状态"] == "待兑换" for r in rows))

    def test_report_failure_happens_before_any_request(self):
        with patch("sys.argv", ["redeem", "-f", "ids.txt", "-c", "code", "-o", "report.csv"]), patch.object(redeem, "load_player_ids", return_value=["123"]), patch.object(redeem, "save_report", side_effect=OSError("full")), patch.object(redeem, "DankRedeemer") as client:
            with self.assertRaises(OSError):
                redeem.main()
            client.assert_not_called()

    def test_interruption_preserves_uncertain_and_pending_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.csv"
            fake = Mock()
            fake.redeem_single.side_effect = [("成功", "兑换成功", 1), KeyboardInterrupt()]
            with patch("sys.argv", ["redeem", "-f", "ids.txt", "-c", "code", "-o", str(report), "--delay", "0"]), patch.object(redeem, "load_player_ids", return_value=["1", "2", "3"]), patch.object(redeem, "DankRedeemer", return_value=fake):
                with self.assertRaises(KeyboardInterrupt):
                    redeem.main()
            with report.open(encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([r["兑换状态"] for r in rows], ["成功", "待核实", "待兑换"])
            fake.session.close.assert_called_once()

    def test_claim_timeout_is_uncertain_without_retry(self):
        client = redeem.DankRedeemer.__new__(redeem.DankRedeemer)
        client.delay = 0
        client.get_captcha = Mock(return_value=("id", b"image"))
        client.ocr = Mock()
        client.ocr.classification.return_value = "1234"
        client.claim_gift = Mock(side_effect=redeem.requests.Timeout("timeout"))
        status, _, attempts = client.redeem_single("123")
        self.assertEqual((status, attempts), ("待核实", 1))
        client.claim_gift.assert_called_once()

    def test_existing_report_and_same_input_are_protected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "existing.csv"
            path.write_text("original")
            for source, extra in (("ids.txt", []), (str(path), ["--force"])):
                with patch("sys.argv", ["redeem", "-f", source, "-c", "code", "-o", str(path)] + extra), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    redeem.parse_args()
            self.assertEqual(path.read_text(), "original")

    def test_captcha_retries_are_bounded(self):
        client = redeem.DankRedeemer.__new__(redeem.DankRedeemer)
        client.delay = 0.7
        client.get_captcha = Mock(return_value=("id", b"image"))
        client.ocr = Mock()
        client.ocr.classification.return_value = "bad"
        client.claim_gift = Mock()
        with patch.object(redeem.time, "sleep") as sleep:
            status, _, attempts = client.redeem_single("123", max_retries=2)
        self.assertEqual((status, attempts), ("失败", 2))
        client.claim_gift.assert_not_called()
        self.assertEqual(sleep.call_args.args[0], 0.7)


class SyncTests(unittest.TestCase):
    def fixture(self, tmp):
        source, target = Path(tmp) / "source", Path(tmp) / "target"
        (source / "danke-test").mkdir(parents=True)
        (source / "danke-test/SKILL.md").write_text("test")
        return source, target

    def test_check_does_not_mutate(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, target = self.fixture(tmp)
            self.assertFalse(sync.sync_links(source, target))
            self.assertFalse(target.exists())

    def test_apply_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, target = self.fixture(tmp)
            self.assertTrue(sync.sync_links(source, target, apply=True))
            self.assertTrue(sync.sync_links(source, target, apply=True))
            self.assertEqual((target / "danke-test").resolve(), source / "danke-test")

    def test_conflict_keeps_all_targets_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, target = self.fixture(tmp)
            (source / "danke-first").mkdir()
            (source / "danke-first/SKILL.md").write_text("new")
            (target / "danke-test").mkdir(parents=True)
            (target / "danke-test/local.md").write_text("local work")
            with self.assertRaises(FileExistsError):
                sync.sync_links(source, target, apply=True)
            self.assertEqual((target / "danke-test/local.md").read_text(), "local work")
            self.assertFalse((target / "danke-first").exists())

    def test_broken_link_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, target = self.fixture(tmp)
            target.mkdir()
            (target / "danke-test").symlink_to("missing")
            with self.assertRaises(FileExistsError):
                sync.sync_links(source, target, apply=True)
            self.assertTrue((target / "danke-test").is_symlink())

    def test_empty_source_is_error(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            sync.sync_links(Path(tmp), Path(tmp) / "target")


if __name__ == "__main__":
    unittest.main()
