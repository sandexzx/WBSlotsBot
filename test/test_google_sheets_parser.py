#!/usr/bin/env python3

import sys
import os
import json
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from google_sheets_parser import create_parser_from_env


def test_google_sheets_parser():
    print("Запуск теста парсера Google таблиц...")
    
    try:
        parser = create_parser_from_env()
        print("✓ Парсер создан успешно")
        
        print("Получение списка доступных листов...")
        available_sheets = parser.get_available_sheets()
        print(f"✓ Найдено листов: {len(available_sheets)}")
        print(f"  Доступные листы: {', '.join(available_sheets)}")
        
        print("\nПарсинг всех листов...")
        all_data = parser.parse_all_sheets()
        print(f"✓ Обработано листов: {len(all_data)}")
        
        result = parser.to_dict(all_data)
        
        output_file = os.path.join(os.path.dirname(__file__), 'test_output', 'parsed_data.json')
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"✓ Результаты сохранены в {output_file}")
        
        print("\n=== РЕЗУЛЬТАТЫ ПАРСИНГА ===")
        total_products = 0
        for sheet_name, sheet_data in all_data.items():
            print(f"\nЛист '{sheet_name}':")
            print(f"  Склады: {', '.join(sheet_data.warehouses) if sheet_data.warehouses else 'Не указаны'}")
            print(f"  Дата начала: {sheet_data.start_date}")
            print(f"  Дата окончания: {sheet_data.end_date}")
            print(f"  Количество товаров: {len(sheet_data.products)}")
            total_products += len(sheet_data.products)
            
            if sheet_data.products:
                print("  Первые 3 товара:")
                for i, product in enumerate(sheet_data.products[:3]):
                    print(f"    {i+1}. Баркод: {product.barcode}, Количество: {product.quantity}")
                    
        print(f"\n📊 ИТОГО: {len(all_data)} листов, {total_products} товаров")
                
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        return False


def main():
    print("=" * 50)
    print("ТЕСТ ПАРСЕРА GOOGLE ТАБЛИЦ")
    print("=" * 50)
    
    success = test_google_sheets_parser()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ ТЕСТ ЗАВЕРШЕН УСПЕШНО")
    else:
        print("❌ ТЕСТ ПРОВАЛЕН")
    print("=" * 50)


if __name__ == "__main__":
    main()