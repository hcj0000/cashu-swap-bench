import json
import math
import random
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from swap_bench import Note, best_selection, evaluate, largest_first, parse_case


ROOT = Path(__file__).resolve().parent


class SwapBenchTests(unittest.TestCase):
    def test_documented_example(self):
        notes, target = parse_case(json.loads((ROOT / "example.json").read_text()))
        best = best_selection(notes, target)
        self.assertEqual((best.positions, best.fee_sat, best.change_sat), ((2, 3), 1, 0))
        greedy = largest_first(notes, target)
        self.assertEqual((greedy.positions, greedy.fee_sat, greedy.change_sat), ((1, 2), 2, 7))
        self.assertEqual(evaluate(notes, target, [1]).change_sat, -1)

    def test_nut02_rounding_after_aggregation(self):
        for count, expected_fee in [(1, 1), (3, 1), (10, 1), (11, 2), (20, 2)]:
            notes = [Note(2, 100)] * count
            self.assertEqual(evaluate(notes, 1, range(1, count + 1)).fee_sat, expected_fee)
        for rate, expected in [(0, 0), (999, 1), (1000, 1), (1001, 2)]:
            self.assertEqual(evaluate([Note(8, rate)], 1, [1]).fee_sat, expected)

    def test_zero_fee_and_ties(self):
        notes = [Note(2, 0), Note(1, 0), Note(1, 0), Note(2, 0)]
        self.assertEqual(best_selection(notes, 2).positions, (1,))

    def test_infeasible_or_empty_wallet(self):
        self.assertIsNone(best_selection([], 1))
        self.assertIsNone(best_selection([Note(1, 1000), Note(1, 1000)], 1))

    def test_large_integer_values(self):
        amount = 2 ** 62
        fee_ppk = (2 ** 53) * 1000 + 1
        self.assertEqual(evaluate([Note(amount, fee_ppk)], 1, [1]).fee_sat, 2 ** 53 + 1)

    def test_invalid_case_and_duplicate_picks(self):
        for case in [
            {"target_sat": True, "notes": [], "keysets_ppk": {"A": 0}},
            {"target_sat": 1, "notes": [], "keysets_ppk": {"A": -1}},
            {"target_sat": 1, "notes": [{"amount_sat": 2, "keyset": "B"}], "keysets_ppk": {"A": 0}},
            {"target_sat": 1, "notes": [{}] * 33, "keysets_ppk": {"A": 0}},
        ]:
            with self.subTest(case=case), self.assertRaises(ValueError):
                parse_case(case)
        for positions in ([0], [2], [1, 1]):
            with self.subTest(positions=positions), self.assertRaises(ValueError):
                evaluate([Note(8, 0)], 1, positions)

    def test_independent_oracle(self):
        # Bit masks and rational arithmetic form an independent reference.
        rng = random.Random(20261123)
        for _ in range(180):
            notes = [Note(2 ** rng.randrange(6), rng.choice((0, 50, 500, 1000, 1001, 2500)))
                     for _ in range(rng.randint(1, 8))]
            target = rng.randint(1, sum(n.amount_sat for n in notes) + 1)
            ranks = []
            for mask in range(1, 1 << len(notes)):
                selected = [(i, n) for i, n in enumerate(notes, 1) if mask & (1 << (i - 1))]
                fee = math.ceil(sum(Fraction(n.fee_ppk, 1000) for _, n in selected))
                change = sum(n.amount_sat for _, n in selected) - target - fee
                if change >= 0:
                    ranks.append((fee, change, len(selected), tuple(i for i, _ in selected)))
            expected = min(ranks, default=None)
            result = best_selection(notes, target)
            self.assertEqual(result.rank() if result else None, expected)

    def test_combines_fractional_fees_across_halves(self):
        # Fees of 600 and 400 ppk fit in one sat. Charging each half a
        # whole sat, or minimizing raw ppk ahead of change, misses (1, 3).
        notes = [Note(8, 600), Note(32, 250), Note(8, 400), Note(32, 250)]
        self.assertEqual(best_selection(notes, 15).rank(), (1, 0, 2, (1, 3)))

    def test_full_size_with_equal_candidates(self):
        case = {"target_sat": 15, "notes": [{"keyset": "A", "amount_sat": 1}] * 32,
                "keysets_ppk": {"A": 50}}
        notes, target = parse_case(case)
        self.assertEqual(best_selection(notes, target).rank(), (1, 0, 16, tuple(range(1, 17))))

    def test_command_line_status_and_json(self):
        command = [sys.executable, "-B", str(ROOT / "swap_bench.py")]
        demo = subprocess.run(command + ["--json", "--pick", "1"], capture_output=True, text=True)
        self.assertEqual(demo.returncode, 0)
        self.assertEqual(json.loads(demo.stdout)["your_pick"]["change_sat"], -1)
        with tempfile.TemporaryDirectory() as directory:
            scenario = Path(directory) / "case.json"
            scenario.write_text('{"target_sat":1,"notes":[],"keysets_ppk":{"A":0}}')
            result = subprocess.run(command + [str(scenario), "--json"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIsNone(json.loads(result.stdout)["optimal"])
            scenario.write_text("bad json")
            result = subprocess.run(command + [str(scenario)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("Invalid scenario", result.stderr)


if __name__ == "__main__":
    unittest.main()
