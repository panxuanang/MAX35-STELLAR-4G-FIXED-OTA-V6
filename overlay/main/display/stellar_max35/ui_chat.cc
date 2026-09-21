#include "ui_pages.h"

#include <algorithm>
#include <esp_timer.h>

namespace stellar_max35 {
namespace {
constexpr uint32_t kInk = 0x334155;
constexpr uint32_t kMuted = 0x64748B;
constexpr uint32_t kBlue = 0x6E9DD8;
constexpr uint32_t kPaper = 0xFFFEFB;

lv_obj_t* Label(lv_obj_t* parent, const char* text, int x, int y, int w,
                uint32_t color, lv_text_align_t align = LV_TEXT_ALIGN_LEFT) {
    auto* o = lv_label_create(parent);
    lv_label_set_text(o, text);
    lv_obj_set_pos(o, x, y);
    lv_obj_set_width(o, w);
    lv_obj_set_style_text_color(o, lv_color_hex(color), 0);
    lv_obj_set_style_text_align(o, align, 0);
    return o;
}
}

void BuildChatUi(lv_obj_t* screen, ChatUi* ui) {
    ui->root = lv_obj_create(screen);
    lv_obj_set_pos(ui->root, 0, 0);
    lv_obj_set_size(ui->root, 480, 320);
    lv_obj_set_style_bg_color(ui->root, lv_color_hex(0xF7FAFC), 0);
    lv_obj_set_style_bg_grad_color(ui->root, lv_color_hex(0xFFF9F0), 0);
    lv_obj_set_style_bg_grad_dir(ui->root, LV_GRAD_DIR_VER, 0);
    lv_obj_set_style_border_width(ui->root, 0, 0);
    lv_obj_set_style_radius(ui->root, 0, 0);
    lv_obj_set_style_pad_all(ui->root, 0, 0);
    lv_obj_remove_flag(ui->root, LV_OBJ_FLAG_SCROLLABLE);

    // Compact conversational context. The response area receives almost the whole 3.5-inch screen.
    ui->user = Label(ui->root, "我在听…", 18, 10, 444, kMuted);
    lv_label_set_long_mode(ui->user, LV_LABEL_LONG_DOT);

    ui->answer_box = lv_obj_create(ui->root);
    lv_obj_set_pos(ui->answer_box, 10, 38);
    lv_obj_set_size(ui->answer_box, 460, 244);
    lv_obj_set_style_radius(ui->answer_box, 20, 0);
    lv_obj_set_style_bg_color(ui->answer_box, lv_color_hex(kPaper), 0);
    lv_obj_set_style_bg_opa(ui->answer_box, LV_OPA_COVER, 0);
    lv_obj_set_style_border_color(ui->answer_box, lv_color_hex(0xE7E2D8), 0);
    lv_obj_set_style_border_width(ui->answer_box, 1, 0);
    lv_obj_set_style_shadow_width(ui->answer_box, 14, 0);
    lv_obj_set_style_shadow_opa(ui->answer_box, LV_OPA_10, 0);
    lv_obj_set_style_pad_all(ui->answer_box, 14, 0);
    lv_obj_set_style_clip_corner(ui->answer_box, true, 0);
    lv_obj_set_scrollbar_mode(ui->answer_box, LV_SCROLLBAR_MODE_OFF);
    lv_obj_remove_flag(ui->answer_box, LV_OBJ_FLAG_SCROLLABLE);

    ui->answer = lv_label_create(ui->answer_box);
    lv_obj_set_pos(ui->answer, 0, 0);
    lv_obj_set_width(ui->answer, 430);
    lv_label_set_long_mode(ui->answer, LV_LABEL_LONG_WRAP);
    lv_label_set_text(ui->answer, "你好，我在这里。\n需要的时候直接和我说话就好。");
    lv_obj_set_style_text_color(ui->answer, lv_color_hex(kInk), 0);
    lv_obj_set_style_text_line_space(ui->answer, 6, 0);

    ui->state = Label(ui->root, "●  等待语音", 18, 292, 444, kBlue, LV_TEXT_ALIGN_CENTER);
}

void ChatUiSetUser(ChatUi* ui, const char* text) {
    if (ui->user) lv_label_set_text_fmt(ui->user, "你：%s", text ? text : "");
}

void ChatUiStopScroll(ChatUi* ui) {
    if (!ui || !ui->answer) return;
    lv_anim_delete(ui->answer, nullptr);
    lv_obj_set_y(ui->answer, 0);
}

void ChatUiSetAnswer(ChatUi* ui, const char* text) {
    if (!ui || !ui->answer) return;
    ChatUiStopScroll(ui);
    lv_label_set_text(ui->answer, text ? text : "");
    lv_obj_set_y(ui->answer, 0);
}

int64_t ChatUiStartReadableScroll(ChatUi* ui, int delay_ms, int ms_per_pixel) {
    if (!ui || !ui->answer || !ui->answer_box) return 0;
    lv_obj_update_layout(ui->answer);
    const int visible = lv_obj_get_height(ui->answer_box) - 28;
    const int h = lv_obj_get_height(ui->answer);
    if (h <= visible) return 0;
    const int distance = h - visible;
    const int duration = std::max(2400, distance * ms_per_pixel);
    lv_anim_t a;
    lv_anim_init(&a);
    lv_anim_set_var(&a, ui->answer);
    lv_anim_set_values(&a, 0, -distance);
    lv_anim_set_delay(&a, delay_ms);
    lv_anim_set_duration(&a, duration);
    lv_anim_set_exec_cb(&a, [](void* obj, int32_t value) {
        lv_obj_set_y(static_cast<lv_obj_t*>(obj), value);
    });
    lv_anim_start(&a);
    return esp_timer_get_time() + static_cast<int64_t>(delay_ms + duration) * 1000LL;
}

void ChatUiSetState(ChatUi* ui, const char* text, uint32_t color) {
    if (!ui->state) return;
    lv_label_set_text_fmt(ui->state, "●  %s", text ? text : "");
    lv_obj_set_style_text_color(ui->state, lv_color_hex(color), 0);
}

}  // namespace stellar_max35
