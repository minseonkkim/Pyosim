# 외부 API 정리 (0-3)

> 키는 코드/문서에 적지 않는다. `etl/.env`(gitignore됨)에만. 검증: `python etl/scripts/check_api_keys.py`

## 발급 현황

| 소스                          | 상태       | 비고                                  |
| ----------------------------- | ---------- | ------------------------------------- |
| 열린국회정보 (open.assembly)  | ✅ 발급됨   | `ASSEMBLY_API_KEY` — **이 키 하나로 포털 전체 271개 서비스**(사무처·NABO·입법조사처·도서관·미래연) 동작. 라이브 검증 완료 |
| 열린재정 (openfiscaldata)     | ✅ 발급됨   | `OFD_API_KEY` — 세금 도구. OPFI160~172 동작 확인 |
| 선관위 (info.nec / data.go.kr)| ⬜ 미발급   | Phase 3 전과 DB 착수 전 필요          |
| 공공데이터포털 (data.go.kr)   | ⬜ 미발급   | Phase 2 선거구·자금 + **조세지출·세목별 세입**(세금 도구) 착수 전 필요 |

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
| `nzmimeepazxkubdpn` | 국회의원 발의법률안        | 17,567    | `AGE`                | `Bill`(+`proposer_id`) — 발의자 연결 ✅ |
| `TVBPMBILL11`       | 의안검색(전체)             | 18,795    | `AGE`                | (의안 전수, 보조)          |

주요 필드 매핑:

- **명단**(`nwvrqwxyaytdsfvhu`): `HG_NM`→이름, `POLY_NM`→정당, `ORIG_NM`→지역구, `MONA_CD`→`Person.assembly_member_code`(표결 매핑 키)
- **표결현황**(`ncocpgfiaoituanbr`): `BILL_NO`→의안번호, `BILL_ID`→`Bill.assembly_bill_id`(PRC_…), `BILL_NAME`→제목, `PROC_RESULT_CD`→상태, `MEMBER/VOTE/YES/NO/BLANK_TCNT`→`Vote` 집계, `LINK_URL`→likms 1차 출처
- **의원별 표결**(`nojepdqqaweusdfbi`): `MONA_CD`→의원 매핑, `RESULT_VOTE_MOD`(찬성/반대/기권/불참)→`VoteRecord.choice`
- **발의법률안**(`nzmimeepazxkubdpn`): `BILL_NO`→의안번호(Bill upsert), `RST_MONA_CD`→대표발의자(`Person.assembly_member_code` 직접 연결, 이름매칭 불필요), `RST_PROPOSER`→대표발의자명, `PUBL_MONA_CD`/`PUBL_PROPOSER`→공동발의(Phase 2-5), `DETAIL_LINK`→likms 출처. 표결 안 된 계류 의안도 포함 → 의원 '대표발의' 목록을 채움

> ⚠️ **알려진 데이터 불일치**: 집계(`ncocpgfiaoituanbr`)의 `YES_TCNT` 와 의원별 기록(`nojepdqqaweusdfbi`) 찬성 합계가 의안에 따라 소폭 다를 수 있음(예: 232 vs 218). 정부 두 API 간 차이 — 결과 표시 시 집계=헤드라인 수치, 의원별 기록=정당별 분해로 분리 사용하고 각주 처리. (로드맵 1-2 "매핑 정합성 검증")

샘플 응답: [api_samples/allnamember_sample.json](api_samples/allnamember_sample.json)

### 수집 잡 실행

