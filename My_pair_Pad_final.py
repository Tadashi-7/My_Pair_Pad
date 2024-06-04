import os
import streamlit as st
import pandas as pd
import numpy as np
import gspread
from google.oauth2.service_account import Credentials
from gspread_dataframe import set_with_dataframe
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
import folium
from streamlit_folium import folium_static

# 環境変数の読み込み
load_dotenv()

# 環境変数から認証情報を取得
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
PRIVATE_KEY_PATH = os.getenv("PRIVATE_KEY_PATH")
PRIVATE_KEY_PATH = r"gspread-test-425102-115e6f4c5062.json"
SP_SHEET     = 'tech03' # sheet名


# セッション状態の初期化
if 'show_all' not in st.session_state:
    st.session_state['show_all'] = False  # 初期状態は地図上の物件のみを表示

# 地図上以外の物件も表示するボタンの状態を切り替える関数
def toggle_show_all():
    st.session_state['show_all'] = not st.session_state['show_all']

# スプレッドシートからデータを読み込む関数
def load_data_from_spreadsheet():
    # googleスプレッドシートの認証 jsonファイル読み込み(key値はGCPから取得)
    SP_CREDENTIAL_FILE = PRIVATE_KEY_PATH

    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]

    credentials = Credentials.from_service_account_file(
        SP_CREDENTIAL_FILE,
        scopes=scopes
    )
    gc = gspread.authorize(credentials)

    SP_SHEET_KEY = '1tQD2MtTPl7gg5Ar_y9mjxgq7crMgH2M-0H4tgekOk-Y' # d/〇〇/edit の〇〇部分
    sh = gc.open_by_key(SP_SHEET_KEY)

    # 不動産データの取得
    worksheet = sh.worksheet(SP_SHEET) # シートのデータ取得
    pre_data = worksheet.get_all_values()
    df = pd.DataFrame(pre_data[1:], columns=pre_data[0]) # 一段目をカラム、以下データフレームで取得

    return df

# データフレームの前処理を行う関数
def preprocess_dataframe(df):
    # '賃料(管理費込み)' 列から '万円' を削除
    df['賃料(管理費込み)'] = df['賃料(管理費込み)'].str.replace('万円', '', regex=False)
    # 空文字列を NaN に置き換える
    df['賃料(管理費込み)'] = df['賃料(管理費込み)'].replace('', np.nan)
    # 数値に変換
    df['賃料(管理費込み)'] = df['賃料(管理費込み)'].astype(float)
    return df

# 緯度・経度の前処理を行う関数
def preprocess_lat_lon(df):
    df['緯度'] = pd.to_numeric(df['緯度'], errors='coerce')
    df['経度'] = pd.to_numeric(df['経度'], errors='coerce')
    return df

# リンクをクリック可能にする関数
def make_clickable(url):
    return f'<a target="_blank" href="{url}">{url}</a>'

# 地図を作成し、マーカーを追加する関数
def create_map(df):
    # 有効な緯度経度データを持つ行のみをフィルタリング
    filtered_df = df.dropna(subset=['緯度', '経度'])
    
    if filtered_df.empty:
        return None
    
    # 地図の初期設定（緯度経度のデータがある物件の平均位置を中心に）
    #map_center = [filtered_df['緯度'].mean(), filtered_df['経度'].mean()]

    #地図の初期位置を丸の内に設定
    map_center = [35.6811, 139.767] 
    m = folium.Map(location=map_center, zoom_start=12)

   # 丸の内に特別なマーカーを追加
    folium.Marker(
        location=map_center,
        popup="丸の内",
        icon=folium.Icon(color='red', icon='info-sign')
    ).add_to(m)

    # 丸の内エリアに色を塗る（円で表現）
    folium.Circle(
        location=map_center,
        radius=500,  # メートル単位
        popup="丸の内エリア",
        color='red',
        fill=True,
        fill_color='red',
        fill_opacity=0.2
    ).add_to(m)

    # 他の物件のマーカーを追加
    for idx, row in filtered_df.iterrows():
        # ポップアップに表示するHTMLコンテンツを作成
        popup_html = f"""
        <b>住所:</b> {row['住所']}<br>
        <b>賃料:</b> {row['賃料(管理費込み)']}万円<br>
        <b>間取り:</b> {row['間取り']} ({row['階数']})<br>
        <b>築年数:</b> {row['築年数']}年<br>
        {row['物件URL']}
        """
        # HTMLをポップアップに設定
        popup = folium.Popup(popup_html, max_width=400)
        folium.Marker(
            [row['緯度'], row['経度']],
            popup=popup,
            icon=folium.Icon(color='blue', icon='home')
        ).add_to(m)

    return m

