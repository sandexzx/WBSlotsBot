#!/usr/bin/env python3
import sys
import os
import time
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Добавляем src в путь для импорта модулей
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from google_sheets_parser import create_parser_from_env
from wb_api import WBMonitor, WildBerriesAPI


class WBSlotsMonitor:
    def __init__(self, update_interval: int = 300, telegram_notifier=None):  # 5 минут по умолчанию
        self.update_interval = update_interval
        self.sheets_parser = create_parser_from_env()
        self.wb_monitor = WBMonitor()
        self.last_update = None
        self.cycle_count = 0
        self.telegram_notifier = telegram_notifier
        
        # Настройки для оптимизации API запросов
        self.api_requests_per_minute = 6  # Каждый endpoint имеет свой лимит 6/минуту
        self.api_pause_between_requests = 4  # начальная пауза между API циклами
        self.current_api_requests = 0
        self.parsed_data = None  # Кешируем данные парсинга
        
        # Адаптивные тайминги
        self.minute_start_time = None  # Время начала минутного цикла
        self.api_execution_times = []  # История времени выполнения API запросов
        self.target_minute_duration = 60  # Целевая длительность минуты в секундах
        
    def format_datetime(self, dt_str: str) -> str:
        """Форматирует дату для красивого вывода"""
        try:
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            return dt.strftime('%d.%m %H:%M')
        except:
            return dt_str
    
    def print_separator(self, char: str = "=", length: int = 80):
        """Печатает разделитель"""
        print(char * length)
    
    def print_header(self, text: str):
        """Печатает заголовок"""
        self.print_separator()
        print(f" {text}")
        self.print_separator()
    
    def calculate_adaptive_pause(self, api_execution_time: float) -> float:
        """
        Рассчитывает адаптивную паузу на основе времени выполнения API запросов
        
        Args:
            api_execution_time: Время выполнения последнего API запроса
            
        Returns:
            Рекомендованная пауза в секундах
        """
        # Добавляем время последнего запроса в историю
        self.api_execution_times.append(api_execution_time)
        
        # Оставляем только последние 10 измерений для расчета среднего
        if len(self.api_execution_times) > 10:
            self.api_execution_times = self.api_execution_times[-10:]
        
        # Рассчитываем среднее время выполнения API запроса
        avg_api_time = sum(self.api_execution_times) / len(self.api_execution_times)
        
        # Определяем, сколько API запросов осталось до конца цикла
        remaining_requests = self.api_requests_per_minute - self.current_api_requests
        
        if remaining_requests <= 0:
            # Если это последний запрос в цикле, возвращаем время до начала новой минуты
            if self.minute_start_time:
                elapsed_time = time.time() - self.minute_start_time
                remaining_time = max(0, self.target_minute_duration - elapsed_time)
                return remaining_time
            return self.target_minute_duration
        
        # Рассчитываем оставшееся время в минуте
        if self.minute_start_time:
            elapsed_time = time.time() - self.minute_start_time
            remaining_time = max(0, self.target_minute_duration - elapsed_time)
        else:
            # Если это первый запрос, считаем что у нас есть вся минута
            remaining_time = self.target_minute_duration
        
        # Вычисляем время, которое потратим на оставшиеся API запросы
        estimated_api_time = remaining_requests * avg_api_time
        
        # Вычисляем общее время на паузы
        total_pause_time = remaining_time - estimated_api_time
        
        # Распределяем паузы равномерно между оставшимися запросами
        if remaining_requests > 0:
            adaptive_pause = max(1, total_pause_time / remaining_requests)  # Минимум 1 секунда
        else:
            adaptive_pause = self.api_pause_between_requests
        
        # Ограничиваем максимальную паузу
        adaptive_pause = min(adaptive_pause, 30)  # Максимум 30 секунд
        
        return adaptive_pause
    
    def reset_minute_cycle(self):
        """Сбрасывает счетчики для нового минутного цикла"""
        self.minute_start_time = time.time()
        self.current_api_requests = 0
        print(f"🔄 Начат новый минутный цикл: {datetime.now().strftime('%H:%M:%S')}")
    
    def log_adaptive_timing(self, api_time: float, adaptive_pause: float):
        """Логирует информацию об адаптивных таймингах"""
        if len(self.api_execution_times) > 1:
            avg_api_time = sum(self.api_execution_times) / len(self.api_execution_times)
            print(f"📊 Среднее время API: {avg_api_time:.2f}с")
        
        remaining_requests = self.api_requests_per_minute - self.current_api_requests
        print(f"⏱️  Адаптивная пауза: {adaptive_pause:.1f}с (осталось {remaining_requests} запросов)")
        
        if self.minute_start_time:
            elapsed_time = time.time() - self.minute_start_time
            remaining_minute_time = max(0, self.target_minute_duration - elapsed_time)
            print(f"⏰ Время в текущей минуте: {elapsed_time:.1f}с / {self.target_minute_duration}с (осталось: {remaining_minute_time:.1f}с)")
    
    def display_monitoring_results(self, parsed_data: Dict[str, Any], monitoring_results: Dict[str, Any]):
        """Выводит результаты мониторинга в консоль"""
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.print_header(f"МОНИТОРИНГ СЛОТОВ WB - {timestamp}")
        
        if not monitoring_results.get('success'):
            print(f"❌ ОШИБКА МОНИТОРИНГА: {monitoring_results.get('error', 'Неизвестная ошибка')}")
            return
        
        summary = monitoring_results.get('summary', {})
        print(f"📊 Обработано листов: {summary.get('total_sheets', 0)}")
        print(f"✅ Листов с доступными слотами: {summary.get('sheets_with_slots', 0)}")
        print(f"🎯 Всего найдено слотов: {summary.get('total_available_slots', 0)}")
        print()
        
        # Обрабатываем каждый лист
        for sheet_name, sheet_data in parsed_data.get('sheets', {}).items():
            monitoring_data = monitoring_results.get('sheets', {}).get(sheet_name, {})
            
            print(f"📋 ЛИСТ: {sheet_name}")
            print(f"📅 Период: {sheet_data.get('start_date', 'N/A')} - {sheet_data.get('end_date', 'N/A')}")
            
            # Показываем ошибки, если есть
            errors = monitoring_data.get('errors', [])
            if errors:
                print(f"⚠️  Ошибки: {'; '.join(errors)}")
            
            # Обрабатываем товары
            products = sheet_data.get('products', [])
            available_slots = monitoring_data.get('available_slots', [])
            warehouse_ids = monitoring_data.get('warehouse_ids', {})
            available_options = monitoring_data.get('available_options', {})
            
            if not products:
                print("   Нет товаров для мониторинга")
                print()
                continue
            
            # Группируем данные для удобного отображения
            self.display_products_analysis(products, available_slots, warehouse_ids, available_options)
            print()
    
    def display_products_analysis(self, products: List[Dict], available_slots: List[Dict], 
                                warehouse_ids: Dict[str, int], available_options: Dict[str, Any]):
        """Отображает анализ товаров с группировкой по баркодам"""
        
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
            
            print(f"📦 БАРКОД: {barcode} (Количество: {quantity})")
            
            # Проверяем опции приемки для этого баркода
            barcode_options = options_by_barcode.get(barcode)
            
            if not barcode_options:
                print("   ❌ Нет данных об опциях приемки")
                continue
            
            if barcode_options.get('isError'):
                error = barcode_options.get('error', {})
                print(f"   ❌ ОШИБКА: {error.get('title', 'Unknown')} - {error.get('detail', 'No details')}")
                continue
            
            warehouses_for_barcode = barcode_options.get('warehouses', [])
            if not warehouses_for_barcode:
                print("   ❌ Нет доступных складов для этого товара")
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
                print(f"   🏪 {warehouse_name} (ID: {warehouse_id})")
                
                # Показываем доступные упаковки
                if available_packaging:
                    packaging_list = [f"{emoji} {name}" for name, emoji in available_packaging.items()]
                    print(f"      Упаковки: {', '.join(packaging_list)}")
                else:
                    print("      ❌ Нет доступных упаковок")
                
                # Показываем только подходящие слоты
                print("      📅 Доступные слоты:")
                
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
                    print("         ❌ Нет подходящих слотов")
                else:
                    for date in sorted_dates:
                        date_slots = slots_by_date[date]
                        formatted_date = self.format_datetime(date)
                        
                        for slot in date_slots:
                            coefficient = slot['coefficient']
                            box_type = slot['box_type']
                            
                            if coefficient == 0:
                                cost_info = "🆓 Бесплатно"
                            else:
                                cost_info = f"💰 Множитель: {coefficient}"
                            
                            print(f"         {formatted_date} ({box_type}): {cost_info}")
                
                print()  # Пустая строка между складами
            
            if not has_available_warehouses:
                print("   ❌ Нет доступных складов с открытыми слотами")
            
            print("-" * 60)  # Разделитель между товарами
    
    def run_parsing_cycle(self) -> Dict[str, Any]:
        """Выполняет парсинг Google таблиц"""
        parse_start = time.time()
        
        try:
            print("🔄 Парсинг Google таблиц...")
            
            # Получаем данные в формате словаря {sheet_name: SheetsData}
            sheets_data = self.sheets_parser.parse_all_sheets()
            
            # Преобразуем в нужный формат
            self.parsed_data = self.sheets_parser.to_dict(sheets_data)
            
            parse_time = time.time() - parse_start
            
            if not self.parsed_data.get('sheets'):
                return {
                    'success': False,
                    'error': 'Не удалось получить данные из Google таблиц',
                    'parse_time': parse_time
                }
            
            sheets_count = len(self.parsed_data['sheets'])
            total_products = sum(len(sheet.get('products', [])) for sheet in self.parsed_data['sheets'].values())
            
            print(f"✅ Парсинг завершен за {parse_time:.2f}с. Найдено листов: {sheets_count}, товаров: {total_products}")
            print(f"🚀 Оптимизация: Будет выполнено ровно 3 API запроса (склады + коэффициенты + все товары)")
            print(f"📦 Все {total_products} товаров будут отправлены одним POST запросом")
            
            return {
                'success': True,
                'parse_time': parse_time
            }
            
        except Exception as e:
            parse_time = time.time() - parse_start
            return {
                'success': False,
                'error': str(e),
                'parse_time': parse_time
            }
    
    async def run_api_request(self) -> Dict[str, Any]:
        """Выполняет один API запрос с проверкой остановки"""
        if not self.parsed_data:
            return {
                'success': False,
                'error': 'Нет данных для API запроса. Сначала выполните парсинг.',
                'api_time': 0
            }
        
        api_start = time.time()
        
        try:
            print(f"🔄 API запрос #{self.current_api_requests + 1}/6...")
            
            # Сохраняем parsed_data во временный файл для WBMonitor
            temp_file = 'temp_parsed_data.json'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.parsed_data, f, ensure_ascii=False, indent=2)
            
            try:
                # Выполняем API запрос в executor чтобы он был прерываемым
                loop = asyncio.get_event_loop()
                monitoring_results = await loop.run_in_executor(
                    None, 
                    self.wb_monitor.monitor_parsed_data, 
                    temp_file
                )
            finally:
                # Удаляем временный файл
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            
            api_time = time.time() - api_start
            self.current_api_requests += 1
            
            print(f"✅ API запрос завершен за {api_time:.2f}с")
            
            # Отображение результатов
            self.display_monitoring_results(self.parsed_data, monitoring_results)
            
            # Отправляем уведомление в Telegram если есть telegram_notifier
            if self.telegram_notifier:
                try:
                    await self.telegram_notifier.send_notification(self.parsed_data, monitoring_results)
                except Exception as e:
                    print(f"⚠️  Ошибка отправки Telegram уведомления: {e}")
            
            return {
                'success': True,
                'monitoring_results': monitoring_results,
                'api_time': api_time
            }
            
        except asyncio.CancelledError:
            print("🛑 API запрос отменен")
            api_time = time.time() - api_start
            return {
                'success': False,
                'error': 'API запрос отменен',
                'api_time': api_time
            }
        except Exception as e:
            api_time = time.time() - api_start
            return {
                'success': False,
                'error': str(e),
                'api_time': api_time
            }
    
    async def run_optimized_cycle(self) -> Dict[str, Any]:
        """Выполняет оптимизированный цикл: парсинг + API запрос"""
        cycle_start_time = time.time()
        
        # 1. Парсинг (только если начинаем новый минутный цикл)
        if self.current_api_requests == 0:
            # Начинаем новый минутный цикл
            self.reset_minute_cycle()
            
            parse_result = self.run_parsing_cycle()
            if not parse_result['success']:
                return {
                    'success': False,
                    'error': parse_result['error'],
                    'parse_time': parse_result['parse_time'],
                    'api_time': 0,
                    'total_time': time.time() - cycle_start_time,
                    'cycle_type': 'parse_failed'
                }
        else:
            parse_result = {'success': True, 'parse_time': 0}
        
        # 2. API запрос
        api_result = await self.run_api_request()
        
        total_time = time.time() - cycle_start_time
        
        # Определяем тип цикла и сбрасываем счетчик если нужно
        if self.current_api_requests == 1:
            cycle_type = 'parse_and_api'  # Парсинг + первый API
        elif self.current_api_requests < self.api_requests_per_minute:
            cycle_type = 'api_only'  # Только API
        else:
            cycle_type = 'api_final'  # Последний API в серии
            self.current_api_requests = 0  # Сбрасываем счетчик для следующего минутного цикла
        
        return {
            'success': api_result['success'],
            'error': api_result.get('error'),
            'parse_time': parse_result['parse_time'],
            'api_time': api_result['api_time'],
            'total_time': total_time,
            'cycle_type': cycle_type,
            'api_requests_count': self.current_api_requests if cycle_type != 'api_final' else self.api_requests_per_minute
        }
    
    async def run_continuous_monitoring(self, shutdown_event=None):
        """Запускает оптимизированный непрерывный мониторинг"""
        print("🚀 Запуск АДАПТИВНОГО мониторинга WB слотов")
        print(f"🎯 ОПТИМИЗАЦИЯ: Точно 3 API запроса за цикл (склады + коэффициенты + все товары)")
        print(f"🧠 АДАПТИВНЫЕ ПАУЗЫ: Динамический расчет пауз на основе реального времени API")
        print(f"📋 Стратегия: Парсинг + API → адаптивная пауза → API → адаптивная пауза → повтор")
        print(f"⚡ Лимит WB: {self.api_requests_per_minute} запросов/минуту для КАЖДОГО endpoint'а")
        print(f"🎯 Цель: {self.api_requests_per_minute} циклов ровно за {self.target_minute_duration} секунд")
        self.print_separator()
        
        try:
            while True:
                # Проверяем флаг остановки перед каждым циклом
                if shutdown_event and shutdown_event.is_set():
                    print("\n🛑 Получен сигнал остановки мониторинга")
                    break
                    
                self.cycle_count += 1
                
                # Выполняем оптимизированный цикл
                result = await self.run_optimized_cycle()
                
                # Определяем тип сообщения
                cycle_type = result.get('cycle_type', 'unknown')
                
                if cycle_type == 'parse_and_api':
                    print(f"\n🔄 ЦИКЛ #{self.cycle_count} [ПАРСИНГ + API #1] - {datetime.now().strftime('%H:%M:%S')}")
                elif cycle_type == 'api_only':
                    api_num = result.get('api_requests_count', 0)
                    print(f"\n🔄 ЦИКЛ #{self.cycle_count} [API #{api_num}] - {datetime.now().strftime('%H:%M:%S')}")
                elif cycle_type == 'api_final':
                    print(f"\n🔄 ЦИКЛ #{self.cycle_count} [API #6 - ФИНАЛ] - {datetime.now().strftime('%H:%M:%S')}")
                
                # Логируем время выполнения
                if result['success']:
                    print(f"\n⏱️  ВРЕМЯ ВЫПОЛНЕНИЯ:")
                    if result['parse_time'] > 0:
                        print(f"   📊 Парсинг таблиц: {result['parse_time']:.2f}с")
                    print(f"   🌐 API запрос: {result['api_time']:.2f}с")
                    print(f"   ⚡ Общее время: {result['total_time']:.2f}с")
                    
                    # Сохраняем последнее успешное обновление
                    self.last_update = datetime.now()
                    
                    # Рассчитываем адаптивную паузу
                    adaptive_pause = self.calculate_adaptive_pause(result['api_time'])
                    
                    # Определяем следующую паузу и действие
                    if cycle_type == 'api_final':
                        next_action = "новый цикл с парсингом"
                        print(f"🎯 Завершена серия из {self.api_requests_per_minute} API запросов")
                    else:
                        next_action = f"API запрос #{result.get('api_requests_count', 0) + 1}"
                    
                    # Логируем адаптивные тайминги
                    self.log_adaptive_timing(result['api_time'], adaptive_pause)
                    next_pause = adaptive_pause
                        
                else:
                    print(f"\n❌ ОШИБКА ЦИКЛА: {result['error']}")
                    print(f"⏱️  Время до ошибки: {result['total_time']:.2f}с")
                    next_pause = self.api_pause_between_requests
                    next_action = "повтор"
                
                # Ждем до следующего действия с проверкой shutdown
                print(f"\n😴 Адаптивная пауза {next_pause:.1f}с до: {next_action}")
                next_time = (datetime.now() + timedelta(seconds=next_pause)).strftime('%H:%M:%S')
                print(f"⏰ Следующее действие в: {next_time}")
                    
                self.print_separator(".", 60)
                
                # Прерываемый sleep с проверкой shutdown_event
                if shutdown_event:
                    try:
                        await asyncio.wait_for(shutdown_event.wait(), timeout=next_pause)
                        print("\n🛑 Получен сигнал остановки во время паузы")
                        break
                    except asyncio.TimeoutError:
                        # Timeout означает что пауза закончилась и можно продолжать
                        pass
                else:
                    await asyncio.sleep(next_pause)
                
        except asyncio.CancelledError:
            print(f"\n\n🛑 Мониторинг отменен")
            print(f"📊 Выполнено циклов: {self.cycle_count}")
            print(f"🌐 Выполнено API запросов: {self.current_api_requests}")
            if self.last_update:
                print(f"🕐 Последнее обновление: {self.last_update.strftime('%Y-%m-%d %H:%M:%S')}")
        except KeyboardInterrupt:
            print(f"\n\n🛑 Мониторинг остановлен пользователем")
            print(f"📊 Выполнено циклов: {self.cycle_count}")
            print(f"🌐 Выполнено API запросов: {self.current_api_requests}")
            if self.last_update:
                print(f"🕐 Последнее обновление: {self.last_update.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as e:
            print(f"\n\n💥 КРИТИЧЕСКАЯ ОШИБКА: {str(e)}")
            print(f"📊 Выполнено циклов: {self.cycle_count}")
            print(f"🌐 Выполнено API запросов: {self.current_api_requests}")


async def main():
    """Основная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Мониторинг слотов поставок WildBerries')
    parser.add_argument('--interval', '-i', type=int, default=300, 
                       help='Интервал обновления в секундах (по умолчанию: 300)')
    parser.add_argument('--once', action='store_true', 
                       help='Выполнить только один цикл мониторинга')
    
    args = parser.parse_args()
    
    monitor = WBSlotsMonitor(update_interval=args.interval)
    
    if args.once:
        print("🔄 Выполнение одного оптимизированного цикла...")
        result = await monitor.run_optimized_cycle()
        
        if result['success']:
            print(f"\n✅ Цикл завершен успешно за {result['total_time']:.2f}с")
            if result['parse_time'] > 0:
                print(f"📊 Парсинг: {result['parse_time']:.2f}с")
            print(f"🌐 API: {result['api_time']:.2f}с")
            print(f"🎯 Тип цикла: {result['cycle_type']}")
        else:
            print(f"\n❌ Ошибка мониторинга: {result['error']}")
            sys.exit(1)
    else:
        await monitor.run_continuous_monitoring()


if __name__ == "__main__":
    asyncio.run(main())