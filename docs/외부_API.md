# 외부 API 정리 (0-3)

> 키는 코드/문서에 적지 않는다. `etl/.env`(gitignore됨)에만. 검증: `python etl/scripts/check_api_keys.py`

## 발급 현황

| 소스                          | 상태       | 비고                                  |
| ----------------------------- | ---------- | ------------------------------------- |
| 열린국회정보 (open.assembly)  | ✅ 발급됨   | `ASSEMBLY_API_KEY` — 동작 확인 완료   |
| 선관위 (info.nec / data.go.kr)| ⬜ 미발급   | Phase 3 전과 DB 착수 전 필요          |
| 공공데이터포털 (data.go.kr)   | ⬜ 미발급   | Phase 2 선거구·자금 착수 전 필요      |

## 열린국회정보 (open.assembly.go.kr)

### 호출 규약

- **Base**: `https://open.assembly.go.kr/portal/openapi/{SERVICE}`
- **인증**: 쿼리 파라미터 `KEY={발급키}`
- **포맷**: `Type=json` (또는 xml)
- **페이징**: `pIndex`(1부터), `pSize`(페이지당 건수)
- **⚠️ User-Agent 필수**: 기본 파이썬/curl UA 는 **HTTP 400** 반환.
  브라우저류 UA(`Mozilla/5.0 ...`) 헤더를 반드시 붙일 것. (실측으로 확인)

### 응답 봉투(envelope) 형식

```jsonc
{
  "<SERVICE>": [
    { "head": [
        { "list_total_count": 3295 },
        { "RESULT": { "CODE": "INFO-000", "MESSAGE": "정상 처리되었습니다." } }
      ] },
    { "row": [ { /* 레코드 */ } ] }
  ]
}
```

- 정상 코드: `INFO-000` (그 외 `INFO-300` 인증키 오류 등). 헤더의 `list_total_count` 로 전체 건수 파악 → 페이징.
- 오류 시 위 구조 대신 최상위 `{"RESULT": {...}}` 형태가 올 수 있음 → 두 경우 모두 처리.

### 확인된 서비스

| SERVICE       | 내용                  | 매핑 대상           |
| ------------- | --------------------- | ------------------- |
| `ALLNAMEMBER` | 국회의원 인적사항(통합) | `Person`, `Party`   |

샘플 응답: [api_samples/allnamember_sample.json](api_samples/allnamember_sample.json)

`ALLNAMEMBER.row[]` 주요 필드 → 모델 매핑 후보:

| API 필드    | 의미        | 모델 필드            |
| ----------- | ----------- | -------------------- |
| `NAAS_CD`   | 의원 코드   | (외부 식별자, 추후)  |
| `NAAS_NM`   | 이름        | `Person.name`        |
| `PLPT_NM`   | 정당명      | `Party.name`         |
| `ELECD_NM`  | 선거구      | `Person.district`    |

> ⚠️ `ALLNAMEMBER` 는 역대 의원 통합(3295건)이라 현직 필터가 필요.
> 의안(Bill)·표결(Vote/VoteRecord) 서비스 코드는 **Phase 1-2 착수 시 확정**
> (열린국회정보 OpenAPI 목록에서 의안목록·본회의표결 서비스 식별 → 샘플 수집 → 매핑).

### Rate limit / 호출 한도

- 포털상 일일 호출 한도가 적용됨(계정/서비스별). **정확한 한도는 마이페이지에서 확인 필요(⬜ TODO).**
- 대응: 자체 DB 캐싱 + 배치 수집(1일 1회). (기획서 13장 리스크 대응)

## 선관위 / 공공데이터포털 (미발급)

- 발급처: https://www.data.go.kr (선관위 후보자 전과/재산, 선거구 데이터)
- 발급 후 `etl/.env` 의 `NEC_API_KEY` / `DATA_GO_KR_API_KEY` 채우고 검증 스크립트 확장.
