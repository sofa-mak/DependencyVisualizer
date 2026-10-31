# Импортируем модуль argparse для работы с параметрами командной строки
import argparse
# Импортируем модуль sys для выхода из программы
import sys
# Импортируем встроенную библиотеку для скачивания файлов из интернета
import urllib.request
# Импортируем модуль ssl для обхода ошибки проверки сертификата на Mac
import ssl
# Импортируем встроенную библиотеку для работы с XML файлами
import xml.etree.ElementTree as ET
# Импортируем модуль для работы с очередью (для BFS)
from collections import deque
# Импортируем модуль для работы с файлами
import os
# Импортируем библиотеку pygraphviz для создания графа и его отрисовки
import pygraphviz as pgv

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
    parser.add_argument("-l", "--load-order", action="store_true", help="Вывод порядка загрузки зависимостей")
    return parser.parse_args()

# ФУНКЦИЯ: Парсит тестовый файл
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
    if len(parts) != 3: return []
    group_id, artifact_id, version = parts 
    group_path = group_id.replace('.', '/')
    pom_url = f"{repo_url.rstrip('/')}/{group_path}/{artifact_id}/{version}/{artifact_id}-{version}.pom"
    
    try:
        ssl_context = ssl._create_unverified_context()
        with urllib.request.urlopen(pom_url, context=ssl_context) as response:
            xml_data = response.read()
    except Exception:
        return []

    try:
        tree = ET.fromstring(xml_data)
        for elem in tree.iter():
            if '}' in elem.tag: elem.tag = elem.tag.split('}')[1]
        
        properties = {}
        props_node = tree.find('properties')
        if props_node is not None:
            for prop in props_node: properties[prop.tag] = prop.text
                
        dependencies = tree.findall('.//dependency')
        result = []
        for dep in dependencies:
            g, a, v = dep.find('groupId'), dep.find('artifactId'), dep.find('version')
            if g is not None and a is not None and v is not None:
                ver_str = v.text
                if ver_str and ver_str.startswith('${') and ver_str.endswith('}'):
                    var_name = ver_str[2:-1]
                    if var_name in properties: ver_str = properties[var_name]
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
            
        deps = full_test_graph.get(current_pkg, []) if test_mode else get_maven_dependencies(current_pkg, url)
        for dep in deps:
            graph[current_pkg].append(dep)
            if dep not in visited:
                queue.append((dep, current_depth + 1))
    return graph

# ФУНКЦИЯ: Порядок загрузки (Топологическая сортировка)
def get_load_order(graph, start_package):
    visited, stack, cycle_nodes = set(), [], set()

    def dfs(node):
        if node in visited: return
        if node in cycle_nodes:
            print(f"[!] Внимание: Обнаружен цикл с участием '{node}'. Цикл разорван.")
            return
        cycle_nodes.add(node)
        for dep in graph.get(node, []): dfs(dep)
        cycle_nodes.remove(node)
        visited.add(node)
        stack.append(node)

    dfs(start_package)
    return stack

# ОБНОВЛЕННАЯ ФУНКЦИЯ: Рисует граф с помощью pygraphviz и сохраняет в PNG
def render_graphviz(graph, dot_file, png_file):
    # Создаём направленный граф с помощью pygraphviz
    G = pgv.AGraph(strict=False, directed=True)
    # Задаём стили для узлов и рёбер
    G.node_attr['shape'] = 'box'
    G.node_attr['style'] = 'filled'
    G.node_attr['fillcolor'] = 'lightblue'
    G.node_attr['fontname'] = 'Helvetica'
    G.edge_attr['color'] = 'gray'
    G.edge_attr['fontname'] = 'Helvetica'
    
    # Добавляем в граф все пакеты и их зависимости
    for pkg, deps in graph.items():
        G.add_node(pkg)  # Добавляем узел (пакет)
        for dep in deps:
            G.add_edge(pkg, dep)  # Добавляем ребро (зависимость)

    # Сохраняем граф в текстовый файл .dot
    G.write(dot_file)
    print(f"Текстовое описание графа сохранено в {dot_file}")
    
    # Отрисовываем граф в PNG
    try:
        G.draw(png_file, prog='dot')
        print(f"Изображение графа успешно сохранено в {png_file}")
    except Exception as e:
        print(f"Произошла ошибка при создании картинки: {e}")

# ФУНКЦИЯ: Рисует ASCII-дерево в консоли
def print_ascii_tree(graph, node, prefix="", is_last=True, path=None):
    if path is None: path = []
    if node in path:
        print(f"{prefix}{'└── ' if is_last else '├── '}{node} (цикл)")
        return
    if prefix == "":
        print(node)
    else:
        print(f"{prefix}{'└── ' if is_last else '├── '}{node}")
    new_path = path + [node]
    deps = graph.get(node, [])
    for i, dep in enumerate(deps):
        is_dep_last = (i == len(deps) - 1)
        new_prefix = prefix + ("    " if is_last else "│   ")
        print_ascii_tree(graph, dep, new_prefix, is_dep_last, new_path)

# Главная функция
def main():
    args = get_arguments()
    if args.depth <= 0:
        print("Ошибка: Глубина анализа должна быть больше 0.")
        sys.exit(1)

    print("--- НАСТРОЙКИ ПРОГРАММЫ ---")
    print(f"Пакет: {args.package} | Глубина: {args.depth} | Файл: {args.output}")
    print("---------------------------")

    graph = build_graph(args.package, args.url, args.depth, args.filter, args.test_mode)
    
    if not args.ascii and not args.load_order:
        print("\n--- ГРАФ ЗАВИСИМОСТЕЙ ---")
        for pkg, deps in graph.items():
            print(f"{pkg}: {deps}")

    if args.ascii:
        print("\n--- ASCII-ДЕРЕВО ---")
        print_ascii_tree(graph, args.package)

    if args.load_order:
        print("\n--- ПОРЯДОК ЗАГРУЗКИ ---")
        load_order = get_load_order(graph, args.package)
        for i, pkg in enumerate(load_order, 1):
            print(f"{i}. {pkg}")

    dot_filename = args.output.replace('.png', '.dot')
    render_graphviz(graph, dot_filename, args.output)

if __name__ == "__main__":
    main()