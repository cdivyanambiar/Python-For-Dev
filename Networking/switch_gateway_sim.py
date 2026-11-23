"""Learning switch + gateway simulation (layman networking demo).

Shows: MAC learning, flooding, unicast forwarding, aging, MAC flooding attack, and a host
choosing between "deliver locally" and "send to the default gateway".

Run: python switch_gateway_sim.py
"""
import ipaddress
import time


class Switch:
    """A Layer-2 switch: learns which MAC is on which port and forwards frames accordingly."""

    def __init__(self, ports, table_size=4, aging_seconds=300):
        """
        Args:
            ports: number of ports.
            table_size: max MAC table entries (real switches: thousands; small here to show overflow).
            aging_seconds: entries unused for this long are removed.
        """
        self.ports = ports
        self.table_size = table_size
        self.aging = aging_seconds
        self.mac_table = {}                          # MAC -> (port, last_seen)

    def receive(self, src_mac, dst_mac, in_port, now=None):
        """Handle one frame arriving on in_port. Returns the list of ports it is sent out of."""
        now = time.time() if now is None else now
        self._age(now)
        # 1. LEARN: remember the sender's port (source MAC)
        if src_mac in self.mac_table or len(self.mac_table) < self.table_size:
            self.mac_table[src_mac] = (in_port, now)
        # 2. FORWARD: look up the destination MAC
        if dst_mac in self.mac_table:
            out = self.mac_table[dst_mac][0]
            return [] if out == in_port else [out]   # known: send to that port only
        return [p for p in range(1, self.ports + 1) if p != in_port]   # unknown/broadcast: FLOOD

    def _age(self, now):
        """Remove entries that have been silent longer than the aging time."""
        self.mac_table = {m: (p, t) for m, (p, t) in self.mac_table.items() if now - t < self.aging}


class Hub:
    """A Layer-1 hub: no table, repeats every frame to all other ports."""

    def __init__(self, ports):
        """ports: number of ports."""
        self.ports = ports

    def receive(self, src_mac, dst_mac, in_port):
        """Always flood."""
        return [p for p in range(1, self.ports + 1) if p != in_port]


class Host:
    """A computer with an IP, a subnet mask and a default gateway."""

    def __init__(self, ip, mask, gateway):
        """Store the network settings."""
        self.ip = ipaddress.ip_interface(f"{ip}/{mask}")
        self.gateway = ipaddress.ip_address(gateway)

    def next_hop(self, dst_ip):
        """Where does this host send a packet for dst_ip? Local delivery or the gateway."""
        dst = ipaddress.ip_address(dst_ip)
        return dst if dst in self.ip.network else self.gateway   # same network -> direct; otherwise -> gateway


class Router:
    """Gateway with NAT: rewrites private source IPs to its public IP and remembers the mapping."""

    def __init__(self, public_ip):
        """public_ip: the address the outside world sees."""
        self.public_ip = public_ip
        self.nat = {}                                # public port -> (private ip, private port)
        self._next_port = 40000

    def outbound(self, src_ip, src_port):
        """Translate a private source to (public ip, public port) and remember it."""
        port = self._next_port
        self._next_port += 1
        self.nat[port] = (src_ip, src_port)
        return self.public_ip, port

    def inbound(self, public_port):
        """A reply arrives for public_port: find the private host it belongs to."""
        return self.nat.get(public_port)


if __name__ == "__main__":
    A, B, C = "AA:AA", "BB:BB", "CC:CC"

    # Hub: everything goes everywhere
    assert Hub(4).receive(A, B, 1) == [2, 3, 4]

    # Switch: first frame floods (B unknown), reply teaches B's port, then traffic is unicast
    sw = Switch(ports=4)
    assert sw.receive(A, B, 1, now=0) == [2, 3, 4]       # A->B: B unknown, flood. A learned on port 1
    assert sw.receive(B, A, 2, now=1) == [1]             # B->A: A known, only port 1. B learned on port 2
    assert sw.receive(A, B, 1, now=2) == [2]             # A->B: now only port 2
    assert sw.receive(C, "FF:FF", 3, now=3) == [1, 2, 4] # broadcast always floods
    print("MAC table:", {m: p for m, (p, _) in sw.mac_table.items()})

    # Aging: a silent device is forgotten after the timer
    sw.receive(A, B, 1, now=1000)
    assert B not in sw.mac_table

    # MAC flooding attack: fake sources fill the table, so real devices can no longer be learned -> acts like a hub
    sw = Switch(ports=4, table_size=4)
    for i in range(4):
        sw.receive(f"FA:KE:{i}", "FF:FF", 4, now=0)
    assert sw.receive(A, B, 1, now=1) == [2, 3, 4]       # A could not be learned, B unknown: flooded
    assert A not in sw.mac_table

    # Gateway decision
    pc = Host("192.168.1.10", "255.255.255.0", "192.168.1.1")
    assert str(pc.next_hop("192.168.1.20")) == "192.168.1.20"   # same network: deliver directly
    assert str(pc.next_hop("8.8.8.8")) == "192.168.1.1"         # other network: send to the gateway

    # NAT
    r = Router("203.0.113.5")
    pub = r.outbound("192.168.1.10", 51000)
    assert pub == ("203.0.113.5", 40000) and r.inbound(40000) == ("192.168.1.10", 51000)
    print("switch/gateway simulation: all checks passed")
