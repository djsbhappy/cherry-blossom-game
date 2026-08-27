#!/usr/bin/env python3
"""
개발용 서버. index.html 을 고치고 저장하면 브라우저가 알아서 새로고침한다.

  python dev-server.py [포트]

index.html 자체는 건드리지 않는다. 응답을 보낼 때만 라이브리로드 스니펫을
</body> 앞에 끼워 넣으므로, 저장소 파일은 배포본 그대로 남는다.
"""
import http.server, socketserver, os, sys, time, threading, webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(ROOT, "index.html")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8123

# 파일이 바뀔 때마다 올라가는 세대 번호. SSE 핸들러가 이 값만 지켜본다.
_gen = 0

def _watch():
    global _gen
    last = None
    while True:
        try:
            m = os.path.getmtime(TARGET)
        except OSError:
            m = None
        if last is not None and m != last:
            _gen += 1
            print(f"[reload] index.html 변경 감지 → 브라우저 새로고침 (#{_gen})", flush=True)
        last = m
        time.sleep(0.3)

LIVERELOAD = """
<script>
/* dev-server.py 가 주입한 라이브리로드 (저장소 파일에는 없음) */
(() => {
  let es;
  const connect = () => {
    es = new EventSource('/__reload');
    es.onmessage = () => location.reload();
    es.onerror = () => { es.close(); setTimeout(connect, 1000); };
  };
  connect();
})();
</script>
""".encode("utf-8")

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, fmt, *args):
        if "__reload" not in (args[0] if args else ""):
            super().log_message(fmt, *args)

    def do_GET(self):
        if self.path.startswith("/__reload"):
            return self._sse()
        if self.path in ("/", "/index.html"):
            return self._html()
        if self.path == "/favicon.ico":
            # 없는 파일이라 SimpleHTTPRequestHandler 가 트레이스백을 뱉는다. 조용히 넘긴다.
            self.send_response(204); self.end_headers(); return
        return super().do_GET()

    def _html(self):
        with open(TARGET, "rb") as f:
            body = f.read()
        i = body.rfind(b"</body>")
        body = body[:i] + LIVERELOAD + body[i:] if i != -1 else body + LIVERELOAD
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")   # 고친 내용이 캐시에 막히면 안 된다
        self.end_headers()
        self.wfile.write(body)

    def _sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        seen = _gen
        try:
            while True:
                if _gen != seen:
                    seen = _gen
                    self.wfile.write(b"data: reload\n\n")
                else:
                    self.wfile.write(b": ping\n\n")   # 연결 유지용
                self.wfile.flush()
                time.sleep(0.3)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass   # 탭을 닫았을 뿐이다

class Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

if __name__ == "__main__":
    # 윈도우 콘솔 기본 코드페이지에서 한글 로그가 깨지지 않게
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    threading.Thread(target=_watch, daemon=True).start()
    url = f"http://127.0.0.1:{PORT}/index.html"
    print(f"개발 서버: {url}  (index.html 저장 시 자동 새로고침, Ctrl+C 종료)", flush=True)
    if "--no-open" not in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    Server(("127.0.0.1", PORT), Handler).serve_forever()
