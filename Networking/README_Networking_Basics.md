# Networking Basics (vendor-neutral) - Interview Notes

Generic concepts only: nothing here is specific to any vendor. Demo code: [switch_gateway_sim.py](./switch_gateway_sim.py) (learning switch, MAC table, flooding, aging, MAC flooding attack, default gateway decision, NAT).

Analogy used throughout: a network is a **city**, data is a **letter**, the MAC is a person's **name**, the IP is the **postal address**.

---

## 1. Layers (what each one does)

| # | OSI layer | Unit of data | Addressing | Examples | Devices |
|---|---|---|---|---|---|
| 7 | Application | data | - | HTTP, DNS, DHCP, SSH | proxies, load balancers (L7) |
| 6 | Presentation | data | - | TLS, encoding | |
| 5 | Session | data | - | session setup/teardown | |
| 4 | Transport | segment (TCP) / datagram (UDP) | port numbers | TCP, UDP | firewalls, load balancers (L4) |
| 3 | Network | packet | IP address | IP, ICMP, routing | router, L3 switch |
| 2 | Data link | frame | MAC address | Ethernet, VLAN, ARP | switch, bridge, access point |
| 1 | Physical | bits | - | cables, Wi-Fi radio, fibre | hub, repeater, cables |

TCP/IP simplifies this into 4 layers: Application (5-7), Transport (4), Internet (3), Link (1-2).

**Encapsulation:** data gets wrapped as it goes down: data -> segment (+ports) -> packet (+IPs) -> frame (+MACs) -> bits. The receiver unwraps in reverse.

Memory aid (top to bottom): **A**ll **P**eople **S**eem **T**o **N**eed **D**ata **P**rocessing.

---

## 2. Hub, switch, router, gateway

| Device | Layer | Decides by | Behaviour (layman) |
|---|---|---|---|
| **Repeater / hub** | 1 | nothing | Loudspeaker: copies every signal to all other ports. One shared collision domain. Obsolete. |
| **Bridge** | 2 | MAC | Early two-port switch: joins two segments and filters by MAC. |
| **Switch** | 2 | MAC | Smart postman: learns which MAC is behind which port, delivers only there. |
| **Layer-3 switch** | 2 + 3 | MAC + IP | A switch that can also route between VLANs at hardware speed. |
| **Router** | 3 | IP | Connects different networks, picks the best path using a routing table. |
| **Gateway** | 3-7 | IP (or protocol) | The exit from one network to another. Often the router ("default gateway"); can also translate protocols (e.g. a sensor protocol to IP, email gateway). |
| **Firewall** | 3-7 | rules | Allows or blocks traffic by IP, port, protocol, or application. |
| **Load balancer** | 4 or 7 | port / content | Spreads requests across several servers. |
| **Access point** | 2 | MAC | Bridges Wi-Fi devices onto the wired network. |

### Collision vs broadcast domains
- **Collision domain:** devices that can interfere with each other's transmission. Hub: all ports share one. Switch: each port is its own.
- **Broadcast domain:** devices that receive a broadcast. A switch keeps one (unless VLANs split it); a **router** separates broadcast domains.

---

## 3. MAC address and the switch

- **MAC address:** 48-bit hardware address, written `AA:BB:CC:11:22:33`. The first half identifies the manufacturer (OUI). Meaningful on the local network only. Broadcast MAC: `FF:FF:FF:FF:FF:FF`.
- **IP address:** logical address assigned by configuration/DHCP, used to reach other networks.

### MAC table (also called CAM table or forwarding table)
A table in switch memory: `MAC address -> port (+ VLAN, + age)`.

| MAC | Port |
|---|---|
| AA:AA | 1 |
| BB:BB | 2 |
| CC:CC | 3 |

### What a switch does with every frame
1. **Learn:** read the *source* MAC and record the port it arrived on.
2. **Forward / filter / flood** based on the *destination* MAC:
   - **Known unicast:** send out of that one port only (forward).
   - **Destination is on the same port it came from:** drop it (filter).
   - **Unknown unicast, broadcast, or multicast (no snooping):** **flood** to all ports in the VLAN except the incoming one.
3. **Age:** an entry not refreshed within the aging time (commonly 300 s) is deleted, so moved or powered-off devices are forgotten.

```
 A(port1)           Switch            B(port2)
   |--- frame A->B --->|  learn A=1; B unknown -> flood to 2,3,4
   |                   |--------------->|  B replies
   |<--- reply B->A ---|  learn B=2; A known -> only port 1
   |--- frame A->B --->|  both known -> only port 2
```

### Switching methods
- **Store-and-forward:** receive the whole frame, check the CRC (error check), then forward. Safest, standard.
- **Cut-through:** start forwarding after reading the destination MAC. Lower latency, may forward bad frames.

