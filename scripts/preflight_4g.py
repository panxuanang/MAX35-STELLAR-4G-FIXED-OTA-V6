#!/usr/bin/env python3
"""Fail-fast checks for the MAX35 vendor-4G + UI-only build."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("usage: preflight_4g.py <vendor-xiaozhi-root>")
root = Path(sys.argv[1]).resolve()
main = root / "main"
sdk = root / "sdkconfig"
manifest_p = root / ".stellar_patch_manifest.json"

for p in (sdk, manifest_p, main / "CMakeLists.txt", main / "display" / "stellar_max35" / "stellar_max35_display.cc"):
    if not p.exists():
        raise SystemExit(f"FATAL: required file missing: {p}")

manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
selected = manifest["selected_4g_symbol"]
siblings = manifest.get("disabled_board_siblings", [])
parents = manifest.get("required_board_parents", [])
patched_files = manifest.get("patched_board_files", [])
config = sdk.read_text(encoding="utf-8", errors="ignore")

if not re.search(rf"(?m)^CONFIG_{re.escape(selected)}=y$", config):
    raise SystemExit(f"FATAL: 4G board is not selected: CONFIG_{selected}=y")
print(f"[OK] real SpotPear MAX35 4G board selected: CONFIG_{selected}=y")
for parent in parents:
    if not re.search(rf"(?m)^CONFIG_{re.escape(parent)}=y$", config):
        raise SystemExit(f"FATAL: required MAX35 parent config is not enabled: CONFIG_{parent}=y")
if parents:
    print("[OK] required MAX35 parent config(s) enabled")

bad = []
for s in siblings:
    if re.search(rf"(?m)^CONFIG_{re.escape(s)}=y$", config):
        bad.append(s)
if bad:
    raise SystemExit("FATAL: Wi-Fi/alternate MAX35 board also selected: " + ", ".join(bad))
print("[OK] no alternate SpotPear MAX35 board option is selected")

# Positive modem check in source tree.
ml307_hits = []
for p in main.rglob("*"):
    if not p.is_file() or p.suffix.lower() not in {".c", ".cc", ".cpp", ".h", ".hpp", ".yml", ".yaml"}:
        continue
    t = p.read_text(encoding="utf-8", errors="ignore")
    if "ml307" in (p.as_posix() + "\n" + t).lower():
        ml307_hits.append(p)
if not ml307_hits:
    raise SystemExit("FATAL: vendor firmware contains no ML307 implementation")
print(f"[OK] vendor ML307 implementation retained ({len(ml307_hits)} matching file(s))")

cmake = (main / "CMakeLists.txt").read_text(encoding="utf-8", errors="ignore")
for src in (
    "display/stellar_max35/stellar_max35_display.cc",
    "display/stellar_max35/ui_home.cc",
    "display/stellar_max35/ui_chat.cc",
    "display/stellar_max35/ui_character.c",
):
    if src not in cmake:
        raise SystemExit(f"FATAL: UI source not registered in CMake: {src}")
print("[OK] only the STELLAR display/UI sources were added to main CMake")

if not patched_files:
    raise SystemExit("FATAL: patch manifest has no board display file")
for rel in patched_files:
    p = root / rel
    if not p.exists():
        raise SystemExit(f"FATAL: patched board display file vanished: {rel}")
    t = p.read_text(encoding="utf-8", errors="ignore")
    if "StellarMax35Display" not in t:
        raise SystemExit(f"FATAL: STELLAR display not attached in: {rel}")
    if any(x in rel.lower() for x in ("application.cc", "audio_service.cc", "protocol")):
        raise SystemExit(f"FATAL: protected core file appears in patch manifest: {rel}")
print("[OK] UI is attached only through MAX35 display construction/inheritance")

# Ensure overlay does not import modem/audio/protocol internals.
ui_dir = main / "display" / "stellar_max35"
ui_blob = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in ui_dir.rglob("*") if p.is_file())
for forbidden in ("ml307_board.h", "audio_service.h", "websocket_protocol.h", "mqtt_protocol.h", "audio_codec.h"):
    if forbidden in ui_blob:
        raise SystemExit(f"FATAL: UI overlay reached into hardware/protocol internals: {forbidden}")
print("[OK] UI code has no dependency on ML307/audio/protocol internals")


# Fixed backend / OTA discovery endpoint must be compiled in exactly, and the
# runtime accessor must not allow an NVS/provisioning ota_url to override it.
FIXED_OTA = "http://124.221.112.55:8002/xiaozhi/ota/"
expected = 'CONFIG_OTA_URL="' + FIXED_OTA + '"'
if expected not in config:
    raise SystemExit(f"FATAL: fixed OTA URL missing from sdkconfig: {expected}")
lock_manifest = root / ".stellar_fixed_ota.json"
if not lock_manifest.exists():
    raise SystemExit("FATAL: fixed OTA runtime manifest missing")
lock = json.loads(lock_manifest.read_text(encoding="utf-8"))
if lock.get("fixed_ota_url") != FIXED_OTA:
    raise SystemExit("FATAL: runtime OTA lock URL does not match requested backend")
runtime_file = root / lock.get("runtime_source", "")
if not runtime_file.exists():
    raise SystemExit("FATAL: patched OTA runtime source missing")
runtime_text = runtime_file.read_text(encoding="utf-8", errors="ignore")
m = re.search(r"GetCheckVersionUrl\s*\([^)]*\)\s*\{(?P<body>.*?)\n\}", runtime_text, re.S)
if not m:
    raise SystemExit("FATAL: cannot verify patched GetCheckVersionUrl()")
body = m.group("body")
if "return CONFIG_OTA_URL;" not in body or "GetString" in body or '"ota_url"' in body:
    raise SystemExit("FATAL: OTA runtime accessor can still be overridden")
print(f"[OK] backend discovery URL hard-locked: {FIXED_OTA}")

# If this vendor snapshot exposes the recommended UART ISR setting, require it.
if re.search(r"(?m)^#?\s*CONFIG_UART_ISR_IN_IRAM", config) and not re.search(r"(?m)^CONFIG_UART_ISR_IN_IRAM=y$", config):
    raise SystemExit("FATAL: CONFIG_UART_ISR_IN_IRAM is available but not enabled")
if re.search(r"(?m)^CONFIG_UART_ISR_IN_IRAM=y$", config):
    print("[OK] ML307 UART ISR-in-IRAM reliability option enabled")

# Camera is secondary to the user's 4G+voice goal. Validate only if those
# symbols exist in this vendor snapshot.
if "CONFIG_CAMERA_GC0308" in config:
    if not re.search(r"(?m)^CONFIG_CAMERA_GC0308=y$", config):
        raise SystemExit("FATAL: GC0308 option exists but is not selected")
    if re.search(r"(?m)^CONFIG_CAMERA_(OV2640|OV5640)=y$", config):
        raise SystemExit("FATAL: a non-GC0308 camera SKU is selected")
    print("[OK] rear GC0308 SKU selected")

print("[done] preflight passed: SpotPear 4G base + UI-only patch")
