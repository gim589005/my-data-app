"""
어제자 KOBIS(영화진흥위원회) 일별 박스오피스를 보여주는 스트림릿 앱
- 초보자를 위해 각 단계마다 한국어 주석을 달아두었습니다.
"""

import requests
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone

# ------------------------------------------------------------------
# 1. 기본 설정
# ------------------------------------------------------------------

# 페이지 제목/레이아웃 설정 (제일 먼저 호출해야 함)
st.set_page_config(page_title="어제의 박스오피스", page_icon="🎬", layout="wide")

# KOBIS 오픈API 주소
KOBIS_URL = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"

# 한국 표준시(KST, UTC+9) 타임존
# 배포 서버의 시계가 한국 시간이 아닐 수 있으므로, 서버 시간과 상관없이
# 항상 "한국 기준 어제 날짜"를 계산하기 위해 이렇게 timezone을 직접 지정합니다.
KST = timezone(timedelta(hours=9))


def get_yesterday_kst() -> str:
    """
    한국 시간(KST) 기준으로 '어제' 날짜를 yyyymmdd 형식의 문자열로 돌려줍니다.
    예: 2026-09-17일에 실행하면 '20260916'을 반환.
    """
    now_kst = datetime.now(KST)          # 지금 이 순간을 한국 시간으로 변환
    yesterday_kst = now_kst - timedelta(days=1)  # 하루를 뺀다
    return yesterday_kst.strftime("%Y%m%d")


# ------------------------------------------------------------------
# 2. API 호출 (1시간 캐싱)
# ------------------------------------------------------------------

@st.cache_data(ttl=3600)  # ttl=3600초(1시간) 동안은 같은 target_dt로 다시 호출하면
                          # 실제 API를 부르지 않고 캐시된 결과를 그대로 씀
def fetch_box_office(target_dt: str, api_key: str) -> dict:
    """
    KOBIS API를 호출해서 원본 응답(JSON)을 딕셔너리로 돌려줍니다.
    네트워크 오류가 나면 예외를 그대로 위로 던지고,
    호출 자체는 성공했지만 내용에 문제가 있는 경우(오류 상자 등)는
    이 함수를 부르는 쪽에서 판단하도록 원본 데이터를 그대로 반환합니다.
    """
    params = {
        "key": api_key,
        "targetDt": target_dt,
    }
    # timeout을 넉넉히 줘서 API 응답이 느릴 때 무한정 기다리지 않게 함
    response = requests.get(KOBIS_URL, params=params, timeout=10)
    response.raise_for_status()  # 상태코드가 4xx/5xx면 여기서 예외 발생
    return response.json()


# ------------------------------------------------------------------
# 3. 화면 그리기 시작
# ------------------------------------------------------------------

st.title("🎬 어제의 박스오피스")

target_dt = get_yesterday_kst()
# 화면에 예쁘게 보여주기 위해 yyyymmdd -> yyyy.mm.dd 형태로 변환
pretty_date = f"{target_dt[0:4]}.{target_dt[4:6]}.{target_dt[6:8]}"
st.caption(f"조회 날짜(한국 시간 기준 어제): {pretty_date}")

# ------------------------------------------------------------------
# 4. 인증키 확인
# ------------------------------------------------------------------

# secrets.toml (로컬) 또는 스트림릿 클라우드의 Secrets 설정에
# KOBIS_KEY = "발급받은키" 형태로 등록되어 있어야 합니다.
# 코드에는 절대 실제 키 값을 적지 않습니다.
if "KOBIS_KEY" not in st.secrets:
    st.error(
        "❗ 인증키를 찾을 수 없습니다.\n\n"
        "확인해 주세요:\n"
        "1. 스트림릿 클라우드 앱의 'Settings > Secrets'에 아래처럼 등록되어 있는지\n"
        "   KOBIS_KEY = \"발급받은_인증키\"\n"
        "2. 로컬에서 테스트 중이라면 프로젝트 폴더의 .streamlit/secrets.toml 파일에\n"
        "   같은 내용이 있는지"
    )
    st.stop()  # 인증키가 없으면 여기서 실행을 멈춤

api_key = st.secrets["KOBIS_KEY"]

