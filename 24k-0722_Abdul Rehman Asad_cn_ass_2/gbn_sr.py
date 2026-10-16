"""
Reliable Transfer for a Disaster-Response Network
Roll No: 24K-0722  (random seed = 722)
"""
import argparse
import heapq
import random
import time

LINK_RATE_BPS = 2_000_000
PACKET_BITS = 8_000
TX_TIME = PACKET_BITS / LINK_RATE_BPS     
ONE_WAY_DELAY = 0.250                   
DEFAULT_TIMEOUT = 0.600                 
ROLL_SEED = 722


def checksum16(data: bytes) -> int:
    """16-bit Internet (one's complement) checksum."""
    if len(data) % 2:
        data += b"\x00"
    total = 0
    for i in range(0, len(data), 2):
        total += (data[i] << 8) + data[i + 1]
        total = (total & 0xFFFF) + (total >> 16)
    return ~total & 0xFFFF


class Simulator:
    def __init__(self, protocol, packets, window, bits, loss, corruption, delay,
                 timeout, seed, verbose=True, lose_first=()):
        self.protocol = protocol.lower()
        self.total = packets
        self.window = window            
        self.bits = bits                
        self.space = 2 ** bits       
        self.loss = loss
        self.corruption = corruption
        self.delay = delay
        self.timeout = timeout
        self.seed = seed
        self.rng = random.Random(seed)
        self.verbose = verbose
        self.lose_first = set(lose_first)  
        self.forced_done = set()

        self.events = []
        self.counter = 0
        self.now = 0.0
        self.link_free = 0.0           

        self.transmissions = 0
        self.retransmissions = 0
        self.checksum_errors = 0
        self.delivered = []
        self.first_sent = set()
        self.logs = []

        self.base = 0
        self.nextseqnum = 0
        self.expectedseqnum = 0
        self.rcv_base = 0
        self.buffer = {}
        self.acked = set()
        self.timer_generation = {}
        self.gbn_timer_generation = 0

    def log(self, message):
        line = f"t={self.now * 1000:10.1f} ms | {message}"
        self.logs.append(line)
        if self.verbose:
            print(line)

    def schedule(self, at, kind, data):
        self.counter += 1
        heapq.heappush(self.events, (at, self.counter, kind, data))

    def seq(self, pid):
        return pid % self.space

    def channel(self, kind, pid):
        """Unreliable channel for a data packet or an ACK.

        Wire format (simulation):
          data: (pid, seq_field, payload, checksum)   checksum over seq+payload
          ack : (pid, seq_field, checksum)            checksum over seq
        `pid` is the absolute packet id (simulation bookkeeping only); the
        header field shown in logs is seq = pid mod 2^k.
        """
        seq = self.seq(pid)
        seq_bytes = seq.to_bytes(2, "big")
        if kind == "data":
            payload = f"EOC-MSG-{pid:05d}".encode()
            wire = [pid, seq, payload, checksum16(seq_bytes + payload)]
            depart = max(self.now, self.link_free)   
            self.link_free = depart + TX_TIME
            tx = TX_TIME
            label = f"data seq={seq} (id={pid})"
        else:
            wire = [pid, seq, checksum16(seq_bytes)]
            depart = self.now                          
            tx = 0.0
            label = f"ACK value={seq} (id={pid})"

        if kind == "data" and pid in self.lose_first and pid not in self.forced_done:
            self.forced_done.add(pid)
            self.rng.random(); self.rng.random(); self.rng.random()  
            self.log(f"CHANNEL LOSS (forced): {label}")
            return

        lost = self.rng.random() < self.loss
        corrupted = self.rng.random() < self.corruption
        delayed = self.rng.random() < self.delay
        if lost:
            self.log(f"CHANNEL LOSS: {label}")
            return
        if corrupted:               
            if kind == "data":
                b = bytearray(wire[2]); b[len(b) // 2] ^= 0x01; wire[2] = bytes(b)
            else:
                wire[1] ^= 0x01
            self.log(f"CHANNEL CORRUPTION: {label}; one bit flipped in transit")
        extra = 0.0
        if delayed:
            extra = self.rng.uniform(0.5 * self.timeout, 1.5 * self.timeout)
            self.log(f"CHANNEL DELAY: {label}; extra delay={extra * 1000:.0f} ms")
        self.schedule(depart + tx + ONE_WAY_DELAY + extra, kind, tuple(wire))

    def send_data(self, pid, retransmission=False):
        self.transmissions += 1
        if retransmission:
            self.retransmissions += 1
            self.log(f"RETRANSMIT data seq={self.seq(pid)} (id={pid})")
        else:
            self.log(f"SEND data seq={self.seq(pid)} (id={pid}); window=[{self.base}..{self.base + self.window - 1}]")
        self.channel("data", pid)
        if self.protocol == "gbn":
            if not retransmission and pid == self.base:
                self.start_gbn_timer()
        else:
            self.start_sr_timer(pid)

    def start_gbn_timer(self):
        self.gbn_timer_generation += 1
        due = self.now + self.timeout
        self.schedule(due, "gbn_timeout", self.gbn_timer_generation)
        self.log(f"START GBN timer (oldest unACKed base={self.base}) until t={due * 1000:.1f} ms")

    def start_sr_timer(self, pid):
        gen = self.timer_generation.get(pid, 0) + 1
        self.timer_generation[pid] = gen
        self.schedule(self.now + self.timeout, "sr_timeout", (pid, gen))

    def fill_window(self):
        while self.nextseqnum < self.total and self.nextseqnum < self.base + self.window:
            pid = self.nextseqnum
            self.nextseqnum += 1
            self.send_data(pid, pid in self.first_sent)
            self.first_sent.add(pid)

    def sender_done(self):
        return self.base >= self.total

    def send_ack(self, ack_id):
        self.log(f"SEND ACK value={self.seq(ack_id)} (id={ack_id})")
        self.channel("ack", ack_id)

    def receive_data(self, wire):
        pid, seq, payload, csum = wire
        if checksum16(seq.to_bytes(2, "big") + payload) != csum:
            self.checksum_errors += 1
            self.log(f"RECEIVE data seq={seq}: CHECKSUM ERROR; discard, no ACK")
            return
        if self.protocol == "gbn":
            if pid == self.expectedseqnum:
                self.log(f"RECEIVE data seq={seq}; in order, deliver; expectedseqnum->{self.expectedseqnum + 1}")
                self.delivered.append(pid)
                self.expectedseqnum += 1
                self.send_ack(self.expectedseqnum)         
            else:
                self.log(f"RECEIVE out-of-order data seq={seq}; DISCARD; expectedseqnum={self.seq(self.expectedseqnum)}")
                self.send_ack(self.expectedseqnum)    
        else:
            if self.rcv_base <= pid < self.rcv_base + self.window:
                if pid in self.buffer:
                    self.log(f"RECEIVE duplicate data seq={seq}; already buffered")
                else:
                    self.buffer[pid] = payload
                    self.log(f"RECEIVE data seq={seq}; BUFFER (rcv_base={self.rcv_base})")
                self.send_ack(pid)                         
                while self.rcv_base in self.buffer:
                    self.log(f"DELIVER in order id={self.rcv_base}")
                    self.delivered.append(self.rcv_base)
                    del self.buffer[self.rcv_base]
                    self.rcv_base += 1
                    self.log(f"  receiver window slides: rcv_base={self.rcv_base}")
            elif self.rcv_base - self.window <= pid < self.rcv_base:
                self.log(f"RECEIVE old duplicate seq={seq}; ACK again")
                self.send_ack(pid)
            else:
                self.log(f"RECEIVE data seq={seq} outside receiver window; discard")

    def receive_ack(self, wire):
        pid, seq, csum = wire
        if checksum16(seq.to_bytes(2, "big")) != csum:
            self.checksum_errors += 1
            self.log("RECEIVE ACK: CHECKSUM ERROR; ignore")
            return
        if self.protocol == "gbn":
            if self.base < pid <= self.nextseqnum:
                self.log(f"RECEIVE cumulative ACK value={seq} (id={pid}); base {self.base}->{pid}")
                self.base = pid
                if self.base < self.nextseqnum:
                    self.start_gbn_timer()                 
                else:
                    self.gbn_timer_generation += 1         
                self.fill_window()
            else:
                self.log(f"RECEIVE duplicate/old ACK value={seq}; ignore")
        else:
            if 0 <= pid < self.nextseqnum:
                if pid not in self.acked:
                    self.acked.add(pid)
                    self.log(f"RECEIVE individual ACK seq={seq}; mark id={pid} ACKed")
                else:
                    self.log(f"RECEIVE duplicate ACK seq={seq}")
                moved = False
                while self.base in self.acked:
                    self.base += 1
                    moved = True
                if moved:
                    self.log(f"  sender window slides: base={self.base}")
                self.fill_window()
            else:
                self.log(f"RECEIVE invalid ACK seq={seq}; ignore")

    def run(self):
        if self.total < 1 or self.window < 1 or self.bits < 1:
            raise ValueError("packets, window and bits must be positive")
        if self.protocol == "sr" and self.window > self.space // 2:
            raise ValueError(f"SR window must be <= 2^(k-1) = {self.space // 2} for k={self.bits}")
        if self.protocol == "gbn" and self.window > self.space - 1:
            raise ValueError(f"GBN window must be <= 2^k - 1 = {self.space - 1} for k={self.bits}")
        started = time.perf_counter()
        self.fill_window()
        processed = 0
        while self.events and not self.sender_done():
            self.now, _, kind, data = heapq.heappop(self.events)
            processed += 1
            if processed > 2_000_000:
                raise RuntimeError("too many events; reduce error probabilities or raise timeout")
            if kind == "data":
                self.receive_data(data)
            elif kind == "ack":
                self.receive_ack(data)
            elif kind == "gbn_timeout":
                if data == self.gbn_timer_generation and self.base < self.nextseqnum:
                    self.log(f"TIMEOUT (GBN): base={self.base}; resend ALL outstanding {self.base}..{self.nextseqnum - 1}")
                    for pid in range(self.base, self.nextseqnum):
                        self.send_data(pid, True)
                    self.start_gbn_timer()
            elif kind == "sr_timeout":
                pid, gen = data
                if self.timer_generation.get(pid) == gen and pid not in self.acked and pid >= self.base:
                    self.log(f"TIMEOUT (SR): packet id={pid}; resend only this packet")
                    self.send_data(pid, True)
        elapsed = time.perf_counter() - started
        if self.delivered != list(range(self.total)):
            raise RuntimeError(f"delivery failed or out of order: {len(self.delivered)}/{self.total}")
        sim_s = self.now
        return {
            "protocol": self.protocol.upper(),
            "packets": self.total,
            "window": self.window,
            "seq_bits": self.bits,
            "transmissions": self.transmissions,
            "retransmissions": self.retransmissions,
            "delivered": len(self.delivered),
            "completion_time_ms": round(sim_s * 1000, 1),
            "throughput_kbps": round(self.total * PACKET_BITS / sim_s / 1000, 2) if sim_s else 0,
            "execution_time_s": round(elapsed, 6),
            "seed": self.seed,
        }


def main():
    p = argparse.ArgumentParser(description="Task 3: GBN and Selective Repeat reliable-transfer simulator "
                                "(for the 200-packet experiments run run_experiments.py)")
    p.add_argument("--protocol", choices=["gbn", "sr", "both"], default="both")
    p.add_argument("--packets", type=int, default=10, help="number of data packets")
    p.add_argument("--window", type=int, default=4, help="window size N")
    p.add_argument("--bits", type=int, default=3, help="sequence-number bits k (wrap modulo 2^k)")
    p.add_argument("--loss", type=float, default=0.0, help="loss probability (data and ACKs)")
    p.add_argument("--corruption", type=float, default=0.0, help="corruption probability (data and ACKs)")
    p.add_argument("--delay", type=float, default=0.0, help="extra-delay probability (data and ACKs)")
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="timeout in seconds")
    p.add_argument("--seed", type=int, default=ROLL_SEED, help="random seed (default 722 = roll 24K-0722)")
    p.add_argument("--lose-first", default="", help="comma list of packet ids whose first copy is lost, e.g. 2")
    p.add_argument("--quiet", action="store_true", help="suppress event log")
    a = p.parse_args()
    for v in (a.loss, a.corruption, a.delay):
        if not 0 <= v <= 1:
            p.error("loss, corruption and delay must be between 0 and 1")
    lose_first = [int(x) for x in a.lose_first.split(",") if x.strip()]
    for proto in (["gbn", "sr"] if a.protocol == "both" else [a.protocol]):
        print(f"\n===== {proto.upper()} SIMULATION =====")
        sim = Simulator(proto, a.packets, a.window, a.bits, a.loss, a.corruption, a.delay,
                        a.timeout, a.seed, not a.quiet, lose_first)
        result = sim.run()
        print("\nSUMMARY")
        for k, v in result.items():
            print(f"{k}: {v}")


if __name__ == "__main__":
    main()
