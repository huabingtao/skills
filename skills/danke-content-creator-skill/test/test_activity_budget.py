import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("activity_budget", Path(__file__).resolve().parents[1] / "scripts/calculate_activity_budget.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def example():
    return {
        "initial_items": 5,
        "tasks": {"登录": 50, "主线": 65, "快巡": 100, "特行": 97},
        "box_rewards": {"400": 345, "500": 445, "600": 570},
        "sample": {"items_consumed": 203, "progress_gained": 254},
        "item_price_diamonds": 100,
        "plans": [{"progress": n, "cumulative_rewards": None} for n in [850, 1000, 1650]],
    }


class ActivityBudgetTests(unittest.TestCase):
    def test_time_puzzle_regression(self):
        result = module.calculate_budget(example())
        self.assertEqual(result["base_items"], 317)
        self.assertEqual(result["full_task_items"], 887)
        self.assertEqual(result["task_total_excluding_initial"], 882)
        self.assertEqual([p["required_items"] for p in result["plans"]], [680, 800, 1319])
        rows = {r["boxes"]: r for r in result["rows"]}
        self.assertEqual(rows[500]["total_items"], 762)
        self.assertEqual(rows[500]["estimated_progress_rounded"], 953)
        self.assertEqual(rows[500]["diamond_budget"]["1000"], 3800)
        self.assertEqual(rows[600]["diamond_budget"]["1650"], 43200)
        self.assertEqual(rows[600]["missing_items"]["1650"], 432)

    def test_exact_integer_ratio_does_not_buy_extra_item(self):
        data = example()
        data["sample"] = {"items_consumed": 3, "progress_gained": 10}
        data["plans"] = [{"progress": 1000, "cumulative_rewards": []}]
        self.assertEqual(module.calculate_budget(data)["plans"][0]["required_items"], 300)

    def test_unknown_rewards_are_not_invented_or_confused_with_empty(self):
        data = example()
        data["plans"][1]["cumulative_rewards"] = []
        data["plans"][2]["cumulative_rewards"] = [{"name": "神炼核心", "quantity": 1}]
        result = module.calculate_budget(data)
        self.assertEqual(len(result["warnings"]), 1)
        markdown = module.format_markdown(result)
        self.assertIn("待用户确认", markdown)
        self.assertIn("神炼核心 ×1", markdown)
        self.assertIn("补至 1650（钻石）", markdown)
        self.assertIn("| 600 | 0 | 0 | 43200 |", markdown)
        self.assertNotIn("43200 钻", markdown)

    def test_invalid_quantities_and_cumulative_box_rewards_are_rejected(self):
        for mutate in [
            lambda d: d.update(initial_items=-1),
            lambda d: d["sample"].update(items_consumed=0),
            lambda d: d["tasks"].update(登录=True),
            lambda d: d["box_rewards"].update({"600": 100}),
        ]:
            with self.subTest(mutate=mutate):
                data = example()
                mutate(data)
                with self.assertRaises(ValueError):
                    module.calculate_budget(data)


if __name__ == "__main__":
    unittest.main()
