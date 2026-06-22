# CLAUDE.md — 프로젝트 인수인계 / 작업 가이드

이 파일은 Claude Code가 이 저장소에서 작업을 **이어받기** 위한 맥락 문서다.
(원격 웹 세션의 대화 기록은 로컬로 이전되지 않으므로, 핵심 맥락을 여기 적어 둔다.)

> **설계 *왜*가 궁금하면 `docs/DECISIONS.md`를 먼저 읽어라.** 이 대화에서 합의된 디자인 결정과
> 그 이유(이미 폐기한 접근, 균형 조정 의도 등)가 정리돼 있다. 이미 내린 결정을 되돌리지 말 것.

## 프로젝트 개요

- **무엇**: `index.html` 단일 파일로 동작하는 한국 정치 드라마 커리어 경영 텍스트 게임.
  제목 "Reign of Nations / 권력의 길". LLM이 게임 마스터(GM) 역할.
- **배포**: GitHub Pages. `main` 브랜치가 곧 배포본. (`.github/workflows/pages.yml`)
- **멀티 프로바이더**: OpenRouter / Google Gemini(직접) / Anthropic(직접).
- **API 키·저장 데이터**: 전부 **브라우저 localStorage에만** 저장. 서버·저장소에 절대 안 올라간다.
  → clone한 파일엔 키가 없으니, 실행 후 설정(⚙)에서 키를 다시 넣어야 한다.
- **실행**: 정적 단일 파일이라 서버 불필요. `index.html`을 브라우저로 열면 끝.
  게임 전체가 이 한 파일 안에 있다(HTML+CSS+JS).

## 작업·배포 절차 (중요)

1. 개발은 항상 별도 브랜치에서. (원격 세션 기본 브랜치: `claude/adoring-davinci-8i59tq`)
2. 버전 표기를 올린다: `index.html` 상단 `<span class="ver" id="ver">vX.YZ</span>`.
3. 커밋 → push → PR(초안) → **squash-merge to `main`** 하면 Pages에 배포된다.
4. **머지 전 검증(필수)**:
   ```bash
   # 충돌 마커 0이어야 함
   grep -ncE '^(<{7}|={7}|>{7})' index.html
   # <script> 블록 추출 후 문법 검사
   node -e "const fs=require('fs');const h=fs.readFileSync('index.html','utf8');\
   const m=[...h.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)];let i=0;\
   for(const x of m){fs.writeFileSync('/tmp/s'+i+'.js',x[1]);i++}"
   for f in /tmp/s*.js; do node --check "$f"; done
   ```

## 아키텍처 핵심 ("단일 저자" 원칙)

상태판 = 스토리. GM이 스토리와 함께 상태 태그를 내보내고, 앱은 **표시만** 한다.
구조(막 사다리·통과조건)는 고정 상수, 동적 값(스탯·날짜)은 GM이 스토리와 함께 emit.

- `SYSTEM_PROMPT` — 거대한 백틱 템플릿. **안에 raw 백틱 절대 금지.**
  5막 사다리(관문/통과조건/수순), 시간·턴 모델, 스탯 4종, 선택지 3종 규칙이 들어있다.
- `sysText()` → `SYSTEM_PROMPT`만 반환(캐시 안정). 매 턴 바뀌는 지시는 시스템에 넣지 않는다.
  → 시스템 prefix가 바뀌면 그 뒤 대화 전체가 캐시에서 빠져 비용 폭증한다. 반드시 고정 유지.
- `buildApiMessages()` — 톤·시간점프·프로바이더 보정을 **마지막 user 메시지 끝**에 붙인다(캐시 친화).
  `activeToneReminder()+stratReminder()+jumpDirective()+providerStyle()`.
- `readSSE(res,onEvent)` — SSE 스트리밍. **이벤트 경계를 `/\r?\n\r?\n/`로 split**(직접 Gemini는 CRLF,
  OpenRouter/Claude는 LF). 이 CRLF 처리가 Gemini 직접연결 "빈 응답" 문제의 핵심 수정이었다. 건드리지 말 것.
  `[DONE]` 처리 + 180초 무응답 watchdog 포함.
- `providerStyle()` — 프로바이더별 보정.
  - Anthropic(Claude): 욕설·MZ 말투·코믹을 **세게 풀어라**(Claude는 기본이 점잖아 약함).
  - Gemini: 외모·옷차림·관능 묘사를 **줄여라**(한 줄, 반복 금지). ※욕·코믹 지시는 여기 없음.

## 상태판 / 지표

- GM이 내보내는 커스텀 태그: `<prog>`(진행줄) `<goal>`(목표=관문+통과조건) `<stat>`(스탯 4종).
- 스탯 4종: **세력 / 민심 / 명분 / 리스크** (0~100). 리스크는 드라마 엔진(하드 게이트 아님).
- `setMsgGuide()` — 상태판을 메시지에 렌더: 종합/다음(D-day)/목표/필요(통과조건 vs 현재)/할일/지표.
- `renderStat(s, prev)` — 지표 줄 렌더. **색 규칙(최신 v5.37)**:
  - 값 색: **리스크는 항상 빨강**(경고), 그 외엔 높으면 파랑·낮으면 빨강(임계 60/40).
  - 변화량(델타) 색: **모든 항목 동일 — 오르면 파랑(stat-good), 내리면 빨강(stat-bad).**
  - CSS: `.stat-good`=파랑 `#5aa0ff`, `.stat-bad`=빨강 `#ff5a5a`, `.stat-mid`=회색.
- D-day는 앱이 두 날짜(`<prog>`의 현재날짜·일정날짜)로 계산. GM은 `D-NN`을 직접 쓰지 않는다.

## 삽화(이미지)

- `fetchIllust(story, skipBrief)` → `geminiImage`/`orImage`/`openaiImage`.
- 자동 삽화: 스트리밍 중 GM이 첫 줄에 `[IMG]...[/IMG]`를 주면 텍스트와 **병렬 생성**,
  완성되는 즉시 상태판/본문 아래에 표시. GM이 안 주면 본문으로 폴백 생성.
  `wantImg = autoActive() && ((imgSinceLast+1) >= autoEvery())`.
- `geminiImage`는 `safetySettings`를 BLOCK_NONE로 둔다(차단 회피).

## 절대 규칙 / 주의

- API 키는 localStorage만. 서버·저장소·커밋에 절대 넣지 않는다.
- 본문에서 실존 연예인·유명인에 빗대기 금지('OO를 닮은' 금지). 앱의 `sanitizeBody`가
  연예인 likeness·치장(C컵/미니스커트 등) 상투 묘사를 후처리로 제거한다.
- 상태판 태그(`<prog><goal><stat>` 등)는 `sanitizeBody`가 화면 본문에서 제거한다.
- 커밋/PR에 내부 모델 식별자나 세션 URL 같은 메타를 넣지 않는다(채팅에서만).

## 현재 버전

- **v5.37** (main). 최근: 지표 색 정리(리스크 항상 빨강 + 변화량 방향색 통일).
- 직전: v5.36 지표 델타 표시, v5.35 삽화 안전차단 해제.
