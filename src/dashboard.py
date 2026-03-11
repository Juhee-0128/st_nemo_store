import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os

import json

# 페이지 설정
st.set_page_config(
    page_title="네모스토어 매물 대시보드 (Pro)",
    page_icon="🏠",
    layout="wide"
)

# 데이터 로드 및 전처리 함수
@st.cache_data
def load_data():
    db_path = "/Users/seongjuhee/jhicb6-proj2/nemostore/nemostore.db"
    conn = sqlite3.connect(db_path)
    query = "SELECT * FROM stores"
    df = pd.read_sql(query, conn)
    conn.close()

    # 금액 단위 변환 (col_name.md 기준: 1,000배)
    money_cols = ['deposit', 'monthlyRent', 'maintenanceFee', 'premium', 'sale', 
                  'firstDeposit', 'firstMonthlyRent', 'firstPremium']
    
    for col in money_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0) * 1000
    
    # 총 고정 비용 (월세 + 관리비)
    df['totalMonthlyCost'] = df['monthlyRent'] + df['maintenanceFee']
    
    # 층수 변환
    df['floor_label'] = df['floor'].apply(lambda x: f"지하 {abs(int(x))}층" if x < 0 else (f"{int(x)}층" if x > 0 else "0층/정보없음"))
    
    # JSON 파싱 (이미지 URL 리스트)
    def parse_json(x):
        try:
            return json.loads(x) if x else []
        except:
            return []
    
    df['smallPhotos'] = df['smallPhotoUrls'].apply(parse_json)
    df['originPhotos'] = df['originPhotoUrls'].apply(parse_json)
    
    # 대표역 추출 (지하철역 텍스트에서 역 이름만 추출)
    df['station_name'] = df['nearSubwayStation'].str.split(',').str[0].str.strip()
    
    return df

# 데이터 로드
try:
    df = load_data()
except Exception as e:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
    st.stop()

# 세션 상태 초기화 (상세 페이지용)
if 'selected_article_id' not in st.session_state:
    st.session_state.selected_article_id = None

# 상세 페이지 팝업 (Dialog) 함수
@st.dialog("매물 상세 정보", width="large")
def show_detail(article_id):
    article = df[df['id'] == article_id].iloc[0]
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if article['originPhotos']:
            st.image(article['originPhotos'][0], use_container_width=True, caption=article['title'])
            if len(article['originPhotos']) > 1:
                st.write("📸 추가 이미지")
                cols = st.columns(min(3, len(article['originPhotos'])-1))
                for i, img_url in enumerate(article['originPhotos'][1:4]):
                    cols[i].image(img_url, use_container_width=True)
        else:
            st.warning("이미지가 없습니다.")
            
    with col2:
        st.subheader(article['title'])
        st.write(f"📍 **위치**: {article['nearSubwayStation'] or '정보없음'}")
        st.write(f"🏢 **업종**: {article['businessMiddleCodeName']}")
        st.write(f"📐 **전용면적**: {article['size']}㎡")
        st.write(f"🔝 **층수**: {article['floor_label']} / 전체 {article['groundFloor']}층")
        
        st.divider()
        st.markdown(f"💰 **보증금**: {format_krw(article['deposit'])}원")
        st.markdown(f"📅 **월세**: {format_krw(article['monthlyRent'])}원")
        st.markdown(f"💎 **권리금**: {format_krw(article['premium'])}원 (비공개: {'O' if article['isPremiumClosed'] else 'X'})")
        st.markdown(f"🛠️ **관리비**: {format_krw(article['maintenanceFee'])}원")
        
        # 벤치마킹 데이터 계산
        station = article['station_name']
        biz = article['businessMiddleCodeName']
        
        avg_rent_area = df[df['businessMiddleCodeName'] == biz]['monthlyRent'].mean()
        diff_rent = ((article['monthlyRent'] - avg_rent_area) / avg_rent_area * 100) if avg_rent_area > 0 else 0
        
        st.divider()
        st.write("📊 **상대적 가치 (동일 업종 평균 대비)**")
        color = "red" if diff_rent > 0 else "blue"
        word = "비쌈" if diff_rent > 0 else "합리적"
        st.markdown(f"월세가 평균 대비 <span style='color:{color}; font-weight:bold;'>{abs(diff_rent):.1f}% {word}</span>", unsafe_allow_html=True)

# --- 사이드바 필터 ---
st.sidebar.header("🔍 고급 검색 필터")

