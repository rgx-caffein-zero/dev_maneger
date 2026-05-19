import pandas as pd
import streamlit as st
from streamlit_calendar import calendar

from config_loader import load_servers
from db import list_reservations

st.title("📅 予約状況")

servers = load_servers()
server_map = {s["id"]: s["name"] for s in servers}
server_ids = [s["id"] for s in servers]

reservations = list_reservations()
if not reservations:
    st.info("申請がまだありません。「申請」ページから登録してください。")
    st.stop()

# ---- フィルタ ----
col_servers, col_gpu = st.columns([2, 1])
with col_servers:
    selected_servers = st.multiselect(
        "サーバで絞り込み",
        options=server_ids,
        default=server_ids,
        format_func=lambda x: server_map.get(x, x),
        placeholder="表示するサーバを選択",
    )
with col_gpu:
    filter_gpu = st.radio(
        "GPUフィルタ",
        ["全て", "GPU利用のみ", "CPUのみ"],
        horizontal=True,
    )

filtered = []
for r in reservations:
    if r["server_id"] not in selected_servers:
        continue
    if filter_gpu == "GPU利用のみ" and r["use_gpu"] != 1:
        continue
    if filter_gpu == "CPUのみ" and r["use_gpu"] != 0:
        continue
    filtered.append(r)

# ---- 凡例 ----
GPU_BG, GPU_BORDER = "#e74c3c", "#c0392b"
CPU_BG, CPU_BORDER = "#3498db", "#2874a6"

st.markdown(
    f"""
    <div style="display:flex; gap:24px; align-items:center; margin:8px 0;">
      <div style="display:flex; align-items:center; gap:6px;">
        <span style="display:inline-block; width:14px; height:14px;
                     background:{GPU_BG}; border:1px solid {GPU_BORDER}; border-radius:2px;"></span>
        <span>GPU使用</span>
      </div>
      <div style="display:flex; align-items:center; gap:6px;">
        <span style="display:inline-block; width:14px; height:14px;
                     background:{CPU_BG}; border:1px solid {CPU_BORDER}; border-radius:2px;"></span>
        <span>CPUのみ</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---- カレンダー用イベント生成 ----
events = []
for r in filtered:
    use_gpu = bool(r["use_gpu"])
    server_name = server_map.get(r["server_id"], r["server_id"])
    events.append({
        "id": str(r["id"]),
        "title": f"{r['user_name']} / {server_name}",
        "start": r["start_at"],
        "end": r["end_at"],
        "backgroundColor": GPU_BG if use_gpu else CPU_BG,
        "borderColor": GPU_BORDER if use_gpu else CPU_BORDER,
        "textColor": "#ffffff",
        "extendedProps": {
            "server_name": server_name,
            "user_name": r["user_name"],
            "purpose": r["purpose"],
            "use_gpu": use_gpu,
            "start_at": r["start_at"],
            "end_at": r["end_at"],
        },
    })

calendar_options = {
    "headerToolbar": {
        "left": "prev,next today",
        "center": "title",
        "right": "dayGridMonth,timeGridWeek,timeGridDay,listWeek",
    },
    "buttonText": {
        "today": "今日",
        "month": "月",
        "week": "週",
        "day": "日",
        "list": "一覧",
    },
    "initialView": "dayGridMonth",
    "locale": "ja",
    "firstDay": 1,            # 月曜始まり
    "slotMinTime": "00:00:00",
    "slotMaxTime": "24:00:00",
    "allDaySlot": False,
    "nowIndicator": True,
    "navLinks": True,
    "height": 720,
    "eventTimeFormat": {
        "hour": "2-digit",
        "minute": "2-digit",
        "hour12": False,
    },
    "slotLabelFormat": {
        "hour": "2-digit",
        "minute": "2-digit",
        "hour12": False,
    },
}

custom_css = """
    .fc-event-title { font-weight: 600; }
    .fc-event { cursor: pointer; }
    .fc-toolbar-title { font-size: 1.2rem !important; }
"""

# key にフィルタ条件を含めて、選択変更時に再描画
cal_key = f"cal_{'-'.join(sorted(selected_servers))}_{filter_gpu}"
cal_state = calendar(
    events=events,
    options=calendar_options,
    custom_css=custom_css,
    key=cal_key,
)

# ---- クリックされた予約の詳細 ----
if cal_state and cal_state.get("eventClick"):
    ev = cal_state["eventClick"]["event"]
    props = ev.get("extendedProps", {}) or {}
    badge = "🟢 GPU使用" if props.get("use_gpu") else "⚪ CPUのみ"
    with st.container(border=True):
        st.markdown(f"### 予約詳細  #{ev.get('id')}")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**サーバ**: {props.get('server_name')}")
            st.markdown(f"**申請者**: {props.get('user_name')}")
            st.markdown(f"**種別**: {badge}")
        with c2:
            st.markdown(f"**開始**: {props.get('start_at')}")
            st.markdown(f"**終了**: {props.get('end_at')}")
        st.markdown("**用途**:")
        st.write(props.get("purpose"))
else:
    st.caption("💡 予約ブロックをクリックすると詳細が下に表示されます")

# ---- 一覧（補助） ----
with st.expander("一覧表で見る"):
    if not filtered:
        st.info("条件に合致する予約がありません")
    else:
        df = pd.DataFrame(filtered)
        df["server_name"] = df["server_id"].map(server_map).fillna(df["server_id"])
        df["gpu_label"] = df["use_gpu"].map({1: "GPU", 0: "CPU"})
        display_df = df[
            ["id", "server_name", "user_name", "purpose",
             "gpu_label", "start_at", "end_at"]
        ].copy()
        display_df.columns = ["ID", "サーバ", "申請者", "用途", "GPU", "開始", "終了"]
        st.dataframe(display_df, use_container_width=True, hide_index=True)
