# Test driver: scripted clients, one step at a time, printing what each receives.
import socket, sys, time
port = int(sys.argv[1])
socks = {}
def conn(name):
    s = socket.create_connection(("127.0.0.1", port)); s.settimeout(2); socks[name] = [s, b""]
def send(name, line):
    print(f"{name} > {line}"); socks[name][0].sendall((line + "\n").encode())
def recv(name, n=1):
    s = socks[name]
    for _ in range(n):
        while b"\n" not in s[1]:
            chunk = s[0].recv(4096)
            if not chunk: print(f"{name} < (closed)"); return
            s[1] += chunk
        line, s[1] = s[1].split(b"\n", 1)
        print(f"{name} < {line.decode()}")
conn("ann"); conn("bob")
send("ann", "SAY hi"); recv("ann")
send("ann", "NICK ann"); recv("ann")
send("bob", "NICK ann"); recv("bob")
send("bob", "NICK bob"); recv("bob"); recv("ann")
conn("cy"); send("cy", "NICK cy"); recv("cy"); recv("ann"); recv("bob")
send("bob", "SAY hello all"); recv("ann"); recv("cy"); recv("bob")
send("cy", "WHO"); recv("cy")
send("ann", "DANCE"); recv("ann")
socks["cy"][0].sendall(b"SAY one\nSAY two\n"); print("cy > SAY one + SAY two in one packet")
recv("ann", 2); recv("bob", 2); recv("cy", 2)
send("bob", "QUIT"); recv("bob"); recv("bob"); recv("ann"); recv("cy")
socks["cy"][0].close(); print("cy disconnects"); recv("ann")
send("ann", "WHO"); recv("ann")
send("ann", "SHUTDOWN"); recv("ann")
