"""Small, network-free release checks plus local HTTP health smoke test."""
import ast, json, pathlib, socket, subprocess, sys, tempfile, time, urllib.request
ROOT = pathlib.Path(__file__).resolve().parents[1]
for path in ROOT.glob("*.py"):
    ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
for path in ROOT.glob("*.js"):
    subprocess.run(["node", "--check", str(path)], check=True, capture_output=True)
subprocess.run(["node", "-e", "const fs=require('fs'),vm=require('vm'),a=require('assert');const c=vm.createContext({window:{},Date,Map,Number,Set,JSON});vm.runInContext(fs.readFileSync('library-tools.js','utf8'),c);a.equal(c.window.VitraLibraryTools.parse('Track Name,Artist Name\\nTest,Singer','Test.csv').tracks[0].t,'Test');"], cwd=ROOT, check=True, capture_output=True)
sys.path.insert(0, str(ROOT))
from lyrics_service import parse_lrc, LyricsService

lines = parse_lrc("[00:01.00]Primera línea\n[00:03.00]<00:03.00>Dos <00:03.50>palabras")
assert len(lines) == 2 and lines[1]["words"][1]["time"] == 3.5
with tempfile.TemporaryDirectory() as tmp:
    service = LyricsService(pathlib.Path(tmp))
    assert service.cache_lifetime({"releaseDate": "2020-01-01"}, {"unavailable": True}) == 300
    service.providers.shutdown(wait=True)
with socket.socket() as listener:
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
process = subprocess.Popen([sys.executable, "server.py", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
try:
    for attempt in range(50):
        if process.poll() is not None: raise RuntimeError("Server exited before health check: " + process.stderr.read().decode("utf8", errors="replace")[-3000:])
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1) as response:
                assert json.load(response)["status"] == "ok"
            break
        except OSError: time.sleep(.1)
    else: raise RuntimeError("Health check timed out")
finally:
    process.terminate()
    try: process.wait(timeout=5)
    except subprocess.TimeoutExpired: process.kill(); process.wait()
print("PASS: Python/JavaScript syntax, lyric timestamps/cache behavior and local /healthz.")
