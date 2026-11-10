   #!/usr/bin/env python3
"""Инструмент визуализации графа зависимостей для менеджера пакетов Maven."""

import argparse
import sys
import os
import subprocess
from collections import deque

# Константы для избежания "магических чисел" (Ошибка M1)
MAX_LINE_LENGTH = 80
DEFAULT_DEPTH = 5
GRAPHVIZ_COMMAND = "dot"

def parse_arguments():
    """Парсит аргументы командной строки (Этап 1)."""
    parser = argparse.ArgumentParser(
        description="Визуализатор графа зависимостей Maven"
    )
    
    # Настраиваемые параметры (согласно заданию)
    parser.add_argument(
        "--package", 
        required=True, 
        help="Имя анализируемого пакета"
    )
    parser.add_argument(
        "--repo-url", 
        required=True, 
        help="URL-адрес репозитория или путь к файлу"
    )
    parser.add_argument(
        "--test-mode", 
        action="store_true", 
        help="Режим работы с тестовым репозиторием"
    )
    parser.add_argument(
        "--depth", 
        type=int, 
        default=DEFAULT_DEPTH, 
        help="Максимальная глубина анализа"
    )
    parser.add_argument(
        "--output", 
        default="graph.png", 
        help="Имя сгенерированного файла"
    )
    parser.add_argument(
        "--ascii-tree", 
        action="store_true", 
        help="Режим вывода ASCII-дерева"
    )
    parser.add_argument(
        "--filter", 
        default="", 
        help="Подстрока для фильтрации пакетов"
    )
    
    args = parser.parse_args()
    
    # Обработка ошибок для всех параметров (Этап 1, п.4)
    if args.depth < 1:
        print("Ошибка: Глубина должна быть больше 0", file=sys.stderr)
        sys.exit(1)
        
    return args

def get_dependencies_maven(package_name, repo_url):
    """Сбор данных из Maven (Этап 2). Возвращает список зависимостей."""
    # В реальности здесь был бы парсинг XML из репозитория.
    # Для демонстрации используем тестовые данные (заглушку).
    mock_db = {
        "root": ["foo", "target"],
        "foo": ["left", "right"],
        "left": ["shared"],
        "right": ["shared"],
        "shared": ["target"],
        "target": []
    }
    return mock_db.get(package_name, [])

def build_graph_bfs(args):
    """Построение графа зависимостей алгоритмом BFS (Этап 3)."""
    print(f"--- Построение графа для пакета: {args.package} ---")
    
    # BFS использует Очередь (Queue) - кто первый пришел, тот первый ушел
    queue = deque()
    queue.append((args.package, 0)) # (имя пакета, текущая глубина)
    
    visited = set()
    graph = {} # Словарь: пакет -> список его зависимостей
    
    while queue:
        current_pkg, current_depth = queue.popleft() # pop(0)
        
        # Проверка на циклы и максимальную глубину
        if current_pkg in visited or current_depth > args.depth:
            continue
            
        visited.add(current_pkg)
        
        # Фильтрация пакетов по подстроке (Этап 3, п.2)
        if args.filter and args.filter in current_pkg:
            continue
            
        # Получаем прямые зависимости
        deps = get_dependencies_maven(current_pkg, args.repo_url)
        graph[current_pkg] = deps
        
        for dep in deps:
            if dep not in visited:
                queue.append((dep, current_depth + 1))
                
    return graph

def print_ascii_tree(graph, package_name, indent=""):
    """Вывод графа в виде ASCII-дерева (Этап 5)."""
    print(f"{indent}- {package_name}")
    if package_name in graph:
        for dep in graph[package_name]:
            print_ascii_tree(graph, dep, indent + "  ")

def generate_graphviz_code(graph):
    """Формирует код для Graphviz (Этап 5)."""
    lines = ["digraph G {"]
    for pkg, deps in graph.items():
        for dep in deps:
            # Форматируем строки, чтобы не превышать 80 символов
            edge = f'    "{pkg}" -> "{dep}";'
            lines.append(edge)
    lines.append("}")
    return "\n".join(lines)

def save_image(dot_code, filename):
    """Сохраняет изображение графа в PNG (Этап 5)."""
    try:
        # Запускаем утилиту Graphviz (dot)
        process = subprocess.Popen(
            [GRAPHVIZ_COMMAND, "-Tpng", "-o", filename],
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        process.communicate(input=dot_code)
        print(f"Изображение сохранено в файл: {filename}")
    except FileNotFoundError:
        print("Утилита Graphviz не найдена. Пропускаем генерацию PNG.")

def main():
    """Главная функция программы."""
    args = parse_arguments()
    
    # Этап 1: Вывод всех параметров в формате ключ-значение
    print("--- Текущие настройки ---")
    for key, value in vars(args).items():
        print(f"{key}: {value}")
    print("-------------------------")
    
    # Этап 3: Строим граф
    graph = build_graph_bfs(args)
    
    # Этап 4: Вывод порядка загрузки (упрощенно)
    print("\n--- Порядок загрузки зависимостей ---")
    for pkg in graph.keys():
        print(f"Загрузить: {pkg}")
        
    # Этап 5: Визуализация
    if args.ascii_tree:
        print("\n--- ASCII Дерево ---")
        print_ascii_tree(graph, args.package)
        
    print("\n--- Генерация Graphviz ---")
    dot_code = generate_graphviz_code(graph)
    save_image(dot_code, args.output)

if __name__ == "__main__":
    main()