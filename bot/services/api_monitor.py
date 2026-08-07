import httpx
import time
from datetime import datetime, timezone, timedelta
from telegram.ext import ContextTypes
from bot.utils.admins_store import get_all_admins
from bot.config import ADMIN_IDS

API_MONITOR_STATE = {
    "is_up": True,
    "last_check_time": 0,
    "latency": 0,
    "status_text": "200 OK",
    "downtime_start": None,
    "initialized": False
}

API_URL = "https://api-gwvpn-app.vpnhub.xyz/docs"

def get_moscow_time_str():
    tz = timezone(timedelta(hours=3))
    now = datetime.now(tz)
    return now.strftime("%H:%M:%S")

def get_downtime_str(start_time):
    if not start_time:
        return "0 мин"
    diff = int(time.time() - start_time)
    if diff < 60:
        return f"{diff} сек"
    minutes = diff // 60
    if minutes < 60:
        return f"~{minutes} мин"
    hours = minutes // 60
    return f"~{hours} ч {minutes % 60} мин"

async def check_api():
    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(API_URL)
            latency = int((time.time() - start) * 1000)
            if resp.status_code == 200:
                return True, latency, f"{resp.status_code} OK"
            else:
                return False, latency, f"{resp.status_code} {resp.reason_phrase}"
    except httpx.TimeoutException:
        return False, int((time.time() - start) * 1000), "Connection timeout"
    except Exception as e:
        return False, int((time.time() - start) * 1000), str(e)

async def api_monitor_job(context: ContextTypes.DEFAULT_TYPE):
    global API_MONITOR_STATE
    is_up, latency, status_text = await check_api()
    
    current_time = time.time()
    moscow_time = get_moscow_time_str()
    
    if not API_MONITOR_STATE["initialized"]:
        API_MONITOR_STATE["is_up"] = is_up
        API_MONITOR_STATE["latency"] = latency
        API_MONITOR_STATE["status_text"] = status_text
        API_MONITOR_STATE["initialized"] = True
        
        if not is_up:
            API_MONITOR_STATE["downtime_start"] = current_time
            msg = (
                f"🔴 API не отвечает на запросы, приложение может быть недоступно для пользователей\n"
                f"🌐 {API_URL}\n"
                f"⏰ {moscow_time} (по МСК)\n"
                f"❌ Ошибка: {status_text}"
            )
            await notify_admins(context, msg)
        else:
            msg = (
                f"🤖 Бот успешно стартовал/перезагружен\n"
                f"🟢 Проверили API, доступен и работает в штатном режиме\n"
                f"🌐 {API_URL}\n"
                f"⏰ Время: {moscow_time} (по МСК)\n"
                f"✅ Статус: {status_text} | Пинг: {latency}ms"
            )
            await notify_admins(context, msg)
        return

    was_up = API_MONITOR_STATE["is_up"]
    
    API_MONITOR_STATE["is_up"] = is_up
    API_MONITOR_STATE["latency"] = latency
    API_MONITOR_STATE["status_text"] = status_text
    
    if was_up and not is_up:
        API_MONITOR_STATE["downtime_start"] = current_time
        msg = (
            f"🔴 API не отвечает на запросы, приложение может быть недоступно для пользователей\n"
            f"🌐 {API_URL}\n"
            f"⏰ {moscow_time} (по МСК)\n"
            f"❌ Ошибка: {status_text}"
        )
        await notify_admins(context, msg)
        
    elif not was_up and is_up:
        downtime_str = get_downtime_str(API_MONITOR_STATE["downtime_start"])
        API_MONITOR_STATE["downtime_start"] = None
        msg = (
            f"🟢 API снова работает\n"
            f"🌐 {API_URL}\n"
            f"⏰ {moscow_time} (по МСК)\n"
            f"✅ Статус: {status_text} | Задержка: {latency}ms\n"
            f"⏳ Простой: {downtime_str}"
        )
        await notify_admins(context, msg)

async def notify_admins(context, text):
    all_admins = set(get_all_admins())
    if ADMIN_IDS:
        all_admins.add(ADMIN_IDS[0])
    
    for admin_id in all_admins:
        try:
            await context.bot.send_message(chat_id=admin_id, text=text)
        except Exception:
            pass

def get_api_status_block():
    state = API_MONITOR_STATE
    text = "\n\n🌐 Мониторинг главного API:\n"
    if not state["initialized"]:
        text += f"🔄 {API_URL} — Проверка..."
    elif state["is_up"]:
        text += f"🟢 {API_URL} — OK ({state['latency']}ms)"
    else:
        text += f"🔴 {API_URL} — {state['status_text']} ({state['latency']}ms)"
    return text
