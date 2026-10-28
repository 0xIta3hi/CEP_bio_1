# Performance Evaluation

Run the benchmark inside the project environment:

```bash
venv/bin/python scripts/benchmark.py --trials 20
```

The script writes `artifacts/benchmark.json` and reports median, p95, minimum, and maximum times for fixed-point encoding, Shamir share generation, and the persisted three-party MPyC authentication process. It also records serialized share size per party.

The benchmark uses deterministic synthetic vectors and a warm process per trial is not assumed: each MPyC trial starts three party processes through MPyC's `-M 3` launcher. Results therefore include process startup and local IPC overhead. Hardware, Python, OpenCV, MPyC, and trial count must accompany any reported results.

Face detection and feature extraction are not included in this synthetic benchmark and must be measured separately with the webcam pipeline on the target machine.

## Recognition threshold

Authentication threshold selection is data-dependent. The calibration utility accepts measured genuine and impostor cosine scores and chooses the threshold minimizing balanced error rate. Scores must be collected from the same model, preprocessing, capture conditions, and evaluation population used for the report. The utility does not manufacture evaluation scores.

## Validation run

A two-trial run on the project environment (Python 3.14.8, NumPy 2.5.4, MPyC 0.11, OpenCV 5.0.0) produced:

| Operation | Median |
|---|---:|
| Fixed-point encoding | 0.057 ms |
| Shamir generation | 0.358 ms |
| Persisted MPyC authentication | 459 ms |
| Serialized share per party | 5,150 bytes |

These values include local process startup for MPyC and only two trials, so they are preliminary evidence. They must be replaced or extended with the target hardware, warm-up procedure, and larger trial count before being presented as final performance results.