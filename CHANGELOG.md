# Changelog

## 2.1.0 — Fixed 4G backend

- 固定 OTA / 服务发现地址为 `http://124.221.112.55:8002/xiaozhi/ota/`。
- 不再使用 GitHub Actions Variable 选择 OTA 地址。
- 强制 `CONFIG_OTA_URL` 为上述地址；厂商源码若没有该 Kconfig 项则构建失败。
- 新增运行时 OTA 锁：`GetCheckVersionUrl()` 直接返回 `CONFIG_OTA_URL`，阻止 NVS / Wi-Fi 配网页面的旧 `ota_url` 覆盖固定地址。
- preflight 增加固定后台校验和运行时覆盖校验。
- 保留 SpotPear MAX35 ML307 4G、音频、协议栈和 STELLAR UI-only 架构。
