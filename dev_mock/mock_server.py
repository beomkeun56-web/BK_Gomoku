#!/usr/bin/env python3
"""두뇌서버(brain) 흉내 — 웹앱(index.html) 맥 구독 경로 로컬 시험용.

  python3 dev_mock/mock_server.py            # :8787 로 뜬다(정상 시나리오)
  python3 dev_mock/mock_server.py --scenario need_replay   # 첫 평시 턴에 need_replay 를 던진다
  python3 dev_mock/mock_server.py --scenario err           # err 프레임을 던진다
  python3 dev_mock/mock_server.py --port 8787 --root .     # 게임 파일도 같은 포트로 서빙(동일 출처 → CORS 없음)

엔드포인트
  GET  /ping        → {"ok":true,"ver":...}
  POST /game        → SSE: data:{"t":".."} 여러 개 → data:{"done":true}
                      세션 없음(=데몬 재시작) → data:{"need_replay":true}
  POST /game_image  → {"b64":"<1x1 png>","mime":"image/png"}
그 밖의 GET 은 --root 아래 정적 파일(index.html 등)로 서빙한다.
"""
import argparse, json, os, sys, time, threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

VER = 'mock-brain 0.1'
# 1x1 png
PNG_1X1 = ('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8'
           'z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')

SESS = {}            # sid -> {'system':str, 'n':int}
LOCK = threading.Lock()
ARGS = None
STATE = {'replay_fired': False}

MOCK_TURN = (
    '[IMG] Tense medium close-up inside a Korean National Assembly office at dusk, '
    'warm desk-lamp key light, the lawmaker leans forward while an aide presents a document. [/IMG]\n'
    '# **🇰🇷 첫 등원, 첫 시험** 〔2026/08/22(토) 오전 10시〕\n'
    '<prog>초선 의원 · 여의도 │ 2026/08/22 │ 1막 │ 다음 ▷ 첫 국정감사 2026/10/05</prog>\n'
    '<goal>목표=첫 국정감사 데뷔 (통과: 민심 48·명분 45)</goal> '
    '<stat>세력 21 │ 민심 34 │ 리스크 12 │ 명분 30</stat>\n'
    '> 첫 상임위 배정 협상에서 한 발을 걸쳤다.\n\n'
    '## 의원회관 복도 〔오전 10시〕\n'
    '보좌관이 서류를 내밀며 목소리를 낮춘다.\n'
    '> 이채영 "선배 방에서 벌써 명단을 돌렸답니다."\n'
    '<good>당직자 두 명이 먼저 손을 내밀었다.</good>\n\n'
    '## **✦ 어떻게 하시겠습니까?**\n'
    '1. "정면으로 붙죠. 명단부터 받아옵시다." 〔↑·명분↑〕\n'
    '2. "그 방 약점부터 캐. 조용히." 〔↑↑·리스크↑〕\n'
    '3. "일단 웃으면서 밥부터 먹자고 해." 〔→·민심↑〕\n'
)

# --short: 타자기 렌더가 금방 끝나 턴 전체(히스토리 저장·선택지·삽화)를 빨리 확인할 수 있는 축약본
MOCK_TURN_SHORT = (
    '[IMG] Medium shot, Korean assembly office at dusk, low-key light. [/IMG]\n'
    '# **🇰🇷 짧은 시험 턴** 〔2026/08/22(토) 오전 10시〕\n'
    '<prog>초선 의원 │ 2026/08/22 │ 1막 │ 다음 ▷ 국정감사 2026/10/05</prog>\n'
    '<goal>목표=첫 국정감사 데뷔 (통과: 민심 48·명분 45)</goal> '
    '<stat>세력 21 │ 민심 34 │ 리스크 12 │ 명분 30</stat>\n'
    '> 짧은 시험용 턴.\n\n'
    '## 복도 〔오전 10시〕\n'
    '보좌관이 서류를 내민다.\n\n'
    '## **✦ 어떻게 하시겠습니까?**\n'
    '1. "받읍시다." 〔↑·명분↑〕\n'
    '2. "약점부터 캐." 〔↑↑·리스크↑〕\n'
    '3. "밥부터 먹자." 〔→·민심↑〕\n'
)


