/* 권력의 길 — 최소 서비스워커 (PWA 설치용)
 *
 * ★앱(index.html)을 고쳐 배포할 때마다 CACHE_VER 를 한 칸 올려라.
 *   안 올리면 낡은 index.html이 캐시에서 계속 나온다(번역앱에서 겪은 함정).
 *
 * 정책
 *   - index.html(문서): network-first — 항상 최신을 받고, 오프라인일 때만 캐시로 폴백.
 *   - manifest.json·icons/*: cache-first — 바뀌는 일이 드물고 설치 판정에 필요.
 *   - 그 밖의 요청: 손대지 않는다(그냥 통과).
 * ★게임 API(두뇌서버 /game·/game_image, 구글 드라이브, LLM 제공사)는 절대 가로채지 않는다.
 *   fetch 핸들러는 same-origin GET 만 처리하고, POST·교차출처는 respondWith 자체를 하지 않는다.
 */
const CACHE_VER = 'g54';
const CACHE = 'reign-' + CACHE_VER;
const PRECACHE = ['./index.html', './manifest.json', './icons/icon-192.png', './icons/icon-512.png'];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => c.addAll(PRECACHE).catch(() => {}))   // 일부 실패해도 설치는 진행
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))   // 버전 다른 캐시 정리
      .then(() => self.clients.claim())
  );
});

function isAsset(url) {
  return /\/manifest\.json$|\/icons\/[^/]+$/.test(url.pathname);
}
function isDoc(req, url) {
  return req.mode === 'navigate' || /\/$|\/index\.html$/.test(url.pathname);
}

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;                       // POST(게임 API 등)는 건드리지 않음
  let url;
  try { url = new URL(req.url); } catch (err) { return; }
  if (url.origin !== self.location.origin) return;        // 교차출처(두뇌서버·드라이브·LLM)는 통과

  if (isDoc(req, url)) {                                  // network-first
    e.respondWith(
      fetch(req, { cache: 'no-cache' })                 // GitHub Pages HTTP 캐시(10분) 우회 — 배포 즉시 새 버전(ETag 재검증)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put('./index.html', copy)).catch(() => {});
          return res;
        })
        .catch(() => caches.match('./index.html').then((r) => r || Response.error()))
    );
    return;
  }

  if (isAsset(url)) {                                     // cache-first
    e.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        return res;
      }))
    );
  }
});
