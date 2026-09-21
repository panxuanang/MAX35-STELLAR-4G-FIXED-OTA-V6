#!/usr/bin/env python3
"""Select the detected SpotPear MAX35 ML307 board in an existing sdkconfig.

Only deterministic hardware-selection options are changed.  Audio, modem,
application and protocol settings are intentionally left at SpotPear defaults.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


def parse_known_symbols(root: Path) -> set[str]:
    known: set[str] = set()
    for p in root.rglob("Kconfig*"):
        if not p.is_file() or any(part in {"build", ".git"} for part in p.parts):
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        known.update(re.findall(r"(?m)^\s*(?:menuconfig|config)\s+([A-Za-z0-9_]+)\s*$", text))
    return known


def set_opt(lines: list[str], symbol: str, value: str) -> None:
    key = f"CONFIG_{symbol}"
    value_line = f"{key}={value}"
    pat_value = re.compile(rf"^{re.escape(key)}=.*$")
    pat_unset = re.compile(rf"^# {re.escape(key)} is not set$")
    for i, line in enumerate(lines):
        if pat_value.match(line) or pat_unset.match(line):
            lines[i] = value_line
            return
    lines.append(value_line)


def unset_opt(lines: list[str], symbol: str) -> None:
    key = f"CONFIG_{symbol}"
    unset_line = f"# {key} is not set"
    pat_value = re.compile(rf"^{re.escape(key)}=.*$")
    pat_unset = re.compile(rf"^# {re.escape(key)} is not set$")
    for i, line in enumerate(lines):
        if pat_value.match(line) or pat_unset.match(line):
            lines[i] = unset_line
            return
    lines.append(unset_line)


def set_if_known(lines: list[str], known: set[str], symbols: tuple[str, ...], value: str = "y") -> list[str]:
    changed = []
    for symbol in symbols:
        if symbol in known:
            set_opt(lines, symbol, value)
            changed.append(symbol)
    return changed


def unset_if_known(lines: list[str], known: set[str], symbols: tuple[str, ...]) -> list[str]:
    changed = []
    for symbol in symbols:
        if symbol in known:
            unset_opt(lines, symbol)
            changed.append(symbol)
    return changed


def set_string(lines: list[str], symbol: str, value: str) -> None:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    set_opt(lines, symbol, f'"{escaped}"')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    args = ap.parse_args()
    root = args.root.resolve()
    cfg = root / "sdkconfig"
    symfile = root / ".stellar_max35_4g_symbol"
    siblings_file = root / ".stellar_board_choice_symbols"
    manifest_file = root / ".stellar_patch_manifest.json"
    if not cfg.exists():
        raise SystemExit("sdkconfig does not exist; run idf.py set-target esp32s3 first")
    if not symfile.exists():
        raise SystemExit("4G selector manifest missing; run patch_vendor_4g_ui.py first")

    selected = symfile.read_text(encoding="utf-8").strip()
    siblings = [x.strip() for x in siblings_file.read_text(encoding="utf-8").splitlines() if x.strip()] if siblings_file.exists() else []
    parents = []
    if manifest_file.exists():
        import json
        parents = json.loads(manifest_file.read_text(encoding="utf-8")).get("required_board_parents", [])
    known = parse_known_symbols(root)
    lines = cfg.read_text(encoding="utf-8", errors="ignore").splitlines()

    for parent in parents:
        set_opt(lines, parent, "y")
        print(f"[config] CONFIG_{parent}=y (required parent)")
    set_opt(lines, selected, "y")
    for s in siblings:
        unset_opt(lines, s)
    print(f"[config] CONFIG_{selected}=y")
    if siblings:
        print(f"[config] disabled {len(siblings)} other SpotPear/MAX35 board option(s)")

    # 4G serial reliability: only apply when the vendor Kconfig exposes it.
    if "UART_ISR_IN_IRAM" in known:
        set_opt(lines, "UART_ISR_IN_IRAM", "y")
        print("[config] CONFIG_UART_ISR_IN_IRAM=y")

    # Keep the original 3.5-inch UI's large clock when supported.
    if "LV_FONT_MONTSERRAT_48" in known:
        set_opt(lines, "LV_FONT_MONTSERRAT_48", "y")

    # This product variant uses the rear GC0308.  Names changed across vendor
    # snapshots, so only touch symbols that actually exist in that snapshot.
    enabled_cam = set_if_known(lines, known, (
        "ESP_VIDEO_ENABLE_DVP_VIDEO_DEVICE",
        "CAMERA_GC0308",
        "CAMERA_GC0308_AUTO_DETECT_DVP_INTERFACE_SENSOR",
        "CAMERA_GC0308_DVP_YUV422_YUYV_640X480_16FPS",
        "CAMERA_GC0308_DVP_DEFAULT_FMT_YUV422_YUYV_640X480_16FPS",
        "XIAOZHI_ENABLE_ROTATE_CAMERA_IMAGE",
        "XIAOZHI_CAMERA_IMAGE_ROTATION_ANGLE_90",
    ))
    unset_cam = unset_if_known(lines, known, (
        "CAMERA_OV2640",
        "CAMERA_OV2640_AUTO_DETECT_DVP_INTERFACE_SENSOR",
        "CAMERA_OV5640",
        "CAMERA_OV5640_AUTO_DETECT_DVP_INTERFACE_SENSOR",
        "XIAOZHI_CAMERA_IMAGE_ROTATION_ANGLE_270",
    ))
    if enabled_cam:
        print("[config] rear GC0308 options enabled where available:", ", ".join(enabled_cam))
    if unset_cam:
        print("[config] other camera SKU options disabled where available:", ", ".join(unset_cam))

    fixed_ota = "http://124.221.112.55:8002/xiaozhi/ota/"
    if "OTA_URL" not in known:
        raise SystemExit("FATAL: vendor tree has no CONFIG_OTA_URL; cannot build fixed-backend firmware")
    set_string(lines, "OTA_URL", fixed_ota)
    print(f"[config] fixed CONFIG_OTA_URL={fixed_ota}")

    cfg.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
