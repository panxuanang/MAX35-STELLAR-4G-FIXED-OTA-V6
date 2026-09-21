# STELLAR MAX35 display overlay

This directory is intentionally UI-only.

It may call the public Application device-state getter so the screen can show
Starting / Connecting / Listening / Speaking, but it must not initialize or
configure network, modem, microphone, codec, I2S, protocol, OTA, camera or MCP.

The SpotPear MAX35 ML307 board source owns all hardware initialization.