### Why a switch beats a hub
Faster (dedicated bandwidth per port), full duplex (send and receive at once), no collisions, more privacy (traffic isn't copied everywhere), and many conversations in parallel.

### Switch problems and attacks
- **MAC table overflow / MAC flooding:** an attacker sends many fake source MACs, the table fills, the switch floods everything like a hub, and traffic can be sniffed. Defence: **port security** (limit MACs per port), 802.1X, monitoring table usage.
- **MAC spoofing:** pretending to be another device's MAC.
- **Broadcast storm / loop:** a loop makes frames circulate forever. Defence: **STP**, storm control.
- **ARP spoofing:** forging ARP replies to intercept traffic. Defence: dynamic ARP inspection.

---

## 4. Switch features worth knowing

| Feature | Plain meaning |
|---|---|
| **VLAN** | Splits one physical switch into several separate virtual networks (separate broadcast domains). Hosts in different VLANs need a router/L3 switch to talk. Good for security and less broadcast noise. |
| **Access port vs trunk port** | Access = one VLAN, to an end device. Trunk = carries many VLANs between switches, each frame tagged (**802.1Q** tag). |
| **STP (Spanning Tree Protocol)** | Blocks redundant links to prevent loops, and unblocks them if the active path fails. RSTP is the faster version. |
| **Link aggregation (LACP / port-channel)** | Bundles several cables into one logical link for more bandwidth and redundancy. |
| **Port security** | Limits which/how many MACs may use a port. |
| **Duplex / speed** | Full vs half duplex; a mismatch causes errors and slowness. |
| **PoE** | Power over Ethernet: powers phones, cameras, access points through the cable. |
| **QoS** | Prioritises important traffic (voice, video) when congested. |
| **Port mirroring (SPAN)** | Copies a port's traffic to another port for analysis. |
| **IGMP snooping** | Sends multicast only to ports that asked for it. |
| **Managed vs unmanaged** | Managed switches can be configured, monitored (SNMP, syslog) and secured; unmanaged are plug and play. |

---

## 5. Gateway and routing (how traffic leaves the network)

**Subnet:** IP + mask define which addresses are "local". `192.168.1.10/24` means the first 24 bits are the network, so `192.168.1.0-255` is local (254 usable hosts).

**What a host does when sending:**
1. Compare the destination IP with my subnet (using my mask).
2. **Same subnet:** find its MAC with **ARP** and send the frame directly.
3. **Different subnet:** send the frame to the **default gateway's** MAC (found with ARP). The destination IP is unchanged.

**What a router does:** strips the frame, reads the destination IP, finds the best match in its **routing table** (longest prefix match), decrements **TTL**, rewrites the frame with new MAC addresses for the next hop, and sends it on.

> MAC addresses change at every hop. IP addresses stay the same end to end (except where NAT rewrites them).

**Routing table entry:** `destination network / mask -> next hop, outgoing interface, metric`. A `0.0.0.0/0` entry is the **default route** (anything not matched elsewhere).
Routes come from: directly connected networks, **static** configuration, or **dynamic protocols** (OSPF inside an organisation, BGP between organisations).

**NAT (Network Address Translation):** many private devices share one public IP. The router rewrites the private source `192.168.1.10:51000` to `public-ip:40000` and keeps a table so replies find their way back. PAT/NAT overload = the common home/office kind.

**Private IP ranges:** `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`. `169.254.x.x` means DHCP failed (self-assigned).

---

## 6. Supporting protocols

| Protocol | Job | Key idea |
|---|---|---|
| **ARP** | IP -> MAC on the local network | "Who has 192.168.1.1?" Broadcast question, unicast answer, cached in an ARP table. |
| **DHCP** | Auto-assigns IP, mask, gateway, DNS | Four steps: Discover, Offer, Request, Acknowledge (DORA). |
| **DNS** | Name -> IP | Resolver asks recursively: cache -> root -> TLD -> authoritative server. |
| **ICMP** | Errors and diagnostics | `ping` (echo), `traceroute` (uses TTL to reveal each hop). |
| **TCP** | Reliable, ordered delivery | 3-way handshake (SYN, SYN-ACK, ACK), acknowledgements, retransmission, flow and congestion control. |
| **UDP** | Fast, no guarantees | No handshake, no retransmission. Good for DNS, voice, video, streaming telemetry. |

**TCP vs UDP:** TCP = reliable, ordered, connection-based, heavier (web, email, file transfer, SSH). UDP = connectionless, low latency, may lose or reorder (DNS, VoIP, gaming, syslog, SNMP traps).

**Common ports:** 22 SSH, 23 Telnet, 25 SMTP, 53 DNS, 67/68 DHCP, 80 HTTP, 123 NTP, 161/162 SNMP, 443 HTTPS, 514 syslog, 3389 RDP.

---

## 7. Monitoring and troubleshooting

**Signals a switch or router exposes (via SNMP, syslog, streaming telemetry):**
- Interface up/down and **flapping** counts, speed/duplex
- Error counters: CRC errors, input/output errors, discards, drops
- Utilisation per port, broadcast/multicast rates
- MAC table and ARP table size, CPU, memory, temperature, fan/power status
- Spanning tree topology changes, routing neighbour state

**Top-down troubleshooting ("can't reach X"):**
1. **Physical (L1):** cable, link light, port up? errors?
2. **Data link (L2):** right VLAN? MAC learned on the expected port? duplex mismatch? loop?
3. **Network (L3):** valid IP, mask, gateway? `ping` the gateway, then beyond; `traceroute` to see where it stops.
4. **Name resolution:** can it resolve DNS? (`nslookup`, `dig`).
5. **Transport/app (L4-7):** is the port open (firewall)? is the service listening? check logs.

**Useful commands:** `ping`, `traceroute` / `tracert`, `ipconfig` / `ifconfig` / `ip addr`, `arp -a`, `netstat` / `ss`, `nslookup` / `dig`, `curl`, `tcpdump` / Wireshark.

**Symptoms -> likely causes**

| Symptom | Likely cause |
|---|---|
| Can reach local devices, not the internet | Wrong or missing default gateway, NAT/router issue, DNS |
| Can reach by IP, not by name | DNS problem |
| `169.254.x.x` address | DHCP server unreachable |
| Intermittent slowness and errors | Duplex mismatch, bad cable (CRC errors), congestion |
| Network suddenly very slow, high broadcast | Loop / broadcast storm (STP issue) |
| Two devices fight over an address | Duplicate IP |
| Can't reach another VLAN | No inter-VLAN routing, or wrong VLAN on the port |

---

## 8. Likely interview questions with short answers

**Hub vs switch?** A hub repeats every frame to all ports (one collision domain, half duplex). A switch learns MAC addresses and forwards only to the destination port, so no collisions and more bandwidth and privacy.

**What is a MAC table and how is it built?** A map of MAC address to port, learned from the source MAC of incoming frames and aged out after inactivity.

**What happens if the destination MAC isn't in the table?** The switch floods the frame out of all ports in that VLAN except the one it arrived on. The reply teaches the switch the port.

**What happens when the MAC table is full?** New MACs can't be learned, so more traffic is flooded (hub-like behaviour). Could be an attack (MAC flooding), so use port security.

**Switch vs router?** A switch forwards frames inside one network using MACs. A router forwards packets between networks using IPs and separates broadcast domains.

**What is a default gateway?** The router address a host sends traffic to when the destination is outside its subnet.

**How does ARP work?** The host broadcasts "who has this IP?", the owner replies with its MAC, and the host caches it.

**What is a VLAN and why use it?** A logical split of one switch into separate broadcast domains. It improves security, reduces broadcast traffic, and groups devices logically. Inter-VLAN traffic needs a router or L3 switch.

**What is STP?** A protocol that disables redundant links to prevent loops, and re-enables them on failure.

**What is a broadcast storm?** Frames looping or multiplying endlessly, saturating the network. Caused by switching loops. Prevented with STP and storm control.

**Explain what happens when you open a website.** DNS resolves the name, TCP handshake to the server (via ARP + default gateway + routing + NAT), TLS handshake for HTTPS, HTTP request and response.

**TCP vs UDP?** TCP: reliable, ordered, handshake. UDP: fast, no guarantees.

**How would you detect network problems with data (ties to your AI work)?** Collect interface counters and events, baseline each port/device against peers, alert on abnormal error rates, flapping, utilisation or table size, and correlate with config changes.

## 9. One-line summaries
- Hub: shouts to everyone. Switch: delivers to the right port using the MAC table. Router: moves traffic between networks using IPs. Gateway: the exit from your network.
- MACs change every hop; IPs stay end to end (except NAT).
- Switch learns from the **source** MAC and forwards by the **destination** MAC.
- Unknown or broadcast means flood. Loops need STP. Splitting networks needs VLANs plus a router.

## 10. Practice
1. Draw a 4-port switch and trace A->B, B->A, A->B, showing the MAC table after each frame (then run `switch_gateway_sim.py` to check).
2. Explain, without notes, what happens from typing a URL to seeing the page.
3. Explain a MAC flooding attack and two defences.
4. List the first three things you check when a device "can't reach the internet".
