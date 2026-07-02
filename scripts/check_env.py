"""環境診斷：網頁跑不起來時，執行這支腳本看哪裡有問題。

用法：
    .venv\\Scripts\\python.exe scripts\\check_env.py
或（未建 venv 時）：
    python scripts\\check_env.py
"""
from __future__ import annotations

import importlib
import os
import socket
import sys

REQUIRED = ["streamlit", "pandas", "numpy", "scipy", "plotly", "openpyxl"]
PORT = 8501


def check_python() -> bool:
    v = sys.version_info
    ok = v >= (3, 10)
    print(f"[{'OK ' if ok else 'FAIL'}] Python 版本：{v.major}.{v.minor}.{v.micro}"
          + ("" if ok else "  → 需要 3.10 以上"))
    return ok


def check_packages() -> bool:
    all_ok = True
    for name in REQUIRED:
        try:
            mod = importlib.import_module(name)
            ver = getattr(mod, "__version__", "?")
            print(f"[OK ] 套件 {name}（{ver}）")
        except ImportError:
            all_ok = False
            print(f"[FAIL] 套件 {name} 未安裝  → 執行：pip install -r requirements.txt")
    return all_ok


def check_files() -> bool:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ok = True
    for rel in ["app.py", "requirements.txt"]:
        exists = os.path.exists(os.path.join(root, rel))
        print(f"[{'OK ' if exists else 'FAIL'}] 檔案 {rel}")
        ok = ok and exists
    sample = os.path.join(root, "sample_data", "conversation_sample.xlsx")
    if os.path.exists(sample):
        print("[OK ] 範例資料存在")
    else:
        print("[警告] 範例資料不存在  → 執行：python sample_data/generate_sample.py（不影響上傳自有資料）")
    return ok


def check_port() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        in_use = s.connect_ex(("127.0.0.1", PORT)) == 0
    if in_use:
        print(f"[提醒] 埠 {PORT} 已被占用（可能網頁已在執行，或上次沒關乾淨）")
        print(f"       → 換埠啟動：streamlit run app.py --server.port=8502")
    else:
        print(f"[OK ] 埠 {PORT} 可用")
    return True


def main() -> int:
    print("=" * 48)
    print(" 環境診斷 check_env")
    print("=" * 48)
    results = [check_python(), check_packages(), check_files()]
    check_port()
    print("-" * 48)
    if all(results):
        print("結論：環境正常，可執行  streamlit run app.py")
        return 0
    print("結論：有項目 FAIL，請依上面提示處理後再啟動。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
