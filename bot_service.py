"""
Keyboard builders for the bot.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def create_main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔍 فحص جديد", callback_data="new_scan"), InlineKeyboardButton(text="📊 حالة الفحص", callback_data="scan_status"))
    builder.row(InlineKeyboardButton(text="⏸️ إيقاف مؤقت", callback_data="pause_scan"), InlineKeyboardButton(text="▶️ استئناف", callback_data="resume_scan"))
    builder.row(InlineKeyboardButton(text="⏹️ إيقاف الكل", callback_data="stop_scan"), InlineKeyboardButton(text="📋 قائمة الفحوصات", callback_data="list_scans"))
    builder.row(InlineKeyboardButton(text="❓ مساعدة", callback_data="help"))
    return builder.as_markup()

def create_control_keyboard(scan_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⏸️ إيقاف مؤقت", callback_data=f"pause_{scan_id}"), InlineKeyboardButton(text="▶️ استئناف", callback_data=f"resume_{scan_id}"))
    builder.row(InlineKeyboardButton(text="⏹️ إيقاف", callback_data=f"stop_{scan_id}"), InlineKeyboardButton(text="🔄 تحديث", callback_data=f"refresh_{scan_id}"))
    builder.row(InlineKeyboardButton(text="🏠 القائمة الرئيسية", callback_data="main_menu"))
    return builder.as_markup()