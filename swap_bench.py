"""Compare coin selections for a single Cashu swap using synthetic sat amounts."""

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from itertools import combinations
from pathlib import Path


@dataclass(frozen=True)
class Note:
    amount_sat: int
    fee_ppk: int


@dataclass(frozen=True)
class Selection:
    positions: tuple[int, ...]
    input_sat: int
    fee_ppk: int
    fee_sat: int
    change_sat: int

    def rank(self):
        return self.fee_sat, self.change_sat, len(self.positions), self.positions


def integer(value, minimum, field):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{field} must be an integer of at least {minimum}")
    return value


def parse_case(data):
    if not isinstance(data, dict):
        raise ValueError("the scenario must be a JSON object")
    target = integer(data.get("target_sat"), 1, "target_sat")
    keysets = data.get("keysets_ppk")
    if not isinstance(keysets, dict) or not keysets:
        raise ValueError("keysets_ppk must map keyset nicknames to fees")
    for name, rate in keysets.items():
        integer(rate, 0, f"keysets_ppk.{name}")
    rows = data.get("notes")
    if not isinstance(rows, list) or len(rows) > 18:
        raise ValueError("notes must be an array with at most 18 entries")
    notes = []
    for position, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"note {position} must be an object")
        name = row.get("keyset")
        if not isinstance(name, str) or name not in keysets:
            raise ValueError(f"note {position} refers to an unknown keyset")
        amount = integer(row.get("amount_sat"), 1, f"note {position} amount_sat")
        notes.append(Note(amount, keysets[name]))
    return notes, target


def evaluate(notes, target, positions):
    positions = tuple(sorted(positions))
    if len(set(positions)) != len(positions) or any(
        pos < 1 or pos > len(notes) for pos in positions
    ):
        raise ValueError("pick distinct note numbers from the input, starting at 1")
    chosen = [notes[pos - 1] for pos in positions]
    total = sum(note.amount_sat for note in chosen)
    ppk = sum(note.fee_ppk for note in chosen)
    fee = (ppk + 999) // 1000
    return Selection(positions, total, ppk, fee, total - fee - target)


def best_selection(notes, target):
    # Enumerate all subsets so the result can serve as an independent benchmark.
    # Only the best feasible subset is retained in memory.
    best = None
    positions = range(1, len(notes) + 1)
    for size in range(1, len(notes) + 1):
        for subset in combinations(positions, size):
            candidate = evaluate(notes, target, subset)
            if candidate.change_sat >= 0 and (best is None or candidate.rank() < best.rank()):
                best = candidate
    return best


def largest_first(notes, target):
    positions = sorted(range(1, len(notes) + 1), key=lambda pos: -notes[pos - 1].amount_sat)
    for size in range(1, len(notes) + 1):
        candidate = evaluate(notes, target, positions[:size])
        if candidate.change_sat >= 0:
            return candidate
    return None


def summary(label, selection):
    if selection is None:
        return f"{label}: no feasible selection"
    picked = ", ".join(str(pos) for pos in selection.positions)
    balance = (
        f"{selection.change_sat} sat change" if selection.change_sat >= 0
        else f"short by {-selection.change_sat} sat"
    )
    return (f"{label}: notes [{picked}], input {selection.input_sat} sat, "
            f"fee {selection.fee_sat} sat ({selection.fee_ppk} ppk), {balance}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", nargs="?", type=Path,
                        default=Path(__file__).with_name("example.json"))
    parser.add_argument("--pick", type=int, nargs="+", metavar="N",
                        help="also evaluate your choice of 1-based note numbers")
    parser.add_argument("--json", action="store_true", help="print machine-readable results")
    args = parser.parse_args()
    try:
        notes, target = parse_case(json.loads(args.scenario.read_text(encoding="utf-8-sig")))
        picked = evaluate(notes, target, args.pick) if args.pick else None
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Invalid scenario: {exc}\n")

    results = {"optimal": best_selection(notes, target), "largest_first": largest_first(notes, target)}
    if picked is not None:
        results["your_pick"] = picked
    if args.json:
        payload = {key: asdict(value) if value is not None else None for key, value in results.items()}
        print(json.dumps({"target_sat": target, **payload}, indent=2))
    else:
        print(f"Cashu swap benchmark | target {target} sat")
        for name, value in results.items():
            print(summary(name.replace("_", " "), value))
    return 0 if results["optimal"] is not None else 1


if __name__ == "__main__":
    sys.exit(main())
