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
    
    def check_available_slots(self, sheet_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Проверяет доступные слоты для данных из Google таблицы
        
        Args:
            sheet_data: Данные листа из parsed_data.json
            
        Returns:
            Dict с результатами мониторинга
        """
        result = {
            'sheet_name': sheet_data.get('name', 'Unknown'),
            'timestamp': datetime.now().isoformat(),
            'warehouse_ids': {},
            'available_options': {},
            'coefficients': {},
            'available_slots': [],
            'errors': []
        }
        
        # 1. Получаем ID складов по названиям
        warehouse_names = sheet_data.get('warehouses', [])
        warehouse_ids = self.find_warehouse_ids_by_names(warehouse_names)
        result['warehouse_ids'] = warehouse_ids
        
        # 2. Проверяем опции приемки для товаров
        products = sheet_data.get('products', [])
        if products:
            options_result = self.get_acceptance_options(products)
            
            if options_result['success']:
                result['available_options'] = options_result['data']
            else:
                result['errors'].append(f"Ошибка получения опций: {options_result['error']}")
        
        # 3. Получаем коэффициенты приемки
        coefficients_result = self.get_acceptance_coefficients()
        
        if coefficients_result['success']:
            result['coefficients'] = coefficients_result['data']
            
            # Фильтруем коэффициенты только для наших складов
            our_warehouse_ids = [wid for wid in warehouse_ids.values() if wid is not None]
            
            available_slots = []
            for coef in coefficients_result['data']:
                if (coef['warehouseID'] in our_warehouse_ids and 
                    coef['coefficient'] in [0, 1] and 
                    coef['allowUnload'] is True):
                    
                    available_slots.append({
                        'date': coef['date'],
                        'warehouse_id': coef['warehouseID'],
                        'warehouse_name': coef['warehouseName'],
                        'coefficient': coef['coefficient'],
                        'box_type': coef['boxTypeName'],
                        'is_free': coef['coefficient'] == 0
                    })
            
            result['available_slots'] = available_slots
            
        else:
            result['errors'].append(f"Ошибка получения коэффициентов: {coefficients_result['error']}")
        
        return result


class WBMonitor:
    def __init__(self, api_key: Optional[str] = None):
        self.api = WildBerriesAPI(api_key)
    
    def monitor_parsed_data(self, parsed_data_path: str = 'test/test_output/parsed_data.json') -> Dict[str, Any]:
        """
        Мониторинг всех листов из parsed_data.json
        
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
        
        monitoring_results = {
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'sheets': {},
            'summary': {
                'total_sheets': 0,
                'sheets_with_slots': 0,
                'total_available_slots': 0
            }
        }
        
        sheets = parsed_data.get('sheets', {})
        
        for sheet_name, sheet_data in sheets.items():
            print(f"Мониторим лист: {sheet_name}")
            
            # Добавляем имя листа в данные
            sheet_data_with_name = sheet_data.copy()
            sheet_data_with_name['name'] = sheet_name
            
            sheet_result = self.api.check_available_slots(sheet_data_with_name)
            monitoring_results['sheets'][sheet_name] = sheet_result
            
            # Обновляем сводку
            monitoring_results['summary']['total_sheets'] += 1
            
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