# 検索結果を表示する関数
def display_search_results(df):
    # 物件番号を含む新しい列を作成
    df['物件番号'] = range(1, len(df) + 1)
    
    # URLをクリック可能なリンクに変換
    df['物件URL'] = df['物件URL'].apply(make_clickable)
    
    # 表示する列を選択し、順序を設定
    display_columns = ['物件番号', '住所', '賃料(管理費込み)', '間取り', '階数', '築年数', '物件URL']
    df_display = df[display_columns]
    
    # 列名を日本語に変更
    column_names = {
        '賃料(管理費込み)': '賃料(万円)',
        '物件URL': '詳細'
    }
    df_display = df_display.rename(columns=column_names)
    
    # データフレームをHTMLに変換して表示
    st.markdown(df_display.to_html(escape=False, index=False), unsafe_allow_html=True)

# メインのアプリケーション
def main():
    df = load_data_from_spreadsheet()
    df = preprocess_dataframe(df)
    df = preprocess_lat_lon(df)

    st.title('賃貸物件情報の可視化')

    # 乗り入れ本数と金額帯のフィルタを1:1の割合で分割
    col1, col2 = st.columns(2)

    with col1:
        # 乗り入れ本数の選択
        train_lines = st.radio(
            '■ 最寄り駅からの乗り入れ本数',
            [
                '以下から選択してください',
                'やや多い(8～9本)',
                '多い(10～14本)',
                'とても多い(15本～)'
            ],
            index=0  # デフォルトで最初のオプションを選択
        )

    with col2:
        # 金額帯の選択
        price_range = st.radio(
            '■ 月額費用(管理費込み)',
            [
                '以下から選択してください',
                '15万円以内',
                '20万円以内',
                '25万円以内'
            ],
            index=0  # デフォルトで最初のオプションを選択
        )

    # 選択された条件でデータをフィルタリング
    filtered_df = df[
        (df['乗り入れ本数'] == train_lines) &
        (df['金額帯'] == price_range)
    ].copy()

    # 両方のオプションが選択されている場合にのみ処理を続行
    if train_lines != '以下から選択してください' and price_range != '以下から選択してください':

        # 物件がない場合のメッセージ
        if filtered_df.empty:
            st.write("条件に合う物件が見つかりません。")
        else:
            # '賃料(管理費込み)' 列を数値に変換
            filtered_df['賃料'] = filtered_df['賃料(管理費込み)'].astype(float)

            # 物件URLをクリック可能なリンクに変換
            filtered_df['詳細'] = filtered_df['物件URL'].apply(make_clickable)

            # 表示する列を選択し、順序を設定
            display_columns = ['住所', '階数', '間取り', '築年数', '賃料', '詳細']
            display_df = filtered_df[display_columns].copy()
    
             # '賃料' 列に '万円' を追加
            display_df['賃料'] = display_df['賃料'].apply(lambda x: f"{x}万円")



         # 地図を作成して表示
            map = create_map(filtered_df)
        if map:
            st.write("### 物件の位置")
            folium_static(map)
        else:
             st.write("地図を表示できる物件がありません。")

        # データフレームをHTMLとしてスタイリングして表示
        st.write("### 条件に合う物件一覧")
        st.write(display_df.to_html(escape=False, index=False), unsafe_allow_html=True)

        # 地図上以外の物件も表示するボタン
        if st.button("地図上以外の物件も表示"):
            toggle_show_all()
        if st.session_state['show_all']:
            display_search_results(df)
       
    else:
        # 両方のオプションが "以下から選択してください" の場合、何も表示しない
        pass
            

if __name__ == "__main__":
    main()
