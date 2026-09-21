#pragma once

#include "display/lcd_display.h"
#include "device_state.h"
#include "ui_pages.h"
#include <cstdint>

class StellarMax35Display : public SpiLcdDisplay {
public:
    using SpiLcdDisplay::SpiLcdDisplay;

    void SetChatMessage(const char* role, const char* content) override;
    void UpdateStatusBar(bool update_all = false) override;

private:
    enum class Page { Home, Chat };
    stellar_max35::HomeUi home_;
    stellar_max35::ChatUi chat_;
    Page page_ = Page::Home;
    DeviceState last_state_ = kDeviceStateUnknown;
    bool ui_ready_ = false;
    bool conversation_active_ = false;
    int64_t scroll_finish_us_ = 0;
    int64_t return_home_us_ = 0;

    bool EnsureProductUi();
    void ShowPageInternal(Page page);
    void UpdateHomeInfoInternal();
    void UpdateConversationState(DeviceState state);
};
