#! /usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Простой планировщик зданий 3.0
Функционал:
- Свободное рисование стен любой длины и под любым углом
- Привязка (snapping) к узлам сетки и концам других стен
- Установка окон и дверей в стены
- Сетка (вкл/выкл)
- Экспорт в PDF с корректным отображением всех объектов
- Выделение стен и редактирование параметров (длина, толщина, материал, угол)
- Изменение размера перетаскиванием за ручки (с включением/отключением)
- Автоматическое объединение стен в углах
- Отображение размеров всех стен
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser
import math
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib import colors
from reportlab.lib.units import cm
import cairosvg
import tempfile

# --- КОНСТАНТЫ ---
GRID_SIZE = 50  # Размер клетки сетки в пикселях (экран)
SNAP_RADIUS = 15  # Радиус привязки курсора в пикселях
DEFAULT_WALL_THICKNESS = 0.3  # Толщина стены по умолчанию (м)
SCALE_FACTOR = 20  # Пикселей на метр (базовый масштаб)

# Цвета материалов
MATERIAL_COLORS = {
    "Кирпич": "#B54B3D",
    "Дерево": "#8B5A2B",
    "Газобетон": "#B0B0B0",
    "Каркас": "#F5DEB3",
    "Перегородка": "#D3D3D3"
}

COLOR_WALL_SELECTED = "#0066FF"
COLOR_DIMENSION = "#006400"
COLOR_HANDLE = "#FF6600"

class Point:
    """Класс для хранения точки (координаты в пикселях экрана)"""
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def distance_to(self, other):
        return math.hypot(self.x - other.x, self.y - other.y)

class Wall:
    """Класс Стены"""
    def __init__(self, x1, y1, x2, y2, thickness=DEFAULT_WALL_THICKNESS, material="Дерево"):
        self.start = Point(x1, y1)
        self.end = Point(x2, y2)
        self.thickness = thickness  # в метрах
        self.material = material
        self.selected = False
        self.id = None  # ID объекта на канвасе
        self.resize_handle = None  # Какой угол растягиваем: 'start' или 'end'

    @property
    def length_m(self):
        """Длина стены в метрах"""
        px_len = self.start.distance_to(self.end)
        return px_len / SCALE_FACTOR

    @property
    def length_px(self):
        """Длина стены в пикселях"""
        return self.start.distance_to(self.end)

    @property
    def angle(self):
        """Угол стены в градусах"""
        return math.degrees(math.atan2(self.end.y - self.start.y, self.end.x - self.start.x))

    def get_screen_thickness(self):
        """Толщина стены в пикселях"""
        return self.thickness * SCALE_FACTOR

    def contains_point(self, x, y, tolerance=5):
        """Проверяет, находится ли точка (x,y) близко к линии стены (для выделения)"""
        p = Point(x, y)
        line_vec = Point(self.end.x - self.start.x, self.end.y - self.start.y)
        point_vec = Point(p.x - self.start.x, p.y - self.start.y)
        
        line_len_sq = line_vec.x**2 + line_vec.y**2
        if line_len_sq == 0: return p.distance_to(self.start) < tolerance
        
        t = max(0, min(1, (point_vec.x * line_vec.x + point_vec.y * line_vec.y) / line_len_sq))
        projection = Point(self.start.x + t * line_vec.x, self.start.y + t * line_vec.y)
        return p.distance_to(projection) < tolerance

    def is_near_endpoint(self, x, y, endpoint='start', tolerance=8):
        """Проверяет, находится ли точка рядом с указанным концом стены"""
        pt = self.start if endpoint == 'start' else self.end
        return math.hypot(pt.x - x, pt.y - y) < tolerance

    def get_endpoints(self):
        return [self.start, self.end]

    def set_length(self, new_length_m, from_end=True):
        """Изменяет длину стены, сохраняя угол и позицию одного из концов"""
        current_length_px = self.length_px
        if current_length_px == 0:
            return
        ratio = (new_length_m * SCALE_FACTOR) / current_length_px
        dx = self.end.x - self.start.x
        dy = self.end.y - self.start.y
        
        if from_end:
            # Меняем конец end, start фиксирован
            self.end.x = self.start.x + dx * ratio
            self.end.y = self.start.y + dy * ratio
        else:
            # Меняем конец start, end фиксирован
            self.start.x = self.end.x - dx * ratio
            self.start.y = self.end.y - dy * ratio

    def set_angle(self, new_angle_deg, from_end=True):
        """Изменяет угол стены, сохраняя длину и позицию одного из концов"""
        rad = math.radians(new_angle_deg)
        length_px = self.length_px
        
        if from_end:
            self.end.x = self.start.x + length_px * math.cos(rad)
            self.end.y = self.start.y + length_px * math.sin(rad)
        else:
            self.start.x = self.end.x - length_px * math.cos(rad)
            self.start.y = self.end.y - length_px * math.sin(rad)

    def set_start_pos(self, x, y):
        """Перемещает начало стены"""
        self.start.x = x
        self.start.y = y

    def set_end_pos(self, x, y):
        """Перемещает конец стены"""
        self.end.x = x
        self.end.y = y

