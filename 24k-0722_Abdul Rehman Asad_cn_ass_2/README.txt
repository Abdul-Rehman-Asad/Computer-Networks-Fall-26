CS3001 Computer Networks - Assignment II
Reliable Transfer for a Disaster-Response Network
Roll No: 24K-0722   |   Random seed: 722 (last four digits of roll number)

FILES
  gbn_sr.py              TASK 3 - GBN and Selective Repeat sender/receiver + simulated unreliable
                         channel (written from scratch, no transport library)
  run_experiments.py     TASK 4 - runs cases A, B, C for GBN and SR (imports gbn_sr.py), writes
                         results.csv and gbn_vs_sr.png
  results.csv            measurements for the six required runs (cases A, B, C x GBN, SR)
  gbn_vs_sr.png          graph: retransmissions, completion time, throughput (GBN vs SR)
  report.docx            report (approach, implementation, experiments, results, comparison,
                         conclusion + Tasks 1, 2 and 5)

REQUIREMENTS
  Python 3.9+.  matplotlib is needed only for the graph:  python -m pip install matplotlib

HOW TO RUN
  1) Task 4 experiments (200 packets, N=4, k=3, seed 722) -> writes results.csv + gbn_vs_sr.png
       python run_experiments.py --seed 722

  2) Task 3 sample command (one protocol, 10% loss, full event log)
       python gbn_sr.py --protocol sr --packets 200 --window 4 --bits 3 --loss 0.10 --seed 722 --quiet

  3) Task-2 scenario: 10 packets, N=4, packet 2 lost (both protocols, full log)
       python gbn_sr.py --protocol both --packets 10 --window 4 --bits 3 --lose-first 2 --seed 722

PARAMETERS  (gbn_sr.py; run_experiments.py accepts --packets --window --bits --timeout --seed)
  --protocol gbn|sr|both   protocol to run (default both)
  --packets N              number of data packets (default 10)
  --window N               window size N (default 4)
  --bits k                 sequence-number bits; numbers wrap modulo 2^k (default 3)
  --loss p                 probability a data packet or ACK is lost (0..1)
  --corruption p           probability a data packet or ACK is corrupted (0..1)
  --delay p                probability a data packet or ACK gets extra random delay (0..1)
  --timeout s              retransmission timeout in seconds (default 0.6)
  --seed n                 random seed (default 722)
  --lose-first ids         comma list of packet ids whose FIRST copy is dropped (demo, e.g. 2)
  --quiet                  suppress the per-event log

DESIGN NOTES / ASSUMPTIONS
  * Link from the scenario: R = 2 Mbps, L = 1000 bytes = 8000 bits -> transmission time 4 ms;
    RTT = 500 ms -> one-way propagation 250 ms. Timeout default 600 ms (> RTT + window serialisation).
  * ACKs are treated as very small: no transmission time, only propagation delay.
  * GBN: base, nextseqnum, cumulative ACK (value = next expected packet), ONE timer for the oldest
    unACKed packet, on timeout resend all outstanding packets; receiver (expectedseqnum) discards
    out-of-order packets and re-ACKs the last in-order one.
  * SR: sender/receiver windows (base, nextseqnum, rcv_base), individual ACKs, one timer per packet,
    receiver buffers out-of-order packets and delivers in order, only timed-out packets are resent.
  * Channel: loss, corruption and extra delay (uniform 0.5-1.5 x timeout) apply to data AND ACKs.
    Corruption flips one bit; the receiver detects it with a 16-bit Internet checksum and discards
    the packet/ACK (no ACK for corrupted data -> sender recovers by timeout).
  * Logged sequence numbers wrap modulo 2^k; an absolute packet id is also kept internally to
    distinguish wrap-around cycles (receiver window checks rely on N <= allowed maximum).
  * Window limits enforced: SR needs N <= 2^(k-1); GBN needs N <= 2^k - 1.
  * Completion time = moment the sender receives the ACK that finishes the transfer.
    Throughput = delivered bits / completion time.
  * Results depend on the model and seed; they are simulation outcomes, not measurements
    of a real satellite link.
