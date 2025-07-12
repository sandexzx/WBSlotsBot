#!/usr/bin/env python3
"""
Главный скрипт для запуска WB Slots Monitor с Telegram ботом
Запускает мониторинг WildBerries слотов и Telegram бота в параллельных процессах
"""

import asyncio
import signal
import sys
import os
import logging
from typing import Optional

# Добавляем текущую директорию в путь для импорта модулей
sys.path.append(os.path.dirname(__file__))

from wb_monitor import WBSlotsMonitor
from telegram_bot import create_telegram_notifier

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/main.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Глобальная переменная для флага остановки
shutdown_event = asyncio.Event()


class WBTelegramService:
    """Основной сервис, объединяющий мониторинг WB и Telegram бота"""
    
    def __init__(self, update_interval: int = 300):
        self.update_interval = update_interval
        self.telegram_notifier: Optional = None
        self.wb_monitor: Optional[WBSlotsMonitor] = None
        self.running = False
        
        # Создаем директорию для логов если её нет
        os.makedirs('logs', exist_ok=True)
    
    async def initialize(self):
        """Инициализирует компоненты сервиса"""
        try:
            logger.info("🚀 Инициализация WB Telegram Service...")
            
            # Создаем Telegram notifier
            logger.info("📱 Создание Telegram бота...")
            self.telegram_notifier = create_telegram_notifier()
            
            # Создаем WB monitor с интеграцией Telegram
            logger.info("📊 Создание WB монитора...")
            self.wb_monitor = WBSlotsMonitor(
                update_interval=self.update_interval,
                telegram_notifier=self.telegram_notifier
            )
            
            logger.info("✅ Инициализация завершена успешно")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации: {e}")
            raise
    
    async def start_telegram_bot(self):
        """Запускает Telegram бота с graceful shutdown"""
        try:
            logger.info("🤖 Запуск Telegram бота...")
            # Создаем задачу для бота
            bot_polling_task = asyncio.create_task(self.telegram_notifier.start_bot())
            
            # Ждем либо завершения бота, либо сигнала остановки
            done, pending = await asyncio.wait(
                [bot_polling_task, asyncio.create_task(shutdown_event.wait())],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Если получен сигнал остановки, отменяем бота
            if shutdown_event.is_set():
                logger.info("🛑 Остановка Telegram бота...")
                bot_polling_task.cancel()
                try:
                    await bot_polling_task
                except asyncio.CancelledError:
                    pass
            
            # Отменяем оставшиеся задачи
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
        except Exception as e:
            logger.error(f"❌ Ошибка запуска Telegram бота: {e}")
            raise
    
    async def start_wb_monitoring(self):
        """Запускает мониторинг WB с graceful shutdown"""
        try:
            logger.info("📡 Запуск мониторинга WB слотов...")
            # Передаем shutdown_event в мониторинг
            await self.wb_monitor.run_continuous_monitoring(shutdown_event)
        except Exception as e:
            logger.error(f"❌ Ошибка мониторинга WB: {e}")
            raise
    
    async def run(self):
        """Основной метод запуска сервиса с принудительным завершением"""        
        try:
            # Инициализация
            await self.initialize()
            
            self.running = True
            logger.info("🎯 Запуск сервиса WB Telegram Monitor...")
            
            print("=" * 80)
            print("🚀 WB SLOTS MONITOR С TELEGRAM БОТОМ")
            print("=" * 80)
            print("📱 Telegram бот: Готов к приему подписчиков")
            print("📊 WB Мониторинг: Отслеживает доступные слоты")
            print("🔔 Уведомления: Автоматическая отправка в Telegram")
            print("=" * 80)
            print("Для остановки нажмите Ctrl+C (принудительное завершение через 3 сек)")
            print("=" * 80)
            
            # Создаем задачи
            bot_task = asyncio.create_task(self.start_telegram_bot())
            monitor_task = asyncio.create_task(self.start_wb_monitoring())
            
            # Запускаем shutdown watcher
            async def shutdown_watcher():
                await shutdown_event.wait()
                logger.info("🛑 Shutdown watcher: отменяем все задачи")
                bot_task.cancel()
                monitor_task.cancel()
            
            shutdown_task = asyncio.create_task(shutdown_watcher())
            
            # Ждем любое завершение
            try:
                await asyncio.gather(bot_task, monitor_task, shutdown_task, return_exceptions=True)
            except asyncio.CancelledError:
                logger.info("🛑 Задачи отменены")
            
        except Exception as e:
            logger.error(f"💥 Критическая ошибка сервиса: {e}")
            raise
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Корректное завершение работы сервиса"""
        if not self.running:
            return
            
        logger.info("🛑 Завершение работы сервиса...")
        self.running = False
        
        # Устанавливаем флаг остановки
        shutdown_event.set()
        
        try:
            if self.telegram_notifier:
                await self.telegram_notifier.stop_bot()
                logger.info("✅ Telegram бот остановлен")
        except Exception as e:
            logger.error(f"⚠️  Ошибка остановки Telegram бота: {e}")
        
        logger.info("🏁 Сервис завершен")


def setup_signal_handlers():
    """Настраивает обработчики сигналов для принудительного завершения"""
    def signal_handler(signum, frame):
        logger.info(f"📡 Получен сигнал {signum} - ПРИНУДИТЕЛЬНОЕ ЗАВЕРШЕНИЕ")
        shutdown_event.set()
        
        # Принудительно завершаем через 3 секунды если graceful shutdown не сработал
        def force_exit():
            import time
            time.sleep(3)
            logger.warning("⚠️ Принудительное завершение через 3 секунды")
            os._exit(1)
        
        import threading
        force_thread = threading.Thread(target=force_exit, daemon=True)
        force_thread.start()
    
    # Регистрируем обработчики только для Unix сигналов
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
    if hasattr(signal, 'SIGINT'):
        signal.signal(signal.SIGINT, signal_handler)


async def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description='WB Slots Monitor с Telegram ботом')
    parser.add_argument('--interval', '-i', type=int, default=300,
                       help='Интервал мониторинга в секундах (по умолчанию: 300)')
    
    args = parser.parse_args()
    
    # Настраиваем обработчики сигналов
    setup_signal_handlers()
    
    # Создаем сервис
    service = WBTelegramService(update_interval=args.interval)
    
    try:
        # Запускаем сервис
        await service.run()
        
    except KeyboardInterrupt:
        logger.info("⌨️  Получен Ctrl+C")
        
    except Exception as e:
        logger.error(f"💥 Неожиданная ошибка: {e}")
        sys.exit(1)
    
    finally:
        # Graceful shutdown всегда выполняется
        await service.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Сервис остановлен пользователем")
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
        sys.exit(1)