```bash
# etl/ 디렉터리에서 (etl/.env 의 ASSEMBLY_API_KEY, DATABASE_URL 사용)
python -m jobs.run --job members              # 현직 의원 300
python -m jobs.run --job bills                # 표결된 의안 + 집계 1,596
python -m jobs.run --job vote_records --limit 50   # 의원별 찬반 (rate limit 대응 상한)
python -m jobs.run --job proposers           # 발의법률안 + 대표발의자 연결 (~17.5k)
python -m jobs.run --job committees           # 위원회 엔티티 + 의원 위원회경력(제22대)
python -m jobs.run --job petitions            # 청원 계류·처리현황 (민심 레이어 기능 A, 305건)
python -m jobs.run --job lawnotices           # 입법예고 메타데이터 (기능 B-4.4, 17,709건)
python -m jobs.run --job lawnotice_opinions --limit 50  # 입법예고 시민 찬반 의견(pal 스크랩)
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

### 동일 키로 확장 가능한 서비스 — 전수 카탈로그 + 라이브 검증 (2026-06-20)

> **핵심:** 발급받은 `ASSEMBLY_API_KEY` **하나로 열린국회정보 포털 전체(271개 서비스)** 가 열린다.
> 국회사무처(212) + 국회예산정책처/NABO(23) + 국회입법조사처(18) + 국회도서관(13) + 국회미래연구원(4) + 기타(1).
> **다른 기관 서비스도 같은 키로 동작 확인**(예: NABO `negjnychalvyrcifv`, 입법조사처 `nxlcxbbkapsrjayur` → INFO-000).
> 추가 키 발급 불필요. 아래는 제품(로드맵) 관련 후보를 [explore_catalog.py](../etl/scripts/explore_catalog.py) 로 **라이브 실측**한 결과.
> 범례: ✅ 그대로 동작 / 🔑 키 OK·필수 파라미터 필요(ERROR-300) / ⬜ 현재 데이터 0건(INFO-200, 회기 따라 채워짐).

#### 위원회 (Phase 1-1 Committee 모델 충족)

| SERVICE | 내용 | 건수 | 주요 필드 | 상태 |
| --- | --- | --- | --- | --- |
| `nxrvzonlafugpqjuh` | 위원회 현황 정보 | 358 | `COMMITTEE_NAME`,`CURR_CNT`,`POLY_CNT` | ✅ |
| `nktulghcadyhmiqxi` | 위원회 위원 명단 | 85 | `DEPT_NM`,`HG_NM`,`MONA_CD`(의원매핑),`JOB_RES_NM` | ✅ |
| `nyzrglyvagmrypezq` | 국회의원 위원회 경력 | 3,720 | `MONA_CD`,`FRTO_DATE`,`PROFILE_SJ` | ✅ |
| `nuvypcdgahexhvrjt` | 국회의원 상임위 활동 | — | — | 🔑 |
| `ndiwuqmpambgvnfsj` | 위원회 계류법률안 | — | — | 🔑 |
| `ncwgseseafwbuheph` | 위원회 회의록 | — | — | 🔑 |

#### 청원 (Phase 2 기능 A — 기획서가 적은 'XLS/CSV' 대신 API 직접 수집 가능)

| SERVICE | 내용 | 건수(22대) | 주요 필드 | 상태 |
| --- | --- | --- | --- | --- |
| `nvqbafvaajdiqhehi` | 청원 계류현황 | 286 | `BILL_NO`,`BILL_ID`,`BILL_NAME`,`PROPOSER`,`APPROVER`(소개),`CURR_COMMITTEE`,`PROPOSE_DT`,`COMMITTEE_DT`,`LINK_URL` | ✅ **사용 중**(`--job petitions`, AGE) |
| `ncryefyuaflxnqbqo` | 청원 처리현황 | 19 | +`PROC_RESULT_CD`(최종처리: 본회의불부의/대안반영폐기 등) | ✅ **사용 중**(AGE) |
| `PTTRCP`/`PTTINFODETAIL`/`PTTINFOPPSR` | 청원 접수목록·상세·소개의원 | — | — | 🔑 |
| `NAMEMBERLEGIPTT` | 국회의원 청원현황(의원↔청원) | — | — | 🔑 |
| `PTTJUDGE`/`PTTCNTMAIN` | 청원 심사정보·통계 | — | — | 🔑 |

#### 입법예고 (Phase 2 기능 B-4.4 — **구현 완료** 2026-06-21)

| SERVICE | 내용 | 22대 건수 | 주요 필드 | 상태 |
| --- | --- | --- | --- | --- |
| `nohgwtzsamojdozky` | 종료된 입법예고 | 17,709 | `BILL_ID`,`BILL_NO`,`BILL_NAME`,`PROPOSER`,`PROPOSER_KIND_CD`,`CURR_COMMITTEE`,`NOTI_ED_DT`,`LINK_URL` | ✅ **사용 중**(`--job lawnotices`, AGE 필수) |
| `nknalejkafmvgzmpt` | 진행중 입법예고 | 0 | (동일) | ⬜ 현재 0건(회기 따라 채워짐) |

> ⚠️ **확정(라이브):** 이 API 는 의안 **메타데이터만** 주고 시민 **찬반 의견 카운트는 없다**.
> → 찬반은 **국민참여입법시스템(pal.assembly.go.kr) 의견목록 공개 페이지를 스크랩**한다(별도 OC 키 불필요).
> `LINK_URL` 이 그 페이지를 가리킴. (ETL `--job lawnotice_opinions`, `etl/jobs/lawnotice_opinions.py`)

**찬반 스크랩 방법(라이브 역추적 확정):**
- `GET /napal/lgsltpa/lgsltpaOpn/list.do?lgsltPaId={BILL_ID}&searchConClosed={1=종료/0=진행}&searchConRng=0&pageUnit=100&pageIndex={n}`
- 전체 의견 수 = 헤더 `<div class="board_count"><strong>N</strong>`.
- ⚠️ `searchConRng` 은 **찬반 필터가 아님**(0=전체·1=나의의견[로그인]·2=공개의견). 찬반 입장은 각 의견 **행의 텍스트**(`찬성합니다`/`반대합니다`/그 외=기타)에만 있음.
- 따라서 입장별 필터가 없어 **페이지를 넘기며 '찬성합니다'/'반대합니다' 등장 횟수를 센다**. 기타 = 전체 − 찬성 − 반대.
- 의안당 ceil(전체/100) 페이지. 의견 폭주 의안(수천 건=수십 페이지)은 `MAX_PAGES`(80)로 상한 → 초과 시 전체 수만 저장(분해 보류).
- 🟡 의견 본문·작성자는 저장 안 하고 입장별 집계만. 비공식 스크래핑(robots/ToS 유의)이라 sleep + `only_linked`(우리 Bill 과 연결된 예고만) 선별 수집.
- 결과는 `LawNotice`(마이그레이션 0014) 에 적재되고, **법안 상세(`/api/bills/{id}`)의 `civic_opinion`** 으로 함께 노출됨(별도 페이지 없이 법안 페이지에 통합 — 민심 vs 국회).

#### 의안 심사·단계·공동발의 (Phase 1-3 / 2-5 보강)

| SERVICE | 내용 | 건수 | 주요 필드 | 상태 |
| --- | --- | --- | --- | --- |
| `BILLINFOPPSR` | 의안 제안자정보 → **공동발의** | — | — | 🔑 (Phase 2-5 공동발의 충족) |
| `BILLINFODETAIL` | 의안 상세정보 | — | — | 🔑 |
| `BILLJUDGE` | 의안 심사정보(예·결산 제외) | 36,018 | `PPSR_KIND`,`JRCMIT_NM`,`JRCMIT_PROC_DT/RSLT`,`LINK_URL` | ✅ |
| `BILLRCP` | 의안 접수목록(역대 전수) | 133,168 | `ERACO`,`BILL_KIND`,`PPSR_KIND`,`PROC_RSLT` | ✅ |
| `nayjnliqaexiioauy` | 본회의 부의안건 | 61 | 위원회→법사위→본회의 **단계별 일자** | ✅ AGE |
| `nwbpacrgavhjryiph` | 본회의 처리안건(법률안) | 1,578 | **표결수치**(`YES/NO/BLANK_TCNT`)+전 단계 일자 → 처리 타임라인 골드 | ✅ AGE |

#### 통계 — 기능 B-4.2(관심도 vs 활동량) 분모

| SERVICE | 내용 | 건수 | 상태 |
| --- | --- | --- | --- |
| `BILLCNTRSVT` | 계류의안 통계(위원회별) | 25 | ✅ |
| `nzivskufaliivfhpb` | 역대 의안 통계(대별 가결/부결/폐기) | 20 | ✅ |
| `BILLCNTPRPSR` | 처리 의안통계(발의주체별) | — | 🔑 |

#### 의원 프로필 보강 (Phase 1-2)

| SERVICE | 내용 | 건수 | 주요 필드 | 상태 |
| --- | --- | --- | --- | --- |
| `negnlnyvatsjwocar` | 국회의원 SNS정보 | 300 | `MONA_CD`,트위터/페북/유튜브/블로그 URL | ✅ |
| `nexgtxtmaamffofof` | 국회의원 의원이력 | 615 | `MONA_CD`,`FRTO_DATE`,`PROFILE_SJ` | ✅ |
| `nqfvrbsdafrmuzixe` | 날짜별 의정활동 | — | — | 🔑 |

#### 회의록·발언 (콘텐츠 깊이 — "누가 뭐라 했나")

| SERVICE | 내용 | 상태 |
| --- | --- | --- |
| `nzbyfwhwaoanttzje` | 본회의 회의록 | 🔑 |
| `ncwgseseafwbuheph` | 위원회 회의록 | 🔑 |
| `npeslxqbanwkimebr` | 국회의원 영상회의록(발언영상) | 🔑 |
| `VCONFBILLLIST`/`VCONFDETAIL` 등 | 회의별 의안·회의록 상세 | (전용 회의록 API군 다수) |

#### 일정·정당·국정감사·인사청문 (감시견/시즌 콘텐츠)

| SERVICE | 내용 | 건수 | 상태 |
| --- | --- | --- | --- |
| `ALLSCHEDULE` | 국회일정 통합 | 91,453 | ✅ (감시견 알림 토대) |
| `nekcaiymatialqlxr` | 본회의 일정 | — | 🔑 |
| `nepjpxkkabqiqpbvk` | 정당·교섭단체 의석수 | 9 | ✅ |
| `AUDITREPORTRESULT` | 국정감사 결과보고서 | 347 | ✅ (PDF/HWP URL) |
| `nrvsawtaauyihadij` | 인사청문회 | 58 | ✅ |
| `nztwkhgzakucszgls` | 사업별 예산 편성 규모(국회 자체) | 125 | ✅ |

> 전체 271개 목록 원천: `hollobit/assembly-api-mcp` `docs/discovered-all-codes.json`(동일 키로 271/276 discovered). 위 표는 그중 로드맵 직접 관련 + 라이브 검증분만.

## 열린재정 (openapi.openfiscaldata.go.kr) — `OFD_API_KEY`

> 세금 도구(/tax) 데이터 출처. 규약·이중 인코딩은 [memory: budget-data-via-openfiscal-api] / [openfiscal.py](../etl/clients/openfiscal.py) 참고.
> OPFI 코드대 스윕 결과(`ACNT_YR` 필수, 라이브 검증 2026-06-20): **OPFI160~168, 170~172 동작**(169·173+ 없음).

| SERVICE | 내용 | 상태 |
| --- | --- | --- |
| `OPFI165` | 16대 분야별 결산(실제 집행) — **사용 중** | ✅ |
| `OPFI172` | 16대 분야별 본예산 + 부문/프로그램/단위/세부사업 수 — **사용 중** | ✅ |
| `OPFI166` | **부처(OFFC_NM)별 결산**(63) → '부처별 지출' 신규 가능 | ✅ |
| `OPFI167` | 회계구분(일반/특별/기금) 비율 총괄 | ✅ |
| `OPFI160~164,168,170,171` | 회계·기금·사업 단위 세분(세입세출/회계명/기금분류/단위·세부사업) | ✅ |

> ⚠️ data.go.kr 의 **조세지출·세목별 세입**(세금 도구와 직결)은 열린재정 OPFI 가 아니라 **별도 data.go.kr 키** 필요(미발급). 열린재정 OPFI 로는 '지출(어디로)' 측면만 커버됨.

## 의안 본문 — likms 의안원문 (스크래핑, Phase 1-3 보완)

> ⚠️ **OpenAPI 엔 제안이유·주요내용 본문이 없다**(의안검색·발의법률안·표결현황 모두 메타데이터만, 라이브 확인).
> 본문은 의안정보시스템(likms) 의안원문 HWP 에만 있고 상세페이지는 JS 동적 로딩이라, **HWP 의 미리보기텍스트(`PrvText`) 스트림**에서 추출한다. (ETL `jobs/bill_content.py`, `--job bill_content`)

수집 흐름(라이브 역추적 확정):
1. `GET https://likms.assembly.go.kr/bill/billDetail.do?billId=PRC_…` → 세션 쿠키(JSESSIONID)
2. `POST .../bill/bi/bill/detail/downloadDtlZip.do` (body: `billId`, `docChkList=의안원문`) → zip
3. zip 내 `.hwp` → `olefile` 로 OLE 열기 → `PrvText` 스트림(UTF-16LE 평문) 디코드
4. 마커 파싱: 결합형 `<제안이유 및 주요내용>` 또는 분리형 `<제안이유>`/`<주요내용>` → `Bill.proposal_reason`/`main_content`

🟡 원칙: **공식 원문 그대로 저장**(요약·판정 없음), 출처=likms. 스크래핑이므로 sleep(0.4s)+필요 의안만 선별 수집. 비공식 경로라 likms 구조 변경 시 깨질 수 있음(robots/ToS 유의).

## 선관위 / 공공데이터포털 (미발급)

- 발급처: https://www.data.go.kr (선관위 후보자 전과/재산, 선거구 데이터)
- 발급 후 `etl/.env` 의 `NEC_API_KEY` / `DATA_GO_KR_API_KEY` 채우고 검증 스크립트 확장.
