# Импортируем модуль argparse для работы с параметрами командной строки
import argparse
# Импортируем модуль sys для выхода из программы
import sys
# Импортируем встроенную библиотеку для скачивания файлов из интернета
import urllib.request
# Импортируем модуль ssl для обхода ошибки проверки сертификата на Mac
import ssl
# Импортируем встроенную библиотеку для работы с XML файлами (формат POM)
import xml.etree.ElementTree as ET

# Функция для получения настроек
def get_arguments():
    # Создаем парсер аргументов командной строки
    parser = argparse.ArgumentParser(description="Инструмент визуализации графа зависимостей")
    
    # Пакет (теперь требуем формат groupId:artifactId:version)
    parser.add_argument("-p", "--package", type=str, required=True, help="Пакет (формат groupId:artifactId:version)")
    # URL репозитория
    parser.add_argument("-u", "--url", type=str, required=True, help="URL репозитория")
    # Режим тестового репозитория
    parser.add_argument("-t", "--test-mode", action="store_true", help="Режим тестового репозитория")
    # Имя файла для графа
    parser.add_argument("-o", "--output", type=str, default="graph.png", help="Имя файла с изображением графа")
    # Режим ASCII-дерева
    parser.add_argument("-a", "--ascii", action="store_true", help="Вывод в виде ASCII-дерева")
    # Максимальная глубина
    parser.add_argument("-d", "--depth", type=int, default=3, help="Максимальная глубина")
    # Подстрока для фильтрации
    parser.add_argument("-f", "--filter", type=str, default="", help="Подстрока для фильтрации")
    
    # Возвращаем введенные пользователем параметры
    return parser.parse_args()

# Функция: Скачивает POM-файл и достает из него прямые зависимости
def get_direct_dependencies(package_name, repo_url):
    # Разбиваем строку "junit:junit:4.13.2" по двоеточию на три части
    parts = package_name.split(':')
    # Проверяем, что пользователь ввел ровно 3 части
    if len(parts) != 3:
        print("Ошибка: Пакет должен быть в формате groupId:artifactId:version (например, junit:junit:4.13.2)")
        return []
    
    # Присваиваем переменным значения из списка
    group_id, artifact_id, version = parts 
    # В Maven точки в названии группы заменяются на слэши (например, org.example -> org/example)
    group_path = group_id.replace('.', '/')
    
    # Убираем лишний слэш в конце URL, если он есть
    base_url = repo_url.rstrip('/')
    # Формируем прямую ссылку на POM-файл по стандарту Maven
    pom_url = f"{base_url}/{group_path}/{artifact_id}/{version}/{artifact_id}-{version}.pom"
    
    print(f"Скачиваем данные по адресу: {pom_url}")
    
    try:
        # Создаем контекст, который игнорирует проверку SSL сертификата (чтобы избежать ошибки на Mac)
        ssl_context = ssl._create_unverified_context()
        # Открываем ссылку, скачиваем файл и передаем контекст безопасности
        with urllib.request.urlopen(pom_url, context=ssl_context) as response:
            xml_data = response.read() # Читаем содержимое файла
    except Exception as e:
        # Если произошла ошибка сети, выводим ее
        print(f"Ошибка сети: Не удалось скачать файл. {e}")
        return []

    try:
        # Парсим (разбираем) скачанный XML файл
        tree = ET.fromstring(xml_data)
        
        # Очищаем названия тегов от пространств имен (убираем фигурные скобки), чтобы проще было искать
        for elem in tree.iter():
            if '}' in elem.tag:
                elem.tag = elem.tag.split('}')[1]
        
        # Ищем в файле все блоки dependency
        dependencies = tree.findall('.//dependency')
        result = [] # Создаем пустой список для результатов
        
        # Проходимся циклом по каждой найденной зависимости
        for dep in dependencies:
            g = dep.find('groupId') # Ищем groupId
            a = dep.find('artifactId') # Ищем artifactId
            v = dep.find('version') # Ищем version
            
            # Если нашли groupId и artifactId, добавляем в список
            if g is not None and a is not None:
                ver_str = v.text if v is not None else 'не указана' # Версия может быть не указана
                # Формируем красивую строку и добавляем в общий список
                result.append(f"{g.text}:{a.text}:{ver_str}")
                
        return result # Возвращаем список зависимостей
    except Exception as e:
        # Если XML битый или не читается
        print(f"Ошибка чтения XML: {e}")
        return []

# Главная функция
def main():
    # Получаем настройки
    args = get_arguments()

    # Проверка на глубину (должна быть больше 0)
    if args.depth <= 0:
        print("Ошибка: Глубина анализа должна быть больше 0.")
        sys.exit(1)

    # Вывод настроек (как на этапе 1)
    print("--- НАСТРОЙКИ ПРОГРАММЫ ---")
    print(f"Пакет: {args.package}")
    print(f"URL/Путь: {args.url}")
    print("---------------------------")

    # Получаем прямые зависимости и печатаем их
    print("\n--- ПРЯМЫЕ ЗАВИСИМОСТИ ---")
    deps = get_direct_dependencies(args.package, args.url)
    
    # Если список не пустой, выводим его на экран
    if deps:
        for d in deps:
            print(d) # Печатаем каждую зависимость
    else:
        print("Зависимости не найдены.")

# Точка входа в программу
if __name__ == "__main__":
    main()