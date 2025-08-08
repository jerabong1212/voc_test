
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
# 필요 시 경로 수정 (예: "VOC_data.xlsx")
df = pd.read_excel("VOC_data.xlsx")

# -------------------------
# 사용자 지정(필수 컬럼 이름)
# -------------------------
TREAT_COL = "Treatment"
INTERVAL_COL = "Interval (h)"
TEMP_COL = "Temp"            # 데이터셋의 온도 컬럼명에 맞게 수정
HUMID_COL = "Humid"          # 데이터셋의 상대습도 컬럼명에 맞게 수정
CHAMBER_COL = "Chamber"      # 새로 추가된 컬럼(없으면 자동 처리)
LINE_COL = "Line"            # 새로 추가된 컬럼(없으면 자동 처리)
PROGRESS_COL = "Progress"    # 새로 추가된 컬럼(없으면 자동 처리)

# VOC 후보(데이터셋에 존재하는 것만 사용)
# 기존 + Methyl jasmonate/MeJA를 포함
VOC_CANDIDATES = [
    'z-3-hexenal', 'z-3-hexenol', 'z-3-hexenyl acetate', 'nerolidol', 'DMNT', 'MeSA',
    'Methyl jasmonate', 'MeJA'
]
voc_columns = [c for c in VOC_CANDIDATES if c in df.columns]
if not voc_columns:
    st.warning("VOC 컬럼을 찾지 못했습니다. VOC 컬럼명을 확인하세요.")
    st.stop()

# 처리/인터벌 목록
treatments = df[TREAT_COL].dropna().unique().tolist()
intervals = sorted(df[INTERVAL_COL].dropna().unique().tolist())

# 기대하는 인터벌 체크(-1, 0, 1, 2, 3, 4, 5, 6, 12, 18, 24h; 21h 없음 확인)
expected_intervals = [-1, 0, 1, 2, 3, 4, 5, 6, 12, 18, 24]
missing = [x for x in expected_intervals if x not in intervals]
if missing:
    st.info(f"데이터에 없는 Interval(h): {missing} (예상 간격 기준)")

# -------------------------
# 사이드바: 필터 & 옵션
# -------------------------
st.sidebar.header("🔧 분석 옵션")

# 새로 추가된 메타데이터 필터(있을 때만 표시)
def optional_filter(label, col_name):
    if col_name in df.columns:
        values = ["전체"] + sorted([v for v in df[col_name].dropna().unique().tolist()])
        return st.sidebar.selectbox(f"{label}", values, index=0)
    return "전체"

chamber_sel = optional_filter("Chamber 필터", CHAMBER_COL)
line_sel = optional_filter("Line 필터", LINE_COL)
progress_sel = optional_filter("Progress 필터", PROGRESS_COL)

# 분석 모드
mode = st.sidebar.radio("분석 모드 선택", ["처리별 VOC 비교", "시간별 VOC 변화"])
selected_voc = st.sidebar.selectbox("📌 분석할 VOC 물질 선택", voc_columns)

# 처리별 비교 시, 차트 유형(막대/박스) 선택
if mode == "처리별 VOC 비교":
    chart_type = st.sidebar.radio("차트 유형", ["막대그래프", "박스플롯"], index=0)
    selected_interval = st.sidebar.selectbox("⏱ Interval (h) 선택", ["전체"] + intervals)
else:
    selected_treatment = st.sidebar.selectbox("🧪 처리구 선택", treatments)

# -------------------------
# 공통: 필터 적용
# -------------------------
filtered_df = df.copy()
if chamber_sel != "전체" and CHAMBER_COL in filtered_df.columns:
    filtered_df = filtered_df[filtered_df[CHAMBER_COL] == chamber_sel]
if line_sel != "전체" and LINE_COL in filtered_df.columns:
    filtered_df = filtered_df[filtered_df[LINE_COL] == line_sel]
if progress_sel != "전체" and PROGRESS_COL in filtered_df.columns:
    filtered_df = filtered_df[filtered_df[PROGRESS_COL] == progress_sel]

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

    # 막대그래프(평균±표준편차) 또는 박스플롯
    if chart_type == "막대그래프":
        grouped = data_use.groupby(TREAT_COL)[selected_voc].agg(['mean', 'std']).reset_index()
        fig = px.bar(
            grouped, x=TREAT_COL, y='mean', error_y='std',
            labels={'mean': f"{selected_voc} 농도 (ppb)", TREAT_COL: "처리"},
            title=f"{selected_voc} - 처리별 평균 비교 ({title_suffix})"
        )
        fig.update_layout(margin=dict(l=10, r=10, t=60, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        # 박스플롯
        fig = px.box(
            data_use, x=TREAT_COL, y=selected_voc, points="outliers",
            labels={selected_voc: f"{selected_voc} 농도 (ppb)", TREAT_COL: "처리"},
            title=f"{selected_voc} - 처리별 분포 (박스플롯) ({title_suffix})"
        )
        fig.update_layout(margin=dict(l=10, r=10, t=60, b=10))
        st.plotly_chart(fig, use_container_width=True)

# -------------------------
# 시간별 VOC 변화 (+ 온/습도)
# -------------------------
elif mode == "시간별 VOC 변화":
    data_use = filtered_df[filtered_df[TREAT_COL] == selected_treatment].copy()

    # X축 간격: 지정한 irregular ticks 반영
    # -1, 0, 1, 2, 3, 4, 5, 6, 12, 18, 24
    tick_vals = expected_intervals
    # VOC 시계열
    ts_voc = data_use.groupby(INTERVAL_COL)[selected_voc].mean().reset_index().sort_values(INTERVAL_COL)
    fig_voc = px.line(
        ts_voc, x=INTERVAL_COL, y=selected_voc, markers=True,
        labels={INTERVAL_COL: "Interval (h)", selected_voc: f"{selected_voc} 농도 (ppb)"},
        title=f"{selected_treatment} 처리 - {selected_voc} 변화 추이"
    )
    fig_voc.update_xaxes(tickmode='array', tickvals=tick_vals)
    fig_voc.update_layout(margin=dict(l=10, r=10, t=60, b=10))
    st.plotly_chart(fig_voc, use_container_width=True)

    # 온도/상대습도 시계열(같은 처리에서 함께 확인)
    # Temp와 Humid 컬럼이 있는 경우만 출력
    cols_exist = [c for c in [TEMP_COL, HUMID_COL] if c in data_use.columns]
    if cols_exist:
        # 평균 집계
        ts_env = data_use.groupby(INTERVAL_COL)[cols_exist].mean().reset_index().sort_values(INTERVAL_COL)
        for env_col in cols_exist:
            ylab = "온도 (°C)" if env_col == TEMP_COL else "상대습도 (%)" if env_col == HUMID_COL else env_col
            fig_env = px.line(
                ts_env, x=INTERVAL_COL, y=env_col, markers=True,
                labels={INTERVAL_COL: "Interval (h)", env_col: ylab},
                title=f"{selected_treatment} 처리 - {env_col} 변화 추이"
            )
            fig_env.update_xaxes(tickmode='array', tickvals=tick_vals)
            fig_env.update_layout(margin=dict(l=10, r=10, t=60, b=10))
            st.plotly_chart(fig_env, use_container_width=True)
    else:
        st.info("온도/상대습도 컬럼이 없어 환경변화 그래프는 표시하지 않습니다. (Temp / Humid 컬럼명 확인)")

# -------------------------
# 원본 데이터 확인
# -------------------------
with st.expander("🔍 원본 데이터 보기"):
    st.dataframe(df, use_container_width=True)
