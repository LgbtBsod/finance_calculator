"""scripts/launch.py — стартовый скрипт.

Батники (run.bat / run.sh) только создают/активируют venv и запускают этот
файл. Вся логика запуска здесь:

  1. обновить pip
  2. синхронизировать зависимости (pip install -r requirements.txt --upgrade)
  3. проверить обновления кода:
       - из git-клона  -> git fetch + git pull (с подтверждением, если не --yes)
       - иначе          -> updater.check_updates()
  4. запустить приложение (main.py)

Флаги:
  --skip-deps     не трогать зависимости
  --skip-update   не проверять обновления
  --yes           не спрашивать подтверждений (git pull автоматически)
  прочие          пробрасываются в main.py (например --port 9000, --no-update)
"""

from __future__ import annotations

import os
import runpy
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run(cmd: list[str], *, check: bool = False) -> int:
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=str(ROOT), check=check).returncode


def upgrade_pip() -> None:
    print("[1/4] Обновление pip...")
    _run([sys.executable, "-m", "pip", "install", "-q", "--upgrade", "pip"])


def sync_deps() -> None:
    print("[2/4] Синхронизация зависимостей (requirements.txt)...")
    req = ROOT / "requirements.txt"
    if not req.exists():
        print("  requirements.txt не найден — пропуск")
        return
    code = _run([sys.executable, "-m", "pip", "install", "-q", "--upgrade", "-r", str(req)])
    if code != 0:
        print("  [WARN] не все зависимости обновились — продолжаю")


def _git(*args: str) -> tuple[int, str]:
    r = subprocess.run(
        ["git", *args], cwd=str(ROOT), capture_output=True, text=True
    )
    return r.returncode, (r.stdout or "").strip()


def check_updates(assume_yes: bool) -> None:
    print("[3/4] Проверка обновлений...")
    if (ROOT / ".git").exists():
        _check_git(assume_yes)
    else:
        _check_release()


def _check_git(assume_yes: bool) -> None:
    if _git("rev-parse", "--is-inside-work-tree")[0] != 0:
        print("  не git-репозиторий — пропуск")
        return
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")[1] or "main"
    if _git("fetch", "--quiet", "origin", branch)[0] != 0:
        print("  [WARN] git fetch не удался (нет сети?) — пропуск")
        return
    local = _git("rev-parse", "HEAD")[1]
    remote = _git("rev-parse", f"origin/{branch}")[1]
    if not remote or local == remote:
        print(f"  установлена последняя версия ({local[:7]})")
        return
    ahead = _git("rev-list", "--count", f"HEAD..origin/{branch}")[1] or "?"
    print(f"  доступно обновление: +{ahead} коммит(ов) на origin/{branch}")
    _, log = _git("log", "--oneline", f"HEAD..origin/{branch}")
    for line in log.splitlines()[:10]:
        print(f"    - {line}")

    if _git("status", "--porcelain")[1]:
        print("  [WARN] есть незакоммиченные изменения — git pull пропущен")
        return

    if not assume_yes:
        try:
            ans = input("  Обновить сейчас? (y/N): ").strip().lower()
        except EOFError:
            ans = "n"
        if ans != "y":
            print("  обновление отложено")
            return

    print("  git pull...")
    if _git("pull", "--ff-only", "origin", branch)[0] == 0:
        print("  обновлено — зависимости пересинхронизирую")
        sync_deps()
    else:
        print("  [WARN] git pull не удался")


def _check_release() -> None:
    try:
        from updater import check_updates as _cu

        _cu(auto=False)
    except Exception as exc:  # noqa: BLE001
        print(f"  проверка обновлений недоступна: {exc}")


def start_app(passthrough: list[str]) -> None:
    print("[4/4] Запуск приложения...")
    print("=" * 50)
    sys.argv = [str(ROOT / "main.py"), *passthrough]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    runpy.run_path(str(ROOT / "main.py"), run_name="__main__")


def main() -> None:
    os.chdir(ROOT)
    args = sys.argv[1:]
    skip_deps = "--skip-deps" in args
    skip_update = "--skip-update" in args
    assume_yes = "--yes" in args
    passthrough = [a for a in args if a not in ("--skip-deps", "--skip-update", "--yes")]

    print("=" * 50)
    print("  Личный финансовый калькулятор — запуск")
    print("=" * 50)

    if not skip_deps:
        upgrade_pip()
        sync_deps()
    else:
        print("[1-2/4] Зависимости пропущены (--skip-deps)")

    if not skip_update:
        check_updates(assume_yes)
    else:
        print("[3/4] Проверка обновлений пропущена (--skip-update)")

    start_app(passthrough)


if __name__ == "__main__":
    main()
