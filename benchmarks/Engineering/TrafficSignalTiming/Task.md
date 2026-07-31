# TrafficSignalTiming — optimize arterial signal coordination

## Scientific background
Coordinating traffic signals along an arterial corridor to create "green waves" is a
classic transportation engineering problem. The timing plan (green durations + offsets
between intersections) determines total vehicle delay. The HCM delay formula captures
saturation effects; platoon dispersion degrades progression over distance. Optimal
coordination reduces delay by 30-50% over uncoordinated operation.

Reference: Highway Capacity Manual 6th ed (TRB, 2016); Webster 1958.

## Your task
```python
def optimize_signals(n_intersections, cycle_length, demands):
    \"\"\"Return dict with 'green_times' (5,) in [15, 75] sec and 'offsets' (5,) in [0, 90].\"\"\"
```

## Rules
- Only edit `solution.py`. numpy/scipy only. CPU. Do not read `verification/`.
