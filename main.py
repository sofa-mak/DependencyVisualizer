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
    # НОВЫЙ ПАРАМЕТР: Режим вывода порядка загрузки
    parser.add_argument("-l", "--load-order", action="store_true", help="Вывод порядка загрузки зависимостей")
    return parser.parse_args()

# ФУНКЦИЯ: Парсит тестовый файл (режим -t)
def parse_test_file(filepath):
    graph = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            parts = line.split(':')
            if len(parts) == 2:
                pkg = parts[0].strip()
                deps = [d.strip() for d in parts[1].split(',') if d.strip()]
                graph[pkg] = deps
            else:
                graph[line] = []
    return graph

# ФУНКЦИЯ: Скачивает POM-файл и достает из него прямые зависимости
def get_maven_dependencies(package_name, repo_url):
    parts = package_name.split(':')
    if len(parts) != 3:
        return []
    
    group_id, artifact_id, version = parts 
    group_path = group_id.replace('.', '/')
    base_url = repo_url.rstrip('/')
    pom_url = f"{base_url}/{group_path}/{artifact_id}/{version}/{artifact_id}-{version}.pom"
    
    try:
        ssl_context = ssl._create_unverified_context()
        with urllib.request.urlopen(pom_url, context=ssl_context) as response:
            xml_data = response.read()
    except Exception:
        return []

    try:
        tree = ET.fromstring(xml_data)
        for elem in tree.iter():
            if '}' in elem.tag:
                elem.tag = elem.tag.split('}')[1]
        
        properties = {}
        props_node = tree.find('properties')
        if props_node is not None:
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
                if ver_str and ver_str.startswith('${') and ver_str.endswith('}'):
                    var_name = ver_str[2:-1]
                    if var_name in properties:
                        ver_str = properties[var_name]
                
                if ver_str and not ver_str.startswith('${'):
                    result.append(f"{g.text}:{a.text}:{ver_str}")
                
        return result
    except Exception:
        return []

# ФУНКЦИЯ: Строит граф с помощью BFS
def build_graph(start_package, url, max_depth, filter_str, test_mode):
    if test_mode:
        if not os.path.exists(url):
            print(f"Ошибка: Тестовый файл '{url}' не найден.")
            return {}
        full_test_graph = parse_test_file(url)
    
    graph = {}
    queue = deque([(start_package, 0)])
    visited = set()

    while queue:
        current_pkg, current_depth = queue.popleft()
        if current_pkg in visited: continue
        visited.add(current_pkg)
        
        if filter_str and filter_str in current_pkg:
            graph[current_pkg] = []
            continue
            
        graph[current_pkg] = []
        if current_depth >= max_depth: continue
            
        if test_mode:
            deps = full_test_graph.get(current_pkg, [])
        else:
            deps = get_maven_dependencies(current_pkg, url)
            
        for dep in deps:
            graph[current_pkg].append(dep)
            if dep not in visited:
                queue.append((dep, current_depth + 1))

    return graph

# НОВАЯ ФУНКЦИЯ (ЭТАП 4): Порядок загрузки (Топологическая сортировка)
def get_load_order(graph, start_package):
    visited = set() # Пакеты, которые мы уже полностью обработали
    stack = []      # Сюда будем складывать пакеты в правильном порядке (зависимости первыми)
    cycle_nodes = set() # Пакеты, которые мы сейчас проверяем (для поиска циклов)

    # Внутренняя рекурсивная функция для обхода в глубину (DFS)
    def dfs(node):
        # Если пакет уже в стеке загрузки, пропускаем
        if node in visited:
            return
        # Если мы встретили пакет, который уже есть в текущей цепочке, значит это ЦИКЛ!
        if node in cycle_nodes:
            print(f"[!] Внимание: Обнаружен цикл с участием '{node}'. Цикл будет разорван для сортировки.")
            return

        # Помечаем пакет как "в процессе обработки"
        cycle_nodes.add(node)
        
        # Сначала обходим всех его "детей" (зависимости)
        for dep in graph.get(node, []):
            dfs(dep)
            
        # Когда все зависимости обработаны, убираем пакет из "в процессе"
        cycle_nodes.remove(node)
        # И добавляем его в итоговый стек загрузки
        visited.add(node)
        stack.append(node)

    # Запускаем обход с нашего главного пакета
    dfs(start_package)
    # Так как мы добавляли пакеты после их зависимостей, стек заполнился правильно
    return stack

# ФУНКЦИЯ: Красиво печатает граф
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
    print(f"Режим загрузки: {args.load_order}")
    print("---------------------------")

    # Строим граф
    graph = build_graph(args.package, args.url, args.depth, args.filter, args.test_mode)
    
    # Если НЕ включен режим загрузки, просто печатаем граф
    if not args.load_order:
        print_graph(graph)
    else:
        # Если включен режим загрузки (флаг -l)
        print("\n--- ПОРЯДОК ЗАГРУЗКИ ЗАВИСИМОСТЕЙ ---")
        load_order = get_load_order(graph, args.package)
        
        # Выводим пронумерованный список
        for i, pkg in enumerate(load_order, 1):
            print(f"{i}. {pkg}")

if __name__ == "__main__":
    main()