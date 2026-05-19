# 開発サーバ利用管理ツール

開発用GPUサーバの **利用申請・予約状況・GPU監視** を1画面で行う、Streamlit製の内部向けツールです。

## 機能

- 📝 **利用申請**: サーバ・用途・GPU使用有無・期間（時間単位）の登録／編集／取消
- 📅 **予約状況**: ガントチャート風UIで全サーバの予約を一覧表示
- 📊 **サーバ監視**: SSH経由で `nvidia-smi` を実行し、VRAM・GPU利用率・プロセス一覧をリアルタイム表示
- ⚙️ サーバ台数は `config/servers.yaml` の編集だけで増減可能

## 重複ルール

| GPU使用 | 同一サーバ・同一時間帯の重複 |
|---------|------------------------------|
| あり    | 不可（先勝ち）               |
| なし    | 可                           |

## ディレクトリ構成

```
dev_maneger/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── config/
│   └── servers.yaml      # サーバ一覧（編集で台数増減）
├── data/
│   └── reservations.db   # SQLite（永続化ボリューム）
├── ssh/                  # SSH秘密鍵を配置（.gitignore対象）
└── app/
    ├── main.py            # st.navigation でルーティング
    ├── config_loader.py
    ├── db.py
    ├── ssh_client.py
    └── views/
        ├── home.py        # サイドバー: 🏠 ホーム
        ├── apply.py       # サイドバー: 📝 申請
        ├── schedule.py    # サイドバー: 📅 予約状況
        └── monitor.py     # サイドバー: 📊 サーバ監視
```

## セットアップ

### 1. サーバ設定

`config/servers.yaml` を環境に合わせて編集します。

```yaml
servers:
  - id: server-a
    name: 開発サーバA
    host: 192.168.1.10
    ssh_user: devuser
    ssh_port: 22
  # 増減は項目を足す／削るだけ
```

### 2. SSH鍵の配置

管理ホスト（このツールを動かすサーバ）から、他3台へ **パスワード無しでSSHログイン** できる状態にします。

```bash
# 例: 管理ホストで鍵を生成
ssh-keygen -t ed25519 -f ./ssh/id_ed25519 -N ""

# 各対象サーバへ公開鍵を配布
ssh-copy-id -i ./ssh/id_ed25519.pub devuser@192.168.1.11
ssh-copy-id -i ./ssh/id_ed25519.pub devuser@192.168.1.12
ssh-copy-id -i ./ssh/id_ed25519.pub devuser@192.168.1.13
```

`./ssh/` ディレクトリはコンテナの `/root/.ssh` に読み取り専用でマウントされます。

> ⚠️ `ssh/` 以下は `.gitignore` 対象です。秘密鍵をコミットしないでください。

### 3. 起動

```bash
docker compose up -d --build
```

ブラウザで `http://<管理ホストのIP>:8501` にアクセス。

### 4. 停止

```bash
docker compose down
```

## 設定変更の反映

| 変更内容              | 反映方法                                      |
|-----------------------|-----------------------------------------------|
| `config/servers.yaml` | ページ再読み込みで反映（マウント済みのため）  |
| ソースコード          | `docker compose up -d --build` で再ビルド     |

## データの保存先

- 申請データ: `./data/reservations.db`（SQLite）
- コンテナを削除しても消えません

## トラブルシュート

| 症状                                    | 確認ポイント                                                                 |
|-----------------------------------------|------------------------------------------------------------------------------|
| サーバ監視で「接続失敗」が出る          | 対象サーバへ `ssh devuser@<host>` でログインできるか／鍵のパーミッション      |
| 「GPU情報が取得できませんでした」       | 対象サーバで `nvidia-smi` が動くか／ドライバ導入済みか                         |
| 申請が消える                            | `data/` ボリュームがマウントされているか／コンテナを `-v` 付きで消していないか |

## 運用ルール

- 認証なし・性善説運用です。申請の改ざんを防ぐ仕組みはありません。
- `main`/`master` 等への直接コミット禁止、機密情報のコミット禁止（[CLAUDE.md](CLAUDE.md) 参照）。
