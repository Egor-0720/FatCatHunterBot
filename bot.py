import asyncio
import csv
import os
from datetime import datetime
import aiohttp
from BCSPy import BCSPy

# ========== ТОКЕНЫ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ (Amvera) ==========
BCS_TOKEN = os.getenv("BCS_TOKEN")
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

if not BCS_TOKEN:
    raise Exception("Ошибка: BCS_TOKEN не найден!")
if not TG_BOT_TOKEN or not TG_CHAT_ID:
    raise Exception("Ошибка: Токены Telegram не найдены!")

# ========== НАСТРОЙКИ ==========
FIGI = "BBG004S683W8"
ASK_LEVELS = 10
FAT_FACTOR = 7.0
MM_MIN_QTY = 20000
CSV_FILE = "/data/signals.csv"          # <--- ИСПРАВЛЕНО

active_signals = {}

def init_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["datetime", "fat_price", "fat_qty", "mm_price"])

def save_signal_to_csv(signal_data):
    with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([signal_data["datetime"], signal_data["fat_price"], 
                         signal_data["fat_qty"], signal_data["mm_price"]])

async def send_tg_message(text: str):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    async with aiohttp.ClientSession() as session:
        try:
            await session.post(url, json={"chat_id": TG_CHAT_ID, "text": text})
        except:
            pass

async def monitor_market():
    global active_signals
    bp_provider = BCSPy(BCS_TOKEN)
    
    while True:
        try:
            orderbook = bp_provider.get_orderbook(figi=FIGI, depth=ASK_LEVELS)
            asks = orderbook.get('asks', [])
            
            if not asks:
                await asyncio.sleep(2)
                continue
            
            avg_qty = sum(q for _, q in asks) / len(asks)
            
            fat_price, fat_qty = None, None
            for price, qty in asks:
                if qty >= avg_qty * FAT_FACTOR:
                    fat_price, fat_qty = price, qty
                    break
            
            mm_price = None
            for price, qty in asks:
                if qty >= MM_MIN_QTY:
                    mm_price = price
                    break
            
            if fat_price and mm_price and fat_price < mm_price:
                if fat_price not in active_signals:
                    active_signals[fat_price] = {
                        "fat_qty": fat_qty,
                        "timestamp": datetime.now()
                    }
                    await send_tg_message(f"🔍 НАЙДЕНА! {fat_qty} шт по {fat_price:.2f} | ММ: {mm_price:.2f}")
            
            current_asks = {price: qty for price, qty in asks}
            for price, info in list(active_signals.items()):
                if price not in current_asks:
                    time_to_buy = (datetime.now() - info["timestamp"]).total_seconds()
                    save_signal_to_csv({
                        "datetime": info["timestamp"].strftime('%Y-%m-%d %H:%M:%S'),
                        "fat_price": price,
                        "fat_qty": info["fat_qty"],
                        "mm_price": mm_price
                    })
                    await send_tg_message(f"✅ ВЫКУПЛЕН! За {time_to_buy:.1f} сек")
                    del active_signals[price]
            
            await asyncio.sleep(2)
        except Exception as e:
            print(f"Ошибка: {e}")
            await asyncio.sleep(5)

async def main():
    init_csv()
    await send_tg_message("🚀 FatCatHunterBot запущен на Amvera!")
    await monitor_market()

if __name__ == "__main__":
    asyncio.run(main())
