import requests
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv


load_dotenv()


class WildBerriesAPI:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('WB_API_KEY')
        self.base_url = 'https://supplies-api.wildberries.ru'
        self.headers = {
            'Authorization': self.api_key,
            'Content-Type': 'application/json'
        }
    
    def get_warehouses(self) -> Dict[str, Any]:
        """
        Получает список всех складов WB
        
        Returns:
            Dict содержащий success, data, error
        """
        url = f"{self.base_url}/api/v1/warehouses"
        
        try:
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'data': response.json(),
                    'error': None
                }
            else:
                return {
                    'success': False,
                    'data': None,
                    'error': f"HTTP {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            return {
                'success': False,
                'data': None,
                'error': str(e)
            }
    
    def get_acceptance_coefficients(self) -> Dict[str, Any]:
        """
        Получает коэффициенты приемки для всех складов на ближайшие 14 дней
        
        Returns:
            Dict содержащий success, data, error
        """
        url = f"{self.base_url}/api/v1/acceptance/coefficients"
        
        try:
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'data': response.json(),
                    'error': None
                }
            else:
                return {
                    'success': False,
                    'data': None,
                    'error': f"HTTP {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            return {
                'success': False,
                'data': None,
                'error': str(e)
            }
    
    def get_acceptance_options(self, products: List[Dict[str, Any]], warehouse_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Получает опции приемки для конкретных товаров
        
        Args:
            products: Список товаров [{"quantity": int, "barcode": str}, ...]
            warehouse_id: ID склада (опционально)
            
        Returns:
            Dict содержащий success, data, error
        """
        url = f"{self.base_url}/api/v1/acceptance/options"
        
        if warehouse_id:
            url += f"?warehouseID={warehouse_id}"
        
        try:
            response = requests.post(url, headers=self.headers, json=products)
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'data': response.json(),
                    'error': None
                }
            else:
                return {
                    'success': False,
                    'data': None,
                    'error': f"HTTP {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            return {
                'success': False,
                'data': None,
                'error': str(e)
            }
    
    def find_warehouse_ids_by_names(self, warehouse_names: List[str]) -> Dict[str, Optional[int]]:
        """
        Находит ID складов по их названиям
        
        Args:
            warehouse_names: Список названий складов
            
        Returns:
            Dict {название_склада: ID_склада или None}
        """
        warehouses_result = self.get_warehouses()
        
        if not warehouses_result['success']:
            return {name: None for name in warehouse_names}
        
        warehouses = warehouses_result['data']
        name_to_id = {}
        
        for warehouse in warehouses:
            name_to_id[warehouse['name'].lower()] = warehouse['ID']
        
        result = {}
        for name in warehouse_names:
            result[name] = name_to_id.get(name.lower())
        
        return result
    
    def check_available_slots_optimized(self, all_sheets_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Оптимизированная проверка слотов для всех листов одновременно
        
        Args:
            all_sheets_data: Все данные из parsed_data.json
            
        Returns:
            Dict с результатами мониторинга для всех листов
        """
        result = {
            'timestamp': datetime.now().isoformat(),
            'sheets': {},
            'global_data': {
                'warehouses': {},
                'coefficients': {},
                'all_products_options': {}
            },
            'errors': []
        }
        
        sheets = all_sheets_data.get('sheets', {})
        
        # 1. Получаем список складов (1 запрос)
        print("📋 Запрос списка складов...")
        warehouses_result = self.get_warehouses()
        if warehouses_result['success']:
            result['global_data']['warehouses'] = warehouses_result['data']
            print(f"✅ Получено {len(warehouses_result['data'])} складов")
        else:
            result['errors'].append(f"Ошибка получения складов: {warehouses_result['error']}")
            print(f"❌ Ошибка складов: {warehouses_result['error']}")
            return result
        
        # 2. Получаем коэффициенты приемки (1 запрос)
        print("📊 Запрос коэффициентов приемки...")
        coefficients_result = self.get_acceptance_coefficients()
        if coefficients_result['success']:
            result['global_data']['coefficients'] = coefficients_result['data']
            print(f"✅ Получено {len(coefficients_result['data'])} записей коэффициентов")
        else:
            result['errors'].append(f"Ошибка получения коэффициентов: {coefficients_result['error']}")
            print(f"❌ Ошибка коэффициентов: {coefficients_result['error']}")
        
        # 3. Собираем все товары из всех листов для одного запроса опций
        all_products = []
        product_to_sheet_map = {}  # Маппинг баркод -> название листа
        
        for sheet_name, sheet_data in sheets.items():
            products = sheet_data.get('products', [])
            for product in products:
                all_products.append(product)
                barcode = product['barcode']
                if barcode not in product_to_sheet_map:
                    product_to_sheet_map[barcode] = []
                product_to_sheet_map[barcode].append(sheet_name)
        
        # 4. Получаем опции для всех товаров одним запросом (1 запрос)
        if all_products:
            print(f"📦 Запрос опций для {len(all_products)} товаров...")
            options_result = self.get_acceptance_options(all_products)
            if options_result['success']:
                result['global_data']['all_products_options'] = options_result['data']
                print(f"✅ Получены опции для товаров")
            else:
                result['errors'].append(f"Ошибка получения опций: {options_result['error']}")
                print(f"❌ Ошибка опций: {options_result['error']}")
        else:
            print("⚠️  Нет товаров для запроса опций")
        
        # 5. Обрабатываем результаты для каждого листа
        for sheet_name, sheet_data in sheets.items():
            sheet_result = self._process_sheet_data(
                sheet_name, 
                sheet_data, 
                result['global_data'],
                product_to_sheet_map
            )
            result['sheets'][sheet_name] = sheet_result
        
        return result
    
    def _process_sheet_data(self, sheet_name: str, sheet_data: Dict[str, Any], 
                           global_data: Dict[str, Any], product_to_sheet_map: Dict[str, List[str]]) -> Dict[str, Any]:
        """
        Обрабатывает данные отдельного листа
        """
        sheet_result = {
            'sheet_name': sheet_name,
            'warehouse_ids': {},
            'available_options': {},
            'coefficients': global_data['coefficients'],
            'available_slots': [],
            'errors': []
        }
        
        # Получаем ID складов по названиям из глобальных данных
        warehouse_names = sheet_data.get('warehouses', [])
        warehouse_ids = {}
        
        print(f"🔍 Поиск складов для листа {sheet_name}: {warehouse_names}")
        
        if 'warehouses' in global_data and global_data['warehouses']:
            warehouses = global_data['warehouses']
            name_to_id = {}
            
            for warehouse in warehouses:
                name_to_id[warehouse['name'].lower()] = warehouse['ID']
            
            for name in warehouse_names:
                found_id = name_to_id.get(name.lower())
                warehouse_ids[name] = found_id
                if found_id:
                    print(f"  ✅ {name} → ID: {found_id}")
                else:
                    print(f"  ❌ {name} → не найден")
        else:
            print("  ❌ Нет данных о складах в global_data")
        
        sheet_result['warehouse_ids'] = warehouse_ids
        
        # Извлекаем опции для товаров этого листа
        sheet_products = sheet_data.get('products', [])
        sheet_options = {'result': []}
        
        if 'all_products_options' in global_data and global_data['all_products_options']:
            all_options = global_data['all_products_options']
            
            # Фильтруем опции только для товаров этого листа
            sheet_barcodes = {product['barcode'] for product in sheet_products}
            
            for option_item in all_options.get('result', []):
                if option_item.get('barcode') in sheet_barcodes:
                    sheet_options['result'].append(option_item)
        
        sheet_result['available_options'] = sheet_options
        
        # Формируем доступные слоты
        if 'coefficients' in global_data and global_data['coefficients']:
            our_warehouse_ids = [wid for wid in warehouse_ids.values() if wid is not None]
            
            # Получаем максимальный коэффициент для этого листа
            max_coefficient = sheet_data.get('max_coefficient', 1.0)
            
            available_slots = []
            for coef in global_data['coefficients']:
                if (coef['warehouseID'] in our_warehouse_ids and 
                    coef['coefficient'] != -1 and
                    coef['coefficient'] <= max_coefficient and 
                    coef['allowUnload'] is True):
                    
                    available_slots.append({
                        'date': coef['date'],
                        'warehouse_id': coef['warehouseID'],
                        'warehouse_name': coef['warehouseName'],
                        'coefficient': coef['coefficient'],
                        'box_type': coef['boxTypeName'],
                        'is_free': coef['coefficient'] == 0
                    })
            
            sheet_result['available_slots'] = available_slots
        
        return sheet_result


class WBMonitor:
    def __init__(self, api_key: Optional[str] = None):
        self.api = WildBerriesAPI(api_key)
    
    def monitor_parsed_data(self, parsed_data_path: str = 'test/test_output/parsed_data.json') -> Dict[str, Any]:
        """
        Оптимизированный мониторинг всех листов из parsed_data.json одновременно
        
        Args:
            parsed_data_path: Путь к файлу parsed_data.json
            
        Returns:
            Результаты мониторинга для всех листов
        """
        try:
            with open(parsed_data_path, 'r', encoding='utf-8') as f:
                parsed_data = json.load(f)
        except Exception as e:
            return {
                'success': False,
                'error': f"Не удалось загрузить {parsed_data_path}: {str(e)}",
                'data': None
            }
        
        print("🔄 Выполняем оптимизированные API запросы...")
        
        # Используем оптимизированный метод (всего 3 API запроса)
        optimized_results = self.api.check_available_slots_optimized(parsed_data)
        
        if optimized_results.get('errors'):
            return {
                'success': False,
                'error': '; '.join(optimized_results['errors']),
                'data': optimized_results
            }
        
        # Преобразуем результаты в старый формат для совместимости
        monitoring_results = {
            'success': True,
            'timestamp': optimized_results['timestamp'],
            'sheets': optimized_results['sheets'],
            'summary': {
                'total_sheets': len(optimized_results['sheets']),
                'sheets_with_slots': 0,
                'total_available_slots': 0
            }
        }
        
        # Подсчитываем сводку
        for sheet_name, sheet_result in optimized_results['sheets'].items():
            if sheet_result['available_slots']:
                monitoring_results['summary']['sheets_with_slots'] += 1
                monitoring_results['summary']['total_available_slots'] += len(sheet_result['available_slots'])
        
        return monitoring_results
    
    def save_monitoring_results(self, results: Dict[str, Any], output_dir: str = 'test/test_output') -> str:
        """
        Сохраняет результаты мониторинга в JSON файл
        
        Args:
            results: Результаты мониторинга
            output_dir: Директория для сохранения
            
        Returns:
            Путь к сохраненному файлу
        """
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{output_dir}/wb_monitoring_results_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        return filename