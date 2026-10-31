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
# Импортируем модуль для работы с очередью (нужен для BFS)
from collections import deque
# Импортируем модуль для работы с файлами (для тестового режима)
import os

# Функция для получения настроек
def get_arguments():
    parser = argparse.ArgumentParser(description="Инструмент визуализации графа зависимостей")
    parser.add_argument("-p", "--package", type=str, required=True, help="Пакет (формат groupId:artifactId:version)")
    parser.add_argument("-u", "--url", type=str, required=True, help="URL репозитория или путь к файлу теста")
    parser.add_argument("-t", "--test-mode", action="store_true", help="Режим тестового репозитория")
    parser.add_argument("-o", "--output", type=str, default="graph.png", help="Имя файла с изображением графа")
    parser.add_argument("-a", "--ascii", action="store_true", help="Вывод в виде ASCII-дерева")
    parser.add_argument("-d", "--depth", type=int, default=3, help="Максимальная глубина")
    parser.add_argument("-f", "--filter", type=str, default="", help="Подстрока для фильтрации")
    return parser.parse_args()

# ФУНКЦИЯ: Парсит тестовый файл (режим -t)
def parse_test_file(filepath):
    # Создаем пустой словарь, где ключ - пакет, значение - список его зависимостей
    graph = {}
    # Открываем файл с тестом
    with open(filepath, 'r', encoding='utf-8') as f:
        # Читаем файл построчно
        for line in f:
            line = line.strip() # Убираем пробелы по краям
            # Если строка пустая, пропускаем
            if not line: continue
            
            # Разделяем строку по двоеточию: "A: B, C" -> левая часть "A", правая "B, C"
            parts = line.split(':')
            if len(parts) == 2:
                pkg = parts[0].strip() # Имя текущего пакета
                # Если справа есть зависимости, разделяем их по запятой
                deps = [d.strip() for d in parts[1].split(',') if d.strip()]
                graph[pkg] = deps # Записываем в словарь
            else:
                # Если двоеточия нет, значит у пакета нет зависимостей
                graph[line] = []
    return graph

# ФУНКЦИЯ: Скачивает POM-файл и достает из него прямые зависимости (с подстановкой версий)
def get_maven_dependencies(package_name, repo_url):
    parts = package_name.split(':')
    if len(parts) != 3:
        return [] # Если формат неверный, возвращаем пустоту
    
    group_id, artifact_id, version = parts 
    group_path = group_id.replace('.', '/')
    base_url = repo_url.rstrip('/')
    pom_url = f"{base_url}/{group_path}/{artifact_id}/{version}/{artifact_id}-{version}.pom"
    
    try:
        ssl_context = ssl._create_unverified_context()
        with urllib.request.urlopen(pom_url, context=ssl_context) as response:
            xml_data = response.read()
    except Exception as e:
        return [] # Если не скачалось, значит зависимостей нет или пакет битый

    try:
        tree = ET.fromstring(xml_data)
        # Убираем скобки из тегов
        for elem in tree.iter():
            if '}' in elem.tag:
                elem.tag = elem.tag.split('}')[1]
        
        # Ищем блок properties (там хранятся переменные вроде hamcrestVersion)
        properties = {}
        props_node = tree.find('properties')
        if props_node is not None:
            # Записываем все переменные в словарь
            for prop in props_node:
                properties[prop.tag] = prop.text
                
        dependencies = tree.findall('.//dependency')
        result = []
        
        for dep in dependencies:
            g = dep.find('groupId')
            a = dep.find('artifactId')
            v = dep.find('version')
            
            if g is not None and a is not None and v is not None:
                ver_str = v.text
                # Если версия выглядит как ${...}, пытаемся найти её в properties
                if ver_str and ver_str.startswith('${') and ver_str.endswith('}'):
                    var_name = ver_str[2:-1] # Отрезаем ${ и }
                    # Если нашли такую переменную, подставляем её значение
                    if var_name in properties:
                        ver_str = properties[var_name]
                
                # Если версия все еще с ${ или None, значит мы не смогли её узнать, пропускаем
                if ver_str and not ver_str.startswith('${'):
                    result.append(f"{g.text}:{a.text}:{ver_str}")
                
        return result
    except Exception:
        return []

# ГЛАВНАЯ ФУНКЦИЯ ЭТАПА 3: Строит граф с помощью BFS (поиск в ширину)
def build_graph(start_package, url, max_depth, filter_str, test_mode):
    # Если тестовый режим, читаем граф из файла
    if test_mode:
        # Проверяем, существует ли файл
        if not os.path.exists(url):
            print(f"Ошибка: Тестовый файл '{url}' не найден.")
            return {}
        print(f"Загружаем тестовый граф из файла: {url}")
        full_test_graph = parse_test_file(url)
    
    # Создаем словарь для нашего итогового графа
    graph = {}
    # Очередь для BFS. Кладут туда пары: (Имя пакета, Текущая глубина)
    queue = deque([(start_package, 0)])
    # Множество (set) для уже посещенных пакетов, чтобы не зациклиться
    visited = set()

    # Пока в очереди есть элементы
    while queue:
        # Достаем из очереди первый элемент (слева)
        current_pkg, current_depth = queue.popleft()
        
        # Если мы уже обработали этот пакет, пропускаем его (защита от циклов)
        if current_pkg in visited:
            continue
            
        # Добавляем пакет в посещенные
        visited.add(current_pkg)
        
        # Если пакет содержит подстроку фильтра (и фильтр не пустой), не идем вглубь
        if filter_str and filter_str in current_pkg:
            graph[current_pkg] = [] # Записываем пакет, но без зависимостей
            continue
            
        # Создаем пустой список зависимостей для этого пакета в графе
        graph[current_pkg] = []
        
        # Если достигли максимальной глубины, то зависимости не ищем
        if current_depth >= max_depth:
            continue
            
        # Получаем зависимости (из теста или из Maven)
        if test_mode:
            deps = full_test_graph.get(current_pkg, [])
        else:
            deps = get_maven_dependencies(current_pkg, url)
            
        # Проходимся по всем найденным зависимостям
        for dep in deps:
            # Добавляем зависимость в граф
            graph[current_pkg].append(dep)
            # Если мы ее еще не посещали, добавляем в очередь для дальнейшего анализа
            if dep not in visited:
                queue.append((dep, current_depth + 1))

    return graph

# ФУНКЦИЯ: Красиво печатает граф в виде обычного текста
def print_graph(graph):
    print("\n--- ГРАФ ЗАВИСИМОСТЕЙ ---")
    for pkg, deps in graph.items():
        print(f"{pkg}:")
        if deps:
            for d in deps:
                print(f"  -> {d}")
        else:
            print("  (Нет зависимостей или фильтр)")

# Главная функция
def main():
    args = get_arguments()

    if args.depth <= 0:
        print("Ошибка: Глубина анализа должна быть больше 0.")
        sys.exit(1)

    print("--- НАСТРОЙКИ ПРОГРАММЫ ---")
    print(f"Пакет: {args.package}")
    print(f"URL/Путь: {args.url}")
    print(f"Глубина: {args.depth}")
    print(f"Фильтр: '{args.filter}'")
    print(f"Тестовый режим: {args.test_mode}")
    print("---------------------------")

    # Строим граф
    graph = build_graph(args.package, args.url, args.depth, args.filter, args.test_mode)
    
    # Выводим его на экран
    print_graph(graph)

if __name__ == "__main__":
    main()