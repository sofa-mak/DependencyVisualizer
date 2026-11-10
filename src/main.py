#!/usr/bin/env python3
"""Инструмент визуализации графа зависимостей для менеджера пакетов."""

import argparse
import sys
import subprocess
from collections import deque

# Константы (защита от магических чисел)
DEFAULT_DEPTH = 5
GRAPHVIZ_COMMAND = "dot"
MIN_DEPTH = 1

def parse_arguments():
    """Парсит аргументы командной строки (Этап 1)."""
    parser = argparse.ArgumentParser(
        description="Визуализатор графа зависимостей"
    )
    parser.add_argument("--package", required=True, help="Имя пакета")
    parser.add_argument("--repo-url", required=True, help="Путь к файлу")
    parser.add_argument("--test-mode", action="store_true")
    parser.add_argument("--depth", type=int, default=DEFAULT_DEPTH)
    parser.add_argument("--output", default="graph.png")
    parser.add_argument("--ascii-tree", action="store_true")
    parser.add_argument("--filter", default="")
    
    args = parser.parse_args()
    
    if args.depth < MIN_DEPTH:
        print("Ошибка: Глубина должна быть > 0", file=sys.stderr)
        sys.exit(1)
    return args

def load_test_repo(filepath):
    """Читает тестовый файл и создает словарь зависимостей."""
    graph = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            for line in file:
                if not line.strip():
                    continue
                parts = line.strip().split(':')
                pkg_name = parts[0].strip()
                if len(parts) > 1 and parts[1].strip():
                    deps = [d.strip() for d in parts[1].split(',')]
                    graph[pkg_name] = deps
                else:
                    graph[pkg_name] = []
    except FileNotFoundError:
        print(f"Ошибка: Файл {filepath} не найден", file=sys.stderr)
        sys.exit(1)
    return graph

def get_dependencies(package_name, args, mock_db):
    """Возвращает список прямых зависимостей пакета."""
    if args.test_mode:
        return mock_db.get(package_name, [])
    # В реальности здесь был бы парсинг Maven
    return []

def build_graph_bfs(args, mock_db):
    """Построение графа зависимостей алгоритмом BFS (Этап 3)."""
    print(f"--- Построение графа для: {args.package} ---")
    queue = deque([(args.package, 0)])
    visited = set()
    graph = {}
    
    while queue:
        current_pkg, current_depth = queue.popleft()
        
        if current_pkg in visited or current_depth > args.depth:
            continue
        visited.add(current_pkg)
        
        if args.filter and args.filter in current_pkg:
            continue
            
        deps = get_dependencies(current_pkg, args, mock_db)
        graph[current_pkg] = deps
        
        for dep in deps:
            if dep not in visited:
                queue.append((dep, current_depth + 1))
                
    return graph

def print_ascii_tree(graph, package_name, indent="", path=None):
    """Вывод графа в виде ASCII-дерева с защитой от циклов (Этап 5)."""
    if path is None:
        path = []
        
    print(f"{indent}- {package_name}")
    
    # Если пакет уже есть в текущей ветке, это цикл
    if package_name in path:
        print(f"{indent}  (Обнаружен цикл)")
        return
        
    # Добавляем текущий пакет в путь
    current_path = path + [package_name]
    
    if package_name in graph:
        for dep in graph[package_name]:
            print_ascii_tree(graph, dep, indent + "  ", current_path)

def generate_graphviz_code(graph):
    """Формирует код для Graphviz (Этап 5)."""
    lines = ["digraph G {"]
    for pkg, deps in graph.items():
        for dep in deps:
            lines.append(f'    "{pkg}" -> "{dep}";')
    lines.append("}")
    return "\n".join(lines)

def save_image(dot_code, filename):
    """Сохраняет изображение графа в PNG (Этап 5)."""
    try:
        process = subprocess.Popen(
            [GRAPHVIZ_COMMAND, "-Tpng", "-o", filename],
            stdin=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        process.communicate(input=dot_code)
        print(f"Изображение сохранено в файл: {filename}")
    except FileNotFoundError:
        print("Утилита Graphviz не найдена. Пропускаем генерацию PNG.")

def main():
    """Главная функция программы."""
    args = parse_arguments()
    
    print("--- Текущие настройки ---")
    for key, value in vars(args).items():
        print(f"{key}: {value}")
    print("-------------------------")
    
    mock_db = {}
    if args.test_mode:
        mock_db = load_test_repo(args.repo_url)
        
    graph = build_graph_bfs(args, mock_db)
    
    if args.ascii_tree:
        print("\n--- ASCII Дерево ---")
        print_ascii_tree(graph, args.package)
        
    dot_code = generate_graphviz_code(graph)
    save_image(dot_code, args.output)

if __name__ == "__main__":
    main()