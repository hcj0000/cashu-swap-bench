# Cashu Swap Bench

Find the lowest input fee for a single Cashu swap, then compare the result with a wallet's choice of notes. Runs offline with Python 3.9 or later and its standard library.

## Try it

```console
python swap_bench.py
python swap_bench.py --pick 1
python swap_bench.py example.json --json
python -m unittest -v
```

The example asks for 15 sat in new outputs. The 16-sat note belongs to a keyset charging 1,500 parts per thousand (ppk) per spent proof. Spending it alone costs 2 sat, leaving only 14. The two 8-sat notes each cost 100 ppk to spend. Together their fee rounds up once to 1 sat, leaving exactly 15.

| Selected notes | Face value | Total input fee | Result after allocating 15 sat |
| --- | ---: | ---: | --- |
| 16 | 16 sat | 2 sat | Short by 1 sat |
| 16 and 8 | 24 sat | 2 sat | 7 sat change |
| 8 and 8 | 16 sat | 1 sat | Exact |

## Compare an implementation

Copy `example.json` and enter the target amount, a fee rate per keyset, and the amount and keyset nickname of each available note. Use synthetic values from a single mint and the sat unit. Each entry represents one input, including repeated denominations. Pass the note numbers selected by your algorithm to `--pick`. Positions start at 1 and follow the file order.

The exact search covers up to 32 notes. It minimizes the fee in whole sat, then change, then input count. Equal candidates resolve in file order. This objective lets a wallet author measure a deliberate trade-off, such as paying an extra sat to retire a keyset. The largest-first baseline takes notes in descending face-value order until it can fund the target.

At the 32-note limit the tool enumerates 65,536 subsets per half. It matches halves using the unrounded balance in thousandths of a sat. For each left half it finds the lowest feasible total fee, then considers every right half that ties at that rounded fee. This preserves exact results without enumerating all 4,294,967,296 full-wallet subsets.

JSON output includes the chosen positions, input amount, summed fee in ppk, rounded fee in sat and signed change. Negative change on a supplied pick gives its exact shortfall. The process exits with 0 when the target is feasible, 1 when no subset can fund it, and 2 for invalid input.

The benchmark assumes the mint can issue the required output denominations. It models the sender's swap only. Direct transfers, receiver redemption fees and Lightning fees have separate accounting. The tool reads no wallet, key or token.

The fee formula and balance equation come from [NUT-02](https://cashubtc.github.io/nuts/02/). The token exchange is described in [NUT-03](https://cashubtc.github.io/nuts/03/).
