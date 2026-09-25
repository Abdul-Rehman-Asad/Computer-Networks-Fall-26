
import socket
import struct
import random

def encode_name(domain):
    result = b""
    for part in domain.strip(".").split("."):
        result += bytes([len(part)]) + part.encode()
    return result + b"\0"

def read_name(data, pos):
    name = []
    while True:
        length = data[pos]
        if length == 0:
            return ".".join(name), pos + 1
        if length >= 192:
            pointer = ((length - 192) << 8) + data[pos + 1]
            n, _ = read_name(data, pointer)
            return ".".join(name + [n]), pos + 2
        pos += 1
        name.append(data[pos:pos + length].decode())
        pos += length

def dns_query(domain, server):
    tid = random.randint(0, 65535)

    header = struct.pack("!HHHHHH", tid, 0x0100, 1, 0, 0, 0)
    question = encode_name(domain) + struct.pack("!HH", 1, 1)
    packet = header + question

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5)

    try:
        sock.sendto(packet, (server, 53))
        data, _ = sock.recvfrom(4096)

        rid, flags, qd, an, ns, ar = struct.unpack("!HHHHHH", data[:12])

        if rid != tid:
            print("Invalid response")
            return

        rcode = flags & 15
        status = {
            0: "NOERROR",
            1: "FORMERR",
            2: "SERVFAIL",
            3: "NXDOMAIN",
            4: "NOTIMP",
            5: "REFUSED"
        }.get(rcode, "UNKNOWN")

        print("\nTransaction ID :", rid)
        print("Query Name     :", domain)
        print("Query Type     : A")
        print("Response Status:", status)

        pos = 12
        for _ in range(qd):
            _, pos = read_name(data, pos)
            pos += 4

        print("\nAnswer Records:")

        found = False

        for _ in range(an):
            name, pos = read_name(data, pos)
            rtype, rclass, ttl, length = struct.unpack(
                "!HHIH", data[pos:pos + 10]
            )
            pos += 10

            if rtype == 1 and length == 4:
                ip = socket.inet_ntoa(data[pos:pos + 4])
                print("Name           :", name)
                print("Type           : A")
                print("IPv4 Address   :", ip)
                print("TTL            :", ttl, "seconds")
                found = True

            pos += length

        if not found:
            print("No A record found.")

    except socket.timeout:
        print("DNS request timed out.")

    except Exception as e:
        print("Error:", e)

    finally:
        sock.close()


server = input("Enter DNS server IP: ")

while True:
    domain = input("\nEnter domain name (or exit): ")

    if domain.lower() == "exit":
        break

    if domain:
        dns_query(domain, server)