# ------------------------------------------------------------------
# 5. API 호출 및 오류 처리
# ------------------------------------------------------------------

try:
    raw_data = fetch_box_office(target_dt, api_key)
except requests.exceptions.RequestException:
    # 네트워크 문제, 타임아웃, 5xx 오류 등 요청 자체가 실패한 경우
    st.error(
        "❗ 박스오피스 정보를 불러오지 못했습니다.\n\n"
        "확인해 주세요:\n"
        "1. 인터넷 연결 상태\n"
        "2. KOBIS 서버가 일시적으로 응답하지 않는 것은 아닌지 (잠시 후 새로고침해 보세요)"
    )
    st.stop()

# KOBIS는 인증키가 틀려도 상태코드는 200(정상)으로 오고,
# 대신 응답 안에 faultInfo라는 오류 상자가 들어있습니다. 이를 확인합니다.
if "faultInfo" in raw_data:
    fault = raw_data["faultInfo"]
    fault_msg = fault.get("message", "알 수 없는 오류")
    st.error(
        "❗ KOBIS API가 오류를 반환했습니다.\n\n"
        f"API가 알려준 메시지: {fault_msg}\n\n"
        "확인해 주세요:\n"
        "1. Secrets에 등록한 KOBIS_KEY 값이 정확한지 (오타, 공백 등)\n"
        "2. 발급받은 인증키가 아직 유효한 상태인지 (KOBIS 사이트에서 확인)"
    )
    st.stop()

# 정상적인 경우 응답 구조: boxOfficeResult > dailyBoxOfficeList
box_office_result = raw_data.get("boxOfficeResult", {})
movie_list = box_office_result.get("dailyBoxOfficeList", [])

if not movie_list:
    st.warning(
        "❗ 해당 날짜의 박스오피스 목록이 비어 있습니다.\n\n"
        "확인해 주세요:\n"
        "1. 조회 날짜가 너무 이르지 않은지 (당일/최근 날짜는 아직 집계 전일 수 있음)\n"
        "2. KOBIS 서비스 자체에 장애가 없는지"
    )
    st.stop()

# ------------------------------------------------------------------
# 6. 데이터 정리: 문자열로 오는 숫자들을 진짜 숫자(int)로 변환
# ------------------------------------------------------------------

df = pd.DataFrame(movie_list)

# API가 숫자를 전부 문자열로 주기 때문에, 정렬/그래프에 쓰려면
# 반드시 숫자 타입으로 바꿔줘야 합니다.
numeric_cols = ["rank", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]
for col in numeric_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

# 순위(rank) 기준으로 오름차순 정렬 (1위가 맨 위로)
df = df.sort_values("rank").reset_index(drop=True)

# ------------------------------------------------------------------
# 7. 1위 영화 - 지표 카드 3장
# ------------------------------------------------------------------

top_movie = df.iloc[0]

st.subheader(f"🥇 1위: {top_movie['movieNm']}")

col1, col2, col3 = st.columns(3)
col1.metric("어제 관객수", f"{top_movie['audiCnt']:,} 명")
col2.metric("누적 관객수", f"{top_movie['audiAcc']:,} 명")
col3.metric("스크린 수", f"{top_movie['scrnCnt']:,} 개")

# ------------------------------------------------------------------
# 8. 관객수 상위 5편 - 막대그래프
# ------------------------------------------------------------------

st.subheader("📊 관객수 상위 5편")

top5 = df.sort_values("audiCnt", ascending=False).head(5)

# 막대그래프용 데이터: 영화명을 인덱스로, 관객수를 값으로
chart_df = top5.set_index("movieNm")[["audiCnt"]]
chart_df.columns = ["관객수"]

st.bar_chart(chart_df)

# ------------------------------------------------------------------
# 9. 전체 목록 표
# ------------------------------------------------------------------

st.subheader("📋 전체 순위표")

table_df = df[["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
table_df.columns = ["순위", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]

# 보기 좋게 천 단위 콤마를 넣어서 표시 (표시용 컬럼이므로 정렬에는 영향 없음)
st.dataframe(
    table_df.style.format({
        "관객수": "{:,}",
        "누적관객": "{:,}",
        "스크린수": "{:,}",
    }),
    use_container_width=True,
    hide_index=True,
)
