from datetime import date, datetime, time, timedelta

import streamlit as st

from config_loader import load_servers
from db import (
    add_reservation,
    delete_reservation,
    find_available_slots,
    get_reservation,
    has_gpu_conflict,
    list_reservations,
    update_reservation,
)

BUSINESS_START_HOUR = 9
BUSINESS_END_HOUR = 18
MAX_SUGGESTIONS = 5

st.title("📝 利用申請")

servers = load_servers()
if not servers:
    st.error("サーバ設定が読み込めません。config/servers.yaml を確認してください。")
    st.stop()

server_options = {s["id"]: f"{s['name']} ({s['host']})" for s in servers}
server_ids = list(server_options.keys())

# ---- フォーム値の管理 ----
# 全てのフォーム入力は session_state にキー管理し、再描画をまたいでも値を保持
FORM_DEFAULTS = {
    "form_user_name": "",
    "form_server_id": server_ids[0],
    "form_purpose": "",
    "form_use_gpu": False,
    "form_start_date": date.today(),
    "form_start_time": time(9, 0),
    "form_end_date": date.today(),
    "form_end_time": time(18, 0),
}


def _reset_form() -> None:
    for k, v in FORM_DEFAULTS.items():
        st.session_state[k] = v


for k, v in FORM_DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

if "edit_id" not in st.session_state:
    st.session_state.edit_id = None

# ---- ワンショットトリガー（リセット／編集ロード／候補反映） ----
# ウィジェット生成後は session_state を変更できないため、フォームのリセットは
# フラグを立てて次回の再描画（ウィジェット生成前のここ）で実行する
if st.session_state.pop("trigger_form_reset", False):
    _reset_form()

if st.session_state.pop("trigger_edit_load", False):
    existing = get_reservation(st.session_state.edit_id)
    if existing:
        s_dt = datetime.fromisoformat(existing["start_at"])
        e_dt = datetime.fromisoformat(existing["end_at"])
        st.session_state.form_user_name = existing["user_name"]
        st.session_state.form_server_id = existing["server_id"]
        st.session_state.form_purpose = existing["purpose"]
        st.session_state.form_use_gpu = bool(existing["use_gpu"])
        st.session_state.form_start_date = s_dt.date()
        st.session_state.form_start_time = s_dt.time().replace(second=0, microsecond=0)
        st.session_state.form_end_date = e_dt.date()
        st.session_state.form_end_time = e_dt.time().replace(second=0, microsecond=0)
    else:
        st.session_state.edit_id = None

prefill = st.session_state.pop("trigger_prefill", None)
if prefill:
    p_start = datetime.fromisoformat(prefill["start_at"])
    p_end = datetime.fromisoformat(prefill["end_at"])
    if prefill.get("server_id"):
        st.session_state.form_server_id = prefill["server_id"]
    st.session_state.form_start_date = p_start.date()
    st.session_state.form_start_time = p_start.time().replace(second=0, microsecond=0)
    st.session_state.form_end_date = p_end.date()
    st.session_state.form_end_time = p_end.time().replace(second=0, microsecond=0)
    matched = next(
        (s for s in servers if s["id"] == prefill.get("server_id")), None
    )
    server_label = f"[{matched['name']}] " if matched else ""
    st.toast(
        f"⏱ 提案を反映: {server_label}"
        f"{p_start.strftime('%H:%M')} 〜 {p_end.strftime('%H:%M')}"
    )

# servers.yaml の変更で過去の server_id が消えていた場合に備える
if st.session_state.form_server_id not in server_ids:
    st.session_state.form_server_id = server_ids[0]

if st.session_state.edit_id is not None:
    st.info(f"申請ID #{st.session_state.edit_id} を編集中です")

# ---- フォーム ----
with st.form("reservation_form", clear_on_submit=False):
    col_left, col_right = st.columns(2)
    with col_left:
        st.text_input("申請者名", key="form_user_name")
        st.selectbox(
            "使用サーバ",
            options=server_ids,
            format_func=lambda x: server_options[x],
            key="form_server_id",
        )
        st.checkbox(
            "GPU(VRAM)を使用する",
            key="form_use_gpu",
            help="チェックすると、同一サーバ・同一時間帯のGPU予約と重複できなくなります",
        )

    with col_right:
        st.markdown("**使用期間（時間単位）**")
        date_col, time_col = st.columns(2)
        with date_col:
            st.date_input("開始日", key="form_start_date")
            st.date_input("終了日", key="form_end_date")
        with time_col:
            st.time_input(
                "開始時刻",
                key="form_start_time",
                step=timedelta(hours=1),
            )
            st.time_input(
                "終了時刻",
                key="form_end_time",
                step=timedelta(hours=1),
            )

    st.text_area("用途", key="form_purpose", height=80)

    st.caption(
        f"💡 「空き時間を探す」を押すと、入力中の使用期間から所要時間を計算し、"
        f"**全サーバを横断して** 業務時間 "
        f"{BUSINESS_START_HOUR:02d}:00〜{BUSINESS_END_HOUR:02d}:00 内の空き候補を"
        f"最大 {MAX_SUGGESTIONS} 件提示します（サーバは候補側で選ばれます）。"
    )

    btn_col1, btn_col2, btn_col3 = st.columns([2, 2, 1])
    submitted = btn_col1.form_submit_button(
        "登録 / 更新", type="primary", use_container_width=True
    )
    suggested = btn_col2.form_submit_button(
        "🔍 空き時間を探す", use_container_width=True
    )
    cancelled = btn_col3.form_submit_button(
        "リセット", use_container_width=True
    )

