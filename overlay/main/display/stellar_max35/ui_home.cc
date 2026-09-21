#include "ui_pages.h"
#include "ui_character.h"

#include <cstdio>

namespace stellar_max35 {
namespace {
constexpr uint32_t kInk = 0x3E4B5F;
constexpr uint32_t kMuted = 0x718096;
constexpr uint32_t kBlue = 0x6E9DD8;
constexpr uint32_t kSage = 0x8CA77A;
constexpr uint32_t kCream = 0xFFF9F0;
constexpr uint32_t kMemo = 0xFFFDF7;

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

lv_obj_t* SoftPanel(lv_obj_t* parent, int x, int y, int w, int h) {
    auto* p = lv_obj_create(parent);
    lv_obj_set_pos(p, x, y);
    lv_obj_set_size(p, w, h);
    lv_obj_set_style_radius(p, 18, 0);
    lv_obj_set_style_bg_color(p, lv_color_hex(kMemo), 0);
    lv_obj_set_style_bg_opa(p, LV_OPA_80, 0);
    lv_obj_set_style_border_width(p, 0, 0);
    lv_obj_set_style_shadow_width(p, 12, 0);
    lv_obj_set_style_shadow_opa(p, LV_OPA_10, 0);
    lv_obj_set_style_shadow_offset_y(p, 3, 0);
    lv_obj_set_style_pad_all(p, 0, 0);
    lv_obj_remove_flag(p, LV_OBJ_FLAG_SCROLLABLE);
    return p;
}
}  // namespace

void BuildHomeUi(lv_obj_t* screen, HomeUi* ui) {
    ui->root = lv_obj_create(screen);
    lv_obj_set_pos(ui->root, 0, 0);
    lv_obj_set_size(ui->root, 480, 320);
    lv_obj_set_style_bg_color(ui->root, lv_color_hex(0xF5FAFF), 0);
    lv_obj_set_style_bg_grad_color(ui->root, lv_color_hex(kCream), 0);
    lv_obj_set_style_bg_grad_dir(ui->root, LV_GRAD_DIR_HOR, 0);
    lv_obj_set_style_border_width(ui->root, 0, 0);
    lv_obj_set_style_radius(ui->root, 0, 0);
    lv_obj_set_style_pad_all(ui->root, 0, 0);
    lv_obj_remove_flag(ui->root, LV_OBJ_FLAG_SCROLLABLE);

    // Character is intentionally a separate asset. A clipped 188x246 portrait window removes
    // any source-composition edge pixels and lets future character art be replaced independently.
    auto* portrait = lv_obj_create(ui->root);
    lv_obj_set_pos(portrait, 292, 32);
    lv_obj_set_size(portrait, 188, 246);
    lv_obj_set_style_radius(portrait, 22, 0);
    lv_obj_set_style_bg_opa(portrait, LV_OPA_TRANSP, 0);
    lv_obj_set_style_border_width(portrait, 0, 0);
    lv_obj_set_style_pad_all(portrait, 0, 0);
    lv_obj_set_style_clip_corner(portrait, true, 0);
    lv_obj_remove_flag(portrait, LV_OBJ_FLAG_SCROLLABLE);
    auto* character = lv_image_create(portrait);
    lv_image_set_src(character, &stellar_max35_character);
    lv_obj_set_pos(character, 0, 0);

    // Time/date/weather float directly on the background: no fragmented cards.
    ui->time = Label(ui->root, "--:--", 22, 8, 220, kInk);
#if LV_FONT_MONTSERRAT_48
    // Digits only: Montserrat keeps the clock crisp without replacing the CJK UI font.
    lv_obj_set_style_text_font(ui->time, &lv_font_montserrat_48, 0);
#endif
    lv_obj_set_style_text_letter_space(ui->time, 2, 0);
    ui->date = Label(ui->root, "日期同步中", 23, 61, 225, kMuted);
    ui->weather = Label(ui->root, "网络 4G", 23, 86, 160, kBlue);
    ui->weather_detail = Label(ui->root, "ML307 Cat.1", 134, 86, 140, kMuted, LV_TEXT_ALIGN_RIGHT);

    // One large memo surface, visually treated like translucent stationery rather than an app card.
    auto* memo_paper = SoftPanel(ui->root, 18, 116, 260, 169);
    auto* pin = lv_obj_create(memo_paper);
    lv_obj_set_pos(pin, 18, 15);
    lv_obj_set_size(pin, 8, 8);
    lv_obj_set_style_radius(pin, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_bg_color(pin, lv_color_hex(kSage), 0);
    lv_obj_set_style_bg_opa(pin, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(pin, 0, 0);
    lv_obj_set_style_pad_all(pin, 0, 0);
    Label(memo_paper, "今日备忘", 34, 8, 180, kInk);
    auto* line = lv_obj_create(memo_paper);
    lv_obj_set_pos(line, 17, 38);
    lv_obj_set_size(line, 224, 1);
    lv_obj_set_style_bg_color(line, lv_color_hex(0xD9E3DC), 0);
    lv_obj_set_style_bg_opa(line, LV_OPA_60, 0);
    lv_obj_set_style_border_width(line, 0, 0);
    lv_obj_set_style_pad_all(line, 0, 0);
    ui->memo = Label(memo_paper, "MAX35 4G\n原厂语音与网络底座\n仅替换显示 UI", 18, 49, 222, kInk);
    lv_label_set_long_mode(ui->memo, LV_LABEL_LONG_WRAP);
    lv_obj_set_style_text_line_space(ui->memo, 7, 0);

    // A tiny ambient state line replaces the old large 'press to talk' control.
    auto* state_bg = lv_obj_create(ui->root);
    lv_obj_set_pos(state_bg, 19, 293);
    lv_obj_set_size(state_bg, 258, 20);
    lv_obj_set_style_radius(state_bg, 11, 0);
    lv_obj_set_style_bg_color(state_bg, lv_color_hex(0xFFFFFF), 0);
    lv_obj_set_style_bg_opa(state_bg, LV_OPA_40, 0);
    lv_obj_set_style_border_width(state_bg, 0, 0);
    lv_obj_set_style_pad_all(state_bg, 0, 0);
    lv_obj_remove_flag(state_bg, LV_OBJ_FLAG_SCROLLABLE);
    ui->status = Label(state_bg, "●  小智待命中", 10, 1, 238, kSage);
}

void HomeUiSetClock(HomeUi* ui, const char* time_text, const char* date_text) {
    if (ui->time) lv_label_set_text(ui->time, time_text ? time_text : "--:--");
    if (ui->date) lv_label_set_text(ui->date, date_text ? date_text : "");
}

void HomeUiSetWeather(HomeUi* ui, const char* value, const char* detail) {
    if (ui->weather) lv_label_set_text(ui->weather, value ? value : "网络 4G");
    if (ui->weather_detail) lv_label_set_text(ui->weather_detail, detail ? detail : "等待数据");
}

void HomeUiSetMemo(HomeUi* ui, const char* memo_text) {
    if (ui->memo) lv_label_set_text(ui->memo, memo_text && memo_text[0] ? memo_text : "MAX35 4G\n原厂语音与网络底座\n仅替换显示 UI");
}

void HomeUiSetStatus(HomeUi* ui, const char* state_text, uint32_t color) {
    if (!ui->status) return;
    lv_label_set_text_fmt(ui->status, "●  %s", state_text ? state_text : "小智待命中");
    lv_obj_set_style_text_color(ui->status, lv_color_hex(color), 0);
}

}  // namespace stellar_max35
