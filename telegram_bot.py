#!/usr/bin/env python3
import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Set, Dict, Any
from dataclasses import dataclass

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv(override=True)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TelegramNotifier:
    """Класс для отправки уведомлений через Telegram бота"""
    
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения")
        
        self.bot = Bot(token=self.bot_token)
        self.dp = Dispatcher(storage=MemoryStorage())
        self.subscribed_users: Set[int] = set()
        self.subscriptions_file = 'subscriptions.json'
        
        # Загружаем подписки из файла
        self.load_subscriptions()
        
        # Регистрируем обработчики
        self.register_handlers()
    
    def load_subscriptions(self):
        """Загружает список подписчиков из файла"""
        try:
            if os.path.exists(self.subscriptions_file):
                with open(self.subscriptions_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.subscribed_users = set(data.get('subscribed_users', []))
                logger.info(f"Загружено {len(self.subscribed_users)} подписчиков")
        except Exception as e:
            logger.error(f"Ошибка при загрузке подписок: {e}")
            self.subscribed_users = set()
    
    def save_subscriptions(self):
        """Сохраняет список подписчиков в файл"""
        try:
            data = {
                'subscribed_users': list(self.subscribed_users),
                'updated_at': datetime.now().isoformat()
            }
            with open(self.subscriptions_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Сохранено {len(self.subscribed_users)} подписчиков")
        except Exception as e:
            logger.error(f"Ошибка при сохранении подписок: {e}")
    
    def register_handlers(self):
        """Регистрирует обработчики команд"""
        
        @self.dp.message(Command("start"))
        async def cmd_start(message: types.Message):
            user_id = message.from_user.id
            username = message.from_user.username or "Неизвестно"
            
            # Автоматически подписываем пользователя
            self.subscribed_users.add(user_id)
            self.save_subscriptions()
            
            # Создаем клавиатуру с кнопкой отписки
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отписаться от уведомлений", callback_data="unsubscribe")]
            ])
            
            welcome_text = f"""
🎯 Добро пожаловать в WB Slots Monitor!

Привет, @{username}! 
Ты автоматически подписан на уведомления о доступных слотах поставок WildBerries.

🔔 Ты будешь получать сообщения о:
• Новых доступных слотах
• Бесплатных слотах (коэффициент 0)
• Слотах с низким коэффициентом

Чтобы отписаться от уведомлений, нажми кнопку ниже.
            """
            
            await message.answer(welcome_text.strip(), reply_markup=keyboard)
            logger.info(f"Новый пользователь подписан: {user_id} (@{username})")
        
        @self.dp.callback_query(lambda c: c.data == "unsubscribe")
        async def callback_unsubscribe(callback: types.CallbackQuery):
            user_id = callback.from_user.id
            username = callback.from_user.username or "Неизвестно"
            
            if user_id in self.subscribed_users:
                self.subscribed_users.remove(user_id)
                self.save_subscriptions()
                
                # Создаем клавиатуру с кнопкой подписки
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔔 Подписаться на уведомления", callback_data="subscribe")]
                ])
                
                await callback.message.edit_text(
                    "❌ Ты отписан от уведомлений.\n\nЧтобы снова подписаться, нажми кнопку ниже или отправь /start",
                    reply_markup=keyboard
                )
                logger.info(f"Пользователь отписался: {user_id} (@{username})")
            else:
                await callback.answer("Ты уже не подписан на уведомления", show_alert=True)
            
            await callback.answer()
        
        @self.dp.callback_query(lambda c: c.data == "subscribe")
        async def callback_subscribe(callback: types.CallbackQuery):
            user_id = callback.from_user.id
            username = callback.from_user.username or "Неизвестно"
            
            if user_id not in self.subscribed_users:
                self.subscribed_users.add(user_id)
                self.save_subscriptions()
                
                # Создаем клавиатуру с кнопкой отписки
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="❌ Отписаться от уведомлений", callback_data="unsubscribe")]
                ])
                
                await callback.message.edit_text(
                    "🔔 Ты подписан на уведомления о слотах WB!\n\nЧтобы отписаться, нажми кнопку ниже.",
                    reply_markup=keyboard
                )
                logger.info(f"Пользователь подписался: {user_id} (@{username})")
            else:
                await callback.answer("Ты уже подписан на уведомления", show_alert=True)
            
            await callback.answer()
    
    def format_datetime(self, dt_str: str) -> str:
        """Форматирует дату для красивого вывода"""
        try:
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            return dt.strftime('%d.%m %H:%M')
        except:
            return dt_str
    
    def format_monitoring_message(self, parsed_data: Dict[str, Any], monitoring_results: Dict[str, Any]) -> str:
        """Форматирует сообщение с результатами мониторинга в том же формате что и консоль"""
        
        if not monitoring_results.get('success'):
            return f"❌ Ошибка мониторинга: {monitoring_results.get('error', 'Неизвестная ошибка')}"
        
        timestamp = datetime.now().strftime('%d.%m.%Y %H:%M')
        summary = monitoring_results.get('summary', {})
        
        message_parts = [
            f"🎯 <b>WB SLOTS UPDATE - {timestamp}</b>",
            "",
            f"📊 Обработано листов: {summary.get('total_sheets', 0)}",
            f"✅ Листов с слотами: {summary.get('sheets_with_slots', 0)}",
            f"🎯 Найдено слотов: {summary.get('total_available_slots', 0)}",
            ""
        ]
        
        # Обрабатываем каждый лист
        for sheet_name, sheet_data in parsed_data.get('sheets', {}).items():
            monitoring_data = monitoring_results.get('sheets', {}).get(sheet_name, {})
            available_slots = monitoring_data.get('available_slots', [])
            available_options = monitoring_data.get('available_options', {})
            
            message_parts.append(f"📋 <b>{sheet_name}</b>")
            message_parts.append(f"📅 {sheet_data.get('start_date', 'N/A')} - {sheet_data.get('end_date', 'N/A')}")
            
            # Показываем ошибки, если есть
            errors = monitoring_data.get('errors', [])
            if errors:
                message_parts.append(f"⚠️ Ошибки: {'; '.join(errors)}")
            
            # Обрабатываем товары
            products = sheet_data.get('products', [])
            warehouse_ids = monitoring_data.get('warehouse_ids', {})
            
            if not products:
                message_parts.append("   Нет товаров для мониторинга")
                message_parts.append("")
                continue
            
            # Используем тот же алгоритм что и в консоли
            self.format_products_analysis_for_telegram(
                message_parts, products, available_slots, 
                warehouse_ids, available_options
            )
            message_parts.append("")
        
        # Ограничиваем длину сообщения
        message = "\n".join(message_parts)
        if len(message) > 4000:
            message = message[:3900] + "\n\n... (сообщение обрезано)"
        
        return message
    
    def format_products_analysis_for_telegram(self, message_parts: list, products: list, available_slots: list, 
                                            _warehouse_ids: dict, available_options: dict):
        """Форматирует анализ товаров для Telegram в том же формате что и консоль"""
        
        # Создаем словарь опций по баркодам
        options_by_barcode = {}
        if available_options and 'result' in available_options:
            for item in available_options['result']:
                barcode = item.get('barcode', '')
                options_by_barcode[barcode] = item
        
        # Создаем словарь слотов по складам
        slots_by_warehouse = {}
        for slot in available_slots:
            warehouse_id = slot['warehouse_id']
            if warehouse_id not in slots_by_warehouse:
                slots_by_warehouse[warehouse_id] = []
            slots_by_warehouse[warehouse_id].append(slot)
        
        # Обрабатываем каждый товар
        for product in products:
            barcode = product['barcode']
            quantity = product['quantity']
            
            message_parts.append(f"📦 <b>БАРКОД: {barcode}</b> (Количество: {quantity})")
            
            # Проверяем опции приемки для этого баркода
            barcode_options = options_by_barcode.get(barcode)
            
            if not barcode_options:
                message_parts.append("   ❌ Нет данных об опциях приемки")
                continue
            
            if barcode_options.get('isError'):
                error = barcode_options.get('error', {})
                message_parts.append(f"   ❌ ОШИБКА: {error.get('title', 'Unknown')} - {error.get('detail', 'No details')}")
                continue
            
            warehouses_for_barcode = barcode_options.get('warehouses', [])
            if not warehouses_for_barcode:
                message_parts.append("   ❌ Нет доступных складов для этого товара")
                continue
            
            # Отображаем информацию по каждому доступному складу
            has_available_warehouses = False
            
            for warehouse_option in warehouses_for_barcode:
                warehouse_id = warehouse_option['warehouseID']
                
                # Проверяем, есть ли этот склад в наших слотах
                warehouse_slots = slots_by_warehouse.get(warehouse_id, [])
                
                if not warehouse_slots:
                    continue  # Пропускаем склады без доступных слотов
                
                warehouse_name = warehouse_slots[0]['warehouse_name']  # Берем название из слотов
                
                # Определяем доступные упаковки для товара на этом складе
                available_packaging = {}
                if warehouse_option.get('canBox'):
                    available_packaging['Короба'] = '📦'
                if warehouse_option.get('canMonopallet'):
                    available_packaging['Монопаллеты'] = '🚛'
                if warehouse_option.get('canSupersafe'):
                    available_packaging['Суперсейф'] = '🔒'
                
                # Фильтруем слоты только по доступным упаковкам
                filtered_slots = []
                for slot in warehouse_slots:
                    if slot['box_type'] in available_packaging:
                        filtered_slots.append(slot)
                
                if not filtered_slots:
                    continue  # Пропускаем склады без подходящих слотов
                
                has_available_warehouses = True
                message_parts.append(f"   🏪 <b>{warehouse_name}</b> (ID: {warehouse_id})")
                
                # Показываем доступные упаковки
                if available_packaging:
                    packaging_list = [f"{emoji} {name}" for name, emoji in available_packaging.items()]
                    message_parts.append(f"      Упаковки: {', '.join(packaging_list)}")
                else:
                    message_parts.append("      ❌ Нет доступных упаковок")
                
                # Показываем только подходящие слоты
                message_parts.append("      📅 Доступные слоты:")
                
                # Группируем отфильтрованные слоты по дате
                slots_by_date = {}
                for slot in filtered_slots:
                    date = slot['date']
                    if date not in slots_by_date:
                        slots_by_date[date] = []
                    slots_by_date[date].append(slot)
                
                # Сортируем даты
                sorted_dates = sorted(slots_by_date.keys())
                
                if not sorted_dates:
                    message_parts.append("         ❌ Нет подходящих слотов")
                else:
                    for date in sorted_dates:
                        date_slots = slots_by_date[date]
                        formatted_date = self.format_datetime(date)
                        
                        for slot in date_slots:
                            coefficient = slot['coefficient']
                            box_type = slot['box_type']
                            
                            if coefficient == 0:
                                cost_info = "🆓 <b>Бесплатно</b>"
                            else:
                                cost_info = f"💰 Множитель: {coefficient}"
                            
                            message_parts.append(f"         {formatted_date} ({box_type}): {cost_info}")
                
                message_parts.append("")  # Пустая строка между складами
            
            if not has_available_warehouses:
                message_parts.append("   ❌ Нет доступных складов с открытыми слотами")
            
            message_parts.append("-" * 60)  # Разделитель между товарами
    
    async def send_notification(self, parsed_data: Dict[str, Any], monitoring_results: Dict[str, Any]):
        """Отправляет уведомление всем подписчикам"""
        
        if not self.subscribed_users:
            logger.info("Нет подписчиков для отправки уведомлений")
            return
        
        message = self.format_monitoring_message(parsed_data, monitoring_results)
        
        # Отправляем сообщение всем подписчикам
        successful_sends = 0
        failed_sends = 0
        
        for user_id in self.subscribed_users.copy():  # Копия для безопасного изменения
            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )
                successful_sends += 1
                await asyncio.sleep(0.1)  # Небольшая пауза между отправками
                
            except Exception as e:
                logger.error(f"Ошибка отправки сообщения пользователю {user_id}: {e}")
                
                # Если пользователь заблокировал бота, удаляем его из подписчиков
                if "blocked" in str(e).lower() or "chat not found" in str(e).lower():
                    self.subscribed_users.remove(user_id)
                    logger.info(f"Пользователь {user_id} удален из подписчиков (заблокирован)")
                
                failed_sends += 1
        
        # Сохраняем обновленный список подписчиков
        if failed_sends > 0:
            self.save_subscriptions()
        
        logger.info(f"Уведомления отправлены: {successful_sends} успешно, {failed_sends} ошибок")
    
    async def start_bot(self):
        """Запускает бота"""
        logger.info("Запуск Telegram бота...")
        await self.dp.start_polling(self.bot)
    
    async def stop_bot(self):
        """Останавливает бота"""
        logger.info("Остановка Telegram бота...")
        await self.bot.session.close()


def create_telegram_notifier():
    """Создает экземпляр TelegramNotifier"""
    return TelegramNotifier()


if __name__ == "__main__":
    # Тестовый запуск бота
    async def main():
        notifier = create_telegram_notifier()
        await notifier.start_bot()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")