st.sidebar.subheader("금액 조건 (원)")

def format_krw(val):
    if val >= 100000000:
        return f"{val/100000000:.1f}억"
    elif val >= 10000:
        return f"{val/10000:.0f}만"
    return f"{val:.0f}"

# 보증금 필터
deposit_range = st.sidebar.slider(
    "보증금 범위",
    int(df['deposit'].min()),
    int(df['deposit'].max()),
    (int(df['deposit'].min()), int(df['deposit'].max())),
    step=1000000,
    format="%d"
)

# 월세 + 관리비 합산 필터
total_cost_range = st.sidebar.slider(
    "총 고정 지출 (월세+관리비)",
    int(df['totalMonthlyCost'].min()),
    int(df['totalMonthlyCost'].max()),
    (int(df['totalMonthlyCost'].min()), int(df['totalMonthlyCost'].max())),
    step=100000,
    format="%d"
)

# 권리금 필터
premium_range = st.sidebar.slider(
    "권리금 범위",
    int(df['premium'].min()),
    int(df['premium'].max()),
    (int(df['premium'].min()), int(df['premium'].max())),
    step=1000000,
    format="%d"
)

# 업종 필터
business_types = ["전체"] + sorted(df['businessMiddleCodeName'].unique().tolist())
selected_business = st.sidebar.selectbox("업종 선택", business_types)

# 지하철역 필터
subway_stations = ["전체"] + sorted(df['nearSubwayStation'].dropna().unique().tolist())
selected_subway = st.sidebar.selectbox("인근 지하철역", subway_stations)

# --- 필터링 적용 ---
filtered_df = df[
    (df['deposit'] >= deposit_range[0]) & (df['deposit'] <= deposit_range[1]) &
    (df['totalMonthlyCost'] >= total_cost_range[0]) & (df['totalMonthlyCost'] <= total_cost_range[1]) &
    (df['premium'] >= premium_range[0]) & (df['premium'] <= premium_range[1])
]

if selected_business != "전체":
    filtered_df = filtered_df[filtered_df['businessMiddleCodeName'] == selected_business]

if selected_subway != "전체":
    filtered_df = filtered_df[filtered_df['nearSubwayStation'] == selected_subway]

# 입주 가능일 필터 (간단 키워드 필터)
move_in_types = ["전체"] + sorted(df['moveInDate'].dropna().unique().tolist())
selected_move_in = st.sidebar.selectbox("입주 가능일", move_in_types)
if selected_move_in != "전체":
    filtered_df = filtered_df[filtered_df['moveInDate'] == selected_move_in]

# 검색창
search_query = st.text_input("📝 매물 제목 키워드 검색", placeholder="예: 무권리, 역세권, 깔끔한 등")
if search_query:
    filtered_df = filtered_df[filtered_df['title'].str.contains(search_query, case=False, na=False)]

# --- 지표 (Metrics) ---
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("총 매물 수", f"{len(filtered_df)}건")
with m2:
    avg_deposit = filtered_df['deposit'].mean() if len(filtered_df) > 0 else 0
    st.metric("평균 보증금", f"{format_krw(avg_deposit)}원")
with m3:
    avg_rent = filtered_df['monthlyRent'].mean() if len(filtered_df) > 0 else 0
    st.metric("평균 월세", f"{format_krw(avg_rent)}원")
with m4:
    avg_premium = filtered_df['premium'].mean() if len(filtered_df) > 0 else 0
    st.metric("평균 권리금", f"{format_krw(avg_premium)}원")

st.divider()

# --- 탭 구성 ---
tab_gal, tab_map, tab_ana, tab_list = st.tabs(["🖼️ 갤러리 뷰", "📍 지도 보기", "📊 데이터 분석", "📋 매물 목록"])

with tab_gal:
    st.subheader("📸 매물 갤러리")
    if not filtered_df.empty:
        # 캐싱된 갤러리 렌더링을 위해 컨테이너 활용
        gal_placeholder = st.container()
        with gal_placeholder:
            # 갤러리 레이아웃 (4열로 확장하여 더 많은 매물 노출)
            gal_cols = st.columns(4)
            for idx, row in enumerate(filtered_df.itertuples()):
                with gal_cols[idx % 4]:
                    img_url = row.smallPhotos[0] if row.smallPhotos else "https://via.placeholder.com/300?text=No+Image"
                    st.image(img_url, use_container_width=True)
                    st.markdown(f"**{row.title[:15]}...**" if len(row.title) > 15 else f"**{row.title}**")
                    st.caption(f"{row.businessMiddleCodeName} | {format_krw(row.monthlyRent)}원")
                    if st.button("상세보기", key=f"btn_{row.id}"):
                        show_detail(row.id)
                    st.divider()
    else:
        st.info("검색 결과가 없습니다.")

