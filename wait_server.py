import sys, time, urllib.request

port = int(sys.argv[1]) if len(sys.argv) > 1 else 8799
timeout = float(sys.argv[2]) if len(sys.argv) > 2 else 30
url = f"http://127.0.0.1:{port}/api/health"
end = time.time() + timeout
while time.time() < end:
    try:
        with urllib.request.urlopen(url, timeout=1) as r:
            if r.status == 200:
                print(f"READY {url}")
                raise SystemExit(0)
    except Exception:
        time.sleep(0.4)
print(f"TIMEOUT {url}")
raise SystemExit(1)
