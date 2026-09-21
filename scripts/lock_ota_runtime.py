#!/usr/bin/env python3
"""Force XiaoZhi OTA/server-discovery URL to the build-time CONFIG_OTA_URL.

XiaoZhi versions commonly let an NVS key (wifi/ota_url) override CONFIG_OTA_URL.
For this product build we intentionally disable that override so a 4G-only unit
never needs Wi-Fi provisioning just to select the backend.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

CODE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx"}


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")


def find_matching_brace(text: str, open_pos: int) -> int:
    depth = 0
    in_str = False
    in_char = False
    escape = False
    i = open_pos
    while i < len(text):
        c = text[i]
        if escape:
            escape = False
            i += 1
            continue
        if (in_str or in_char) and c == "\\":
            escape = True
            i += 1
            continue
        if not in_char and c == '"':
            in_str = not in_str
            i += 1
            continue
        if not in_str and c == "'":
            in_char = not in_char
            i += 1
            continue
        if in_str or in_char:
            i += 1
            continue
        if c == "{" :
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError("unbalanced braces")


def patch_get_check_version_url(root: Path) -> tuple[Path, str]:
    main = root / "main"
    matches: list[tuple[Path, re.Match[str]]] = []
    pat = re.compile(
        r"(?:std::string|string)\s+(?:[A-Za-z_][A-Za-z0-9_]*::)?GetCheckVersionUrl\s*\([^)]*\)\s*\{",
        re.M,
    )
    for p in main.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in CODE_SUFFIXES:
            continue
        text = read(p)
        for m in pat.finditer(text):
            matches.append((p, m))

    if not matches:
        raise SystemExit(
            "FATAL: could not find GetCheckVersionUrl() in vendor source. "
            "Refusing to claim a fixed OTA build because an NVS ota_url override may still win."
        )
    if len(matches) > 1:
        raise SystemExit(
            "FATAL: multiple GetCheckVersionUrl() implementations found: "
            + ", ".join(str(p.relative_to(root)) for p, _ in matches)
        )

    p, m = matches[0]
    text = read(p)
    open_pos = text.find("{", m.start(), m.end())
    close_pos = find_matching_brace(text, open_pos)
    old_body = text[open_pos + 1:close_pos]
    # This check is informational only. Older/newer trees may use a different
    # persistence namespace while still exposing GetCheckVersionUrl().
    had_nvs_override = "ota_url" in old_body.lower() or "Settings" in old_body
    replacement = "{\n    // STELLAR fixed-backend build: ignore provisioning/NVS OTA overrides.\n    return CONFIG_OTA_URL;\n}"
    new_text = text[:open_pos] + replacement + text[close_pos + 1:]
    p.write_text(new_text, encoding="utf-8")
    return p, ("removed NVS/config override" if had_nvs_override else "forced CONFIG_OTA_URL return")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vendor", required=True, type=Path)
    ap.add_argument("--url", required=True)
    args = ap.parse_args()
    root = args.vendor.resolve()
    url = args.url.strip()
    if not url.startswith(("http://", "https://")):
        raise SystemExit("FATAL: fixed OTA URL must start with http:// or https://")
    if any(c in url for c in ("\r", "\n", '"')):
        raise SystemExit("FATAL: invalid character in fixed OTA URL")

    p, note = patch_get_check_version_url(root)
    info = {
        "fixed_ota_url": url,
        "runtime_source": str(p.relative_to(root)),
        "runtime_policy": "GetCheckVersionUrl always returns CONFIG_OTA_URL; NVS/provisioning ota_url cannot override it",
        "note": note,
    }
    (root / ".stellar_fixed_ota.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"[ota] runtime locked to CONFIG_OTA_URL in {p.relative_to(root)}")
    print(f"[ota] fixed backend discovery URL: {url}")


if __name__ == "__main__":
    main()
