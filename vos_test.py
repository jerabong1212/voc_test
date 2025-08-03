import streamlit as st
import pandas as pd
import plotly.express as px

# 데이터 로드
df = pd.read_excel("VOC_data.xlsx")


st.set_page_config(page_title="VOC 실험 시각화", layout="wide")
st.title("🌿 식물 VOC 실험 결과 시각화")

# 분석 가능한 물질 목록 추출
voc_columns = ['z-3-hexenal', 'z-3-hexenol', 'z-3-hexenyl acetate', 'nerolidol', 'DMNT', 'MeSA']
treatments = df['Treatment'].unique().tolist()
intervals = sorted(df['Interval (h)'].dropna().unique().tolist())

# 사이드바 설정
st.sidebar.header("🔧 분석 옵션")
mode = st.sidebar.radio("분석 모드 선택", ["처리별 VOC 비교", "시간별 VOC 변화"])
selected_voc = st.sidebar.selectbox("📌 분석할 VOC 물질 선택", voc_columns)

if mode == "처리별 VOC 비교":
    selected_interval = st.sidebar.selectbox("⏱ Interval (h) 선택", ["전체"] + intervals)

    if selected_interval == "전체":
        filtered = df.copy()
    else:
        filtered = df[df['Interval (h)'] == selected_interval]

    grouped = filtered.groupby('Treatment')[selected_voc].agg(['mean', 'std']).reset_index()
    fig = px.bar(grouped, x='Treatment', y='mean', error_y='std',
                 labels={'mean': f"{selected_voc} 평균 함량"},
                 title=f"{selected_voc} - 처리별 평균 비교 (Interval: {selected_interval})")
    st.plotly_chart(fig, use_container_width=True)

elif mode == "시간별 VOC 변화":
    selected_treatment = st.sidebar.selectbox("🧪 처리구 선택", treatments)
    filtered = df[df['Treatment'] == selected_treatment]
    grouped = filtered.groupby('Interval (h)')[selected_voc].mean().reset_index()

    fig = px.line(grouped, x='Interval (h)', y=selected_voc,
                  markers=True,
                  title=f"{selected_treatment} 처리 - {selected_voc} 변화 추이")
    st.plotly_chart(fig, use_container_width=True)

# 원본 데이터 확인
toggle = st.expander("🔍 원본 데이터 보기")
with toggle:
    st.dataframe(df)
