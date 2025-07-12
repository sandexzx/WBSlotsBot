import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from wb_api import WBMonitor, WildBerriesAPI
import json
from datetime import datetime


def test_individual_api_methods():
    """Тестирует отдельные методы API"""
    print("=== Тестирование отдельных методов API ===\n")
    
    api = WildBerriesAPI()
    
    # Тест получения складов
    print("1. Тестируем получение списка складов...")
    warehouses = api.get_warehouses()
    if warehouses['success']:
        print(f"✓ Получено {len(warehouses['data'])} складов")
    else:
        print(f"✗ Ошибка: {warehouses['error']}")
    
    # Тест получения коэффициентов
    print("\n2. Тестируем получение коэффициентов приемки...")
    coefficients = api.get_acceptance_coefficients()
    if coefficients['success']:
        print(f"✓ Получено {len(coefficients['data'])} записей коэффициентов")
    else:
        print(f"✗ Ошибка: {coefficients['error']}")
    
    # Тест поиска ID складов
    print("\n3. Тестируем поиск ID складов по названиям...")
    test_warehouse_names = ["Казань", "Новосибирск", "Электросталь", "несуществующий_склад"]
    warehouse_ids = api.find_warehouse_ids_by_names(test_warehouse_names)
    
    for name, wid in warehouse_ids.items():
        status = "✓" if wid else "✗"
        print(f"{status} {name}: {wid}")
    
    return {
        'warehouses': warehouses,
        'coefficients': coefficients,
        'warehouse_ids': warehouse_ids
    }


def test_monitoring_with_real_data():
    """Тестирует мониторинг с реальными данными из parsed_data.json"""
    print("\n=== Тестирование мониторинга с реальными данными ===\n")
    
    monitor = WBMonitor()
    
    # Запускаем мониторинг
    results = monitor.monitor_parsed_data()
    
    if not results['success']:
        print(f"✗ Ошибка мониторинга: {results['error']}")
        return results
    
    print("✓ Мониторинг выполнен успешно!")
    print(f"Обработано листов: {results['summary']['total_sheets']}")
    print(f"Листов с доступными слотами: {results['summary']['sheets_with_slots']}")
    print(f"Всего доступных слотов: {results['summary']['total_available_slots']}")
    
    # Детали по каждому листу
    print("\n--- Детали по листам ---")
    for sheet_name, sheet_result in results['sheets'].items():
        print(f"\nЛист: {sheet_name}")
        print(f"Склады в таблице: {', '.join(sheet_result.get('warehouse_ids', {}).keys())}")
        
        # Показываем найденные ID складов
        found_warehouses = [f"{name}:{wid}" for name, wid in sheet_result.get('warehouse_ids', {}).items() if wid]
        if found_warehouses:
            print(f"Найденные склады: {', '.join(found_warehouses)}")
        
        # Показываем доступные слоты
        available_slots = sheet_result.get('available_slots', [])
        if available_slots:
            print(f"Доступных слотов: {len(available_slots)}")
            
            # Группируем по складам
            slots_by_warehouse = {}
            for slot in available_slots:
                warehouse_name = slot['warehouse_name']
                if warehouse_name not in slots_by_warehouse:
                    slots_by_warehouse[warehouse_name] = []
                slots_by_warehouse[warehouse_name].append(slot)
            
            for warehouse_name, slots in slots_by_warehouse.items():
                free_slots = len([s for s in slots if s['is_free']])
                paid_slots = len(slots) - free_slots
                print(f"  {warehouse_name}: {len(slots)} слотов (бесплатных: {free_slots}, платных: {paid_slots})")
        else:
            print("Доступных слотов: 0")
        
        # Показываем ошибки
        if sheet_result.get('errors'):
            print(f"Ошибки: {'; '.join(sheet_result['errors'])}")
    
    # Сохраняем результаты
    filename = monitor.save_monitoring_results(results)
    print(f"\n✓ Результаты сохранены в: {filename}")
    
    return results


def test_specific_products():
    """Тестирует опции приемки для конкретных товаров"""
    print("\n=== Тестирование опций приемки для конкретных товаров ===\n")
    
    api = WildBerriesAPI()
    
    # Загружаем данные из parsed_data.json
    try:
        with open('test/test_output/parsed_data.json', 'r', encoding='utf-8') as f:
            parsed_data = json.load(f)
    except Exception as e:
        print(f"✗ Не удалось загрузить parsed_data.json: {e}")
        return None
    
    # Берем товары из листа "Тест"
    test_sheet = parsed_data['sheets'].get('Тест', {})
    products = test_sheet.get('products', [])
    
    if not products:
        print("✗ Нет товаров для тестирования")
        return None
    
    print(f"Тестируем опции для {len(products)} товаров:")
    for product in products:
        print(f"  Баркод: {product['barcode']}, Количество: {product['quantity']}")
    
    # Тестируем опции приемки
    options_result = api.get_acceptance_options(products)
    
    if options_result['success']:
        print("\n✓ Опции приемки получены успешно!")
        
        options_data = options_result['data']
        print(f"Request ID: {options_data.get('requestId', 'N/A')}")
        
        for item in options_data.get('result', []):
            barcode = item.get('barcode')
            print(f"\nБаркод: {barcode}")
            
            if item.get('isError'):
                error = item.get('error', {})
                print(f"  ✗ Ошибка: {error.get('title', 'Unknown')} - {error.get('detail', 'No details')}")
            else:
                warehouses = item.get('warehouses', [])
                if warehouses:
                    print(f"  ✓ Доступно складов: {len(warehouses)}")
                    for warehouse in warehouses:
                        wid = warehouse['warehouseID']
                        options = []
                        if warehouse.get('canBox'):
                            options.append('Короба')
                        if warehouse.get('canMonopallet'):
                            options.append('Монопаллеты')
                        if warehouse.get('canSupersafe'):
                            options.append('Суперсейф')
                        
                        print(f"    Склад {wid}: {', '.join(options) if options else 'Нет доступных опций'}")
                else:
                    print("  ✗ Нет доступных складов")
    else:
        print(f"✗ Ошибка получения опций: {options_result['error']}")
    
    return options_result


def main():
    """Основная функция для запуска всех тестов"""
    print("=== Запуск комплексного тестирования мониторинга WB ===")
    print(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 1. Тестируем отдельные методы API
    api_results = test_individual_api_methods()
    
    # 2. Тестируем опции для конкретных товаров
    options_results = test_specific_products()
    
    # 3. Тестируем полный мониторинг
    monitoring_results = test_monitoring_with_real_data()
    
    # Сводка
    print("\n=== СВОДКА ТЕСТИРОВАНИЯ ===")
    
    if api_results['warehouses']['success']:
        print("✓ Получение списка складов: OK")
    else:
        print("✗ Получение списка складов: FAILED")
    
    if api_results['coefficients']['success']:
        print("✓ Получение коэффициентов: OK")
    else:
        print("✗ Получение коэффициентов: FAILED")
    
    if options_results and options_results['success']:
        print("✓ Получение опций приемки: OK")
    else:
        print("✗ Получение опций приемки: FAILED")
    
    if monitoring_results and monitoring_results['success']:
        print("✓ Комплексный мониторинг: OK")
        print(f"  Найдено доступных слотов: {monitoring_results['summary']['total_available_slots']}")
    else:
        print("✗ Комплексный мониторинг: FAILED")
    
    print(f"\nТестирование завершено: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()