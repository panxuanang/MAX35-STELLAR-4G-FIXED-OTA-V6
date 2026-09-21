#!/usr/bin/env python3
"""Attach the STELLAR MAX35 UI to SpotPear's *vendor 4G firmware*.

This script intentionally does NOT transplant the MAX35 hardware into current
78/xiaozhi.  SpotPear's source remains the firmware base so its ML307 modem,
audio codec/microphone wiring, board power logic, protocol stack and application
logic stay intact.  We only:
  1. identify the real MAX35 + ML307 board option;
  2. copy the product UI sources;
  3. register those UI sources in main/CMakeLists.txt; and
  4. replace the LCD display object/base with StellarMax35Display.

If a 4G/ML307 board cannot be identified unambiguously, fail closed instead of
silently producing a Wi-Fi firmware.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

CODE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp"}
UI_SOURCES = [
    "display/stellar_max35/stellar_max35_display.cc",
    "display/stellar_max35/ui_home.cc",
    "display/stellar_max35/ui_chat.cc",
    "display/stellar_max35/ui_character.c",
]
PROTECTED_HINTS = (
    "application.cc",
    "audio_service.cc",
    "websocket_protocol.cc",
    "mqtt_protocol.cc",
    "protocol.cc",
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


@dataclass
class ConfigBlock:
    symbol: str
    text: str
    path: Path
    start: int
    kind: str
    choice_id: str | None
    if_conditions: tuple[str, ...]


def iter_config_blocks(path: Path):
    """Parse enough Kconfig structure to distinguish choice siblings from parents.

    SpotPear may expose MAX35 as a top-level parent and ML307 as a nested option.
    Treating every nearby SpotPear symbol as a competing board choice can
    accidentally disable that required parent, so we retain choice/if context.
    """
    text = read(path)
    lines = text.splitlines(keepends=True)
    configs: list[tuple[int, str, str, str | None, tuple[str, ...]]] = []
    offset = 0
    choice_stack: list[str] = []
    if_stack: list[str] = []
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        m_choice = re.match(r"^choice(?:\s+([A-Za-z0-9_]+))?\s*$", stripped)
        if m_choice:
            name = m_choice.group(1) or "anonymous"
            choice_stack.append(f"{path.as_posix()}:{lineno}:{name}")
            offset += len(line)
            continue
        if re.match(r"^endchoice\b", stripped):
            if choice_stack:
                choice_stack.pop()
            offset += len(line)
            continue
        m_if = re.match(r"^if\s+(.+?)\s*$", stripped)
        if m_if:
            if_stack.append(m_if.group(1))
            offset += len(line)
            continue
        if re.match(r"^endif\b", stripped):
            if if_stack:
                if_stack.pop()
            offset += len(line)
            continue
        m_cfg = re.match(r"^(menuconfig|config)\s+([A-Za-z0-9_]+)\s*$", stripped)
        if m_cfg:
            configs.append((
                offset,
                m_cfg.group(2),
                m_cfg.group(1),
                choice_stack[-1] if choice_stack else None,
                tuple(if_stack),
            ))
        offset += len(line)

    for i, (pos, symbol, kind, choice_id, if_conditions) in enumerate(configs):
        end = configs[i + 1][0] if i + 1 < len(configs) else len(text)
        yield ConfigBlock(symbol, text[pos:end], path, pos, kind, choice_id, if_conditions)


def boardish(blob: str) -> bool:
    b = blob.lower()
    return (
        ("spotpear" in b or "spot pear" in b or "sp-esp32" in b)
        and any(t in b for t in ("3.5", "3_5", "3-5", "max35", "lcd-cam", "lcd_cam"))
    )


def dependency_board_symbols(block: ConfigBlock, all_blocks: list[ConfigBlock]) -> list[str]:
    """Return required BOARD_* parents from `if` / `depends on` context."""
    by_symbol = {b.symbol: b for b in all_blocks}
    exprs = list(block.if_conditions)
    exprs.extend(re.findall(r"(?m)^\s*depends\s+on\s+(.+?)\s*$", block.text))
    out: list[str] = []
    for expr in exprs:
        for sym in re.findall(r"\b[A-Z][A-Z0-9_]+\b", expr):
            if sym == block.symbol or sym.startswith("IDF_TARGET_"):
                continue
            if not (sym.startswith("BOARD_") or sym.startswith("BOARD_TYPE_")):
                continue
            parent = by_symbol.get(sym)
            if parent is None:
                continue
            context = f"{parent.symbol}\n{parent.text}\n{parent.path.as_posix()}"
            # A dependency with no SpotPear wording may still be a generic
            # board parent; BOARD_TYPE_* is strong enough evidence here.
            if boardish(context) or "SPOTPEAR" in sym or "3_5" in sym or "MAX35" in sym:
                if sym not in out:
                    out.append(sym)
    return out


def find_4g_symbol(root: Path) -> tuple[ConfigBlock, list[ConfigBlock], list[str]]:
    all_blocks: list[ConfigBlock] = []
    for p in sorted(root.rglob("Kconfig*")):
        if not p.is_file() or any(part in {"build", ".git", "managed_components"} for part in p.parts):
            continue
        all_blocks.extend(iter_config_blocks(p))

    candidates: list[tuple[int, ConfigBlock]] = []
    family: list[ConfigBlock] = []
    for block in all_blocks:
        blob = f"{block.symbol}\n{block.text}\n{block.path.as_posix()}".lower()
        if not boardish(blob):
            continue
        family.append(block)
        score = 0
        if "ml307" in blob:
            score += 100
        if "4g" in blob or "cat.1" in blob or "cat1" in blob:
            score += 80
        if "spotpear" in blob or "spot pear" in blob:
            score += 25
        if "3.5" in blob or "3_5" in blob or "3-5" in blob or "max35" in blob:
            score += 25
        if "lcd" in blob:
            score += 5
        if score >= 120:
            candidates.append((score, block))

    if not candidates:
        # Some vendor trees keep the parent SpotPear text in an outer menu/if
        # and the child config prompt is simply "ML307". In that case require
        # ML307/4G in the child plus MAX35 evidence in the same Kconfig file.
        for block in all_blocks:
            blob = f"{block.symbol}\n{block.text}".lower()
            if "ml307" not in blob and "4g" not in blob:
                continue
            file_text = read(block.path).lower()
            if boardish(file_text):
                score = 100 + (40 if "ml307" in blob else 0) + (20 if "4g" in blob else 0)
                candidates.append((score, block))

    if not candidates:
        seen = "\n".join(f"  - {b.symbol}: {b.path.relative_to(root)}" for b in family[:20])
        raise SystemExit(
            "FATAL: Could not find SpotPear MAX35 ML307/4G Kconfig option.\n"
            "Refusing to fall back to Wi-Fi. Nearby board options:\n" + (seen or "  (none)")
        )

    candidates.sort(key=lambda x: (-x[0], len(str(x[1].path)), x[1].symbol))
    top_score = candidates[0][0]
    tied = [b for s, b in candidates if s == top_score]
    if len({b.symbol for b in tied}) > 1:
        raise SystemExit(
            "FATAL: Ambiguous MAX35 4G board options: "
            + ", ".join(f"{b.symbol} ({b.path.relative_to(root)})" for b in tied)
        )
    selected = candidates[0][1]

    # Only configs in the *same Kconfig choice* are true alternatives. Do not
    # disable a SpotPear/MAX35 parent menuconfig that the ML307 child depends on.
    siblings: list[ConfigBlock] = []
    if selected.choice_id:
        siblings = [
            b for b in all_blocks
            if b.symbol != selected.symbol and b.choice_id == selected.choice_id
        ]

    parents = dependency_board_symbols(selected, all_blocks)
    return selected, siblings, parents

def source_files(board_root: Path):
    for p in board_root.rglob("*"):
        if p.is_file() and p.suffix.lower() in CODE_SUFFIXES:
            yield p


def source_blob(path: Path) -> str:
    try:
        return read(path)
    except OSError:
        return ""


def find_4g_board_files(root: Path, symbol: str) -> list[Path]:
    boards = root / "main" / "boards"
    if not boards.is_dir():
        raise SystemExit(f"FATAL: vendor source has no {boards.relative_to(root)} directory")

    ranked: list[tuple[int, Path]] = []
    for p in source_files(boards):
        text = source_blob(p)
        low = (p.as_posix() + "\n" + text).lower()
        if "spilcddisplay" not in low and "stellarmax35display" not in low:
            continue
        score = 0
        if symbol in text or f"CONFIG_{symbol}" in text:
            score += 200
        if "ml307" in low:
            score += 110
        if "4g" in low:
            score += 50
        if any(t in low for t in ("max35", "3.5", "3_5", "3-5", "sp-esp32-s3-lcd")):
            score += 60
        if "spotpear" in low:
            score += 25
        if score >= 85:
            ranked.append((score, p))

    if not ranked:
        # Shared Wi-Fi/4G board source can contain no literal ML307 in the LCD
        # file. Find the MAX35 display source, but only after the Kconfig 4G
        # option was positively identified above.
        for p in source_files(boards):
            text = source_blob(p)
            low = (p.as_posix() + "\n" + text).lower()
            if "spilcddisplay" not in low:
                continue
            if any(t in low for t in ("max35", "3.5", "3_5", "3-5", "sp-esp32-s3-lcd")):
                ranked.append((50, p))

    if not ranked:
        raise SystemExit("FATAL: 4G board option exists, but no MAX35 SpiLcdDisplay source was found")

    ranked.sort(key=lambda x: (-x[0], len(str(x[1]))))
    best = ranked[0][0]
    # Patch all files in the best board directory when they contain a display
    # constructor/base. This covers split .h/.cc implementations safely.
    best_dir = ranked[0][1].parent
    files = []
    for p in source_files(best_dir):
        t = source_blob(p)
        if "SpiLcdDisplay" in t or "StellarMax35Display" in t:
            files.append(p)
    return sorted(set(files))


def assert_vendor_4g_implementation(root: Path, selected_symbol: str) -> None:
    boards = root / "main" / "boards"
    blobs = []
    for p in source_files(boards):
        lowpath = p.as_posix().lower()
        if any(t in lowpath for t in ("ml307", "4g", "max35", "3.5", "3_5")):
            blobs.append(source_blob(p))
    joined = "\n".join(blobs)
    all_board_text = joined.lower()
    markers = ("ml307board", "ml307", "modem", "at_modem", "atmodem")
    if not any(m in all_board_text for m in markers):
        # The modem class may live in a common component while the selected
        # symbol is only in Kconfig/CMake. Check main as a final confirmation.
        main_text = ""
        for p in (root / "main").rglob("*"):
            if p.is_file() and p.suffix.lower() in CODE_SUFFIXES:
                t = source_blob(p)
                if selected_symbol in t or "ml307" in t.lower():
                    main_text += "\n" + t
        if "ml307" not in main_text.lower():
            raise SystemExit("FATAL: selected board says 4G, but no ML307 implementation is present in vendor source")


def copy_ui(product: Path, root: Path) -> list[Path]:
    src = product / "overlay" / "main" / "display" / "stellar_max35"
    if not src.is_dir():
        raise SystemExit(f"missing UI overlay: {src}")
    dst = root / "main" / "display" / "stellar_max35"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    copied = [p for p in dst.rglob("*") if p.is_file()]
    print(f"[ui] copied {len(copied)} UI files -> {dst.relative_to(root)}")
    return copied


def patch_main_cmake(root: Path) -> Path:
    p = root / "main" / "CMakeLists.txt"
    if not p.exists():
        raise SystemExit("FATAL: main/CMakeLists.txt not found")
    text = read(p)
    missing = [s for s in UI_SOURCES if s not in text]
    if not missing:
        print("[cmake] STELLAR UI sources already registered")
        return p

    # xiaozhi vendor trees use a SOURCES list and later pass ${SOURCES} to
    # idf_component_register. Add a separate list(APPEND) immediately before
    # the component registration so we do not rewrite the vendor's source list.
    reg = re.search(r"(?m)^\s*idf_component_register\s*\(", text)
    if not reg:
        raise SystemExit("FATAL: cannot find idf_component_register() in main/CMakeLists.txt")
    pre = text[:reg.start()]
    reg_tail = text[reg.start():]
    if "${SOURCES}" not in reg_tail[:2500]:
        # Fallback for direct SRCS lists: insert entries right after SRCS token.
        sr = re.search(r"idf_component_register\s*\(\s*SRCS\s*", text, re.S)
        if not sr:
            raise SystemExit("FATAL: main CMake does not register ${SOURCES} and has no direct SRCS list")
        indent = " " * 12
        addition = "\n" + "\n".join(f'{indent}"{s}"' for s in missing) + "\n"
        text = text[:sr.end()] + addition + text[sr.end():]
    else:
        block = "\n# STELLAR MAX35 UI-only overlay (hardware/network/audio stay vendor-owned)\n"
        block += "list(APPEND SOURCES\n"
        block += "".join(f'    "{s}"\n' for s in missing)
        block += ")\n\n"
        text = pre + block + reg_tail
    write(p, text)
    print("[cmake] registered UI-only sources")
    return p


def patch_display_file(p: Path) -> bool:
    text = read(p)
    original = text
    include = '#include "display/stellar_max35/stellar_max35_display.h"'
    if "SpiLcdDisplay" not in text and "StellarMax35Display" not in text:
        return False

    # Only include the overlay in a file that actually constructs/derives the
    # display. This does not touch modem/audio/application logic.
    if include not in text:
        lcd_inc = re.search(r'(?m)^\s*#\s*include\s*[<"]display/lcd_display\.h[>"]\s*$', text)
        if lcd_inc:
            text = text[:lcd_inc.end()] + "\n" + include + text[lcd_inc.end():]
        else:
            text = include + "\n" + text

    changed = False
    text, n = re.subn(r"\bnew\s+SpiLcdDisplay\s*\(", "new StellarMax35Display(", text)
    if n:
        changed = True

    # If SpotPear wraps SpiLcdDisplay in a board-specific display subclass,
    # preserve that subclass and only swap its display base.
    class_pat = re.compile(
        r"class\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*public\s+SpiLcdDisplay\b"
    )
    classes = class_pat.findall(text)
    for cls in classes:
        text = re.sub(
            rf"class\s+{re.escape(cls)}\s*:\s*public\s+SpiLcdDisplay\b",
            f"class {cls} : public StellarMax35Display",
            text,
            count=1,
        )
        text = text.replace(
            "using SpiLcdDisplay::SpiLcdDisplay;",
            "using StellarMax35Display::StellarMax35Display;",
        )
        # Constructor initializer for custom display classes.
        text = re.sub(r":\s*SpiLcdDisplay\s*\(", ": StellarMax35Display(", text)
        changed = True

    if changed and text != original:
        write(p, text)
        print(f"[board] attached STELLAR UI in {p}")
        return True
    return False


def make_manifest(root: Path, selected: ConfigBlock, siblings: list[ConfigBlock], parents: list[str], patched: list[Path]) -> None:
    (root / ".stellar_max35_4g_symbol").write_text(selected.symbol + "\n", encoding="utf-8")
    (root / ".stellar_board_choice_symbols").write_text(
        "\n".join(b.symbol for b in siblings) + ("\n" if siblings else ""), encoding="utf-8"
    )
    (root / ".stellar_patched_board_files").write_text(
        "\n".join(str(p.relative_to(root)) for p in patched) + "\n", encoding="utf-8"
    )
    info = {
        "selected_4g_symbol": selected.symbol,
        "selected_kconfig": str(selected.path.relative_to(root)),
        "disabled_board_siblings": [b.symbol for b in siblings],
        "required_board_parents": parents,
        "patched_board_files": [str(p.relative_to(root)) for p in patched],
        "policy": "vendor-4g-base-ui-only",
    }
    (root / ".stellar_patch_manifest.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vendor", required=True, type=Path, help="SpotPear xiaozhi source root")
    ap.add_argument("--product", required=True, type=Path, help="this UI overlay repository root")
    args = ap.parse_args()
    root = args.vendor.resolve()
    product = args.product.resolve()

    if not (root / "main" / "CMakeLists.txt").exists():
        raise SystemExit(f"not a xiaozhi source root: {root}")

    selected, siblings, parents = find_4g_symbol(root)
    print(f"[board] selected 4G Kconfig: CONFIG_{selected.symbol}=y")
    print(f"[board] source: {selected.path.relative_to(root)}")
    if parents:
        print("[board] required parent config(s): " + ", ".join("CONFIG_" + p for p in parents))
    assert_vendor_4g_implementation(root, selected.symbol)

    board_files = find_4g_board_files(root, selected.symbol)
    print("[board] MAX35 display candidates:")
    for p in board_files:
        print("  -", p.relative_to(root))

    copy_ui(product, root)
    patch_main_cmake(root)

    patched = [p for p in board_files if patch_display_file(p)]
    if not patched:
        raise SystemExit(
            "FATAL: found MAX35 4G board, but did not replace any SpiLcdDisplay construction/base. "
            "Refusing to build an unverified firmware."
        )

    # Guard against accidental architectural regression.
    rels = [str(p.relative_to(root)).replace("\\", "/") for p in patched]
    for rel in rels:
        low = rel.lower()
        if any(h in low for h in PROTECTED_HINTS):
            raise SystemExit(f"FATAL: UI patch touched protected core file: {rel}")

    make_manifest(root, selected, siblings, parents, patched)
    print("[done] vendor 4G firmware retained; STELLAR UI attached only to display layer")


if __name__ == "__main__":
    main()
