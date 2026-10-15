
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

# 인구 데이터 ZIP 파일 주소
DATA_URL = (
    "https://raw.githubusercontent.com/hoyeon-max/project/"
    "main/population_ts_yearly_gender.zip"
)

# 0세부터 99세까지, 마지막은 100세 이상
AGES = [f"{age}세" for age in range(100)] + ["100세 이상"]

# CSV에 들어 있는 남녀별 인구 열 이름
MALE_COLS = [f"남_{age}" for age in AGES]
FEMALE_COLS = [f"여_{age}" for age in AGES]

# 평균연령 계산에 사용할 숫자 나이
# 100세 이상은 계산할 때 100세로 간주합니다.
AGE_NUMBERS = list(range(100)) + [100]


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

    .warning-note {
        background: #FFF0D6;
        border: 1px solid #E8B65D;
        border-radius: 12px;
        padding: 10px 14px;
        color: #7A4B10;
        margin-top: 8px;
        font-weight: 600;
    }

    .insight-note {
        background: #FFF0E5;
        border-left: 5px solid #D98B62;
        border-radius: 10px;
        padding: 14px 18px;
        color: #694632;
        margin-top: 14px;
        margin-bottom: 20px;
        font-size: 16px;
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
    # ZIP 주소를 pandas로 바로 읽습니다.
    # UTF-8로 읽기 실패 시 CP949로 다시 시도합니다.
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

    # 열 이름 앞뒤에 공백이 있다면 제거합니다.
    data.columns = data.columns.astype(str).str.strip()

    # 연도와 지역 정보 열이 있는지 확인합니다.
    required = ["연도", "시도", "시군구", "동"]
    missing = [col for col in required if col not in data.columns]

    if missing:
        raise ValueError(
            f"필수 열이 없습니다: {', '.join(missing)}"
        )

    # 남녀별 0~100세 이상 인구 열을 확인합니다.
    population_cols = MALE_COLS + FEMALE_COLS
    missing_pop = [
        col for col in population_cols if col not in data.columns
    ]

    if missing_pop:
        raise ValueError(
            "인구 열을 찾을 수 없습니다. 누락된 열 예시: "
            + ", ".join(missing_pop[:8])
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

    # 지역명에 공백이나 결측값이 있으면 정리합니다.
    for col in ["시도", "시군구", "동"]:
        data[col] = data[col].fillna("").astype(str).str.strip()
        data[col] = data[col].replace("", "미분류")

    # 인구 열을 숫자로 변환합니다.
    # 빈 값이나 숫자로 바꿀 수 없는 값은 0으로 처리합니다.
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
    st.info("인터넷 연결, ZIP 주소, CSV 열 이름을 확인해 주세요.")
    st.exception(error)
    st.stop()


# ============================================================
# 4. 시도 → 시군구 → 동 드롭다운
# ============================================================

st.subheader("📍 지역 선택")

col1, col2, col3 = st.columns(3)

# 첫 번째 드롭다운: 시도
sido_list = sorted(df["시도"].unique().tolist())

with col1:
    sido = st.selectbox(
        "① 시도",
        sido_list,
        key="sido_select",
    )

# 두 번째 드롭다운: 선택한 시도의 시군구
sido_df = df[df["시도"] == sido]
sigungu_list = sorted(sido_df["시군구"].unique().tolist())

with col2:
    sigungu = st.selectbox(
        "② 시군구",
        sigungu_list,
        key=f"sigungu_{sido}",
    )

# 세 번째 드롭다운: 선택한 시군구의 동
sigungu_df = sido_df[sido_df["시군구"] == sigungu]
dong_list = sorted(sigungu_df["동"].unique().tolist())

with col3:
    dong = st.selectbox(
        "③ 읍·면·동",
        dong_list,
        key=f"dong_{sido}_{sigungu}",
    )

# 선택한 지역의 행만 가져옵니다.
area_df = sigungu_df[sigungu_df["동"] == dong]

if area_df.empty:
    st.warning("선택한 지역의 자료가 없습니다.")
    st.stop()

# 같은 지역이 여러 행이면 나이별 인구를 합산합니다.
population = area_df[MALE_COLS + FEMALE_COLS].sum()

male = [int(population[col]) for col in MALE_COLS]
female = [int(population[col]) for col in FEMALE_COLS]

# 나이별 남녀 합계
age_totals = [
    m + f for m, f in zip(male, female)
]


# ============================================================
# 5. 지표 계산: 총인구, 평균연령, 고령화율
# ============================================================

male_total = sum(male)
female_total = sum(female)
total_population = male_total + female_total

# 평균연령은 각 나이의 인구를 가중치로 계산합니다.
# 100세 이상은 100세로 간주합니다.
if total_population > 0:
    weighted_age_sum = sum(
        age * count
        for age, count in zip(AGE_NUMBERS, age_totals)
    )
    average_age = weighted_age_sum / total_population
else:
    average_age = 0.0

# 65세 이상 인구는 65세부터 100세 이상까지의 합계입니다.
population_65_plus = sum(age_totals[65:])

# 고령화율 = 65세 이상 인구 / 전체 인구 × 100
aging_rate = (
    population_65_plus / total_population * 100
    if total_population > 0
    else 0.0
)

# 고령화율이 20%를 초과하면 주의 표시를 켭니다.
is_aging_alert = aging_rate > 20


# ============================================================
# 6. 그래프 위에 지표 카드 3개 표시
# ============================================================

st.markdown("---")

st.subheader(
    f"📊 {sido} {sigungu} {dong} · {latest_year}년 주요 지표"
)

card1, card2, card3 = st.columns(3)

with card1:
    st.metric(
        label="👥 총인구",
        value=f"{total_population:,}명",
    )

with card2:
    st.metric(
        label="🎂 평균연령",
        value=f"{average_age:.1f}세",
    )

with card3:
    # 고령화율이 20%를 초과하면 카드 제목에 주의 표시를 붙입니다.
    aging_label = (
        "⚠️ 고령화율"
        if is_aging_alert
        else "🌿 고령화율"
    )

    st.metric(
        label=aging_label,
        value=f"{aging_rate:.1f}%",
        help="전체 인구 중 65세 이상 인구의 비율입니다.",
    )

    if is_aging_alert:
        st.markdown(
            """
            <div class="warning-note">
                ⚠️ 고령화율이 20%를 넘었습니다.
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# 7. Plotly 인구 피라미드
# ============================================================

st.markdown("---")
st.subheader("👥 인구 피라미드")

st.caption(
    "남자는 왼쪽, 여자는 오른쪽입니다. "
    "막대에 마우스를 올리면 해당 나이의 인구를 확인할 수 있습니다."
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

# 좌우 축을 대칭으로 맞춰 남녀 인구를 비교하기 쉽게 합니다.
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
        # 남자 인구는 음수지만 눈금에는 양수로 표시합니다.
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
        # 중요: 나이 라벨을 0세부터 100세 이상까지 직접 고정합니다.
        # 자동 정렬이나 축 전체를 뒤집는 옵션은 사용하지 않습니다.
        categoryorder="array",
        categoryarray=AGES,
        tickmode="array",
        tickvals=AGES,
        ticktext=AGES,
        gridcolor="#F0E5D9",
        automargin=True,
    ),
)

st.plotly_chart(fig, use_container_width=True)


# ============================================================
# 8. 피라미드 아래 자동 설명
# ============================================================

# 아이는 0~14세, 어르신은 65세 이상으로 정의합니다.
children_population = sum(age_totals[:15])
children_rate = (
    children_population / total_population * 100
    if total_population > 0
    else 0.0
)

elderly_rate = aging_rate

# 아이 비율과 어르신 비율을 비교해 자동 설명을 만듭니다.
if total_population == 0:
    insight = (
        "인구 자료가 없어 연령 구성을 비교하기 어렵습니다."
    )

elif children_rate > elderly_rate:
    insight = (
        f"아이(0~14세) 비율은 {children_rate:.1f}%로 "
        f"어르신(65세 이상, {elderly_rate:.1f}%) 비율보다 높아요. "
        "상대적으로 아이의 비중이 큰 편입니다."
    )

elif elderly_rate > children_rate:
    insight = (
        f"어르신(65세 이상) 비율은 {elderly_rate:.1f}%로 "
        f"아이(0~14세, {children_rate:.1f}%) 비율보다 높아요. "
        "상대적으로 어르신의 비중이 큰 편입니다."
    )

else:
    insight = (
        f"아이(0~14세)와 어르신(65세 이상) 비율이 "
        f"모두 {children_rate:.1f}%로 같아요."
    )

st.markdown(
    f"""
    <div class="insight-note">
        <strong>
            이 동네는 아이가 많은 편인가요, 어르신이 많은 편인가요?
        </strong>
        <br>
        {insight}
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 9. 나이별 인구 숫자 표
# ============================================================

with st.expander("📋 나이별 인구 숫자 보기"):
    detail = pd.DataFrame(
        {
            "나이": AGES,
            "남자 인구": male,
            "여자 인구": female,
            "전체 인구": age_totals,
        }
    )

    st.dataframe(
        detail,
        use_container_width=True,
        hide_index=True,
    )

st.caption(
    f"자료 연도: {latest_year}년 · "
    f"지역: {sido} {sigungu} {dong} · "
    "평균연령 계산 시 100세 이상은 100세로 간주합니다."
)
