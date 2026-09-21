#include "stellar_max35_display.h"

#include "application.h"
#include <esp_log.h>
#include <esp_timer.h>
#include <cstring>
#include <ctime>
#include <cstdio>

namespace {
constexpr const char* TAG = "StellarMAX35_4G";
constexpr uint32_t kGreen = 0x7FA37A;
constexpr uint32_t kBlue = 0x6E9DD8;
constexpr uint32_t kGold = 0xC89B5D;
constexpr uint32_t kRed = 0xD36C74;
constexpr int kScrollDelayMs = 1800;
constexpr int kScrollMsPerPixel = 90;
constexpr int64_t kReturnHomeDelayUs = 4500000LL;
constexpr int64_t kAfterScrollDelayUs = 1800000LL;

bool IsConversing(DeviceState s) {
    return s == kDeviceStateConnecting || s == kDeviceStateListening || s == kDeviceStateSpeaking;
}

const char* StateText(DeviceState s) {
    switch (s) {
        case kDeviceStateStarting: return "小智启动中";
        case kDeviceStateConnecting: return "4G 正在连接";
        case kDeviceStateListening: return "正在聆听";
        case kDeviceStateSpeaking: return "正在回答";
        case kDeviceStateUpgrading: return "系统升级中";
        case kDeviceStateFatalError: return "系统异常";
        default: return "4G 小智待命中";
    }
}

uint32_t StateColor(DeviceState s) {
    if (s == kDeviceStateListening) return kBlue;
    if (s == kDeviceStateSpeaking) return kGold;
    if (s == kDeviceStateFatalError) return kRed;
    return kGreen;
}

const char* Weekday(int w) {
    static const char* k[] = {"星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"};
    return (w >= 0 && w < 7) ? k[w] : "";
}
}  // namespace

bool StellarMax35Display::EnsureProductUi() {
    if (ui_ready_) return true;

    DisplayLockGuard lock(this);
    if (ui_ready_) return true;

#if LVGL_VERSION_MAJOR >= 9
    auto* screen = lv_screen_active();
#else
    auto* screen = lv_scr_act();
#endif
    if (!screen) return false;

    stellar_max35::BuildHomeUi(screen, &home_);
    stellar_max35::BuildChatUi(screen, &chat_);

    page_ = Page::Home;
    conversation_active_ = false;
    last_state_ = Application::GetInstance().GetDeviceState();
    ShowPageInternal(Page::Home);
    UpdateHomeInfoInternal();
    ui_ready_ = true;
    ESP_LOGI(TAG, "STELLAR UI attached; vendor 4G/audio/application stack left untouched");
    return true;
}