class Opening:
    """Класс для Окна или Двери (проем в стене)"""
    def __init__(self, wall, offset_from_start, width, type_opening="window"):
        self.wall = wall  # Ссылка на объект стены
        self.offset = offset_from_start  # Расстояние от начала стены в пикселях
        self.width = width  # Ширина проема в пикселях
        self.type = type_opening  # 'window' или 'door'
        self.selected = False

    def get_screen_coords(self):
        """Возвращает координаты центра и угла для отрисовки"""
        if not self.wall: return None
        
        dx = self.wall.end.x - self.wall.start.x
        dy = self.wall.end.y - self.wall.start.y
        length = math.hypot(dx, dy)
        if length == 0: return None
        
        # Нормализованный вектор направления
        ux, uy = dx / length, dy / length
        
        # Центр проема
        cx = self.wall.start.x + ux * self.offset
        cy = self.wall.start.y + uy * self.offset
        
        angle = math.degrees(math.atan2(dy, dx))
        return cx, cy, angle

class BuildingPlan:
    """Основная модель данных проекта"""
    def __init__(self):
        self.walls = []
        self.openings = []
        self.project_name = "Мой проект"
        self.show_grid = True
        self.scale = SCALE_FACTOR

    def add_wall(self, wall):
        self.walls.append(wall)

    def remove_wall(self, wall):
        if wall in self.walls:
            self.walls.remove(wall)
        # Удаляем связанные проемы
        self.openings = [op for op in self.openings if op.wall != wall]

    def add_opening(self, opening):
        self.openings.append(opening)

    def clear(self):
        self.walls = []
        self.openings = []

class Renderer:
    """Базовый класс для отрисовки (общая логика)"""
    
    @staticmethod
    def draw_wall_path(canvas_obj, wall, scale_px_per_m):
        """Рисует контур стены (два параллельных отрезка + торцы)"""
        thick_px = wall.thickness * scale_px_per_m
        half_thick = thick_px / 2
        
        dx = wall.end.x - wall.start.x
        dy = wall.end.y - wall.start.y
        length = math.hypot(dx, dy)
        if length == 0: return []
        
        # Нормаль к стене
        nx = -dy / length
        ny = dx / length
        
        # 4 угла стены
        x1 = wall.start.x + nx * half_thick
        y1 = wall.start.y + ny * half_thick
        x2 = wall.end.x + nx * half_thick
        y2 = wall.end.y + ny * half_thick
        x3 = wall.end.x - nx * half_thick
        y3 = wall.end.y - ny * half_thick
        x4 = wall.start.x - nx * half_thick
        y4 = wall.start.y - ny * half_thick
        
        coords = [x1, y1, x2, y2, x3, y3, x4, y4]
        return coords

    @staticmethod
    def get_snap_points(plan):
        """Собирает все точки привязки (концы всех стен)"""
        points = []
        for wall in plan.walls:
            points.append(wall.start)
            points.append(wall.end)
        return points

