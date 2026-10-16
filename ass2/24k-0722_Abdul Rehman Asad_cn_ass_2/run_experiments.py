"""
CS3001 Computer Networks - Assignment II  |  TASK 4: Experiments & comparison
Roll No: 24K-0722  (random seed = 722)
"""
import argparse
import csv

from gbn_sr import Simulator, DEFAULT_TIMEOUT, ROLL_SEED

CASES = [
    ("A", "Reliable", 0.0, 0.0, 0.0),
    ("B", "Loss 0.10", 0.10, 0.0, 0.0),
    ("C", "Mixed errors", 0.05, 0.05, 0.10),
]


def run_experiments(seed, packets=200, window=4, bits=3, timeout=DEFAULT_TIMEOUT):
    results = []
    for cid, cname, loss, corr, dly in CASES:
        for protocol in ("gbn", "sr"):
            sim = Simulator(protocol, packets, window, bits, loss, corr, dly, timeout, seed, verbose=False)
            row = sim.run()
            row.update({"case": f"{cid}_{cname}", "loss_probability": loss,
                        "corruption_probability": corr, "delay_probability": dly})
            results.append(row)
            print(f"{cid} {cname:13s} {row['protocol']:3s}: tx={row['transmissions']:4d} "
                  f"retrans={row['retransmissions']:4d} delivered={row['delivered']:3d} "
                  f"time={row['completion_time_ms']:9.1f} ms  throughput={row['throughput_kbps']:6.2f} kbps")
    cols = ["case", "protocol", "packets", "window", "seq_bits", "loss_probability",
            "corruption_probability", "delay_probability", "transmissions", "retransmissions",
            "delivered", "completion_time_ms", "throughput_kbps", "execution_time_s", "seed"]
    with open("results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(results)
    make_graph(results, seed, packets, window, bits)
    return results


def make_graph(results, seed, packets, window, bits, path="gbn_vs_sr.png"):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed (python -m pip install matplotlib); graph skipped")
        return
    labels = [f"{c}\n{n}" for c, n, *_ in CASES]
    def series(metric, proto):
        return [next(r[metric] for r in results if r["case"].startswith(c) and r["protocol"] == proto)
                for c, *_ in CASES]
    panels = [("retransmissions", "Retransmissions", "packets"),
              ("completion_time_ms", "Completion time", "ms"),
              ("throughput_kbps", "Throughput", "kbps")]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))
    width = 0.38
    for ax, (metric, title, unit) in zip(axes, panels):
        g, s = series(metric, "GBN"), series(metric, "SR")
        x = list(range(3))
        b1 = ax.bar([i - width / 2 for i in x], g, width, label="GBN", color="#c0504d")
        b2 = ax.bar([i + width / 2 for i in x], s, width, label="SR", color="#4f81bd")
        for bars in (b1, b2):
            for bar in bars:
                h = bar.get_height()
                txt = f"{h:g}" if metric != "throughput_kbps" else f"{h:.2f}"
                ax.text(bar.get_x() + bar.get_width() / 2, h, txt, ha="center", va="bottom", fontsize=8)
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.set_ylabel(unit)
        ax.set_title(title)
        ax.set_ylim(0, max(g + s) * 1.12 if max(g + s) else 1)
        ax.legend(loc="upper left" if metric != "throughput_kbps" else "upper right")
    fig.suptitle(f"GBN vs SR ({packets} packets, N={window}, k={bits}, seed {seed})")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"graph saved to {path}")


def main():
    p = argparse.ArgumentParser(description="Task 4: run cases A, B, C for GBN and SR")
    p.add_argument("--packets", type=int, default=200, help="packets per run (default 200)")
    p.add_argument("--window", type=int, default=4, help="window size N (default 4)")
    p.add_argument("--bits", type=int, default=3, help="sequence-number bits k (default 3)")
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="timeout in seconds")
    p.add_argument("--seed", type=int, default=ROLL_SEED, help="random seed (default 722 = roll 24K-0722)")
    a = p.parse_args()
    run_experiments(a.seed, packets=a.packets, window=a.window, bits=a.bits, timeout=a.timeout)


if __name__ == "__main__":
    main()
