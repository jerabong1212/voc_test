
import streamlit as st
import pandas as pd
import plotly.express as px

# -------------------------
# 기본 설정
# -------------------------
st.set_page_config(page_title="VOC 실험 시각화", layout="wide")
st.title("🌿 식물 VOC 실험 결과 시각화")

# -------------------------
# 데이터 로드
# -------------------------
try:
    df = pd.read_excel("VOC_data.xlsx")
except Exception as e:
    st.error(f"데이터 로딩 오류: {e}")
    st.stop()

# -------------------------
# 컬럼명(엑셀 1행) - 실제 명칭에 맞춤
# -------------------------
NAME_COL      = "Name"
TREAT_COL     = "Treatment"
START_COL     = "Start Date"
END_COL       = "End Date"
CHAMBER_COL   = "Chamber"
LINE_COL      = "Line"
PROGRESS_COL  = "Progress"
INTERVAL_COL  = "Interval (h)"
TEMP_COL      = "Temp (℃)"
HUMID_COL     = "Humid (%)"

# -------------------------
# VOC 8종: 7개 + ethene
# - 'DEN'은 내부 컬럼명 유지, UI 표기만 'DMNT'로 변환
# - 'methyl jasmonate (temporary)'는 UI 표기 'Methyl jasmonate'
# -------------------------
VOC_INTERNAL = [
    "(+/-)-nerolidol",
    "(Z)-3-hexen-1-ol",
    "(Z)-3-hexenal",
    "(Z)-3-hexenyl acetate",
    "DEN",  # displayed as DMNT
    "methyl jasmonate (temporary)",  # displayed as Methyl jasmonate
    "methyl salicylate",
    "ethene"
]

# 실제 존재 확인 및 대체
voc_columns = []
for col in VOC_INTERNAL:
    if col in df.columns:
        voc_columns.append(col)
    elif col == "DEN" and "DMNT" in df.columns:
        voc_columns.append("DMNT")  # fallback if some file uses DMNT as column name
    else:
        pass

# 필수 8개 확인
if len(voc_columns) != 8:
    st.error(f"VOC 8종을 정확히 찾지 못했습니다. 감지된 VOC: {voc_columns}")
    st.stop()

# 디스플레이용 라벨 매핑
DISPLAY_MAP = {
    "DEN": "DMNT",
    "DMNT": "DMNT",
    "methyl jasmonate (temporary)": "Methyl jasmonate",
    # 나머지는 그대로 사용
}
def display_name(col):
    return DISPLAY_MAP.get(col, col)

# -------------------------
# 처리/인터벌 목록 및 기대 인터벌 체크
# -------------------------
if TREAT_COL not in df.columns or INTERVAL_COL not in df.columns:
    st.error(f"필수 키 컬럼 누락: {TREAT_COL}, {INTERVAL_COL}")
    st.stop()

treatments = sorted(df[TREAT_COL].dropna().unique().tolist())
intervals = sorted(df[INTERVAL_COL].dropna().unique().tolist())

expected_intervals = [-1, 0, 1, 2, 3, 4, 5, 6, 12, 18, 24]
missing = [x for x in expected_intervals if x not in intervals]
if missing:
    st.info(f"데이터에 없는 Interval(h): {missing} (기준 간격)")

# -------------------------
# 사이드바: 필터 & 옵션
# -------------------------
st.sidebar.header("🔧 분석 옵션")

# Chamber / Line는 핵심 → 항상 표시(없으면 경고)
if CHAMBER_COL not in df.columns or LINE_COL not in df.columns:
    st.warning("Chamber/Line 컬럼이 없습니다. 파일 헤더를 확인하세요.")

chambers = ["전체"] + sorted(df[CHAMBER_COL].dropna().unique().tolist()) if CHAMBER_COL in df.columns else ["전체"]
lines    = ["전체"] + sorted(df[LINE_COL].dropna().unique().tolist()) if LINE_COL in df.columns else ["전체"]

chamber_sel = st.sidebar.selectbox("🏠 Chamber", chambers, index=0)
line_sel    = st.sidebar.selectbox("🧵 Line", lines, index=0)

