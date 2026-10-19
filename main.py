
import re
import requests
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

# 인구 데이터 ZIP 파일
DATA_URL = (
    "https://raw.githubusercontent.com/hoyeon-max/project/"
    "main/population_ts_yearly_gender.zip"
)

# 행정동 경계 GeoJSON
# 통계청 SGIS 기반 행정동 경계 자료
GEOJSON_URL = (
    "https://raw.githubusercontent.com/vuski/admdongkor/"
    "master/ver20260401/HangJeongDong_ver20260401.geojson"
)

# 0세부터 99세까지, 마지막은 100세 이상
AGES = [f"{age}세" for age in range(100)] + ["100세 이상"]

MALE_COLS = [f"남_{age}" for age in AGES]
FEMALE_COLS = [f"여_{age}" for age in AGES]

# 100세 이상은 평균연령 계산 시 100세로 간주
AGE_NUMBERS = list(range(100)) + [100]


# ============================================================
# 2. 화면 디자인
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

    .map-note {
        background: #FFFFFF;
        border: 1px solid #EEDFD0;
        border-radius: 10px;
        padding: 12px 16px;
        color: #694632;
        margin-top: 8px;
        margin-bottom: 16px;
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
            우리 동네의 인구 분포와 행정구역 위치를 확인해 보세요.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 3. 공통 문자열 정리
# ============================================================

def normalize_name(value):
    """지역 이름 비교 시 공백과 불필요한 문자를 정리합니다."""
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    return re.sub(r"\s+", "", str(value).strip())


def split_full_admin_name(full_name):
    """
    GeoJSON의 adm_nm 예:
    '서울특별시 종로구 청운효자동'

    반환:
    시도, 시군구, 동
    """
    parts = str(full_name).strip().split()

    if len(parts) >= 3:
        return parts[0], " ".join(parts[1:-1]), parts[-1]

    if len(parts) == 2:
        return parts[0], "", parts[-1]

    if len(parts) == 1:
        return "", "", parts[0]

    return "", "", ""


def province_matches(geo_sido, selected_sido):
    """시도 명칭을 비교합니다."""
    a = normalize_name(geo_sido)
    b = normalize_name(selected_sido)

    if a == b:
        return True

    # 명칭 변경이나 표기 차이를 위한 보조 비교
    aliases = {
        "강원도": "강원특별자치도",
        "강원특별자치도": "강원도",
        "전라북도": "전북특별자치도",
        "전북특별자치도": "전라북도",
    }

    if aliases.get(a) == b:
        return True

    return False


def sigungu_matches(geo_sigungu, selected_sigungu):
    """
    시군구 이름을 비교합니다.
    예를 들어 경계 파일이 '수원시 장안구'이고
    인구 데이터가 '장안구'인 경우도 비교할 수 있게 합니다.
    """
    a = normalize_name(geo_sigungu)
    b = normalize_name(selected_sigungu)

    if not a or not b:
        return False

    return (
        a == b
        or a.endswith(b)
        or b.endswith(a)
    )


# ============================================================
# 4. 인구 데이터 불러오기
# ============================================================

@st.cache_data(show_spinner=False)
def load_data():
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

    data.columns = data.columns.astype(str).str.strip()

    required = ["연도", "시도", "시군구", "동"]
    missing = [col for col in required if col not in data.columns]

    if missing:
        raise ValueError(
            f"필수 열이 없습니다: {', '.join(missing)}"
        )

    population_cols = MALE_COLS + FEMALE_COLS
    missing_pop = [
        col for col in population_cols
        if col not in data.columns
    ]

    if missing_pop:
        raise ValueError(
            "인구 열을 찾을 수 없습니다. 누락된 열 예시: "
            + ", ".join(missing_pop[:8])
        )

    data["연도"] = pd.to_numeric(data["연도"], errors="coerce")
    data = data.dropna(subset=["연도"]).copy()
    data["연도"] = data["연도"].astype(int)
    data = data[data["연도"].between(2015, 2026)].copy()

    if data.empty:
        raise ValueError("2015~2026년 데이터가 없습니다.")

    latest_year = int(data["연도"].max())
    data = data[data["연도"] == latest_year].copy()

    for col in ["시도", "시군구", "동"]:
        data[col] = (
            data[col]
            .fillna("")
            .astype(str)
            .str.strip()
            .replace("", "미분류")
        )

    for col in population_cols:
        data[col] = pd.to_numeric(
            data[col],
            errors="coerce",
        ).fillna(0)

    return data, latest_year


# ============================================================
# 5. 행정동 GeoJSON 불러오기
# ============================================================

@st.cache_data(show_spinner="행정구역 경계 지도를 불러오는 중...")
def load_admin_geojson():
    response = requests.get(GEOJSON_URL, timeout=60)
    response.raise_for_status()

    geojson = response.json()

    if geojson.get("type") != "FeatureCollection":
        raise ValueError(
            "지도 파일이 GeoJSON FeatureCollection 형식이 아닙니다."
        )

    features = []
    feature_info = []

    for index, feature in enumerate(geojson.get("features", [])):
        properties = feature.get("properties", {})

        # 행정동 경계 데이터의 전체 지역 이름
        full_name = (
            properties.get("adm_nm")
            or properties.get("FULL_NM")
            or properties.get("name")
            or ""
        )

        if not full_name:
            continue

        geo_sido, geo_sigungu, geo_dong = (
            split_full_admin_name(full_name)
        )

        # GeoJSON 피처를 구별하기 위한 내부 식별자
        # 원본 행정구역 코드를 변경하지 않고 별도 키를 사용합니다.
        map_id = str(index)

        properties["_map_id"] = map_id
        properties["_full_name"] = str(full_name)
        properties["_sido_name"] = geo_sido
        properties["_sigungu_name"] = geo_sigungu
        properties["_dong_name"] = geo_dong

        feature["properties"] = properties
        features.append(feature)

        feature_info.append({
            "map_id": map_id,
            "전체이름": str(full_name),
            "시도": geo_sido,
            "시군구": geo_sigungu,
            "동": geo_dong,
        })

    if not features:
        raise ValueError(
            "GeoJSON에서 행정동 이름(adm_nm)을 찾지 못했습니다."
        )

    geojson["features"] = features
    feature_df = pd.DataFrame(feature_info)

    return geojson, feature_df


try:
    with st.spinner("최신 인구 데이터를 불러오는 중입니다..."):
        df, latest_year = load_data()

    geojson, geo_features_df = load_admin_geojson()

except Exception as error:
    st.error("데이터를 불러오거나 정리하는 중 오류가 발생했습니다.")
    st.info(
        "인터넷 연결, 인구 데이터 주소, "
        "지도 데이터 주소와 열 이름을 확인해 주세요."
    )
    st.exception(error)
    st.stop()


# ============================================================
# 6. 시도 → 시군구 → 읍·면·동 선택
# ============================================================

st.subheader("📍 지역 선택")

col1, col2, col3 = st.columns(3)

sido_list = sorted(df["시도"].unique().tolist())

with col1:
    sido = st.selectbox(
        "① 시도",
        sido_list,
        key="sido_select",
    )

sido_df = df[df["시도"] == sido]
sigungu_list = sorted(sido_df["시군구"].unique().tolist())

with col2:
    sigungu = st.selectbox(
        "② 시군구",
        sigungu_list,
        key=f"sigungu_{sido}",
    )

sigungu_df = sido_df[sido_df["시군구"] == sigungu]
dong_list = sorted(sigungu_df["동"].unique().tolist())

with col3:
    dong = st.selectbox(
        "③ 읍·면·동",
        dong_list,
        key=f"dong_{sido}_{sigungu}",
    )

area_df = sigungu_df[sigungu_df["동"] == dong]

if area_df.empty:
    st.warning("선택한 지역의 인구 자료가 없습니다.")
    st.stop()


# ============================================================
# 7. 선택한 지역의 인구 계산
# ============================================================

population = area_df[MALE_COLS + FEMALE_COLS].sum()

male = [int(population[col]) for col in MALE_COLS]
female = [int(population[col]) for col in FEMALE_COLS]

age_totals = [
    m + f for m, f in zip(male, female)
]

male_total = sum(male)
female_total = sum(female)
total_population = male_total + female_total

if total_population > 0:
    weighted_age_sum = sum(
        age * count
        for age, count in zip(AGE_NUMBERS, age_totals)
    )
    average_age = weighted_age_sum / total_population
else:
    average_age = 0.0

population_65_plus = sum(age_totals[65:])

aging_rate = (
    population_65_plus / total_population * 100
    if total_population > 0
    else 0.0
)

is_aging_alert = aging_rate > 20


# ============================================================
# 8. 지표 카드
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
# 9. 선택한 시군구 지도 데이터 찾기
# ============================================================

# 전체 이름을 분해해 둔 GeoJSON 속성에서
# 시도와 시군구가 일치하는 경계만 찾습니다.
selected_sgg_features = []

for feature in geojson["features"]:
    properties = feature["properties"]

    feature_sido = properties.get("_sido_name", "")
    feature_sigungu = properties.get("_sigungu_name", "")

    if (
        province_matches(feature_sido, sido)
        and sigungu_matches(feature_sigungu, sigungu)
    ):
        selected_sgg_features.append(feature)

# 선택한 동의 이름이 일치하는 경계를 찾습니다.
selected_dong_features = []

for feature in selected_sgg_features:
    feature_dong = feature["properties"].get("_dong_name", "")

    if normalize_name(feature_dong) == normalize_name(dong):
        selected_dong_features.append(feature)


# ============================================================
# 10. 행정구역 경계 지도
# ============================================================

st.markdown("---")
st.subheader("🗺️ 선택한 지역 지도")

st.markdown(
    f"""
    <div class="map-note">
        <strong>선택 지역:</strong> {sido} {sigungu} {dong}<br>
        연한 색은 선택한 시군구의 읍·면·동 경계이고,
        <strong>주황색은 선택한 읍·면·동</strong>입니다.
    </div>
    """,
    unsafe_allow_html=True,
)

if not selected_sgg_features:
    st.warning(
        "선택한 시군구와 일치하는 지도 경계를 찾지 못했습니다. "
        "인구 데이터와 경계 데이터의 지역 이름 또는 행정구역 개편 여부를 확인해 주세요."
    )

else:
    # 현재 시군구의 피처만 모아 작은 GeoJSON을 만듭니다.
    selected_geojson = {
        "type": "FeatureCollection",
        "features": selected_sgg_features,
    }

    fig_map = go.Figure()

    # 1) 시군구에 속한 모든 읍·면·동을 연한 색으로 표시
    base_locations = [
        feature["properties"]["_map_id"]
        for feature in selected_sgg_features
    ]

    base_names = [
        feature["properties"]["_full_name"]
        for feature in selected_sgg_features
    ]

    fig_map.add_trace(
        go.Choropleth(
            geojson=selected_geojson,
            featureidkey="properties._map_id",
            locations=base_locations,
            z=[0] * len(base_locations),
            customdata=base_names,
            zmin=0,
            zmax=1,
            colorscale=[
                [0, "#F3DCC5"],
                [1, "#F3DCC5"],
            ],
            showscale=False,
            marker={
                "line": {
                    "color": "#FFFFFF",
                    "width": 1.0,
                }
            },
            hovertemplate=(
                "<b>%{customdata}</b>"
                "<extra></extra>"
            ),
            name="시군구 내 읍·면·동",
        )
    )

    # 2) 선택한 읍·면·동을 주황색으로 강조
    if selected_dong_features:
        highlight_locations = [
            feature["properties"]["_map_id"]
            for feature in selected_dong_features
        ]

        highlight_names = [
            feature["properties"]["_full_name"]
            for feature in selected_dong_features
        ]

        fig_map.add_trace(
            go.Choropleth(
                geojson=selected_geojson,
                featureidkey="properties._map_id",
                locations=highlight_locations,
                z=[1] * len(highlight_locations),
                customdata=highlight_names,
                zmin=0,
                zmax=1,
                colorscale=[
                    [0, "#E87943"],
                    [1, "#E87943"],
                ],
                showscale=False,
                marker={
                    "line": {
                        "color": "#8D4929",
                        "width": 1.8,
                    }
                },
                hovertemplate=(
                    "<b>선택한 지역</b><br>"
                    "%{customdata}"
                    "<extra></extra>"
                ),
                name="선택한 읍·면·동",
            )
        )

        st.caption(
            f"선택한 지역의 경계를 찾았습니다: "
            f"{len(selected_dong_features)}개 경계 피처"
        )

    else:
        st.warning(
            f"시군구 경계는 찾았지만 '{dong}'과 정확히 일치하는 "
            "읍·면·동 경계를 찾지 못했습니다. "
            "행정동과 법정동 명칭 차이 또는 행정구역 변경 때문일 수 있습니다."
        )

    fig_map.update_geos(
        visible=False,
        fitbounds="locations",
        showcountries=False,
        showcoastlines=False,
        showland=False,
        showframe=False,
        bgcolor="rgba(0,0,0,0)",
    )

    fig_map.update_layout(
        title={
            "text": f"{sido} {sigungu} 행정구역 경계",
            "x": 0.5,
            "xanchor": "center",
        },
        height=650,
        margin={"l": 0, "r": 0, "t": 60, "b": 0},
        paper_bgcolor="#FFF9F2",
        plot_bgcolor="#FFF9F2",
        showlegend=False,
    )

    st.plotly_chart(
        fig_map,
        use_container_width=True,
        config={"displayModeBar": True},
    )

    st.caption(
        "배경 타일 없이 행정구역 경계만 표시합니다. "
        "지도에 마우스를 올리면 지역 이름을 확인할 수 있습니다."
    )


# ============================================================
# 11. 인구 피라미드
# ============================================================

st.markdown("---")
st.subheader("👥 인구 피라미드")

st.caption(
    "남자는 왼쪽, 여자는 오른쪽입니다. "
    "막대에 마우스를 올리면 해당 나이의 인구를 확인할 수 있습니다."
)

fig = go.Figure()

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

max_count = max(male + female + [1])
limit = max_count * 1.1

fig.update_layout(
    title={
        "text": f"{sido} {sigungu} {dong} 인구 분포",
        "x": 0.5,
        "xanchor": "center",
    },
    barmode="overlay",
    bargap=0.12,
    height=1500,
    plot_bgcolor="#FFFCF8",
    paper_bgcolor="#FFF9F2",
    font={
        "family": "Arial, sans-serif",
        "size": 12,
        "color": "#4D392D",
    },
    margin={"l": 100, "r": 35, "t": 85, "b": 70},
    legend={
        "orientation": "h",
        "x": 0.5,
        "xanchor": "center",
        "y": 1.02,
        "yanchor": "bottom",
    },
    xaxis={
        "title": "인구 (명)",
        "range": [-limit, limit],
        "zeroline": True,
        "zerolinecolor": "#9A8574",
        "zerolinewidth": 2,
        "gridcolor": "#EDE2D6",
        "tickmode": "array",
        "tickvals": [
            -limit,
            -limit / 2,
            0,
            limit / 2,
            limit,
        ],
        "ticktext": [
            f"{int(limit):,}",
            f"{int(limit / 2):,}",
            "0",
            f"{int(limit / 2):,}",
            f"{int(limit):,}",
        ],
    },
    yaxis={
        "title": "나이",
        "categoryorder": "array",
        "categoryarray": AGES,
        "tickmode": "array",
        "tickvals": AGES,
        "ticktext": AGES,
        "gridcolor": "#F0E5D9",
        "automargin": True,
    },
)

st.plotly_chart(fig, use_container_width=True)


# ============================================================
# 12. 피라미드 아래 자동 설명
# ============================================================

children_population = sum(age_totals[:15])

children_rate = (
    children_population / total_population * 100
    if total_population > 0
    else 0.0
)

elderly_rate = aging_rate

if total_population == 0:
    insight = "인구 자료가 없어 연령 구성을 비교하기 어렵습니다."

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
# 13. 나이별 인구 숫자 표
# ============================================================

with st.expander("📋 나이별 인구 숫자 보기"):
    detail = pd.DataFrame({
        "나이": AGES,
        "남자 인구": male,
        "여자 인구": female,
        "전체 인구": age_totals,
    })

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
