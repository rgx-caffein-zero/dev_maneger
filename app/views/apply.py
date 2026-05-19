from datetime import date, datetime, time, timedelta

import streamlit as st

from config_loader import load_servers
from db import (
    add_reservation,
    delete_reservation,
    get_reservation,
    has_gpu_conflict,
    list_reservations,
    update_reservation,
)

st.title("📝 利用申請")

servers = load_servers()
if not servers:
    st.error("サーバ設定が読み込めません。config/servers.yaml を確認してください。")
    st.stop()

server_options = {s["id"]: f"{s['name']} ({s['host']})" for s in servers}
server_ids = list(server_options.keys())

if "edit_id" not in st.session_state:
    st.session_state.edit_id = None

defaults = {
    "user_name": "",
    "server_id": server_ids[0],
    "purpose": "",
    "use_gpu": False,
    "start_date": date.today(),
    "start_time": time(9, 0),
    "end_date": date.today(),
    "end_time": time(18, 0),
}

if st.session_state.edit_id is not None:
    existing = get_reservation(st.session_state.edit_id)
    if existing:
        start_dt = datetime.fromisoformat(existing["start_at"])
        end_dt = datetime.fromisoformat(existing["end_at"])
        defaults.update({
            "user_name": existing["user_name"],
            "server_id": existing["server_id"],
            "purpose": existing["purpose"],
            "use_gpu": bool(existing["use_gpu"]),
            "start_date": start_dt.date(),
            "start_time": start_dt.time().replace(second=0, microsecond=0),
            "end_date": end_dt.date(),
            "end_time": end_dt.time().replace(second=0, microsecond=0),
        })
        st.info(f"申請ID #{st.session_state.edit_id} を編集中です")
    else:
        st.session_state.edit_id = None

with st.form("reservation_form", clear_on_submit=False):
    col_left, col_right = st.columns(2)
    with col_left:
        user_name = st.text_input("申請者名", value=defaults["user_name"])
        server_index = (
            server_ids.index(defaults["server_id"])
            if defaults["server_id"] in server_ids
            else 0
        )
        server_id = st.selectbox(
            "使用サーバ",
            options=server_ids,
            index=server_index,
            format_func=lambda x: server_options[x],
        )
        use_gpu = st.checkbox(
            "GPU(VRAM)を使用する",
            value=defaults["use_gpu"],
            help="チェックすると、同一サーバ・同一時間帯のGPU予約と重複できなくなります",
        )

    with col_right:
        st.markdown("**使用期間（時間単位）**")
        date_col, time_col = st.columns(2)
        with date_col:
            start_date = st.date_input("開始日", value=defaults["start_date"])
            end_date = st.date_input("終了日", value=defaults["end_date"])
        with time_col:
            start_time = st.time_input(
                "開始時刻",
                value=defaults["start_time"],
                step=timedelta(hours=1),
            )
            end_time = st.time_input(
                "終了時刻",
                value=defaults["end_time"],
                step=timedelta(hours=1),
            )

    purpose = st.text_area("用途", value=defaults["purpose"], height=80)

    btn_col1, btn_col2 = st.columns([1, 1])
    submitted = btn_col1.form_submit_button(
        "登録 / 更新", type="primary", use_container_width=True
    )
    cancelled = btn_col2.form_submit_button(
        "編集をキャンセル", use_container_width=True
    )

if cancelled:
    st.session_state.edit_id = None
    st.rerun()

if submitted:
    start_at = datetime.combine(start_date, start_time).isoformat(timespec="seconds")
    end_at = datetime.combine(end_date, end_time).isoformat(timespec="seconds")

    errors = []
    if not user_name.strip():
        errors.append("申請者名を入力してください")
    if not purpose.strip():
        errors.append("用途を入力してください")
    if end_at <= start_at:
        errors.append("終了日時は開始日時より後にしてください")
    if use_gpu and has_gpu_conflict(
        server_id, start_at, end_at, exclude_id=st.session_state.edit_id
    ):
        errors.append("指定の時間帯は既にGPU使用の予約があります")

    if errors:
        for e in errors:
            st.error(e)
    elif st.session_state.edit_id is not None:
        update_reservation(
            st.session_state.edit_id,
            user_name.strip(),
            server_id,
            purpose.strip(),
            use_gpu,
            start_at,
            end_at,
        )
        st.success(f"申請ID #{st.session_state.edit_id} を更新しました")
        st.session_state.edit_id = None
        st.rerun()
    else:
        new_id = add_reservation(
            user_name.strip(), server_id, purpose.strip(),
            use_gpu, start_at, end_at,
        )
        st.success(f"申請ID #{new_id} を登録しました")
        st.rerun()

st.divider()
st.subheader("既存の申請")

reservations = list_reservations()
if not reservations:
    st.info("申請がまだありません")
else:
    for r in reservations:
        with st.container(border=True):
            cols = st.columns([4, 1, 1])
            with cols[0]:
                server_label = server_options.get(r["server_id"], r["server_id"])
                gpu_badge = "🟢 GPU" if r["use_gpu"] else "⚪ CPUのみ"
                st.markdown(
                    f"**#{r['id']} | {server_label} | {gpu_badge}**"
                )
                st.caption(
                    f"申請者: {r['user_name']} / "
                    f"期間: {r['start_at']} 〜 {r['end_at']}"
                )
                st.text(r["purpose"])
            with cols[1]:
                if st.button("✏️ 編集", key=f"edit_{r['id']}", use_container_width=True):
                    st.session_state.edit_id = r["id"]
                    st.rerun()
            with cols[2]:
                if st.button(
                    "🗑️ 削除", key=f"del_{r['id']}", use_container_width=True
                ):
                    delete_reservation(r["id"])
                    st.toast(f"申請ID #{r['id']} を削除しました")
                    st.rerun()
