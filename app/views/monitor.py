import pandas as pd
import streamlit as st

from config_loader import load_servers
from ssh_client import fetch_gpu_status

st.title("📊 サーバ監視（リアルタイム）")

servers = load_servers()
if not servers:
    st.error("サーバ設定が読み込めません。config/servers.yaml を確認してください。")
    st.stop()

col1, col2 = st.columns([1, 4])
with col1:
    auto_refresh = st.checkbox("30秒ごとに自動更新", value=False)
with col2:
    if st.button("🔄 今すぐ更新", type="primary"):
        st.rerun()

if auto_refresh:
    try:
        from streamlit_autorefresh import st_autorefresh

        st_autorefresh(interval=30_000, key="server_monitor_autorefresh")
    except ImportError:
        st.warning(
            "streamlit-autorefresh がインストールされていないため自動更新は無効です"
        )

for server in servers:
    with st.container(border=True):
        st.subheader(f"{server['name']}  `{server['host']}`")

        with st.spinner(f"{server['name']} の状態を取得中..."):
            status = fetch_gpu_status(server)

        if not status["ok"]:
            st.error(f"取得失敗: {status['error']}")
            continue

        if not status["gpus"]:
            st.warning(
                "GPU情報が取得できませんでした "
                "（GPU未搭載 / nvidia-smi 未導入 / 権限不足 のいずれか）"
            )
            continue

        for gpu in status["gpus"]:
            # utilization.gpu は「演算利用率」。VRAMを占有していても計算してなければ0%になる点に注意
            util = gpu["util_percent"]
            used = gpu["memory_used_mib"]
            total = gpu["memory_total_mib"]
            mem_pct = (used / total * 100) if total else 0.0

            st.markdown(f"**GPU{gpu['index']}: {gpu['name']}**")
            m_col1, m_col2 = st.columns(2)
            with m_col1:
                st.metric(
                    label="GPU演算利用率",
                    value=f"{util}%",
                    help="nvidia-smi の utilization.gpu。計算中かどうかの指標です。",
                )
            with m_col2:
                st.metric(
                    label="VRAM使用率",
                    value=f"{mem_pct:.1f}%",
                    help=f"{used} / {total} MiB",
                )
            st.progress(
                min(mem_pct / 100, 1.0),
                text=f"VRAM: {used} / {total} MiB",
            )

        if status["processes"]:
            with st.expander(
                f"GPUプロセス一覧 ({len(status['processes'])}件)"
            ):
                proc_df = pd.DataFrame(status["processes"])
                proc_df.columns = ["PID", "プロセス名", "VRAM(MiB)"]
                st.dataframe(
                    proc_df, use_container_width=True, hide_index=True
                )
        else:
            st.caption("現在GPUを使用しているプロセスはありません")