class TkinterRenderer(Renderer):
    """Отрисовка на Canvas Tkinter"""
    
    def __init__(self, canvas_widget, plan):
        self.canvas = canvas_widget
        self.plan = plan
        self.items = {}  # Хранение ID объектов для обновления

    def clear(self):
        self.canvas.delete("all")
        self.items = {}

    def draw_grid(self, width, height):
        if not self.plan.show_grid:
            return
            
        step = GRID_SIZE
        self.canvas.create_rectangle(0, 0, width, height, fill="white")
        
        # Вертикальные линии
        for x in range(0, width, step):
            self.canvas.create_line(x, 0, x, height, fill="#e0e0e0", tags="grid")
        # Горизонтальные линии
        for y in range(0, height, step):
            self.canvas.create_line(0, y, width, y, fill="#e0e0e0", tags="grid")
            
        # Координатная сетка (подписи)
        for x in range(0, width, step):
            m_val = x / self.plan.scale
            self.canvas.create_text(x, 10, text=f"{m_val:.1f}", font=("Arial", 8), fill="#aaa", tags="grid")
        for y in range(0, height, step):
            m_val = y / self.plan.scale
            self.canvas.create_text(10, y, text=f"{m_val:.1f}", font=("Arial", 8), fill="#aaa", tags="grid")

    def render(self):
        self.clear()
        width = int(self.canvas.cget("width"))
        height = int(self.canvas.cget("height"))
        
        self.draw_grid(width, height)
        
        # Отрисовка стен с размерами
        for wall in self.plan.walls:
            color = MATERIAL_COLORS.get(wall.material, "#000000")
            coords = self.draw_wall_path(self.canvas, wall, self.plan.scale)
            
            # Заливка
            if len(coords) == 8:
                outline_color = COLOR_WALL_SELECTED if wall.selected else "black"
                self.canvas.create_polygon(coords, fill=color, outline=outline_color, width=2 if wall.selected else 1, tags="wall")
            
            # Размер стены рядом с ней (рисуем для всех стен) - увеличенное смещение для лучшей видимости
            mid_x = (wall.start.x + wall.end.x) / 2
            mid_y = (wall.start.y + wall.end.y) / 2
            # Смещение перпендикулярно стене
            dx = wall.end.x - wall.start.x
            dy = wall.end.y - wall.start.y
            length = math.hypot(dx, dy)
            if length > 0:
                nx, ny = -dy/length, dx/length
                dim_x = mid_x + nx * 25  # Увеличено смещение
                dim_y = mid_y + ny * 25
                self.canvas.create_text(dim_x, dim_y, text=f"{wall.length_m:.2f}м", 
                                       font=("Arial", 10, "bold"), fill=COLOR_DIMENSION, tags="dimension")
            
            # Маркеры выделения (ручки для изменения размера) - только если стена выделена
            if wall.selected:
                # Ручки на концах стены - рисуем всегда, но цвет зависит от режима
                r = 6
                handle_color = COLOR_HANDLE if self.resize_mode_enabled else "blue"
                self.canvas.create_oval(wall.start.x-r, wall.start.y-r, wall.start.x+r, wall.start.y+r, 
                                       fill="white", outline=handle_color, width=2, tags="resize_handle_start")
                self.canvas.create_oval(wall.end.x-r, wall.end.y-r, wall.end.x+r, wall.end.y+r,
                                       fill="white", outline=handle_color, width=2, tags="resize_handle_end")

        # Отрисовка проемов (окна/двери)
        for op in self.plan.openings:
            pos = op.get_screen_coords()
            if pos:
                cx, cy, angle = pos
                w_px = op.width
                
                # Вектор вдоль стены
                dx = op.wall.end.x - op.wall.start.x
                dy = op.wall.end.y - op.wall.start.y
                length = math.hypot(dx, dy)
                if length == 0: continue
                ux, uy = dx/length, dy/length
                
                # Точки проема
                p1x = cx - ux * (w_px/2)
                p1y = cy - uy * (w_px/2)
                p2x = cx + ux * (w_px/2)
                p2y = cy + uy * (w_px/2)
                
                thick = op.wall.get_screen_thickness()
                # Нормаль
                nx, ny = -uy, ux
                
                poly = [
                    p1x + nx*thick/2, p1y + ny*thick/2,
                    p2x + nx*thick/2, p2y + ny*thick/2,
                    p2x - nx*thick/2, p2y - ny*thick/2,
                    p1x - nx*thick/2, p1y - ny*thick/2
                ]
                
                fill_color = "white" if op.type == "window" else "#DDA0DD"
                self.canvas.create_polygon(poly, fill=fill_color, outline="black", width=1, tags="opening")
                
                # Подпись типа
                self.canvas.create_text(cx, cy, text="Д" if op.type == "door" else "О", font=("Arial", 8), fill="red")

    def draw_temp_line(self, x1, y1, x2, y2, info_text=""):
        """Рисует временную линию при создании стены"""
        self.canvas.delete("temp")
        self.canvas.create_line(x1, y1, x2, y2, fill="red", width=2, dash=(4,4), tags="temp")
        # Текст с размерами
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2
        dist = math.hypot(x2-x1, y2-y1)
        meters = dist / self.plan.scale
        angle = math.degrees(math.atan2(y2-y1, x2-x1))
        
        self.canvas.create_text(mid_x, mid_y - 15, text=f"{meters:.2f} м\n{angle:.0f}°", fill="red", font=("Arial", 9, "bold"), tags="temp")

    def remove_temp(self):
        self.canvas.delete("temp")

    def draw_snap_indicator(self, x, y):
        self.canvas.delete("snap")
        r = 6
        self.canvas.create_oval(x-r, y-r, x+r, y+r, outline="green", width=2, tags="snap")

    def export_svg(self, filename, plan):
        """Экспорт плана в SVG формат"""
        width = 800
        height = 600
        
        svg_content = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">']
        svg_content.append('  <rect width="100%" height="100%" fill="white"/>')
        
        # Рисуем стены
        for wall in plan.walls:
            color_hex = MATERIAL_COLORS.get(wall.material, "#000000")
            coords = self.draw_wall_path(None, wall, plan.scale)
            
            if len(coords) == 8:
                points = " ".join(f"{coords[i]},{coords[i+1]}" for i in range(0, 8, 2))
                svg_content.append(f'  <polygon points="{points}" fill="{color_hex}" stroke="black" stroke-width="2"/>')
            
            # Размеры
            mid_x = (wall.start.x + wall.end.x) / 2
            mid_y = (wall.start.y + wall.end.y) / 2
            dx = wall.end.x - wall.start.x
            dy = wall.end.y - wall.start.y
            length = math.hypot(dx, dy)
            if length > 0:
                nx, ny = -dy/length, dx/length
                dim_x = mid_x + nx * 25
                dim_y = mid_y + ny * 25
                svg_content.append(f'  <text x="{dim_x}" y="{dim_y}" font-family="Arial" font-size="10" fill="green" text-anchor="middle">{wall.length_m:.2f}м</text>')
        
        # Рисуем проемы
        for op in plan.openings:
            pos = op.get_screen_coords()
            if pos:
                cx, cy, angle = pos
                w_px = op.width
                dx = op.wall.end.x - op.wall.start.x
                dy = op.wall.end.y - op.wall.start.y
                length = math.hypot(dx, dy)
                if length == 0: continue
                ux, uy = dx/length, dy/length
                
                p1x = cx - ux * (w_px/2)
                p1y = cy - uy * (w_px/2)
                p2x = cx + ux * (w_px/2)
                p2y = cy + uy * (w_px/2)
                
                thick = op.wall.get_screen_thickness()
                nx, ny = -uy, ux
                
                poly_points = f"{p1x + nx*thick/2},{p1y + ny*thick/2} {p2x + nx*thick/2},{p2y + ny*thick/2} {p2x - nx*thick/2},{p2y - ny*thick/2} {p1x - nx*thick/2},{p1y - ny*thick/2}"
                fill_color = "white" if op.type == "window" else "#DDA0DD"
                svg_content.append(f'  <polygon points="{poly_points}" fill="{fill_color}" stroke="black" stroke-width="1"/>')
                
                label = "Д" if op.type == "door" else "О"
                svg_content.append(f'  <text x="{cx}" y="{cy}" font-family="Arial" font-size="8" fill="red" text-anchor="middle">{label}</text>')
        
        svg_content.append('</svg>')
        
        with open(filename, 'w') as f:
            f.write('\n'.join(svg_content))