class H(SimpleHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *a):
        sys.stderr.write('[mock] %s - %s\n' % (self.address_string(), fmt % a))

    # ---- CORS ----
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-BK-KEY')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header('Content-Length', '0')
        self.end_headers()

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self._cors()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _body(self):
        n = int(self.headers.get('Content-Length') or 0)
        raw = self.rfile.read(n) if n else b''
        try:
            return json.loads(raw.decode('utf-8') or '{}')
        except Exception:
            return {}

    def do_GET(self):
        if self.path.split('?')[0] == '/ping':
            self._json({'ok': True, 'ver': VER, 'sessions': list(SESS)})
            return
        return SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        path = self.path.split('?')[0]
        if path == '/game':
            return self.do_game()
        if path == '/game_image':
            return self.do_image()
        self._json({'err': 'unknown path ' + path}, 404)

    # ---- /game (SSE) ----
    def _sse_open(self):
        self.send_response(200)
        self._cors()
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'close')
        self.protocol_version = 'HTTP/1.1'
        self.close_connection = True
        self.end_headers()

    def _frame(self, obj):
        self.wfile.write(('data: ' + json.dumps(obj, ensure_ascii=False) + '\n\n').encode())
        self.wfile.flush()

    def do_game(self):
        key = self.headers.get('X-BK-KEY') or ''
        b = self._body()
        sid = b.get('sid') or ''
        print('[mock] /game sid=%s key=%s reset=%s replay=%d user=%r system=%s'
              % (sid, ('있음' if key else '없음'), b.get('reset'), len(b.get('replay') or []),
                 (b.get('user') or '')[:40], ('있음(%d자)' % len(b['system'])) if b.get('system') else '없음'),
              file=sys.stderr)
        if not key:
            self._json({'err': 'no key'}, 401)
            return
        with LOCK:
            if b.get('reset'):
                SESS[sid] = {'system': b.get('system') or '', 'n': len(b.get('replay') or [])}
            known = sid in SESS
            force = (ARGS.scenario == 'need_replay' and not b.get('reset') and not STATE['replay_fired'])
            if force:
                STATE['replay_fired'] = True
        self._sse_open()
        if force or not known:
            # 데몬 재시작 등으로 세션 소실 → 앱이 전체 기록을 replay 로 다시 올려야 한다
            self._frame({'need_replay': True})
            return
        if ARGS.scenario == 'err':
            self._frame({'err': 'mock 강제 오류'})
            return
        txt = MOCK_TURN_SHORT if ARGS.short else MOCK_TURN
        step = 24
        for i in range(0, len(txt), step):
            self._frame({'t': txt[i:i + step]})
            time.sleep(0.02)
        with LOCK:
            SESS[sid]['n'] += 2
        self._frame({'usage': {'in': 1234, 'out': len(txt)}})
        self._frame({'done': True})

    # ---- /game_image ----
    def do_image(self):
        key = self.headers.get('X-BK-KEY') or ''
        b = self._body()
        print('[mock] /game_image key=%s prompt=%r'
              % (('있음' if key else '없음'), (b.get('prompt') or '')[:60]), file=sys.stderr)
        if not key:
            self._json({'err': 'no key'}, 401)
            return
        if ARGS.scenario == 'img_err':
            self._json({'err': 'mock 이미지 실패'})
            return
        time.sleep(0.3)
        self._json({'b64': PNG_1X1, 'mime': 'image/png'})


def main():
    global ARGS
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8787)
    ap.add_argument('--root', default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument('--short', action='store_true', help='축약 응답(타자기 렌더 빨리 끝남)')
    ap.add_argument('--scenario', default='ok', choices=['ok', 'need_replay', 'err', 'img_err'])
    ARGS = ap.parse_args()
    os.chdir(ARGS.root)
    srv = ThreadingHTTPServer(('127.0.0.1', ARGS.port), H)
    print('[mock] http://127.0.0.1:%d  root=%s  scenario=%s' % (ARGS.port, ARGS.root, ARGS.scenario),
          file=sys.stderr)
    srv.serve_forever()


if __name__ == '__main__':
    main()
