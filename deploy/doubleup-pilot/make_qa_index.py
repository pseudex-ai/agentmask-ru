"""One page that opens every QA screenshot on this machine, with a way back.

The desktop folder is the deliverable the owner actually clicks; the harness
writes into the repo's .state tree. This script rebuilds the single entry page
from whatever is in the folder, so a re-run of one tester never leaves the index
describing the previous run.

    python3 make_qa_index.py [--root ~/Desktop/pseudex-qa-screenshots]
"""
from __future__ import annotations

import argparse
import html
import shutil
from pathlib import Path

DEFAULT_ROOT = Path.home() / "Desktop" / "pseudex-qa-screenshots"
SOURCE = Path(__file__).resolve().parent / ".state" / "qa" / "dialogues"

PILOT = [f"pilot-tester-{index}" for index in range(1, 6)]
NAMES = {"pilot-tester-1": "Тестировщик 1", "pilot-tester-2": "Тестировщик 2",
         "pilot-tester-3": "Тестировщик 3", "pilot-tester-4": "Тестировщик 4",
         "pilot-tester-5": "Тестировщик 5"}

STYLE = """
body{background:#0d0f12;color:#e6e6e6;font:14px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:0 28px 48px}
nav{position:sticky;top:0;z-index:5;background:#0d0f12f2;border-bottom:1px solid #232830;padding:10px 0;margin:0 -28px 18px 28px}
nav a{display:inline-block;margin-right:14px;font-size:13px}
h1{font-size:22px;margin:18px 0 4px}h2{font-size:17px;margin:34px 0 6px;color:#7dd3a0}
h3{font-size:14px;margin:18px 0 4px;color:#cfd6dd}
p.note{color:#9aa0a6;margin:4px 0 10px;font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}
figure{margin:0;background:#15181d;border:1px solid #232830;border-radius:8px;overflow:hidden}
figure img{width:100%;display:block;background:#000}
figcaption{padding:6px 8px;font-size:11px;color:#9aa0a6;word-break:break-all}
a{color:#7dd3a0}
a.back{font-size:12px}
code{background:#15181d;padding:1px 4px;border-radius:4px}
"""


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def shots(folder: Path) -> list[Path]:
    return sorted(path for path in folder.glob("*.png") if path.is_file())


def grid(folder: Path, base: Path) -> list[str]:
    parts = ["<div class='grid'>"]
    for image in shots(folder):
        relative = image.relative_to(base).as_posix()
        parts.append(
            f"<figure><a href='{esc(relative)}' target='_blank'>"
            f"<img loading='lazy' src='{esc(relative)}' alt='{esc(image.name)}'></a>"
            f"<figcaption>{esc(image.name)}</figcaption></figure>")
    parts.append("</div>")
    return parts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    # The harness output is the truth; the desktop copy is derived from it.
    for tester in PILOT:
        source = SOURCE / tester
        if not source.is_dir():
            continue
        target = root / "pilot" / tester.replace("pilot-", "")
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)

    sections: list[tuple[str, str, Path]] = []  # anchor, title, folder
    pilot_root = root / "pilot"
    for tester in sorted(pilot_root.iterdir()) if pilot_root.is_dir() else []:
        if tester.is_dir():
            key = f"pilot-{tester.name}"
            sections.append((f"qa-{esc(key)}", NAMES.get(key, tester.name), tester))
    for folder in sorted(path for path in root.iterdir()
                         if path.is_dir() and path.name != "pilot"):
        sections.append((f"qa-{esc(folder.name)}", folder.name, folder))
    agent_lab = root / "agent-lab"
    if agent_lab.is_dir():
        for folder in sorted(path for path in agent_lab.iterdir() if path.is_dir()):
            sections.append((f"qa-agent-{esc(folder.name)}", f"agent-lab / {folder.name}", folder))

    parts = [
        "<!doctype html><meta charset='utf-8'>",
        "<title>Pseudex · все прогоны</title>",
        f"<style>{STYLE}</style>",
        "<nav>", "<a href='#top'><b>наверх</b></a>",
    ]
    for anchor, title, _ in sections:
        parts.append(f"<a href='#{anchor}'>{esc(title)}</a>")
    parts.append("</nav><div id='top'></div>")
    parts.append("<h1>Pseudex · все прогоны и скриншоты</h1>")
    parts.append("<p class='note'>Клик по картинке открывает полный PNG. В отчётах тестировщиков "
                 "каждый шаг содержит два вида доказательства: снимок экрана и таблицу "
                 "«что модель увидела → настоящее значение», снятую наведением на подсвеченный фрагмент. "
                 "Навигация — в полосе сверху; из любого отчёта есть ссылка «← ко всем прогонам».</p>")

    parts.append("<h2 id='qa-pilot'>1. Пять ручных тестировщиков (живой DeepSeek)</h2>")
    for anchor, title, folder in sections:
        if folder.parent.name != "pilot":
            continue
        report = folder / "report.html"
        count = len(shots(folder))
        parts.append(f"<h3 id='{anchor}'>{esc(title)} · {count} снимков</h3>")
        if report.is_file():
            relative = report.relative_to(root).as_posix()
            parts.append(f"<p class='note'><a href='{esc(relative)}' target='_blank'>полный отчёт "
                         f"{esc(title)} →</a></p>")
        parts.extend(grid(folder, root))

    parts.append("<h2 id='qa-other'>2. Остальные прогоны</h2>")
    for anchor, title, folder in sections:
        if folder.parent.name == "pilot":
            continue
        count = len(shots(folder))
        report = folder / "report.html"
        parts.append(f"<h3 id='{anchor}'>{esc(title)} · {count} снимков</h3>")
        if report.is_file():
            relative = report.relative_to(root).as_posix()
            parts.append(f"<p class='note'><a href='{esc(relative)}' target='_blank'>отчёт →</a></p>")
        parts.extend(grid(folder, root))

    (root / "index.html").write_text("".join(parts))
    print(f"index: {root / 'index.html'} · sections: {len(sections)}")


if __name__ == "__main__":
    main()
