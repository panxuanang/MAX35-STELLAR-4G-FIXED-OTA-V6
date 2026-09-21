#pragma once

#include <lvgl.h>
#include <cstdint>

namespace stellar_max35 {

struct HomeUi {
    lv_obj_t* root = nullptr;
    lv_obj_t* time = nullptr;
    lv_obj_t* date = nullptr;
    lv_obj_t* weather = nullptr;
    lv_obj_t* weather_detail = nullptr;
    lv_obj_t* memo = nullptr;
    lv_obj_t* status = nullptr;
};

struct ChatUi {
    lv_obj_t* root = nullptr;
    lv_obj_t* user = nullptr;
    lv_obj_t* answer_box = nullptr;
    lv_obj_t* answer = nullptr;
    lv_obj_t* state = nullptr;
};

void BuildHomeUi(lv_obj_t* screen, HomeUi* ui);
void HomeUiSetClock(HomeUi* ui, const char* time_text, const char* date_text);
void HomeUiSetWeather(HomeUi* ui, const char* value, const char* detail);
void HomeUiSetMemo(HomeUi* ui, const char* memo_text);
void HomeUiSetStatus(HomeUi* ui, const char* state_text, uint32_t color);

void BuildChatUi(lv_obj_t* screen, ChatUi* ui);
void ChatUiSetUser(ChatUi* ui, const char* text);
void ChatUiSetAnswer(ChatUi* ui, const char* text);
void ChatUiSetState(ChatUi* ui, const char* text, uint32_t color);
void ChatUiStopScroll(ChatUi* ui);
int64_t ChatUiStartReadableScroll(ChatUi* ui, int delay_ms, int ms_per_pixel);

}  // namespace stellar_max35
