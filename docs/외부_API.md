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

### 확인된 서비스 (Phase 1-2 수집 파이프라인에서 사용)

> 서비스 코드는 암호화 문자열이라 문서가 불일치 → `etl/scripts/explore_services.py` / `explore_votes.py` 로 **라이브 검증 완료**.

| SERVICE             | 내용                       | 22대 건수 | 필수 파라미터        | 매핑 대상                  |
| ------------------- | -------------------------- | --------- | -------------------- | -------------------------- |
| `nwvrqwxyaytdsfvhu` | 현직 국회의원 명단         | 300       | `AGE`                | `Person`, `Party`          |
| `ncocpgfiaoituanbr` | 의안별 표결현황(본회의 집계) | 1,596     | `AGE`                | `Bill`, `Vote`(집계)       |
| `nojepdqqaweusdfbi` | 의원별 본회의 표결정보      | BILL당 ~285 | `AGE`, `BILL_ID`   | `VoteRecord`               |
| `ALLNAMEMBER`       | 국회의원 인적사항(역대 통합) | 3,295     | —                    | (역대·사진 보강용, 추후)   |
| `nzmimeepazxkubdpn` | 국회의원 발의법률안        | 17,533    | `AGE`                | (공동발의·발의자, Phase 2) |
| `TVBPMBILL11`       | 의안검색(전체)             | 18,795    | `AGE`                | (의안 전수, 보조)          |

주요 필드 매핑:

- **명단**(`nwvrqwxyaytdsfvhu`): `HG_NM`→이름, `POLY_NM`→정당, `ORIG_NM`→지역구, `MONA_CD`→`Person.assembly_member_code`(표결 매핑 키)
- **표결현황**(`ncocpgfiaoituanbr`): `BILL_NO`→의안번호, `BILL_ID`→`Bill.assembly_bill_id`(PRC_…), `BILL_NAME`→제목, `PROC_RESULT_CD`→상태, `MEMBER/VOTE/YES/NO/BLANK_TCNT`→`Vote` 집계, `LINK_URL`→likms 1차 출처
- **의원별 표결**(`nojepdqqaweusdfbi`): `MONA_CD`→의원 매핑, `RESULT_VOTE_MOD`(찬성/반대/기권/불참)→`VoteRecord.choice`

> ⚠️ **알려진 데이터 불일치**: 집계(`ncocpgfiaoituanbr`)의 `YES_TCNT` 와 의원별 기록(`nojepdqqaweusdfbi`) 찬성 합계가 의안에 따라 소폭 다를 수 있음(예: 232 vs 218). 정부 두 API 간 차이 — 결과 표시 시 집계=헤드라인 수치, 의원별 기록=정당별 분해로 분리 사용하고 각주 처리. (로드맵 1-2 "매핑 정합성 검증")

샘플 응답: [api_samples/allnamember_sample.json](api_samples/allnamember_sample.json)

### 수집 잡 실행

```bash
# etl/ 디렉터리에서 (etl/.env 의 ASSEMBLY_API_KEY, DATABASE_URL 사용)
python -m jobs.run --job members              # 현직 의원 300
python -m jobs.run --job bills                # 표결된 의안 + 집계 1,596
python -m jobs.run --job vote_records --limit 50   # 의원별 찬반 (rate limit 대응 상한)
python -m jobs.run --job bills --dry-run      # 미리보기(미기록)
```

> DB 없이 적재 경로만 검증: `python etl/scripts/smoke_load.py` (임시 SQLite, 소량 실수집).

`ALLNAMEMBER.row[]` 주요 필드 → 모델 매핑 후보:

| API 필드    | 의미        | 모델 필드            |
| ----------- | ----------- | -------------------- |
| `NAAS_CD`   | 의원 코드   | (외부 식별자, 추후)  |
| `NAAS_NM`   | 이름        | `Person.name`        |
| `PLPT_NM`   | 정당명      | `Party.name`         |
| `ELECD_NM`  | 선거구      | `Person.district`    |

> ⚠️ `ALLNAMEMBER` 는 역대 의원 통합(3295건)이라 현직 필터 필요 → 현직 명단은 `nwvrqwxyaytdsfvhu`(300명) 사용.
> ✅ 의안(Bill)·표결(Vote/VoteRecord) 서비스 코드 **확정 완료**(위 표). 사진(`NAAS_PIC`) 등 보강은 추후 `ALLNAMEMBER` 매칭.

### Rate limit / 호출 한도

- 포털상 일일 호출 한도가 적용됨(계정/서비스별). **정확한 한도는 마이페이지에서 확인 필요(⬜ TODO).**
- 대응: 자체 DB 캐싱 + 배치 수집(1일 1회). (기획서 13장 리스크 대응)

## 선관위 / 공공데이터포털 (미발급)

- 발급처: https://www.data.go.kr (선관위 후보자 전과/재산, 선거구 데이터)
- 발급 후 `etl/.env` 의 `NEC_API_KEY` / `DATA_GO_KR_API_KEY` 채우고 검증 스크립트 확장.
