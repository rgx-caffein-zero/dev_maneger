import paramiko

NVIDIA_SMI_GPU = (
    "nvidia-smi "
    "--query-gpu=index,name,utilization.gpu,memory.used,memory.total "
    "--format=csv,noheader,nounits"
)

NVIDIA_SMI_PROC = (
    "nvidia-smi "
    "--query-compute-apps=pid,process_name,used_memory "
    "--format=csv,noheader,nounits"
)


def _exec(host: str, user: str, port: int, command: str, timeout: int = 10):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host,
            username=user,
            port=port,
            timeout=timeout,
            allow_agent=True,
            look_for_keys=True,
        )
        _, stdout, stderr = client.exec_command(command, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        return out, err
    finally:
        client.close()


def _parse_int(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def fetch_gpu_status(server: dict) -> dict:
    host = server["host"]
    user = server["ssh_user"]
    port = int(server.get("ssh_port", 22))

    try:
        out, err = _exec(host, user, port, NVIDIA_SMI_GPU)
    except Exception as e:
        return {"ok": False, "error": f"接続失敗: {e}", "gpus": [], "processes": []}

    if err and not out:
        return {"ok": False, "error": err, "gpus": [], "processes": []}

    gpus = []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 5:
            gpus.append({
                "index": parts[0],
                "name": parts[1],
                "util_percent": _parse_int(parts[2]),
                "memory_used_mib": _parse_int(parts[3]),
                "memory_total_mib": _parse_int(parts[4]),
            })

    processes = []
    try:
        proc_out, _ = _exec(host, user, port, NVIDIA_SMI_PROC)
        for line in proc_out.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                processes.append({
                    "pid": parts[0],
                    "name": parts[1],
                    "memory_mib": _parse_int(parts[2]),
                })
    except Exception:
        # プロセス一覧の取得失敗は致命ではないので握りつぶしてGPU情報のみ返す
        pass

    return {"ok": True, "error": "", "gpus": gpus, "processes": processes}