void StellarMax35Display::ShowPageInternal(Page page) {
    if (!home_.root || !chat_.root) return;
    lv_obj_add_flag(home_.root, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(chat_.root, LV_OBJ_FLAG_HIDDEN);

    lv_obj_t* target = page == Page::Home ? home_.root : chat_.root;
    lv_obj_remove_flag(target, LV_OBJ_FLAG_HIDDEN);
    lv_obj_move_foreground(target);
    page_ = page;
    if (page != Page::Chat) stellar_max35::ChatUiStopScroll(&chat_);
}

void StellarMax35Display::SetChatMessage(const char* role, const char* content) {
    if (!role || !content || !content[0]) return;
    if (!EnsureProductUi()) return;

    DisplayLockGuard lock(this);
    if (std::strcmp(role, "system") == 0) return;

    if (std::strcmp(role, "user") == 0) {
        conversation_active_ = true;
        return_home_us_ = 0;
        scroll_finish_us_ = 0;
        ShowPageInternal(Page::Chat);
        stellar_max35::ChatUiSetUser(&chat_, content);
        stellar_max35::ChatUiSetAnswer(&chat_, "我听到了，正在思考…");
        stellar_max35::ChatUiSetState(&chat_, "正在思考", kBlue);
        return;
    }

    if (std::strcmp(role, "assistant") == 0) {
        conversation_active_ = true;
        return_home_us_ = 0;
        ShowPageInternal(Page::Chat);
        stellar_max35::ChatUiSetAnswer(&chat_, content);
        stellar_max35::ChatUiSetState(&chat_, "小智正在回答", kGold);
        scroll_finish_us_ = stellar_max35::ChatUiStartReadableScroll(
            &chat_, kScrollDelayMs, kScrollMsPerPixel);
    }
}

void StellarMax35Display::UpdateHomeInfoInternal() {
    if (!home_.root) return;

    std::time_t now = std::time(nullptr);
    std::tm tm{};
    localtime_r(&now, &tm);
    char t[16];
    char d[64];
    if (now > 1700000000) {
        std::snprintf(t, sizeof(t), "%02d:%02d", tm.tm_hour, tm.tm_min);
        std::snprintf(d, sizeof(d), "%d月%d日  %s", tm.tm_mon + 1, tm.tm_mday, Weekday(tm.tm_wday));
    } else {
        std::snprintf(t, sizeof(t), "--:--");
        std::snprintf(d, sizeof(d), "时间同步中");
    }

    stellar_max35::HomeUiSetClock(&home_, t, d);
    stellar_max35::HomeUiSetWeather(&home_, "网络 4G", "ML307 Cat.1");
    stellar_max35::HomeUiSetMemo(
        &home_, "MAX35 4G 原厂底座\n网络 / 麦克风 / 音频协议保持原厂\n本工程只替换显示 UI");
    stellar_max35::HomeUiSetStatus(&home_, StateText(last_state_), StateColor(last_state_));
}

void StellarMax35Display::UpdateConversationState(DeviceState state) {
    if (page_ != Page::Chat) return;
    if (state == kDeviceStateListening) {
        stellar_max35::ChatUiSetState(&chat_, "我在听，请说话", kBlue);
    } else if (state == kDeviceStateConnecting) {
        stellar_max35::ChatUiSetState(&chat_, "4G 正在连接 AI", kBlue);
    } else if (state == kDeviceStateSpeaking) {
        stellar_max35::ChatUiSetState(&chat_, "小智正在回答", kGold);
    }
}

void StellarMax35Display::UpdateStatusBar(bool update_all) {
    // Call the oldest stable display-layer implementation. The STELLAR overlay
    // paints its own full-screen status and deliberately does not depend on
    // vendor-specific network/battery status widgets.
    Display::UpdateStatusBar(update_all);
    if (!EnsureProductUi()) return;

    const DeviceState state = Application::GetInstance().GetDeviceState();
    const int64_t now = esp_timer_get_time();
    DisplayLockGuard lock(this);

    if (state != last_state_) {
        if (state == kDeviceStateListening && page_ == Page::Home) {
            conversation_active_ = true;
            return_home_us_ = 0;
            ShowPageInternal(Page::Chat);
            stellar_max35::ChatUiSetUser(&chat_, "正在聆听…");
            stellar_max35::ChatUiSetAnswer(&chat_, "请说，我在听。");
        }
        UpdateConversationState(state);
        last_state_ = state;
    }

    if (page_ == Page::Home) {
        UpdateHomeInfoInternal();
        return;
    }

    if (page_ == Page::Chat && conversation_active_) {
        if (state == kDeviceStateIdle) {
            if (scroll_finish_us_ > now) {
                return_home_us_ = scroll_finish_us_ + kAfterScrollDelayUs;
            } else if (return_home_us_ == 0) {
                return_home_us_ = now + kReturnHomeDelayUs;
            }
        } else if (IsConversing(state)) {
            return_home_us_ = 0;
        }

        if (return_home_us_ > 0 && now >= return_home_us_) {
            conversation_active_ = false;
            return_home_us_ = 0;
            scroll_finish_us_ = 0;
            ShowPageInternal(Page::Home);
            UpdateHomeInfoInternal();
        }
    }
}