# 진행상태(Progress) 필터 멀티선택
progress_vals_all = sorted(df[PROGRESS_COL].dropna().unique().tolist()) if PROGRESS_COL in df.columns else []
progress_sel = st.sidebar.multiselect("🧭 Progress(복수 선택 가능)", progress_vals_all, default=progress_vals_all)

mode = st.sidebar.radio("분석 모드 선택", ["처리별 VOC 비교", "시간별 VOC 변화"])
selected_voc = st.sidebar.selectbox("📌 VOC 물질 선택", [display_name(c) for c in voc_columns])
# 내부 컬럼명 역매핑
inv_map = {display_name(c): c for c in voc_columns}
selected_voc_internal = inv_map[selected_voc]

# 분할 보기 옵션: Chamber / Line
facet_by_chamber = st.sidebar.checkbox("Chamber로 분할 보기", value=False)
facet_by_line    = st.sidebar.checkbox("Line으로 분할 보기", value=False)

if mode == "처리별 VOC 비교":
    chart_type = st.sidebar.radio("차트 유형", ["막대그래프", "박스플롯"], index=0)
    selected_interval = st.sidebar.selectbox("⏱ Interval (h) 선택", ["전체"] + intervals)
else:
    selected_treatment = st.sidebar.selectbox("🧪 처리구 선택", treatments)

# -------------------------
# 공통: 필터 적용
# -------------------------
filtered_df = df.copy()
if CHAMBER_COL in filtered_df.columns and chamber_sel != "전체":
    filtered_df = filtered_df[filtered_df[CHAMBER_COL] == chamber_sel]
if LINE_COL in filtered_df.columns and line_sel != "전체":
    filtered_df = filtered_df[filtered_df[LINE_COL] == line_sel]
if PROGRESS_COL in filtered_df.columns and progress_sel:
    filtered_df = filtered_df[filtered_df[PROGRESS_COL].isin(progress_sel)]

# -------------------------
# 처리별 VOC 비교
# -------------------------
def add_facets(kwargs):
    # facet 설정 도우미
    if facet_by_chamber and CHAMBER_COL in filtered_df.columns:
        kwargs["facet_col"] = CHAMBER_COL
    if facet_by_line and LINE_COL in filtered_df.columns:
        # 둘 다 켜지면 Line을 행, Chamber를 열로 배치
        if "facet_col" in kwargs:
            kwargs["facet_row"] = LINE_COL
        else:
            kwargs["facet_col"] = LINE_COL
    return kwargs

if mode == "처리별 VOC 비교":
    if selected_interval == "전체":
        data_use = filtered_df.copy()
        title_suffix = "모든 시간"
    else:
        data_use = filtered_df[filtered_df[INTERVAL_COL] == selected_interval]
        title_suffix = f"Interval: {selected_interval}h"

    y_label = f"{selected_voc} 농도 (ppb)"
    # legend에서 Progress 구분 가능하도록 색상에 Progress 사용
    color_kw = {"color": PROGRESS_COL} if PROGRESS_COL in data_use.columns else {}

    if chart_type == "막대그래프":
        # 평균±표준편차, Progress 구분을 위해 groupby 키 확장
        group_keys = [TREAT_COL]
        if PROGRESS_COL in data_use.columns:
            group_keys.append(PROGRESS_COL)
        if CHAMBER_COL in data_use.columns and facet_by_chamber:
            group_keys.append(CHAMBER_COL)
        if LINE_COL in data_use.columns and facet_by_line:
            group_keys.append(LINE_COL)

        grouped = data_use.groupby(group_keys)[selected_voc_internal].agg(mean="mean", std="std").reset_index()

        fig_kwargs = dict(
            x=TREAT_COL, y="mean",
            labels={"mean": y_label, TREAT_COL: "처리"},
            title=f"{selected_voc} - 처리별 평균 비교 ({title_suffix})",
            **color_kw
        )
        fig_kwargs = add_facets(fig_kwargs)
        fig = px.bar(grouped, **fig_kwargs, error_y="std", barmode="group")
        fig.update_layout(margin=dict(l=10, r=10, t=60, b=10))
        st.plotly_chart(fig, use_container_width=True)

    else:  # 박스플롯
        fig_kwargs = dict(
            x=TREAT_COL, y=selected_voc_internal,
            labels={selected_voc_internal: y_label, TREAT_COL: "처리"},
            title=f"{selected_voc} - 처리별 분포 (박스플롯) ({title_suffix})",
            points="outliers",
            **color_kw
        )
        fig_kwargs = add_facets(fig_kwargs)
        fig = px.box(data_use, **fig_kwargs)
        fig.update_layout(margin=dict(l=10, r=10, t=60, b=10))
        st.plotly_chart(fig, use_container_width=True)

