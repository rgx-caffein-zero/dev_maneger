import streamlit as st

from db import init_db

st.set_page_config(
    page_title="開発サーバ管理ツール",
    page_icon="🖥️",
    layout="wide",
)

init_db()

pages = [
    st.Page("views/home.py", title="ホーム", icon="🏠", default=True),
    st.Page("views/apply.py", title="申請", icon="📝"),
    st.Page("views/schedule.py", title="予約状況", icon="📅"),
    st.Page("views/monitor.py", title="サーバ監視", icon="📊"),
]

pg = st.navigation(pages)
pg.run()
