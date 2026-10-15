
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# ============================================================
# 1. 기본 설정
# ============================================================

st.set_page_config(
    page_title="동네별 인구 피라미드",
    page_icon="🏡",
    layout="wide",
)

DATA_URL = (
    "https://raw.githubusercontent.com/hoyeon-max/project/"
    "main/population_ts_yearly_gender.zip"
)

# 나이 순서는 반드시 0세부터 100세 이상까지 유지합니다.
AGES = [f"{age}세" for age in range(101)]
AGES[-1] = "100세 이상"

MALE_COLS = [f"남_{age}" for age in AGES]
FEMALE_COLS = [f"여_{age}" for age in AGES]


# ============================================================
# 2. 따뜻한 톤의 화면 디자인
# ============================================================

st.markdown(
    """
    <style>
    .stApp {
        background-color: #FFF9F2;
        color: #4D392D;
    }
    h1, h2, h3 {
        color: #824D35 !important;
    }
    .hero {
        padding: 24px;
        border-radius: 18px;
        background: linear-gradient(120deg, #FBE5CC, #F8DCD2);
        border: 1px solid #EED1B7;
        margin-bottom: 20px;
    }
    .hero p {
        color: #795A48;
        margin-bottom: 0;
    }
    div[data-testid="stMetric"] {
        background: #FFFFFF;
        padding: 16px;
        border: 1px solid #EEDFD0;
        border-radius: 14px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
        <h1>🏡 동네별 인구 피라미드</h1>
        <p>
            시도, 시군구, 읍·면·동을 선택해
            우리 동네의 남녀별 연령 분포를 확인해 보세요.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 3. 데이터 읽기 및 정리
# ============================================================

@st.cache_data(show_spinner=False)
def load_data():
    # URL이 ZIP 파일이므로 compression="zip"을 지정합니다.
    # 기본 UTF-8로 읽고, 실패하면 CP949로 다시 시도합니다.
    try:
        data = pd.read_csv(
            DATA_URL,
            compression="zip",
            encoding="utf-8-sig",
            low_memory=False,
        )
    except UnicodeDecodeError:
        data = pd.read_csv(
            DATA_URL,
            compression="zip",
            encoding="cp949",
            low_memory=False,
        )

    # 열 이름 앞뒤의 공백을 정리합니다.
    data.columns = data.columns.astype(str).str.strip()

    # 지역과 연도에 필요한 열이 있는지 확인합니다.
    required = ["연도", "시도", "시군구", "동"]
    missing = [col for col in required if col not in data.columns]

    if missing:
        raise ValueError(
            f"필수 열이 없습니다: {', '.join(missing)}"
        )

    # 0~100세 이상의 남녀 인구 열을 확인합니다.
    population_cols = MALE_COLS + FEMALE_COLS
    missing_pop = [
        col for col in population_cols if col not in data.columns
    ]

    if missing_pop:
        raise ValueError(
            "인구 열을 찾을 수 없습니다. "
            f"누락된 열 예시: {', '.join(missing_pop[:8])}"
        )

    # 연도를 숫자로 바꾸고 2015~2026년 자료만 남깁니다.
    data["연도"] = pd.to_numeric(data["연도"], errors="coerce")
    data = data.dropna(subset=["연도"]).copy()
    data["연도"] = data["연도"].astype(int)
    data = data[data["연도"].between(2015, 2026)].copy()

    if data.empty:
        raise ValueError("2015~2026년 데이터가 없습니다.")

    # 데이터에 실제로 존재하는 가장 최신 연도만 사용합니다.
    latest_year = int(data["연도"].max())
    data = data[data["연도"] == latest_year].copy()

    # 지역 이름의 결측값과 공백을 정리합니다.
    for col in ["시도", "시군구", "동"]:
        data[col] = data[col].fillna("").astype(str).str.strip()
        data[col] = data[col].replace("", "미분류")

    # 인구 값은 숫자로 변환합니다.
    # 빈 값이나 숫자로 변환할 수 없는 값은 0으로 처리합니다.
    for col in population_cols:
        data[col] = pd.to_numeric(
            data[col], errors="coerce"
        ).fillna(0)

    return data, latest_year


try:
    with st.spinner("최신 인구 데이터를 불러오는 중입니다..."):
        df, latest_year = load_data()
except Exception as error:
    st.error("데이터를 불러오거나 정리하는 중 오류가 발생했습니다.")
    st.info(
        "인터넷 연결, ZIP 주소, CSV 열 이름을 확인해 주세요."
    )
    st.exception(error)
    st.stop()


# ============================================================
# 4. 시도 → 시군구 → 동 드롭다운
# ============================================================

st.subheader("📍 지역 선택")

col1, col2, col3 = st.columns(3)

# 첫 번째 선택: 시도
sido_list = sorted(df["시도"].unique().tolist())

with col1:
    sido = st.selectbox(
        "① 시도",
        sido_list,
        key="sido_select",
    )

# 두 번째 선택: 선택한 시도에 속하는 시군구만 표시합니다.
sido_df = df[df["시도"] == sido]
sigungu_list = sorted(sido_df["시군구"].unique().tolist())

with col2:
    sigungu = st.selectbox(
        "② 시군구",
        sigungu_list,
        key=f"sigungu_{sido}",
    )

# 세 번째 선택: 선택한 시군구에 속하는 동만 표시합니다.
sigungu_df = sido_df[sido_df["시군구"] == sigungu]
dong_list = sorted(sigungu_df["동"].unique().tolist())

with col3:
    dong = st.selectbox(
        "③ 읍·면·동",
        dong_list,
        key=f"dong_{sido}_{sigungu}",
    )

# 현재 선택한 동네의 행만 가져옵니다.
area_df = sigungu_df[sigungu_df["동"] == dong]

if area_df.empty:
    st.warning("선택한 지역의 자료가 없습니다.")
    st.stop()

# 동일한 지역이 여러 행에 걸쳐 있다면 나이별 인구를 합산합니다.
population = area_df[MALE_COLS + FEMALE_COLS].sum()

male = [int(population[col]) for col in MALE_COLS]
female = [int(population[col]) for col in FEMALE_COLS]


# ============================================================
# 5. 인구 요약
# ============================================================

male_total = sum(male)
female_total = sum(female)
all_total = male_total + female_total

st.markdown("---")
st.subheader(f"📊 {sido} {sigungu} {dong} · {latest_year}년")

m1, m2, m3 = st.columns(3)

m1.metric("전체 인구", f"{all_total:,}명")
m2.metric("남자 인구", f"{male_total:,}명")
m3.metric("여자 인구", f"{female_total:,}명")


# ============================================================
# 6. Plotly 인구 피라미드
# ============================================================

st.markdown("---")
st.subheader("👥 인구 피라미드")
st.caption(
    "남자는 왼쪽, 여자는 오른쪽입니다. "
    "막대에 마우스를 올리면 해당 연령의 인구를 확인할 수 있습니다."
)

fig = go.Figure()

# 남자 인구는 음수로 바꾸어 왼쪽에 표시합니다.
fig.add_trace(
    go.Bar(
        name="남자",
        x=[-value for value in male],
        y=AGES,
        orientation="h",
        marker_color="#779BC4",
        customdata=male,
        hovertemplate=(
            "나이: %{y}<br>"
            "남자 인구: %{customdata:,}명"
            "<extra></extra>"
        ),
    )
)

# 여자 인구는 양수 그대로 오른쪽에 표시합니다.
fig.add_trace(
    go.Bar(
        name="여자",
        x=female,
        y=AGES,
        orientation="h",
        marker_color="#E7A08D",
        hovertemplate=(
            "나이: %{y}<br>"
            "여자 인구: %{x:,}명"
            "<extra></extra>"
        ),
    )
)

# 남녀를 비교하기 쉽도록 좌우 가로축 범위를 대칭으로 맞춥니다.
max_count = max(male + female + [1])
limit = max_count * 1.1

fig.update_layout(
    title=dict(
        text=f"{sido} {sigungu} {dong} 인구 분포",
        x=0.5,
        xanchor="center",
    ),
    barmode="overlay",
    bargap=0.12,
    height=1500,
    plot_bgcolor="#FFFCF8",
    paper_bgcolor="#FFF9F2",
    font=dict(
        family="Arial, sans-serif",
        size=12,
        color="#4D392D",
    ),
    margin=dict(l=100, r=35, t=85, b=70),
    legend=dict(
        orientation="h",
        x=0.5,
        xanchor="center",
        y=1.02,
        yanchor="bottom",
    ),
    xaxis=dict(
        title="인구 (명)",
        range=[-limit, limit],
        zeroline=True,
        zerolinecolor="#9A8574",
        zerolinewidth=2,
        gridcolor="#EDE2D6",
        # 음수로 그린 남자 인구도 눈금은 양수로 읽히도록 표시합니다.
        tickmode="array",
        tickvals=[
            -limit,
            -limit / 2,
            0,
            limit / 2,
            limit,
        ],
        ticktext=[
            f"{int(limit):,}",
            f"{int(limit / 2):,}",
            "0",
            f"{int(limit / 2):,}",
            f"{int(limit):,}",
        ],
    ),
    yaxis=dict(
        title="나이",
        # 중요: 나이 카테고리를 직접 지정합니다.
        # 이 목록은 0세, 1세, ... 99세, 100세 이상 순서입니다.
        categoryorder="array",
        categoryarray=AGES,
        tickmode="array",
        tickvals=AGES,
        ticktext=AGES,
        # 축 전체를 뒤집는 옵션은 사용하지 않습니다.
        # categoryarray의 순서대로 0세가 아래, 100세 이상이 위에 놓입니다.
        gridcolor="#F0E5D9",
        automargin=True,
    ),
)

st.plotly_chart(fig, use_container_width=True)


# ============================================================
# 7. 나이별 숫자 표
# ============================================================

with st.expander("📋 나이별 인구 숫자 보기"):
    detail = pd.DataFrame(
        {
            "나이": AGES,
            "남자 인구": male,
            "여자 인구": female,
            "전체 인구": [
                m + f for m, f in zip(male, female)
            ],
        }
    )

    st.dataframe(
        detail,
        use_container_width=True,
        hide_index=True,
    )

st.caption(
    f"자료 연도: {latest_year}년 · "
    f"지역: {sido} {sigungu} {dong}"
)
