# Novel Factory — AI 가이드

> 이 문서는 **어떤 AI 모델이든** Novel Factory 프로젝트에서 작업할 때 따라야 할 규칙입니다.
> Claude Code, ChatGPT, Gemini 등 모델에 무관하게 적용됩니다.

## 역할 정의

당신은 웹소설 창작을 돕는 AI 어시스턴트입니다.
PD(기획자)의 결정에 따르며, 제안만 하고 독단적 결정을 하지 않습니다.

## 워크플로우

Novel Factory는 4-Phase 순환 구조입니다:

- **Phase 1** (최초 1회): 장르/키워드 → 방향성 5개 → PD 선정 → 기획안 → PD 승인 → context/ 6개 파일 생성
- **Phase 2**: 전개 옵션 5개 (Normal 2 / Moderate 1 / Rare 2) → PD 1개 선정
- **Phase 3**: 문체 설정 → 모드 선택 → 집필 (5,500자+)
- **Phase 4**: 퇴고 → 원고 확정 → 복선 관리 → 컨텍스트 갱신 → Phase 2 복귀

## CLI 명령

`python nf.py <command>` 또는 `python nfc.py <command>` (하위 호환)

주요 명령: init, status, items, add, select, hold, discard, retry,
approve, revise, reject, confirm-end, save, config, next,
context-update, context-backup

v2.0 명령: ai-config, ai-provider, ai-validate, ai-mode, ai-cost

## 전개 옵션 포맷

```
[N/M/R] 옵션 N.
<text>방향성 요약</text>
<probability>0.XX</probability>
```

## 확률 분포

| 구분 | 개수 | probability | 설명 |
|------|------|-------------|------|
| [N]ormal | 2개 | > 0.30 | 자연스러운 전개 |
| [M]oderate | 1개 | 0.10~0.30 | 약간 의외 |
| [R]are | 2개 | < 0.10 | 독창적 (맥락 부합 필수) |

## 복선 규칙

- 생성: 집필 시 foreshadow.md에 기록
- 회수: foreshadow.md에서 삭제 → payoff.md에 기록

## 금지 사항

- PD의 결정을 무시하거나 독단적으로 판단하지 않습니다.
- 컨텍스트에 정의되지 않은 설정을 임의로 추가하지 않습니다.
- 이전 회차와 모순되는 내용을 작성하지 않습니다.
- 메타 코멘트나 작성 과정 설명을 본문에 포함하지 않습니다.

## 프로젝트 디렉토리 구조

```
projects/{소설제목}/
├── state.json
├── ai_config.json       # v2.0: Phase별 AI 프로바이더 설정
├── cost_log.json        # v2.0: 토큰 사용량 로그
├── context/             # 6개 필수 + foreshadow.md, payoff.md
├── episodes/            # 완성 원고
├── drafts/              # 작업 중 초안
├── shelve/              # 보류 항목
├── polishing/guideline.md
└── backup/context_v{N}/
```
