from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from config_loader import load_servers
from db import list_reservations

st.title("📅 予約状況")

servers = load_servers()
server_map = {s["id"]: s["name"] for s in servers}

reservations = list_reservations()
if not reservations:
    st.info("申請がまだありません。「申請」ページから登録してください。")
    st.stop()

df = pd.DataFrame(reservations)
df["server_name"] = df["server_id"].map(server_map).fillna(df["server_id"])
df["start_at"] = pd.to_datetime(df["start_at"])
df["end_at"] = pd.to_datetime(df["end_at"])
df["gpu_label"] = df["use_gpu"].map({1: "GPU", 0: "CPU"})
df["label"] = df["user_name"] + " (" + df["gpu_label"] + ")"

col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    days_back = st.slider("過去(日)", 0, 14, 1)
with col2:
    days_ahead = st.slider("未来(日)", 1, 60, 14)
with col3:
    filter_mode = st.radio(
        "フィルタ", ["全て", "GPU利用のみ", "CPUのみ"], horizontal=True
    )

now = datetime.now()
view_start = now - timedelta(days=days_back)
view_end = now + timedelta(days=days_ahead)

filtered = df[(df["end_at"] >= view_start) & (df["start_at"] <= view_end)].copy()
if filter_mode == "GPU利用のみ":
    filtered = filtered[filtered["use_gpu"] == 1]
elif filter_mode == "CPUのみ":
    filtered = filtered[filtered["use_gpu"] == 0]

# y軸を全サーバ表示にしておくと予約ゼロのサーバも見える
all_server_names = [s["name"] for s in servers]

if filtered.empty:
    st.info("表示範囲内に予約がありません")
else:
    fig = px.timeline(
        filtered,
        x_start="start_at",
        x_end="end_at",
        y="server_name",
        color="user_name",
        hover_data={
            "purpose": True,
            "gpu_label": True,
            "start_at": "|%Y-%m-%d %H:%M",
            "end_at": "|%Y-%m-%d %H:%M",
            "server_name": False,
        },
        text="label",
    )
    fig.update_yaxes(
        title="サーバ",
        categoryorder="array",
        categoryarray=all_server_names[::-1],
    )
    fig.update_xaxes(title="日時", range=[view_start, view_end])
    fig.update_layout(
        height=max(300, 80 * len(all_server_names)),
        legend_title="申請者",
        margin=dict(l=10, r=10, t=30, b=10),
    )
    fig.add_vline(
        x=now.timestamp() * 1000,
        line_dash="dash",
        line_color="red",
        annotation_text="現在",
        annotation_position="top",
    )
    st.plotly_chart(fig, use_container_width=True)

st.subheader("申請一覧")
display_df = df[
    ["id", "server_name", "user_name", "purpose",
     "gpu_label", "start_at", "end_at"]
].copy()
display_df.columns = ["ID", "サーバ", "申請者", "用途", "GPU", "開始", "終了"]
st.dataframe(display_df, use_container_width=True, hide_index=True)
