"""
Telegram Username Scanner Pro - Main Bot File
"""
import asyncio
import os
import uuid
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from scanner.engine import ScanManager, ScanOperation
from utils.logger import logger
from utils.constants import ScanStatus, SCANNER_MESSAGES
from keyboards import create_main_keyboard, create_control_keyboard

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)
scan_manager = ScanManager()

class ScanStates(StatesGroup):
    waiting_for_pattern = State()

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(SCANNER_MESSAGES["welcome"], reply_markup=create_main_keyboard(), parse_mode="Markdown")

@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ تم الإلغاء.", reply_markup=create_main_keyboard())

@dp.callback_query(F.data == "new_scan")
async def cb_new_scan(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_scans = await scan_manager.list_scans(callback.from_user.id)
    active_scans = [s for s in user_scans if s.status in (ScanStatus.RUNNING, ScanStatus.PAUSED)]
    if len(active_scans) >= 3:
        await callback.message.edit_text("⚠️ **لديك 3 فحوصات نشطة بالفعل!**\n\nالرجاء إنهاء الفحوصات الحالية قبل بدء فحص جديد.", reply_markup=create_main_keyboard(), parse_mode="Markdown")
        return
    await state.set_state(ScanStates.waiting_for_pattern)
    await callback.message.edit_text("📝 **أدخل نمط اليوزرات:**\n\n**الرموز المدعومة:**\n• `$` = حرف (a-z)\n• `#` = رقم (0-9)\n• `_` = شرطة سفلية\n\n**أمثلة:**\n• `test$$` ← testab, testxy\n• `user####` ← user0000, user9999\n• `$_$_$_#` ← نمط مختلط\n\n📌 أقل طول: 5 أحرف | أقصى طول: 32 حرف\n📌 أقصى عدد توليفات: 1,000,000\n\n_أرسل النمط الآن أو /cancel للإلغاء_", parse_mode="Markdown", reply_markup=None)

@dp.callback_query(F.data == "scan_status")
async def cb_scan_status(callback: CallbackQuery):
    await callback.answer()
    user_scans = await scan_manager.list_scans(callback.from_user.id)
    if not user_scans:
        await callback.message.edit_text("📭 **لا توجد فحوصات نشطة.**\n\nابدأ فحص جديد من القائمة الرئيسية.", reply_markup=create_main_keyboard(), parse_mode="Markdown")
        return
    active_scans = [s for s in user_scans if s.status in (ScanStatus.RUNNING, ScanStatus.PAUSED)]
    completed_scans = [s for s in user_scans if s.status == ScanStatus.COMPLETED]
    text = "📊 **حالة الفحوصات:**\n\n"
    if active_scans:
        text += "**🔄 الفحوصات النشطة:**\n"
        for scan in active_scans:
            text += f"• `{scan.pattern}` - {scan.status.value}\n  {scan.progress.checked:,}/{scan.progress.total_usernames:,} | ✅ {scan.progress.available:,}\n\n"
    if completed_scans:
        text += "**✅ الفحوصات المكتملة:**\n"
        for scan in completed_scans[-5:]:
            text += f"• `{scan.pattern}` - ✅ {scan.progress.available:,} متاح\n"
    if not active_scans and not completed_scans: text += "لا توجد فحوصات بعد. "
    await callback.message.edit_text(text, reply_markup=create_main_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data == "stop_scan")
async def cb_stop_scan(callback: CallbackQuery):
    await callback.answer()
    user_scans = await scan_manager.list_scans(callback.from_user.id)
    active_scans = [s for s in user_scans if s.status in (ScanStatus.RUNNING, ScanStatus.PAUSED)]
    if not active_scans:
        await callback.message.edit_text("⏹️ **لا توجد فحوصات نشطة لإيقافها.**", reply_markup=create_main_keyboard(), parse_mode="Markdown")
        return
    stopped_count = 0
    for scan in active_scans:
        await scan.stop()
        stopped_count += 1
    for scan in active_scans:
        if scan.available_usernames:
            try:
                file = FSInputFile(scan.save_path)
                await callback.message.answer_document(file, caption=f"📁 نتائج فحص `{scan.pattern}`\n✅ تم العثور على {len(scan.available_usernames):,} يوزر متاح")
            except Exception as e: logger.error(f"Failed to send file: {e}")
    await callback.message.edit_text(f"⏹️ **تم إيقاف {stopped_count} فحص/فحوصات بنجاح!**\nتم إرسال ملفات النتائج.", reply_markup=create_main_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data == "pause_scan")
async def cb_pause_scan(callback: CallbackQuery):
    await callback.answer()
    user_scans = await scan_manager.list_scans(callback.from_user.id)
    running_scans = [s for s in user_scans if s.status == ScanStatus.RUNNING]
    if not running_scans:
        await callback.message.edit_text("⏸️ **لا توجد فحوصات قيد التشغيل.**", reply_markup=create_main_keyboard(), parse_mode="Markdown")
        return
    for scan in running_scans: await scan.pause()
    await callback.message.edit_text(f"⏸️ **تم إيقاف {len(running_scans)} فحص/فحوصات مؤقتاً.**\nاستخدم استئناف للمتابعة.", reply_markup=create_main_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data == "resume_scan")
async def cb_resume_scan(callback: CallbackQuery):
    await callback.answer()
    user_scans = await scan_manager.list_scans(callback.from_user.id)
    paused_scans = [s for s in user_scans if s.status == ScanStatus.PAUSED]
    if not paused_scans:
        await callback.message.edit_text("▶️ **لا توجد فحوصات متوقفة للاستئناف.**", reply_markup=create_main_keyboard(), parse_mode="Markdown")
        return
    for scan in paused_scans: await scan.resume()
    await callback.message.edit_text(f"▶️ **تم استئناف {len(paused_scans)} فحص/فحوصات!**", reply_markup=create_main_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data == "list_scans")
async def cb_list_scans(callback: CallbackQuery):
    await callback.answer()
    user_scans = await scan_manager.list_scans(callback.from_user.id)
    if not user_scans:
        await callback.message.edit_text("📋 **لا توجد فحوصات مسجلة.**", reply_markup=create_main_keyboard(), parse_mode="Markdown")
        return
    text = "📋 **قائمة الفحوصات:**\n\n"
    for i, scan in enumerate(user_scans[-10:], 1):
        status_emoji = {ScanStatus.RUNNING: "🔄", ScanStatus.PAUSED: "⏸️", ScanStatus.STOPPED: "⏹️", ScanStatus.COMPLETED: "✅", ScanStatus.ERROR: "❌"}.get(scan.status, "❓")
        text += f"{i}. {status_emoji} `{scan.pattern}`\n   📊 {scan.progress.checked:,}/{scan.progress.total_usernames:,}\n   ✅ {scan.progress.available:,} متاح | ❌ {scan.progress.taken:,} مستخدم\n\n"
    await callback.message.edit_text(text, reply_markup=create_main_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery):
    await callback.answer()
    help_text = ("🤖 Telegram Username Scanner Pro - المساعدة\n\n🔹 ما هو هذا البوت؟\nأداة متطورة لفحص توفر يوزرات تليجرام بسرعة عالية\nبدون الحاجة إلى حساب تليجرام أو رقم هاتف.\n\n🔹 التقنيات المستخدمة:\n🔹 فحص متعدد الاستراتيجيات (3 طرق مختلفة)\n🔹 تدوير البروكسيات تلقائياً\n🔹 تشويش بصمات TLS/TCP\n🔹 تجاوز حماية كلاودفلير\n🔹 تخزين مؤقت ذكي\n\n🔹 الأداء:\n⚡ حتى 500 طلب/ثانية\n🔧 تحجيم تلقائي للعاملين\n\n🔹 الاستخدام:\n1️⃣ اضغط فحص جديد\n2️⃣ أدخل النمط (مثال: `test$$##`)\n3️⃣ انتظر النتائج\n4️⃣ احصل على ملف النتائج")
    await callback.message.edit_text(help_text, reply_markup=create_main_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(SCANNER_MESSAGES["welcome"], reply_markup=create_main_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("pause_"))
async def cb_pause_scan_id(callback: CallbackQuery):
    await callback.answer()
    scan_id = callback.data.replace("pause_", "")
    scan = await scan_manager.get_scan(scan_id)
    if not scan: await callback.message.edit_text("⚠️ الفحص غير موجود."); return
    await scan.pause()
    await callback.message.edit_text(scan.get_progress_message(), reply_markup=create_control_keyboard(scan_id), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("resume_"))
async def cb_resume_scan_id(callback: CallbackQuery):
    await callback.answer()
    scan_id = callback.data.replace("resume_", "")
    scan = await scan_manager.get_scan(scan_id)
    if not scan: await callback.message.edit_text("⚠️ الفحص غير موجود."); return
    await scan.resume()
    await callback.message.edit_text(scan.get_progress_message(), reply_markup=create_control_keyboard(scan_id), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("stop_"))
async def cb_stop_scan_id(callback: CallbackQuery):
    await callback.answer()
    scan_id = callback.data.replace("stop_", "")
    scan = await scan_manager.get_scan(scan_id)
    if not scan: await callback.message.edit_text("⚠️ الفحص غير موجود."); return
    await scan.stop()
    if scan.available_usernames:
        try:
            file = FSInputFile(scan.save_path)
            await callback.message.answer_document(file, caption=f"📁 نتائج فحص `{scan.pattern}`\n✅ {len(scan.available_usernames):,} يوزر متاح")
        except Exception as e: logger.error(f"Failed to send file: {e}")
    await callback.message.edit_text(f"⏹️ تم إيقاف الفحص: `{scan.pattern}`\n✅ متاح: {scan.progress.available:,}\n❌ مستخدم: {scan.progress.taken:,}\n⚡ السرعة: {scan.progress.speed:.1f}/s", reply_markup=create_main_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("refresh_"))
async def cb_refresh_scan(callback: CallbackQuery):
    await callback.answer()
    scan_id = callback.data.replace("refresh_", "")
    scan = await scan_manager.get_scan(scan_id)
    if not scan: await callback.message.edit_text("⚠️ الفحص غير موجود."); return
    try: await callback.message.edit_text(scan.get_progress_message(), reply_markup=create_control_keyboard(scan_id), parse_mode="Markdown")
    except Exception: pass

@dp.message(ScanStates.waiting_for_pattern)
async def handle_pattern_input(message: Message, state: FSMContext):
    pattern = message.text.strip() if message.text else ""
    if not pattern or pattern.lower() in ("/cancel", "cancel"):
        await state.clear()
        await message.answer("❌ تم الإلغاء.", reply_markup=create_main_keyboard())
        return
    from generators.pattern_parser import PatternParser
    parsed = PatternParser.parse(pattern)
    if not parsed.is_valid:
        await message.answer(f"❌ **نمط غير صالح!**\n\n{parsed.error_message}\n\n_أرسل نمطاً آخر أو /cancel للإلغاء_", parse_mode="Markdown")
        return
    await state.clear()
    scan_id = str(uuid.uuid4())[:8]
    save_path = f"/tmp/scan_{scan_id}_{message.from_user.id}.txt"
    scan = await scan_manager.create_scan(scan_id=scan_id, pattern=pattern, user_id=message.from_user.id, save_path=save_path)
    total = await scan.start()
    status_msg = await message.answer(f"🚀 **بدأ الفحص!**\n\n📝 النمط: `{pattern}`\n🔢 الإجمالي: {total:,} توليفة\n\n_سيتم تحديث التقرير كل 10 ثوانٍ..._", reply_markup=create_control_keyboard(scan_id), parse_mode="Markdown")
    asyncio.create_task(_update_progress_loop(message.from_user.id, status_msg.message_id, scan))

async def _update_progress_loop(user_id: int, message_id: int, scan: ScanOperation):
    while scan.status in (ScanStatus.RUNNING, ScanStatus.PAUSED):
        await asyncio.sleep(10)
        try:
            await bot.edit_message_text(scan.get_progress_message(), chat_id=user_id, message_id=message_id, reply_markup=create_control_keyboard(scan.scan_id), parse_mode="Markdown")
        except Exception: pass
    try: await bot.edit_message_text(scan.get_progress_message(), chat_id=user_id, message_id=message_id, reply_markup=create_main_keyboard(), parse_mode="Markdown")
    except Exception: pass
    if scan.available_usernames and scan.save_path:
        try:
            import os
            if os.path.exists(scan.save_path):
                file = FSInputFile(scan.save_path)
                await bot.send_document(user_id, file, caption=f"📁 **نتائج `{scan.pattern}`**\n✅ {len(scan.available_usernames):,} يوزر متاح")
        except Exception as e: logger.error(f"Failed to send results: {e}")

async def main():
    await scan_manager.initialize()
    logger.info("🤖 Bot is starting...")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    asyncio.run(main())