# -------------------------
# 시간별 VOC 변화 (+ 온/습도)
# -------------------------
elif mode == "시간별 VOC 변화":
    data_use = filtered_df[filtered_df[TREAT_COL] == selected_treatment].copy()

    # X축 간격 고정
    tick_vals = expected_intervals

    # VOC 시계열: Progress 구분 색상
    group_keys = [INTERVAL_COL]
    if PROGRESS_COL in data_use.columns:
        group_keys.append(PROGRESS_COL)
    if CHAMBER_COL in data_use.columns and facet_by_chamber:
        group_keys.append(CHAMBER_COL)
    if LINE_COL in data_use.columns and facet_by_line:
        group_keys.append(LINE_COL)

    ts_voc = data_use.groupby(group_keys)[selected_voc_internal].mean().reset_index().sort_values(INTERVAL_COL)

    fig_kwargs = dict(
        x=INTERVAL_COL, y=selected_voc_internal, markers=True,
        labels={INTERVAL_COL: "Interval (h)", selected_voc_internal: f"{selected_voc} 농도 (ppb)"},
        title=f"{selected_treatment} 처리 - {selected_voc} 변화 추이"
    )
    if PROGRESS_COL in data_use.columns:
        fig_kwargs["color"] = PROGRESS_COL
    fig_kwargs = add_facets(fig_kwargs)

    fig_voc = px.line(ts_voc, **fig_kwargs)
    fig_voc.update_xaxes(tickmode='array', tickvals=tick_vals)
    fig_voc.update_layout(margin=dict(l=10, r=10, t=60, b=10))
    st.plotly_chart(fig_voc, use_container_width=True)

    # 온도/상대습도 시계열 (컬럼 존재 시)
    cols_exist = [c for c in [TEMP_COL, HUMID_COL] if c in data_use.columns]
    if cols_exist:
        for env_col in cols_exist:
            group_keys_env = [INTERVAL_COL]
            if PROGRESS_COL in data_use.columns:
                group_keys_env.append(PROGRESS_COL)
            if CHAMBER_COL in data_use.columns and facet_by_chamber:
                group_keys_env.append(CHAMBER_COL)
            if LINE_COL in data_use.columns and facet_by_line:
                group_keys_env.append(LINE_COL)

            ts_env = data_use.groupby(group_keys_env)[env_col].mean().reset_index().sort_values(INTERVAL_COL)
            ylab = "온도 (°C)" if env_col == TEMP_COL else "상대습도 (%)" if env_col == HUMID_COL else env_col
            fig_kwargs_env = dict(
                x=INTERVAL_COL, y=env_col, markers=True,
                labels={INTERVAL_COL: "Interval (h)", env_col: ylab},
                title=f"{selected_treatment} 처리 - {env_col} 변화 추이"
            )
            if PROGRESS_COL in data_use.columns:
                fig_kwargs_env["color"] = PROGRESS_COL
            fig_kwargs_env = add_facets(fig_kwargs_env)

            fig_env = px.line(ts_env, **fig_kwargs_env)
            fig_env.update_xaxes(tickmode='array', tickvals=tick_vals)
            fig_env.update_layout(margin=dict(l=10, r=10, t=60, b=10))
            st.plotly_chart(fig_env, use_container_width=True)
    else:
        st.info("온도/상대습도 컬럼이 없어 환경변화 그래프는 표시하지 않습니다.")

# -------------------------
# 원본 데이터 확인
# -------------------------
with st.expander("🔍 원본 데이터 보기"):
    st.dataframe(df, use_container_width=True)
