
import re
import unicodedata
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
# 필수 컬럼명(기존 유지)
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
# 유틸: 컬럼 이름 정규화(대소문자/공백/기호/한글기호 차이 흡수)
# -------------------------
def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", str(s)).strip().lower()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[^\w]+", "", s)  # 영숫자/밑줄 외 제거
    return s

cols = list(df.columns)
norm_map = {c: norm(c) for c in cols}

# 시작/끝 표적 문자열(여러 변형 고려)
targets_start = ["trans-nerolidol", "t-nerolidol", "(+/-)-nerolidol", "nerolidol"]
targets_end   = ["xylenes+ethylbenzene", "xylenes + ethylbenzene", "xylenesethylbenzene"]

start_idx = None
end_idx = None

norm_targets_start = [norm(t) for t in targets_start]
norm_targets_end = [norm(t) for t in targets_end]

for i, c in enumerate(cols):
    nc = norm_map[c]
    if start_idx is None and nc in norm_targets_start:
        start_idx = i
    if end_idx is None and nc in norm_targets_end:
        end_idx = i

if start_idx is None or end_idx is None:
    st.error("지정 범위의 시작/끝 VOC 컬럼명을 찾지 못했습니다. (trans-nerolidol ~ xylenes + ethylbenzene)")
    st.write("감지된 컬럼(일부):", cols[:40])
    st.stop()

if start_idx > end_idx:
    start_idx, end_idx = end_idx, start_idx

voc_columns = cols[start_idx:end_idx+1]

# 숫자형 컬럼만 사용(안전장치)
numeric_voc = []
for c in voc_columns:
    s = pd.to_numeric(df[c], errors="coerce")
    # 숫자가 하나도 없으면 제외
    if s.notna().any():
        numeric_voc.append(c)

if not numeric_voc:
    st.error("선정된 VOC 구간에서 숫자형 컬럼을 찾지 못했습니다.")
    st.stop()

voc_columns = numeric_voc

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
# 사이드바: 필터 & 옵션 (기존 유지)
# -------------------------
st.sidebar.header("🔧 분석 옵션")

# Chamber / Line
if CHAMBER_COL not in df.columns or LINE_COL not in df.columns:
    st.warning("Chamber/Line 컬럼이 없습니다. 파일 헤더를 확인하세요.")

chambers = ["전체"] + sorted(df[CHAMBER_COL].dropna().unique().tolist()) if CHAMBER_COL in df.columns else ["전체"]
lines    = ["전체"] + sorted(df[LINE_COL].dropna().unique().tolist()) if LINE_COL in df.columns else ["전체"]

chamber_sel = st.sidebar.selectbox("🏠 Chamber", chambers, index=0)
line_sel    = st.sidebar.selectbox("🧵 Line", lines, index=0)

# Progress 멀티선택
progress_vals_all = sorted(df[PROGRESS_COL].dropna().unique().tolist()) if PROGRESS_COL in df.columns else []
progress_sel = st.sidebar.multiselect("🧭 Progress(복수 선택 가능)", progress_vals_all, default=progress_vals_all)

mode = st.sidebar.radio("분석 모드 선택", ["처리별 VOC 비교", "시간별 VOC 변화"])
selected_voc = st.sidebar.selectbox("📌 분석할 VOC 물질 선택", voc_columns)

# Facet 옵션
facet_by_chamber = st.sidebar.checkbox("Chamber로 분할 보기", value=False)
facet_by_line    = st.sidebar.checkbox("Line으로 분할 보기", value=False)

if mode == "처리별 VOC 비교":
    chart_type = st.sidebar.radio("차트 유형", ["막대그래프", "박스플롯"], index=0)
    selected_interval = st.sidebar.selectbox("⏱ Interval (h) 선택", ["전체"] + intervals)
else:
    selected_treatment = st.sidebar.selectbox("🧪 처리구 선택", treatments)

# -------------------------
# 공통 필터 적용
# -------------------------
filtered_df = df.copy()
if CHAMBER_COL in filtered_df.columns and chamber_sel != "전체":
    filtered_df = filtered_df[filtered_df[CHAMBER_COL] == chamber_sel]
if LINE_COL in filtered_df.columns and line_sel != "전체":
    filtered_df = filtered_df[filtered_df[LINE_COL] == line_sel]
if PROGRESS_COL in filtered_df.columns and progress_sel:
    filtered_df = filtered_df[filtered_df[PROGRESS_COL].isin(progress_sel)]

def add_facets(kwargs):
    if facet_by_chamber and CHAMBER_COL in filtered_df.columns:
        kwargs["facet_col"] = CHAMBER_COL
    if facet_by_line and LINE_COL in filtered_df.columns:
        if "facet_col" in kwargs:
            kwargs["facet_row"] = LINE_COL
        else:
            kwargs["facet_col"] = LINE_COL
    return kwargs

# -------------------------
# 처리별 VOC 비교
# -------------------------
if mode == "처리별 VOC 비교":
    if selected_interval == "전체":
        data_use = filtered_df.copy()
        title_suffix = "모든 시간"
    else:
        data_use = filtered_df[filtered_df[INTERVAL_COL] == selected_interval]
        title_suffix = f"Interval: {selected_interval}h"

    y_label = f"{selected_voc} 농도 (ppb)"
    color_kw = {"color": PROGRESS_COL} if PROGRESS_COL in data_use.columns else {}

    if chart_type == "막대그래프":
        group_keys = [TREAT_COL]
        if PROGRESS_COL in data_use.columns:
            group_keys.append(PROGRESS_COL)
        if CHAMBER_COL in data_use.columns and facet_by_chamber:
            group_keys.append(CHAMBER_COL)
        if LINE_COL in data_use.columns and facet_by_line:
            group_keys.append(LINE_COL)

        grouped = data_use.groupby(group_keys)[selected_voc].agg(mean="mean", std="std").reset_index()
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
            x=TREAT_COL, y=selected_voc,
            labels={selected_voc: y_label, TREAT_COL: "처리"},
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
    tick_vals = expected_intervals

    group_keys = [INTERVAL_COL]
    if PROGRESS_COL in data_use.columns:
        group_keys.append(PROGRESS_COL)
    if CHAMBER_COL in data_use.columns and facet_by_chamber:
        group_keys.append(CHAMBER_COL)
    if LINE_COL in data_use.columns and facet_by_line:
        group_keys.append(LINE_COL)

    ts_voc = data_use.groupby(group_keys)[selected_voc].mean().reset_index().sort_values(INTERVAL_COL)
    fig_kwargs = dict(
        x=INTERVAL_COL, y=selected_voc, markers=True,
        labels={INTERVAL_COL: "Interval (h)", selected_voc: f"{selected_voc} 농도 (ppb)"},
        title=f"{selected_treatment} 처리 - {selected_voc} 변화 추이"
    )
    if PROGRESS_COL in data_use.columns:
        fig_kwargs["color"] = PROGRESS_COL
    fig_kwargs = add_facets(fig_kwargs)

    fig_voc = px.line(ts_voc, **fig_kwargs)
    fig_voc.update_xaxes(tickmode='array', tickvals=tick_vals)
    fig_voc.update_layout(margin=dict(l=10, r=10, t=60, b=10))
    st.plotly_chart(fig_voc, use_container_width=True)

    # 온도/상대습도
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