# ---- フォーム現在値の取り出し ----
cur_start_dt = datetime.combine(
    st.session_state.form_start_date, st.session_state.form_start_time
)
cur_end_dt = datetime.combine(
    st.session_state.form_end_date, st.session_state.form_end_time
)
cur_start_at = cur_start_dt.isoformat(timespec="seconds")
cur_end_at = cur_end_dt.isoformat(timespec="seconds")

# ---- 「空き時間を探す」処理 ----
if suggested:
    err = None
    duration_hours = 0
    if cur_end_dt <= cur_start_dt:
        err = "終了日時は開始日時より後にしてください"
    elif cur_start_dt.date() != cur_end_dt.date():
        err = "提案機能は同一日内の予約のみ対応しています（開始日と終了日を揃えてください）"
    else:
        seconds = (cur_end_dt - cur_start_dt).total_seconds()
        duration_hours = int(seconds // 3600)
        biz_window = BUSINESS_END_HOUR - BUSINESS_START_HOUR
        if duration_hours <= 0:
            err = "所要時間が1時間未満です"
        elif duration_hours > biz_window:
            err = f"所要時間が業務時間長（{biz_window}時間）を超えています"

    if err:
        st.session_state.sg_results = {"error": err}
    else:
        # 全サーバを横断して候補を収集
        all_candidates = []
        for srv in servers:
            slots = find_available_slots(
                server_id=srv["id"],
                target_date=cur_start_dt.date(),
                duration_hours=duration_hours,
                use_gpu=st.session_state.form_use_gpu,
                business_start_hour=BUSINESS_START_HOUR,
                business_end_hour=BUSINESS_END_HOUR,
                max_results=MAX_SUGGESTIONS,
            )
            for s_iso, e_iso in slots:
                all_candidates.append({
                    "server_id": srv["id"],
                    "server_name": srv["name"],
                    "start_at": s_iso,
                    "end_at": e_iso,
                })
        # 開始時刻順、同時刻はサーバID順で安定化
        all_candidates.sort(key=lambda c: (c["start_at"], c["server_id"]))
        st.session_state.sg_results = {
            "candidates": all_candidates[:MAX_SUGGESTIONS],
            "duration": duration_hours,
            "use_gpu": st.session_state.form_use_gpu,
            "past": cur_start_dt.date() < date.today(),
        }

# ---- 提案結果の表示 ----
res = st.session_state.get("sg_results")
if res:
    with st.container(border=True):
        st.markdown("### 💡 空き時間候補")
        if "error" in res:
            st.error(res["error"])
        else:
            if res["past"]:
                st.warning("過去の日付が指定されています（参考表示）")
            if not res["candidates"]:
                st.info(
                    f"業務時間 {BUSINESS_START_HOUR:02d}:00〜{BUSINESS_END_HOUR:02d}:00 "
                    "内に空き候補が見つかりませんでした（全サーバを確認）"
                )
            else:
                st.success(f"{len(res['candidates'])} 件の候補があります")
                for i, c in enumerate(res["candidates"]):
                    s_dt = datetime.fromisoformat(c["start_at"])
                    e_dt = datetime.fromisoformat(c["end_at"])
                    gpu_badge = "🟢 GPU" if res["use_gpu"] else "⚪ CPU"
                    pick_col, btn_col = st.columns([4, 1])
                    with pick_col:
                        st.markdown(
                            f"{gpu_badge} **[{c['server_name']}]** "
                            f"**{s_dt.strftime('%Y-%m-%d %H:%M')} 〜 "
                            f"{e_dt.strftime('%H:%M')}** ({res['duration']}時間)"
                        )
                    with btn_col:
                        if st.button(
                            "この時間で反映",
                            key=f"sg_pick_{i}",
                            use_container_width=True,
                        ):
                            st.session_state.trigger_prefill = {
                                "server_id": c["server_id"],
                                "start_at": c["start_at"],
                                "end_at": c["end_at"],
                            }
                            st.session_state.pop("sg_results", None)
                            st.rerun()

# ---- リセット ----
if cancelled:
    st.session_state.edit_id = None
    st.session_state.pop("sg_results", None)
    st.session_state.trigger_form_reset = True
    st.rerun()

# ---- 登録/更新 ----
if submitted:
    user_name = st.session_state.form_user_name
    server_id = st.session_state.form_server_id
    purpose = st.session_state.form_purpose
    use_gpu = st.session_state.form_use_gpu

    errors = []
    if not user_name.strip():
        errors.append("申請者名を入力してください")
    if not purpose.strip():
        errors.append("用途を入力してください")
    if cur_end_at <= cur_start_at:
        errors.append("終了日時は開始日時より後にしてください")
    if use_gpu and has_gpu_conflict(
        server_id, cur_start_at, cur_end_at, exclude_id=st.session_state.edit_id
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
            cur_start_at,
            cur_end_at,
        )
        st.success(f"申請ID #{st.session_state.edit_id} を更新しました")
        st.session_state.edit_id = None
        st.session_state.pop("sg_results", None)
        st.session_state.trigger_form_reset = True
        st.rerun()
    else:
        new_id = add_reservation(
            user_name.strip(), server_id, purpose.strip(),
            use_gpu, cur_start_at, cur_end_at,
        )
        st.success(f"申請ID #{new_id} を登録しました")
        st.session_state.pop("sg_results", None)
        st.session_state.trigger_form_reset = True
        st.rerun()

# ---- 既存申請の一覧 ----
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
                    st.session_state.trigger_edit_load = True
                    st.session_state.pop("sg_results", None)
                    st.rerun()
            with cols[2]:
                if st.button(
                    "🗑️ 削除", key=f"del_{r['id']}", use_container_width=True
                ):
                    delete_reservation(r["id"])
                    st.toast(f"申請ID #{r['id']} を削除しました")
                    st.rerun()