class PdfRenderer(Renderer):
    """Отрисовка в PDF"""
    
    def generate(self, filename, plan):
        c = pdfcanvas.Canvas(filename, pagesize=A4)
        width, height = A4
        
        # Титульный лист
        c.setFont("Helvetica-Bold", 24)
        c.drawCentredString(width/2, height - 50, plan.project_name)
        
        c.setFont("Helvetica", 12)
        c.drawString(50, height - 90, f"Дата создания: {__import__('datetime').date.today()}")
        c.drawString(50, height - 110, f"Количество стен: {len(plan.walls)}")
        c.drawString(50, height - 130, f"Количество проемов: {len(plan.openings)}")
        
        c.showPage()
        
        # Страница плана
        # Масштабирование под страницу
        # Находим границы плана
        if not plan.walls:
            c.drawString(50, height/2, "План пуст. Нарисуйте стены.")
            c.save()
            return

        min_x = min(w.start.x for w in plan.walls)
        max_x = max(w.end.x for w in plan.walls)
        min_y = min(w.start.y for w in plan.walls)
        max_y = max(w.end.y for w in plan.walls)
        
        plan_w_px = max_x - min_x
        plan_h_px = max_y - min_y
        
        # Поля в пунктах (72 pt = 1 inch ~ 2.54cm)
        margin = 40
        avail_w = width - 2*margin
        avail_h = height - 2*margin
        
        # Вычисляем масштаб: сколько пунктов приходится на 1 пиксель модели
        # Или лучше: сколько пунктов на метр?
        # Пусть 1 метр = S пунктов.
        # План ширина в метрах = plan_w_px / plan.scale
        # S = avail_w / (plan_w_m + отступ)
        
        plan_w_m = plan_w_px / plan.scale
        plan_h_m = plan_h_px / plan.scale
        
        scale_factor = min(avail_w / (plan_w_m + 2), avail_h / (plan_h_m + 2)) # +2 метра запаса
        
        # Центрирование
        start_x = margin + (avail_w - plan_w_m * scale_factor) / 2
        start_y = height - margin - (avail_h - plan_h_m * scale_factor) / 2 # Y в PDF снизу вверх, но мы инвертируем логику или рисуем сверху вниз?
        # В Tkinter Y растет вниз. В PDF Y растет вверх.
        # Проще всего инвертировать Y при отрисовке: y_pdf = origin_y - y_model * scale
        
        origin_x = start_x
        origin_y = start_y # Это будет верхний левый угол плана в PDF

        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(width/2, height - 40, "План этажа 1")
        
        # Функция конвертации координат
        def to_pdf(x, y):
            # Инвертируем Y, чтобы рисунок был как на экране (верх слева)
            return origin_x + x * (scale_factor / plan.scale), origin_y - y * (scale_factor / plan.scale)

        # Рисуем стены
        for wall in plan.walls:
            color_hex = MATERIAL_COLORS.get(wall.material, "#000000")
            # Конвертация цвета hex в rgb для reportlab
            r = int(color_hex[1:3], 16) / 255.0
            g = int(color_hex[3:5], 16) / 255.0
            b = int(color_hex[5:7], 16) / 255.0
            
            coords_screen = self.draw_wall_path(None, wall, plan.scale) # Получаем пиксели модели
            # Конвертируем 4 точки в PDF
            poly_pdf = []
            for i in range(0, 8, 2):
                px, py = to_pdf(coords_screen[i], coords_screen[i+1])
                poly_pdf.extend([px, py])
            
            c.setFillColorRGB(r, g, b)
            c.setStrokeColorRGB(0, 0, 0)
            c.setLineWidth(1)
            c.drawPolygon(poly_pdf)
            
        # Рисуем проемы
        for op in plan.openings:
            pos = op.get_screen_coords()
            if pos:
                cx, cy, angle = pos
                # Пересчет координат проема аналогично стенам (упрощенно - белый прямоугольник)
                # Вектор стены
                dx = op.wall.end.x - op.wall.start.x
                dy = op.wall.end.y - op.wall.start.y
                length = math.hypot(dx, dy)
                if length == 0: continue
                ux, uy = dx/length, dy/length
                
                # Координаты концов проема в модели
                p1x = cx - ux * (op.width/2)
                p1y = cy - uy * (op.width/2)
                p2x = cx + ux * (op.width/2)
                p2y = cy + uy * (op.width/2)
                
                thick = op.wall.get_screen_thickness()
                nx, ny = -uy, ux
                
                pts = [
                    (p1x + nx*thick/2, p1y + ny*thick/2),
                    (p2x + nx*thick/2, p2y + ny*thick/2),
                    (p2x - nx*thick/2, p2y - ny*thick/2),
                    (p1x - nx*thick/2, p1y - ny*thick/2)
                ]
                
                poly_pdf = []
                for (px, py) in pts:
                    pdf_x, pdf_y = to_pdf(px, py)
                    poly_pdf.extend([pdf_x, pdf_y])
                
                c.setFillColorRGB(1, 1, 1) # Белый
                if op.type == "door":
                    c.setFillColorRGB(0.8, 0.6, 0.8)
                c.drawPolygon(poly_pdf)

        c.save()

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Простой планировщик зданий 3.0")
        self.geometry("1200x750")
        
        self.plan = BuildingPlan()
        self.renderer = None  # Будет создан после создания canvas
        
        # Состояние редактора
        self.mode = "draw_wall"  # draw_wall, select, add_window, add_door
        self.current_wall_start = None
        self.dragged_object = None
        self.drag_offset = Point(0,0)
        self.hover_snap_point = None
        self.resize_mode_enabled = False  # Режим изменения размера перетаскиванием ручек
        self.active_resize_handle = None  # 'start' или 'end' - какая ручка активна
        
        self._init_ui()
        
        # Для отслеживания позиции мыши при добавлении проемов
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        
    def _init_ui(self):
        # Верхняя панель инструментов
        toolbar = ttk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        # Кнопки режимов
        ttk.Label(toolbar, text="Режим:").pack(side=tk.LEFT, padx=5)
        
        self.btn_draw = ttk.Button(toolbar, text="🏗 Стена", command=lambda: self.set_mode("draw_wall"))
        self.btn_draw.pack(side=tk.LEFT, padx=2)
        
        self.btn_select = ttk.Button(toolbar, text="✋ Выделение", command=lambda: self.set_mode("select"))
        self.btn_select.pack(side=tk.LEFT, padx=2)
        
        self.btn_win = ttk.Button(toolbar, text="🪟 Окно", command=lambda: self.set_mode("add_window"))
        self.btn_win.pack(side=tk.LEFT, padx=2)
        
        self.btn_door = ttk.Button(toolbar, text="🚪 Дверь", command=lambda: self.set_mode("add_door"))
        self.btn_door.pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        # Настройки новых стен
        ttk.Label(toolbar, text="Материал:").pack(side=tk.LEFT, padx=5)
        self.combo_material = ttk.Combobox(toolbar, values=list(MATERIAL_COLORS.keys()), state="readonly", width=10)
        self.combo_material.current(1) # Дерево
        self.combo_material.pack(side=tk.LEFT, padx=2)
        
        ttk.Label(toolbar, text="Толщина (м):").pack(side=tk.LEFT, padx=5)
        self.entry_thickness = ttk.Entry(toolbar, width=5)
        self.entry_thickness.insert(0, "0.3")
        self.entry_thickness.pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        # Чекбокс режима изменения размера
        self.resize_var = tk.BooleanVar(value=False)
        self.chk_resize = ttk.Checkbutton(toolbar, text="✏️ Изменение размера ручками", 
                                          variable=self.resize_var, command=self.toggle_resize_mode)
        self.chk_resize.pack(side=tk.LEFT, padx=5)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        # Действия
        self.btn_grid = ttk.Button(toolbar, text="Сетка: ВКЛ", command=self.toggle_grid)
        self.btn_grid.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(toolbar, text="🗑 Удалить выделенное", command=self.delete_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="📄 Сохранить PDF", command=self.export_pdf).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="🖼 Сохранить PNG", command=self.export_png).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="❌ Очистить все", command=self.clear_all).pack(side=tk.RIGHT, padx=5)
        
        # Основная рабочая область
        main_frame = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Холст
        canvas_frame = ttk.Frame(main_frame)
        main_frame.add(canvas_frame, weight=3)
        
        self.canvas = tk.Canvas(canvas_frame, bg="white", width=800, height=500)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.renderer = TkinterRenderer(self.canvas, self.plan)
        
        # Правая панель - свойства выделенной стены
        props_frame = ttk.LabelFrame(main_frame, text="Свойства выделенной стены", padding=10)
        main_frame.add(props_frame, weight=1)
        
        # Поля редактирования свойств
        ttk.Label(props_frame, text="Длина (м):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.prop_length = ttk.Entry(props_frame, width=10)
        self.prop_length.grid(row=0, column=1, pady=5, padx=5)
        self.prop_length.bind("<Return>", lambda e: self.apply_wall_properties())
        
        ttk.Label(props_frame, text="Толщина (м):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.prop_thickness = ttk.Entry(props_frame, width=10)
        self.prop_thickness.grid(row=1, column=1, pady=5, padx=5)
        self.prop_thickness.bind("<Return>", lambda e: self.apply_wall_properties())
        
        ttk.Label(props_frame, text="Угол (°):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.prop_angle = ttk.Entry(props_frame, width=10)
        self.prop_angle.grid(row=2, column=1, pady=5, padx=5)
        self.prop_angle.bind("<Return>", lambda e: self.apply_wall_properties())
        
        ttk.Label(props_frame, text="Материал:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.prop_material = ttk.Combobox(props_frame, values=list(MATERIAL_COLORS.keys()), state="readonly", width=10)
        self.prop_material.grid(row=3, column=1, pady=5, padx=5)
        self.prop_material.bind("<<ComboboxSelected>>", lambda e: self.apply_wall_properties())
        
        # Кнопки применения
        btn_apply = ttk.Button(props_frame, text="Применить", command=self.apply_wall_properties)
        btn_apply.grid(row=4, column=0, columnspan=2, pady=10, sticky=tk.EW)
        
        btn_close = ttk.Button(props_frame, text="Снять выделение", command=self.deselect_all)
        btn_close.grid(row=5, column=0, columnspan=2, pady=5, sticky=tk.EW)
        
        # Информация о выделенном объекте
        self.info_label = ttk.Label(props_frame, text="Нет выделенных объектов", wraplength=200)
        self.info_label.grid(row=6, column=0, columnspan=2, pady=10)
        
        # Привязка событий
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<Delete>", lambda e: self.delete_selected())
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        
        # Статус бар
        self.status_var = tk.StringVar()
        self.status_var.set("Готов к работе. Выберите режим 'Стена' для начала рисования.")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.set_mode("draw_wall")
        self.renderer.render()

    def set_mode(self, mode):
        self.mode = mode
        self.current_wall_start = None
        self.renderer.remove_temp()
        self.status_var.set(f"Режим: {mode}")
        
        # Обновляем состояние кнопок
        for btn in [self.btn_draw, self.btn_select, self.btn_win, self.btn_door]:
            btn.state(['!pressed'])

    def toggle_grid(self):
        self.plan.show_grid = not self.plan.show_grid
        self.btn_grid.config(text=f"Сетка: {'ВКЛ' if self.plan.show_grid else 'ВЫКЛ'}")
        self.renderer.render()

    def toggle_resize_mode(self):
        self.resize_mode_enabled = self.resize_var.get()
        self.status_var.set(f"Режим изменения размера ручками: {'ВКЛ' if self.resize_mode_enabled else 'ВЫКЛ'}")
        self.renderer.render()

    def get_snap_point(self, x, y):
        """Ищет ближайшую точку привязки"""
        snap_points = Renderer.get_snap_points(self.plan)
        # Добавляем точки сетки
        if self.plan.show_grid:
            gx = round(x / GRID_SIZE) * GRID_SIZE
            gy = round(y / GRID_SIZE) * GRID_SIZE
            snap_points.append(Point(gx, gy))
            
        best_point = None
        min_dist = SNAP_RADIUS
        
        mouse = Point(x, y)
        for pt in snap_points:
            d = mouse.distance_to(pt)
            if d < min_dist:
                min_dist = d
                best_point = pt
                
        return best_point

    def check_resize_handle_click(self, x, y):
        """Проверяет клик по ручке изменения размера выделенной стены"""
        if not self.resize_mode_enabled:
            return None
        for wall in self.plan.walls:
            if wall.selected:
                r = 8
                if math.hypot(wall.start.x - x, wall.start.y - y) < r:
                    return (wall, 'start')
                if math.hypot(wall.end.x - x, wall.end.y - y) < r:
                    return (wall, 'end')
        return None

    def on_mouse_move(self, event):
        x, y = event.x, event.y
        self.last_mouse_x = x
        self.last_mouse_y = y
        
        snap = self.get_snap_point(x, y)
        
        if snap and self.mode == "draw_wall":
            self.hover_snap_point = snap
            self.renderer.draw_snap_indicator(snap.x, snap.y)
            x, y = snap.x, snap.y
        else:
            self.hover_snap_point = None
            self.canvas.delete("snap")
            
        if self.mode == "draw_wall" and self.current_wall_start:
            self.renderer.draw_temp_line(self.current_wall_start.x, self.current_wall_start.y, x, y)
            dist = math.hypot(x - self.current_wall_start.x, y - self.current_wall_start.y)
            m = dist / self.plan.scale
            ang = math.degrees(math.atan2(y - self.current_wall_start.y, x - self.current_wall_start.x))
            self.status_var.set(f"Длина: {m:.2f} м | Угол: {ang:.1f}°")
        elif self.mode == "select":
            # Проверка наведения на ручку
            handle_info = self.check_resize_handle_click(x, y)
            if handle_info and self.resize_mode_enabled:
                self.canvas.config(cursor="sb_h_double_arrow")
            else:
                self.canvas.config(cursor="")

    def on_mouse_down(self, event):
        x, y = event.x, event.y
        self.last_mouse_x = x
        self.last_mouse_y = y
        
        # Для режимов добавления проемов используем точные координаты клика без snapping
        if self.mode in ["add_window", "add_door"]:
            # Ищем стену под курсором
            for wall in self.plan.walls:
                if wall.contains_point(x, y, tolerance=10):
                    self.add_opening_to_wall(wall, self.mode, x, y)
                    return
            return
        
        snap = self.get_snap_point(x, y)
        if snap: x, y = snap.x, snap.y
        
        if self.mode == "draw_wall":
            if not self.current_wall_start:
                self.current_wall_start = Point(x, y)
                self.status_var.set("Перетащите мышь для указания длины и угла стены.")
            else:
                # Завершение стены
                self.finish_wall(x, y)
        
        elif self.mode == "select":
            # Сначала проверяем клик по ручке изменения размера
            if self.resize_mode_enabled:
                handle_info = self.check_resize_handle_click(x, y)
                if handle_info:
                    wall, handle = handle_info
                    self.active_resize_handle = handle
                    self.dragged_object = wall
                    self.status_var.set(f"Изменение размера стены за {handle}")
                    return
            
            # Поиск объекта для перетаскивания
            for wall in reversed(self.plan.walls):
                if wall.contains_point(x, y):
                    self.dragged_object = wall
                    self.drag_offset = Point(x - wall.start.x, y - wall.start.y)
                    wall.selected = True
                    # Снимаем выделение с остальных
                    for w in self.plan.walls:
                        if w != wall: w.selected = False
                    self.update_properties_panel()
                    self.renderer.render()
                    return
            
            # Если не попали в стену, снимаем выделение
            for w in self.plan.walls: w.selected = False
            self.update_properties_panel()
            self.renderer.render()

    def on_mouse_drag(self, event):
        x, y = event.x, event.y
        snap = self.get_snap_point(x, y)
        if snap: x, y = snap.x, snap.y
        
        if self.mode == "draw_wall" and self.current_wall_start:
            self.renderer.draw_temp_line(self.current_wall_start.x, self.current_wall_start.y, x, y)
            
        elif self.mode == "select" and self.dragged_object:
            wall = self.dragged_object
            
            if self.resize_mode_enabled and self.active_resize_handle:
                # Изменение размера перетаскиванием ручки
                if self.active_resize_handle == 'start':
                    wall.set_start_pos(x, y)
                elif self.active_resize_handle == 'end':
                    wall.set_end_pos(x, y)
            else:
                # Перемещение всей стены
                dx = x - self.drag_offset.x - wall.start.x
                dy = y - self.drag_offset.y - wall.start.y
                
                wall.start.x += dx
                wall.start.y += dy
                wall.end.x += dx
                wall.end.y += dy
            
            self.update_properties_panel()
            self.renderer.render()

    def on_mouse_up(self, event):
        if self.mode == "select":
            self.dragged_object = None
            self.active_resize_handle = None
            
    def finish_wall(self, x, y):
        try:
            thick = float(self.entry_thickness.get())
            if thick <= 0: raise ValueError
        except:
            messagebox.showerror("Ошибка", "Некорректная толщина стены")
            self.current_wall_start = None
            self.renderer.remove_temp()
            return
            
        mat = self.combo_material.get()
        wall = Wall(self.current_wall_start.x, self.current_wall_start.y, x, y, thick, mat)
        
        # Проверка на нулевую длину
        if wall.length_m < 0.1:
            messagebox.showwarning("Внимание", "Стена слишком короткая")
            self.current_wall_start = None
            self.renderer.remove_temp()
            return
            
        self.plan.add_wall(wall)
        self.current_wall_start = None # Начинаем новую стену от конца предыдущей? Пока нет.
        self.renderer.remove_temp()
        self.renderer.render()
        self.status_var.set(f"Стена добавлена. Длина: {wall.length_m:.2f} м")

    def update_properties_panel(self):
        """Обновляет панель свойств на основе выделенной стены"""
        selected_walls = [w for w in self.plan.walls if w.selected]
        
        if len(selected_walls) == 1:
            wall = selected_walls[0]
            self.prop_length.delete(0, tk.END)
            self.prop_length.insert(0, f"{wall.length_m:.2f}")
            
            self.prop_thickness.delete(0, tk.END)
            self.prop_thickness.insert(0, f"{wall.thickness:.2f}")
            
            self.prop_angle.delete(0, tk.END)
            self.prop_angle.insert(0, f"{wall.angle:.1f}")
            
            self.prop_material.set(wall.material)
            
            self.info_label.config(text=f"Стена выбрана\nДлина: {wall.length_m:.2f}м\nУгол: {wall.angle:.1f}°")
        elif len(selected_walls) > 1:
            self.info_label.config(text=f"Выбрано стен: {len(selected_walls)}")
            self.prop_length.delete(0, tk.END)
            self.prop_thickness.delete(0, tk.END)
            self.prop_angle.delete(0, tk.END)
        else:
            self.info_label.config(text="Нет выделенных объектов")
            self.prop_length.delete(0, tk.END)
            self.prop_thickness.delete(0, tk.END)
            self.prop_angle.delete(0, tk.END)

    def apply_wall_properties(self):
        """Применяет изменения из панели свойств к выделенной стене"""
        selected_walls = [w for w in self.plan.walls if w.selected]
        
        if len(selected_walls) != 1:
            messagebox.showwarning("Внимание", "Выделите ровно одну стену для редактирования")
            return
        
        wall = selected_walls[0]
        
        try:
            new_length = float(self.prop_length.get())
            if new_length > 0:
                wall.set_length(new_length, from_end=True)
        except ValueError:
            pass
        
        try:
            new_thick = float(self.prop_thickness.get())
            if new_thick > 0:
                wall.thickness = new_thick
        except ValueError:
            pass
        
        try:
            new_angle = float(self.prop_angle.get())
            wall.set_angle(new_angle, from_end=True)
        except ValueError:
            pass
        
        new_material = self.prop_material.get()
        if new_material in MATERIAL_COLORS:
            wall.material = new_material
        
        self.renderer.render()
        self.status_var.set("Свойства стены обновлены")

    def deselect_all(self):
        """Снимает выделение со всех стен"""
        for w in self.plan.walls:
            w.selected = False
        self.update_properties_panel()
        self.renderer.render()

    def on_double_click(self, event):
        """Двойной клик - быстрое добавление окна/двери или выделение"""
        x, y = event.x, event.y
        
        if self.mode in ["add_window", "add_door"]:
            # Ищем стену под курсором
            for wall in self.plan.walls:
                if wall.contains_point(x, y, tolerance=10):
                    self.add_opening_to_wall(wall, self.mode, x, y)
                    return

    def add_opening_to_wall(self, wall, opening_type, click_x, click_y):
        """Добавляет окно или дверь в стену по координатам клика"""
        dx = wall.end.x - wall.start.x
        dy = wall.end.y - wall.start.y
        length = math.hypot(dx, dy)
        if length == 0:
            return
        
        # Проекция точки клика на линию стены
        t = ((click_x - wall.start.x) * dx + (click_y - wall.start.y) * dy) / (length * length)
        t = max(0.1, min(0.9, t))  # Ограничиваем от 10% до 90% длины стены
        offset_px = t * length
        
        # Ширина проема в пикселях (примерно 1 метр)
        width_px = 1.0 * SCALE_FACTOR
        
        # Проверка - не выходит ли проем за границы стены
        if offset_px < width_px/2 or offset_px > length - width_px/2:
            messagebox.showwarning("Внимание", "Недостаточно места для проема на этом участке стены")
            return
        
        opening = Opening(wall, offset_px, width_px, opening_type)
        self.plan.add_opening(opening)
        self.renderer.render()
        self.status_var.set(f"{'Окно' if opening_type == 'window' else 'Дверь'} добавлено")

    def set_mode(self, mode):
        self.mode = mode
        self.current_wall_start = None
        self.renderer.remove_temp()
        self.status_var.set(f"Режим: {mode}")
        
        # Обновляем состояние кнопок
        for btn in [self.btn_draw, self.btn_select, self.btn_win, self.btn_door]:
            btn.state(['!pressed'])
        
        # Если режим добавления проема - подсказываем пользователю
        if mode == "add_window":
            self.status_var.set("Кликните на стену для добавления окна")
        elif mode == "add_door":
            self.status_var.set("Кликните на стену для добавления двери")

    def delete_selected(self):
        count = 0
        # Удаляем стены
        for wall in list(self.plan.walls):
            if wall.selected:
                self.plan.remove_wall(wall)
                count += 1
        if count > 0:
            self.renderer.render()
            self.update_properties_panel()
            self.status_var.set(f"Удалено объектов: {count}")
        else:
            self.status_var.set("Ничего не выделено для удаления")

    def clear_all(self):
        if messagebox.askyesno("Подтверждение", "Удалить весь проект?"):
            self.plan.clear()
            self.renderer.render()
            self.status_var.set("Проект очищен")

    def export_pdf(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
        if file_path:
            try:
                renderer = PdfRenderer()
                renderer.generate(file_path, self.plan)
                messagebox.showinfo("Успех", f"Файл сохранен: {file_path}")
            except Exception as e:
                messagebox.showerror("Ошибка PDF", str(e))

    def export_png(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png")])
        if file_path:
            try:
                # Создаем временный SVG файл
                with tempfile.NamedTemporaryFile(mode='w', suffix='.svg', delete=False) as tmp_svg:
                    svg_path = tmp_svg.name
                    # Генерируем SVG (упрощенно, можно доработать полноценный SVG экспортер)
                    self.renderer.export_svg(svg_path, self.plan)
                
                # Конвертируем SVG в PNG
                cairosvg.svg2png(url=svg_path, write_to=file_path)
                
                # Удаляем временный файл
                os.unlink(svg_path)
                
                messagebox.showinfo("Успех", f"PNG сохранен: {file_path}")
            except Exception as e:
                messagebox.showerror("Ошибка PNG", str(e))
                # Если cairosvg не установлен, пробуем простой скриншот
                if "cairosvg" in str(e):
                    self.screenshot_simple(file_path)

    def screenshot_simple(self, file_path):
        """Простой скриншот холста через PIL"""
        try:
            from PIL import ImageGrab
            x = self.canvas.winfo_rootx()
            y = self.canvas.winfo_rooty()
            width = self.canvas.winfo_width()
            height = self.canvas.winfo_height()
            img = ImageGrab.grab(bbox=(x, y, x+width, y+height))
            img.save(file_path)
            messagebox.showinfo("Успех", f"Скриншот сохранен: {file_path}")
        except Exception as e:
            messagebox.showerror("Ошибка скриншота", str(e))

if __name__ == "__main__":
    app = Application()
    app.mainloop()
