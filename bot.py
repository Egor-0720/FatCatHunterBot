import asyncio
import csv
import os
from datetime import datetime
import aiohttp

# Библиотека от Игоря Чечета [citation:1][citation:3]
from BCSPy import BCSPy

# ========== ТОКЕНЫ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ (Amvera) ==========
BCS_TOKEN = os.getenv("BCS_TOKEN")        # Твой токен БКС
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")  # Токен ТГ бота
TG_CHAT_ID = os.getenv("TG_CHAT_ID")      # Твой ID в ТГ

# Проверка, что всё на месте
if not BCS_TOKEN:
    raise Exception("Ошибка: BCS_TOKEN не найден!")
if not TG_BOT_TOKEN or not TG_CHAT_ID:
    raise Exception("Ошибка: Токены Telegram не найдены!")

# ========== НАСТРОЙКИ ==========
FIGI = "BBG004S683W8"                   # Код Совкомбанка (FIGI)
ASK_LEVELS = 10                         # Глубина стакана
FAT_FACTOR = 7.0                        # Дядька — в 7 раз толще среднего
MM_MIN_QTY = 20000                      # Маркет-мейкер — от 20000 лотов
CSV_FILE = "/data/signals.csv"          # Файл для статистики (папка /data на Amvera)

active_signals = {}

def init_csv():
    """Создаёт файл статистики, если его нет"""
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["datetime", "fat_price", "fat_qty", "mm_price"])

def save_signal_to_csv(signal_data):
    """Сохраняет данные о выкупе дядьки в CSV"""
    with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([signal_data["datetime"], signal_data["fat_price"], 
                         signal_data["fat_qty"], signal_data["mm_price"]])

async def send_tg_message(text: str):
    """Просто отправляет сообщение в Telegram"""
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    async with aiohttp.ClientSession() as session:
        try:
            await session.post(url, json={"chat_id": TG_CHAT_ID, "text": text})
        except:
            pass

async def monitor_market():
    """Главная функция — смотрит стакан и ищет дядьку"""
    global active_signals
    
    # Создаём провайдера BCSPy [citation:1]
    bp_provider = BCSPy(BCS_TOKEN)
    
    while True:
        try:
            # Получаем стакан (10 уровней) — библиотека умеет [citation:1]
            orderbook = bp_provider.get_orderbook(figi=FIGI, depth=ASK_LEVELS)
            asks = orderbook.get('asks', [])  # Заявки на продажу
            
            if not asks:
                await asyncio.sleep(2)
                continue
            
            # 1. Считаем средний объём на уровне
            avg_qty = sum(q for _, q in asks) / len(asks)
            
            # 2. Ищем дядьку (объём > среднего * FAT_FACTOR)
            fat_price, fat_qty = None, None
            for price, qty in asks:
                if qty >= avg_qty * FAT_FACTOR:
                    fat_price, fat_qty = price, qty
                    break
            
            # 3. Ищем Маркет-Мейкера (объём >= MM_MIN_QTY)
            mm_price = None
            for price, qty in asks:
                if qty >= MM_MIN_QTY:
                    mm_price = price
                    break
            
            # 4. Если нашли и дядьку, и ММ, и дядька стоит перед ММ
            if fat_price and mm_price and fat_price < mm_price:
                if fat_price not in active_signals:
                    active_signals[fat_price] = {
                        "fat_qty": fat_qty,
                        "timestamp": datetime.now()
                    }
                    # Отправляем в Telegram, что нашли
                    await send_tg_message(f"🔍 НАЙДЕНА! {fat_qty} шт по {fat_price:.2f} | ММ: {mm_price:.2f}")
            
            # 5. Проверяем, не выкупили ли дядьку
            current_asks = {price: qty for price, qty in asks}
            for price, info in list(active_signals.items()):
                if price not in current_asks:
                    # Дядька исчез — выкуплен!
                    time_to_buy = (datetime.now() - info["timestamp"]).total_seconds()
                    save_signal_to_csv({
                        "datetime": info["timestamp"].strftime('%Y-%m-%d %H:%M:%S'),
                        "fat_price": price,
                        "fat_qty": info["fat_qty"],
                        "mm_price": mm_price
                    })
                    await send_tg_message(f"✅ ВЫКУПЛЕН! За {time_to_buy:.1f} сек")
                    del active_signals[price]
            
            await asyncio.sleep(2)  # Пауза, чтобы не спамить запросы
            
        except Exception as e:
            print(f"Ошибка в мониторинге: {e}")
            await asyncio.sleep(5)

async def main():
    init_csv()
    await send_tg_message("🚀 FatCatHunterBot запущен на Amvera!")
    await monitor_market()

if __name__ == "__main__":
    asyncio.run(main())
