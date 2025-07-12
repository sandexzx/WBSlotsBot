import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv


load_dotenv()


class WBAPITester:
    def __init__(self):
        self.api_key = os.getenv('WB_API_KEY')
        self.base_url = 'https://supplies-api.wildberries.ru'
        self.headers = {
            'Authorization': self.api_key,
            'Content-Type': 'application/json'
        }
        self.results = {}
    
    def test_get_warehouses(self):
        """Тест получения списка складов WB"""
        print("Тестируем получение списка складов...")
        
        url = f"{self.base_url}/api/v1/warehouses"
        
        try:
            response = requests.get(url, headers=self.headers)
            
            test_result = {
                'test_name': 'get_warehouses',
                'url': url,
                'status_code': response.status_code,
                'success': response.status_code == 200,
                'timestamp': datetime.now().isoformat(),
                'response_headers': dict(response.headers),
                'data': None,
                'error': None
            }
            
            if response.status_code == 200:
                data = response.json()
                test_result['data'] = data
                print(f"✓ Успешно получен список из {len(data)} складов")
            else:
                test_result['error'] = response.text
                print(f"✗ Ошибка: {response.status_code} - {response.text}")
                
        except Exception as e:
            test_result = {
                'test_name': 'get_warehouses',
                'url': url,
                'status_code': None,
                'success': False,
                'timestamp': datetime.now().isoformat(),
                'response_headers': None,
                'data': None,
                'error': str(e)
            }
            print(f"✗ Исключение: {str(e)}")
        
        self.results['warehouses'] = test_result
        return test_result
    
    def test_get_acceptance_coefficients(self):
        """Тест получения коэффициентов приемки"""
        print("Тестируем получение коэффициентов приемки...")
        
        url = f"{self.base_url}/api/v1/acceptance/coefficients"
        
        try:
            response = requests.get(url, headers=self.headers)
            
            test_result = {
                'test_name': 'get_acceptance_coefficients',
                'url': url,
                'status_code': response.status_code,
                'success': response.status_code == 200,
                'timestamp': datetime.now().isoformat(),
                'response_headers': dict(response.headers),
                'data': None,
                'error': None
            }
            
            if response.status_code == 200:
                data = response.json()
                test_result['data'] = data
                print(f"✓ Успешно получены коэффициенты для {len(data)} записей")
            else:
                test_result['error'] = response.text
                print(f"✗ Ошибка: {response.status_code} - {response.text}")
                
        except Exception as e:
            test_result = {
                'test_name': 'get_acceptance_coefficients',
                'url': url,
                'status_code': None,
                'success': False,
                'timestamp': datetime.now().isoformat(),
                'response_headers': None,
                'data': None,
                'error': str(e)
            }
            print(f"✗ Исключение: {str(e)}")
        
        self.results['acceptance_coefficients'] = test_result
        return test_result
    
    def test_get_acceptance_options(self):
        """Тест получения опций приемки"""
        print("Тестируем получение опций приемки...")
        
        url = f"{self.base_url}/api/v1/acceptance/options"
        
        # Загружаем реальные данные из parsed_data.json
        try:
            with open('test/test_output/parsed_data.json', 'r', encoding='utf-8') as f:
                parsed_data = json.load(f)
            
            # Используем данные из листа "Тест"
            test_sheet = parsed_data['sheets']['Тест']
            test_data = []
            
            for product in test_sheet['products']:
                test_data.append({
                    "quantity": product['quantity'],
                    "barcode": product['barcode']
                })
            
            print(f"Используем реальные данные: {len(test_data)} товаров")
            
        except Exception as e:
            print(f"Не удалось загрузить parsed_data.json, используем тестовые данные: {e}")
            # Резервные тестовые данные
            test_data = [
                {
                    "quantity": 100,
                    "barcode": "2044207833977"
                }
            ]
        
        try:
            response = requests.post(url, headers=self.headers, json=test_data)
            
            test_result = {
                'test_name': 'get_acceptance_options',
                'url': url,
                'request_data': test_data,
                'status_code': response.status_code,
                'success': response.status_code == 200,
                'timestamp': datetime.now().isoformat(),
                'response_headers': dict(response.headers),
                'data': None,
                'error': None
            }
            
            if response.status_code == 200:
                data = response.json()
                test_result['data'] = data
                print(f"✓ Успешно получены опции приемки")
            else:
                test_result['error'] = response.text
                print(f"✗ Ошибка: {response.status_code} - {response.text}")
                
        except Exception as e:
            test_result = {
                'test_name': 'get_acceptance_options',
                'url': url,
                'request_data': test_data,
                'status_code': None,
                'success': False,
                'timestamp': datetime.now().isoformat(),
                'response_headers': None,
                'data': None,
                'error': str(e)
            }
            print(f"✗ Исключение: {str(e)}")
        
        self.results['acceptance_options'] = test_result
        return test_result
    
    def save_results(self):
        """Сохранение результатов тестов в JSON файл"""
        output_dir = 'test/test_output'
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{output_dir}/wb_api_test_results_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        
        print(f"Результаты сохранены в: {filename}")
        return filename
    
    def run_all_tests(self):
        """Запуск всех тестов"""
        print("=== Запуск тестов WB API ===\n")
        
        self.test_get_warehouses()
        print()
        
        self.test_get_acceptance_coefficients()
        print()
        
        self.test_get_acceptance_options()
        print()
        
        filename = self.save_results()
        
        # Сводка результатов
        print("=== Сводка результатов ===")
        successful_tests = sum(1 for result in self.results.values() if result['success'])
        total_tests = len(self.results)
        print(f"Успешных тестов: {successful_tests}/{total_tests}")
        
        for test_name, result in self.results.items():
            status = "✓" if result['success'] else "✗"
            print(f"{status} {test_name}: {result['status_code']}")


if __name__ == "__main__":
    tester = WBAPITester()
    tester.run_all_tests()