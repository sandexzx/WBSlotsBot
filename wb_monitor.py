#!/usr/bin/env python3
import sys
import os
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Добавляем src в путь для импорта модулей
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from google_sheets_parser import create_parser_from_env
from wb_api import WBMonitor, WildBerriesAPI


class WBSlotsMonitor:
    def __init__(self, update_interval: int = 300):  # 5 минут по умолчанию
        self.update_interval = update_interval
        self.sheets_parser = create_parser_from_env()
        self.wb_monitor = WBMonitor()
        self.last_update = None
        self.cycle_count = 0
        
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
    
    def run_monitoring_cycle(self) -> Dict[str, Any]:
        """Выполняет один цикл мониторинга"""
        cycle_start_time = time.time()
        
        try:
            # 1. Парсинг Google таблиц
            print("🔄 Парсинг Google таблиц...")
            parse_start = time.time()
            
            # Получаем данные в формате словаря {sheet_name: SheetsData}
            sheets_data = self.sheets_parser.parse_all_sheets()
            
            # Преобразуем в нужный формат
            parsed_data = self.sheets_parser.to_dict(sheets_data)
            
            parse_time = time.time() - parse_start
            
            if not parsed_data.get('sheets'):
                return {
                    'success': False,
                    'error': 'Не удалось получить данные из Google таблиц',
                    'parse_time': parse_time,
                    'api_time': 0,
                    'total_time': time.time() - cycle_start_time
                }
            
            print(f"✅ Парсинг завершен за {parse_time:.2f}с. Найдено листов: {len(parsed_data['sheets'])}")
            
            # 2. Мониторинг через API WB
            print("🔄 Запрос API WildBerries...")
            api_start = time.time()
            
            # Сохраняем parsed_data во временный файл для WBMonitor
            temp_file = 'temp_parsed_data.json'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(parsed_data, f, ensure_ascii=False, indent=2)
            
            try:
                monitoring_results = self.wb_monitor.monitor_parsed_data(temp_file)
            finally:
                # Удаляем временный файл
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            
            api_time = time.time() - api_start
            total_time = time.time() - cycle_start_time
            
            print(f"✅ API запросы завершены за {api_time:.2f}с")
            
            # 3. Отображение результатов
            self.display_monitoring_results(parsed_data, monitoring_results)
            
            return {
                'success': True,
                'parsed_data': parsed_data,
                'monitoring_results': monitoring_results,
                'parse_time': parse_time,
                'api_time': api_time,
                'total_time': total_time
            }
            
        except Exception as e:
            total_time = time.time() - cycle_start_time
            return {
                'success': False,
                'error': str(e),
                'parse_time': 0,
                'api_time': 0,
                'total_time': total_time
            }
    
    def run_continuous_monitoring(self):
        """Запускает непрерывный мониторинг"""
        print("🚀 Запуск непрерывного мониторинга WB слотов")
        print(f"⏰ Интервал обновления: {self.update_interval} секунд")
        self.print_separator()
        
        try:
            while True:
                self.cycle_count += 1
                
                print(f"\n🔄 ЦИКЛ #{self.cycle_count} - {datetime.now().strftime('%H:%M:%S')}")
                
                # Выполняем мониторинг
                result = self.run_monitoring_cycle()
                
                # Логируем время выполнения
                if result['success']:
                    print(f"\n⏱️  ВРЕМЯ ВЫПОЛНЕНИЯ:")
                    print(f"   Парсинг таблиц: {result['parse_time']:.2f}с")
                    print(f"   API запросы: {result['api_time']:.2f}с")
                    print(f"   Общее время: {result['total_time']:.2f}с")
                    
                    # Сохраняем последнее успешное обновление
                    self.last_update = datetime.now()
                else:
                    print(f"\n❌ ОШИБКА ЦИКЛА: {result['error']}")
                    print(f"⏱️  Время до ошибки: {result['total_time']:.2f}с")
                
                # Ждем до следующего цикла
                print(f"\n😴 Ожидание {self.update_interval} секунд до следующего цикла...")
                print(f"⏰ Следующий цикл в: {(datetime.now() + timedelta(seconds=self.update_interval)).strftime('%H:%M:%S')}")
                self.print_separator(".", 60)
                
                time.sleep(self.update_interval)
                
        except KeyboardInterrupt:
            print(f"\n\n🛑 Мониторинг остановлен пользователем")
            print(f"📊 Выполнено циклов: {self.cycle_count}")
            if self.last_update:
                print(f"🕐 Последнее обновление: {self.last_update.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as e:
            print(f"\n\n💥 КРИТИЧЕСКАЯ ОШИБКА: {str(e)}")
            print(f"📊 Выполнено циклов: {self.cycle_count}")


def main():
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
        print("🔄 Выполнение одного цикла мониторинга...")
        result = monitor.run_monitoring_cycle()
        
        if result['success']:
            print(f"\n✅ Мониторинг завершен успешно за {result['total_time']:.2f}с")
        else:
            print(f"\n❌ Ошибка мониторинга: {result['error']}")
            sys.exit(1)
    else:
        monitor.run_continuous_monitoring()


if __name__ == "__main__":
    main()