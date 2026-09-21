# MAX35 STELLAR 4G — 固定自建后台版

适用硬件：SpotPear / 斑梨 `ESP32S3-MAX35-TouchLCD-BCamera-Case-4G`，3.5 英寸 MAX35 + ML307 Cat.1。

这版仍然以 **SpotPear 原厂 4G 小智源码**为底座：ML307、麦克风、ES8311/ES7210、I2S、Application、AudioService、WebSocket/MQTT 等都保留厂商实现；STELLAR 代码只替换显示 UI。

唯一新增的核心行为是把小智的 OTA / 后台发现入口固定为：

`http://124.221.112.55:8002/xiaozhi/ota/`

## 为什么要同时改两层

只改 `CONFIG_OTA_URL` 还不够稳妥，因为部分小智版本会优先读取 NVS 中配网页面保存的 `wifi/ota_url`。本工程做两层锁定：

1. `sdkconfig` 强制写入 `CONFIG_OTA_URL="http://124.221.112.55:8002/xiaozhi/ota/"`；
2. OTA 运行时 `GetCheckVersionUrl()` 被改成直接返回 `CONFIG_OTA_URL`，不再读取配网/NVS 的 `ota_url`。

因此 4G 版不需要进入 Wi-Fi 配网来选择 OTA 地址，旧 NVS 里的 OTA 地址也不能把它覆盖。

## GitHub Actions 编译

把整个目录上传到新 GitHub 仓库：

1. 打开 **Actions**；
2. 运行 **Build MAX35 4G - Fixed Backend + STELLAR UI**；
3. 下载 `MAX35-STELLAR-4G-FIXED-BACKEND-Firmware`；
4. 将 `MAX35_STELLAR_4G_FIXED_BACKEND_2.1.0_merged-binary.bin` 从 `0x0` 烧录。

CI 会在编译前强制检查：

- 选中的是 MAX35 + ML307/4G 板型，而不是 Wi-Fi 板型；
- `CONFIG_OTA_URL` 必须精确等于上述固定地址；
- `GetCheckVersionUrl()` 必须已经禁止 NVS/配网 OTA 覆盖；
- ML307 实现仍然存在；
- UI 不依赖或重写音频、Modem、Protocol 内部代码。

任何一项不满足都会直接失败，不会生成一个“看起来编译成功但实际连错后台”的固件。

## 后台还需要满足什么

这个 `8002/xiaozhi/ota/` 接口需要给设备下发实际的语音服务连接信息，例如公网可达的 WebSocket 地址。4G 设备不能访问 `127.0.0.1`、`localhost` 或 `192.168.x.x` 一类内网地址。

如果你的语音服务实际是 `ws://124.221.112.55:8000/xiaozhi/v1/`，请确认 OTA 接口返回的 `websocket.url` 也是这个公网地址（或你真实使用的公网域名/端口）。

## UI 文件

以后只调整界面时主要修改：

- `overlay/main/display/stellar_max35/ui_home.cc`
- `overlay/main/display/stellar_max35/ui_chat.cc`
- `overlay/main/display/stellar_max35/ui_character.c/.h`
- `overlay/main/display/stellar_max35/stellar_max35_display.cc`

不要再改 4G、音频和协议层。