with tab_map:
    st.subheader("🗺️ 매물 위치 (지하철역 기준)")
    station_coords = {
        '을지로입구역': {'lat': 37.5660, 'lon': 126.9822},
        '종각역': {'lat': 37.5702, 'lon': 126.9831},
        '시청역': {'lat': 37.5657, 'lon': 126.9769},
        '명동역': {'lat': 37.5609, 'lon': 126.9863},
        '종로3가역': {'lat': 37.5704, 'lon': 126.9922},
        '충무로역': {'lat': 37.5612, 'lon': 126.9942},
        '회현역': {'lat': 37.5585, 'lon': 126.9782}
    }
    
    map_data = []
    for row in filtered_df.itertuples():
        coords = station_coords.get(row.station_name)
        if coords:
            import random
            map_data.append({
                'title': row.title,
                'lat': coords['lat'] + random.uniform(-0.0005, 0.0005),
                'lon': coords['lon'] + random.uniform(-0.0005, 0.0005)
            })
    
    if map_data:
        map_df = pd.DataFrame(map_data)
        st.map(map_df)
    else:
        st.info("지역 정보가 매칭되는 매물이 없습니다.")

with tab_ana:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🔝 인기 매물 (조회수 기준)")
        top_viewed = filtered_df.nlargest(10, 'viewCount')[['title', 'viewCount', 'businessMiddleCodeName']]
        fig = px.bar(top_viewed, x='viewCount', y='title', orientation='h', 
                     color='viewCount', color_continuous_scale='Reds', template='plotly_white')
        fig.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig, use_container_width=True)
        
    with c2:
        st.subheader("🏢 층별 평균 월세 분석")
        floor_avg = filtered_df.groupby('floor_label')['monthlyRent'].mean().reset_index()
        fig = px.bar(floor_avg, x='floor_label', y='monthlyRent', color='monthlyRent',
                     color_continuous_scale='Blues', template='plotly_white')
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("📐 전용면적당 가격(areaPrice) 분포")
    if not filtered_df.empty:
        fig = px.histogram(filtered_df, x='areaPrice', nbins=30, color='businessMiddleCodeName',
                           marginal="box", template='plotly_white', 
                           title="전용면적당 가격 분포 (업종별)")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("📈 매물 등록 트렌드")
    if not filtered_df.empty:
        # 날짜 타입 변환 및 일별 카운트
        trend_df = filtered_df.copy()
        trend_df['created_date'] = pd.to_datetime(trend_df['createdDateUtc']).dt.date
        date_counts = trend_df.groupby('created_date').size().reset_index(name='count')
        fig = px.line(date_counts, x='created_date', y='count', markers=True, 
                      template='plotly_white', title="일자별 신규 매물 등록 현황")
        st.plotly_chart(fig, use_container_width=True)

with tab_list:
    st.subheader("📋 전체 매물 상세 리스트")
    display_cols = ['title', 'businessMiddleCodeName', 'deposit', 'monthlyRent', 'premium', 'maintenanceFee', 'totalMonthlyCost', 'size', 'floor_label', 'nearSubwayStation', 'viewCount', 'moveInDate']
    col_mapping = {
        'title': '매물 제목', 
        'businessMiddleCodeName': '업종', 
        'deposit': '보증금(원)', 
        'monthlyRent': '월세(원)', 
        'premium': '권리금(원)', 
        'maintenanceFee': '관리비(원)', 
        'totalMonthlyCost': '총고정지출(원)',
        'size': '면적(㎡)', 
        'floor_label': '층수', 
        'nearSubwayStation': '지하철역',
        'viewCount': '조회수',
        'moveInDate': '입주가능일'
    }
    display_df = filtered_df[display_cols].rename(columns=col_mapping)
    st.dataframe(display_df, use_container_width=True)

# 푸터
st.markdown("---")
st.caption("데이터 출처: 네모스토어 수집 데이터 | 시각화: Plotly & Streamlit Map")
