import sys
import os
import time
import math
import shutil 
import json   
import subprocess
from collections import OrderedDict

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QMenu, QMessageBox, QStatusBar, QScrollArea, QLabel, 
    QPushButton, QTextEdit, QLineEdit, QFileDialog, QSplitter, QFrame,
    QProgressDialog, QTreeWidget, QTreeWidgetItem, QDialog, QInputDialog,
    QPlainTextEdit, QSizePolicy, QToolButton, QSizeGrip
)
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPainterPath, QAction, QIcon, QTextCursor
)
from PyQt6.QtCore import Qt, QPointF, QRect, QTimer, QSize, pyqtSignal

# ====================================================================
# CẤU HÌNH PATH & STYLE
# ====================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT_DIR = os.path.join(BASE_DIR, 'GitFlow_Data')

MODERN_STYLESHEET = """
    QMainWindow { background-color: #f8fafc; }
    
    QMessageBox { background-color: white; font-size: 13px; }
    
    /* Style Nút Bấm Sidebar */
    QPushButton {
        background-color: #e2e8f0; color: #334155; border: none; border-radius: 4px;
        padding: 6px 12px; font-weight: bold;
    }
    QPushButton:hover {
        background-color: #cbd5e1; color: #1e293b;
    }
    QPushButton:disabled {
        background-color: #f1f5f9; color: #cbd5e1;
    }

    /* Thanh cuộn đẹp */
    QScrollBar:horizontal {
        border: none; background: #f1f5f9; height: 12px; margin: 0; border-radius: 6px;
    }
    QScrollBar::handle:horizontal {
        background: #cbd5e1; min-width: 20px; border-radius: 6px; margin: 2px;
    }
    QScrollBar::handle:horizontal:hover { background: #94a3b8; }

    QScrollBar:vertical {
        border: none; background: #f1f5f9; width: 12px; margin: 0; border-radius: 6px;
    }
    QScrollBar::handle:vertical {
        background: #cbd5e1; min-height: 20px; border-radius: 6px; margin: 2px;
    }
    QScrollBar::handle:vertical:hover { background: #94a3b8; }
"""

BRANCH_COLORS = {
    'master':  {'node': '#2563eb', 'lane': '#eff6ff', 'line': '#1e40af'}, 
    'hotfix':  {'node': '#dc2626', 'lane': '#fef2f2', 'line': '#991b1b'}, 
    'release': {'node': '#0d9488', 'lane': '#f0fdfa', 'line': '#115e59'}, 
    'develop': {'node': '#9333ea', 'lane': '#faf5ff', 'line': '#6b21a8'}, 
    'feature': {'node': '#16a34a', 'lane': '#f0fdf4', 'line': '#14532d'}  
}

# ====================================================================
# HELPER: FILE EDITOR
# ====================================================================

class FileEditorDialog(QDialog):
    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.setWindowTitle(f"Sửa: {os.path.basename(file_path)}")
        self.resize(700, 500)
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(file_path))
        
        self.editor = QPlainTextEdit()
        self.editor.setFont(QFont("Consolas", 10))
        self.editor.setStyleSheet("background-color: #1e293b; color: #f8fafc; border-radius: 4px;")
        layout.addWidget(self.editor)
        
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("💾 Lưu")
        btn_save.setStyleSheet("background-color: #10b981; color: white;") 
        btn_save.clicked.connect(self.save_file)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)
        self.load_file()

    def load_file(self):
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self.editor.setPlainText(f.read())
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))

    def save_file(self):
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write(self.editor.toPlainText())
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))

# ====================================================================
# ENGINE & DATA
# ====================================================================

class Commit:
    def __init__(self, id, message, branch_name, is_tag=None, note="", has_folder=False):
        self.id = id
        self.message = message
        self.branch_name = branch_name
        self.parents = []     
        self.children = []
        self.x = 0
        self.y = 0 
        self.is_tag = is_tag
        self.note = note
        self.has_folder = has_folder 

    def add_parent(self, commit):
        if commit not in self.parents: self.parents.append(commit)
    def add_child(self, commit):
        if commit not in self.children: self.children.append(commit)

    def to_dict(self):
        return {
            "id": self.id, "message": self.message, "branch_name": self.branch_name,
            "is_tag": self.is_tag, "parent_ids": [p.id for p in self.parents],
            "x": self.x, "y": self.y, "note": self.note, "has_folder": self.has_folder
        }

class Branch:
    def __init__(self, name, color_key, head):
        self.name = name
        self.color_key = color_key
        colors = BRANCH_COLORS.get(color_key, BRANCH_COLORS['feature'])
        self.color = colors['node']
        self.lane_color = colors['lane']
        self.line_color = colors['line']
        self.head = head
        self.commits = [head] 

    def commit(self, new_commit):
        new_commit.add_parent(self.head)
        self.head.add_child(new_commit)
        self.head = new_commit
        self.commits.append(new_commit)

class ProjectEngine:
    def __init__(self, project_name="Project_Default"):
        self.project_name = project_name
        self.branches = OrderedDict() 
        self.all_commits = {}
        self.commit_counter = 0
        self.branch_line_offset = {}
        self.commit_x_map = {} 
        
        self.x_step = 100   
        self.y_step = 70    
        self.base_start_x = 60
        self.current_max_x = self.base_start_x
        self.current_max_y = 300 
        self.current_branch_name = 'master'
        self.canvas = None 

        self.project_dir = os.path.join(DATA_ROOT_DIR, project_name)
        self.json_path = os.path.join(self.project_dir, 'data.json')
        self.files_dir = os.path.join(self.project_dir, 'Commit_Files')

        self._setup_directories()
        if not self.load_data(): self._initialize_git_history_clean() 

    def _setup_directories(self):
        if not os.path.exists(self.project_dir): os.makedirs(self.project_dir)
        if not os.path.exists(self.files_dir): os.makedirs(self.files_dir)

    def _get_new_commit_id(self):
        self.commit_counter += 1
        return f"{self.project_name[0]}-{self.commit_counter}"

    def get_commit_folder_path(self, commit_id):
        return os.path.join(self.files_dir, commit_id)

    def copy_folder_with_progress(self, src, dst, progress_callback):
        if os.path.exists(dst): shutil.rmtree(dst)
        os.makedirs(dst)
        total_files = sum([len(files) for r, d, files in os.walk(src)])
        copied_files = 0
        for root, dirs, files in os.walk(src):
            rel_path = os.path.relpath(root, src)
            target_dir = os.path.join(dst, rel_path)
            if not os.path.exists(target_dir): os.makedirs(target_dir)
            for file in files:
                shutil.copy2(os.path.join(root, file), os.path.join(target_dir, file))
                copied_files += 1
                if progress_callback: progress_callback(copied_files, total_files)

    def save_data(self):
        data = {
            "counter": self.commit_counter, "current_branch": self.current_branch_name,
            "commits": [c.to_dict() for c in self.all_commits.values()],
            "branches": list(self.branches.keys())
        }
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

    def load_data(self):
        if not os.path.exists(self.json_path): return False
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.commit_counter = data["counter"]
            self.current_branch_name = data["current_branch"]
            
            for c_data in data["commits"]:
                c = Commit(c_data["id"], c_data["message"], c_data["branch_name"], 
                           c_data["is_tag"], c_data.get("note", ""), c_data.get("has_folder", False))
                c.x, c.y = c_data["x"], c_data["y"]
                self.all_commits[c.id] = c
                self.commit_x_map[c.id] = c.x
            
            for c_data in data["commits"]:
                child = self.all_commits[c_data["id"]]
                for pid in c_data["parent_ids"]:
                    if pid in self.all_commits:
                        parent = self.all_commits[pid]
                        child.add_parent(parent)
                        parent.add_child(child)
            
            self.branches = OrderedDict()
            commits_by_branch = {}
            for c in self.all_commits.values():
                commits_by_branch.setdefault(c.branch_name, []).append(c)
            
            for b_name in data.get("branches", []):
                if b_name in commits_by_branch:
                    branch_commits = commits_by_branch[b_name]
                    head = max(branch_commits, key=lambda x: x.x)
                    color_key = b_name if b_name in BRANCH_COLORS else 'feature'
                    br = Branch(b_name, color_key, head)
                    br.commits = branch_commits
                    self.branches[b_name] = br
            
            self.calculate_commit_positions()
            return True
        except Exception: return False

    def _initialize_git_history_clean(self):
        c1 = Commit(f"{self.project_name[0]}-1", "Init", "master", is_tag="v0.1")
        self.all_commits[c1.id] = c1
        self.commit_counter = 1
        self.branches["master"] = Branch("master", 'master', c1)
        self.current_branch_name = 'master'
        self.commit_x_map[c1.id] = self.base_start_x
        self.current_max_x = self.base_start_x
        self.calculate_commit_positions()
        self.save_data()

    def _recalculate_branch_offsets(self):
        current_y = 60
        order = ['master', 'hotfix', 'release', 'develop']
        def sort_key(name): return order.index(name) if name in order else 99
        for name in sorted(self.branches.keys(), key=sort_key):
            self.branch_line_offset[name] = current_y
            current_y += self.y_step
        self.current_max_y = current_y + 50

    def calculate_commit_positions(self):
        self._recalculate_branch_offsets()
        max_x_found = self.base_start_x
        for commit in self.all_commits.values():
            commit.y = self.branch_line_offset.get(commit.branch_name, 0)
            commit.x = self.commit_x_map.get(commit.id, 0)
            if commit.x > max_x_found: max_x_found = commit.x
        
        self.current_max_x = max_x_found
        if self.canvas:
            self.canvas.update_size(self.current_max_x + 400, self.current_max_y)

    def _create_new_branch(self, name, color_key, new_commit, start_commit):
        new_branch = Branch(name, color_key, new_commit)
        self.branches[name] = new_branch
        self.all_commits[new_commit.id] = new_commit
        new_commit.add_parent(start_commit)
        start_commit.add_child(new_commit)
        self.current_max_x += self.x_step
        self.commit_x_map[new_commit.id] = self.current_max_x
        self.current_branch_name = name
        self.calculate_commit_positions()
        self.save_data()

    def update_note(self, commit_id, text):
        if commit_id in self.all_commits:
            self.all_commits[commit_id].note = text
            self.save_data()

# ====================================================================
# CANVAS (VẼ)
# ====================================================================

class GitFlowCanvas(QWidget):
    node_selected = pyqtSignal(object, str) 

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.engine.canvas = self 
        self.selected_node_id = None
        self.node_positions = {} 
        self.setMouseTracking(True)
        self.setStyleSheet("background-color: white;") 
        self.node_radius = 6 
        self.anim_frame = 0
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.animate_nodes)
        self.anim_timer.start(50)

    def update_size(self, w, h):
        self.setMinimumSize(int(w), int(h))
        self.resize(int(w), int(h))
        self.adjustSize() 

    def animate_nodes(self):
        self.anim_frame += 0.2
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        self.node_positions.clear()
        self.draw_lanes(painter)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.draw_connections(painter)
        self.draw_branch_extensions(painter)
        self.draw_nodes_and_labels(painter)
        painter.end()

    def draw_lanes(self, painter):
        w = self.width()
        for branch in self.engine.branches.values():
            y = self.engine.branch_line_offset.get(branch.name)
            if not y: continue
            
            lane_rect = QRect(0, int(y - self.engine.y_step/2), w, self.engine.y_step)
            painter.setBrush(QColor(branch.lane_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(lane_rect)
            
            painter.setPen(QColor(branch.color))
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.drawText(10, int(y) - 20, branch.name.upper())

    def draw_connections(self, painter):
        pen = QPen(QColor("#64748b"), 1.2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for commit in self.engine.all_commits.values():
            for parent in commit.parents:
                path = QPainterPath(QPointF(parent.x, parent.y))
                if parent.y == commit.y:
                    painter.drawLine(QPointF(parent.x, parent.y), QPointF(commit.x, commit.y))
                else:
                    cp1 = QPointF(parent.x + (commit.x - parent.x) * 0.5, parent.y)
                    cp2 = QPointF(commit.x - (commit.x - parent.x) * 0.5, commit.y)
                    path.cubicTo(cp1, cp2, QPointF(commit.x, commit.y))
                    painter.drawPath(path)

    def draw_branch_extensions(self, painter):
        w = self.width()
        for b_name, branch in self.engine.branches.items():
            head = branch.head
            y = self.engine.branch_line_offset.get(b_name)
            if not y: continue
            
            should_draw = False
            if b_name in ['master', 'develop']:
                should_draw = True
            else:
                is_merged_away = False
                for child in head.children:
                    if child.branch_name != b_name:
                         target_branch = self.engine.branches.get(child.branch_name)
                         if target_branch: is_merged_away = True
                
                if not is_merged_away:
                    should_draw = True

            if should_draw and head.x < w:
                pen = QPen(QColor(branch.line_color), 1, Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.drawLine(QPointF(head.x, y), QPointF(w, y))

    def draw_nodes_and_labels(self, painter):
        for commit in self.engine.all_commits.values():
            branch = self.engine.branches.get(commit.branch_name)
            if not branch: continue
            self.node_positions[commit.id] = QPointF(commit.x, commit.y)
            
            if commit.id == self.selected_node_id:
                pulse = (math.sin(self.anim_frame * 5) + 1) / 2
                painter.setPen(QPen(QColor(255, 0, 0, int(100 + 100 * pulse)), 3))
                r = self.node_radius + 2
            else:
                painter.setPen(QPen(QColor("white"), 1.5))
                r = self.node_radius

            painter.setBrush(QColor(branch.color))
            painter.drawEllipse(QPointF(commit.x, commit.y), r, r)

            if commit.has_folder:
                painter.setBrush(QColor("#f59e0b"))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(commit.x + 6, commit.y - 6), 3, 3)

            if commit.is_tag:
                painter.setPen(QColor('#334155'))
                painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                painter.drawText(int(commit.x) - 10, int(commit.y) - 12, commit.is_tag)

    def mousePressEvent(self, event):
        clicked = None
        for nid, pos in self.node_positions.items():
            if (event.position() - pos).manhattanLength() < 15:
                clicked = nid
                break
        
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected_node_id = clicked
            if clicked:
                br = self.engine.all_commits[clicked].branch_name
                self.engine.current_branch_name = br
                self.node_selected.emit(self.engine, clicked)
            else:
                self.node_selected.emit(None, "")
            self.update()
            
        elif event.button() == Qt.MouseButton.RightButton and clicked:
            self.selected_node_id = clicked
            self.node_selected.emit(self.engine, clicked)
            self.update()
            self.show_context_menu(event.globalPosition().toPoint())

    def show_context_menu(self, pos):
        menu = QMenu(self)
        wrapper = self.parent().parent().parent() 
        if not isinstance(wrapper, ProjectWrapper): wrapper = self.parent().parent()

        commit = self.engine.all_commits[self.selected_node_id]
        
        menu.addAction("➕ Commit Mới", lambda: wrapper.handle_logic('push_commit'))
        
        merge_menu = menu.addMenu("🔀 Merge vào...")
        for b_name in self.engine.branches:
            if b_name != commit.branch_name:
                merge_menu.addAction(b_name.upper(), lambda t=b_name: wrapper.handle_logic(f'merge_to_{t}'))

        create_menu = menu.addMenu("✨ Tạo Nhánh")
        create_menu.addAction("Feature", lambda: wrapper.handle_logic('create_feature'))
        
        if commit.branch_name == 'master':
            if 'develop' not in self.engine.branches:
                create_menu.addAction("Develop (Mới)", lambda: wrapper.handle_logic('create_develop'))
            create_menu.addAction("Hotfix", lambda: wrapper.handle_logic('create_hotfix'))
            
        menu.addSeparator()
        menu.addAction("🗑️ Xóa Node", lambda: wrapper.handle_logic('delete_node'))
        menu.exec(pos)

# ====================================================================
# PROJECT WRAPPER (GIAO DIỆN DỰ ÁN)
# ====================================================================

class ProjectWrapper(QWidget):
    def __init__(self, project_name, main_window):
        super().__init__()
        self.main_window = main_window
        self.engine = ProjectEngine(project_name)
        self.is_minimized = False
        
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
        self.setMinimumHeight(200)

        self.setStyleSheet("""
            ProjectWrapper { 
                background: white; 
                border: 1px solid #cbd5e1; 
                border-radius: 6px; 
                margin-bottom: 8px;
            }
        """)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0) 
        self.layout.setSpacing(0)
        
        # HEADER
        header = QFrame()
        header.setFixedHeight(36) 
        header.setStyleSheet("""
            QFrame { 
                background-color: #f1f5f9; 
                border-bottom: 1px solid #cbd5e1; 
                border-top-left-radius: 6px; 
                border-top-right-radius: 6px; 
            }
            QLabel { color: #334155; font-weight: bold; font-size: 12px; }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 0, 5, 0) 
        
        icon = QLabel("📦")
        title = QLabel(project_name.upper())
        
        btn_style = """
            QToolButton { border-radius: 10px; border: none; background: transparent; font-weight: bold; color: #64748b; }
            QToolButton:hover { background: #e2e8f0; color: #0f172a; }
        """
        
        self.btn_end = QToolButton()
        self.btn_end.setText("⏩ End")
        self.btn_end.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_end.setStyleSheet("QToolButton { border: 1px solid #cbd5e1; border-radius: 4px; padding: 2px 8px; background: white; } QToolButton:hover { background: #f8fafc; }")
        self.btn_end.clicked.connect(self.scroll_to_end)

        self.btn_min = QToolButton()
        self.btn_min.setText("−")
        self.btn_min.setFixedSize(20, 20)
        self.btn_min.setStyleSheet(btn_style)
        self.btn_min.clicked.connect(self.toggle_content)

        self.btn_close = QToolButton()
        self.btn_close.setText("✕")
        self.btn_close.setFixedSize(20, 20)
        self.btn_close.setStyleSheet(btn_style.replace("#e2e8f0", "#fee2e2").replace("#0f172a", "#ef4444"))
        self.btn_close.clicked.connect(self.delete_project)

        header_layout.addWidget(icon)
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_end)
        header_layout.addWidget(self.btn_min)
        header_layout.addWidget(self.btn_close)
        
        self.layout.addWidget(header)
        
        # CANVAS
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        self.canvas = GitFlowCanvas(self.engine)
        self.canvas.node_selected.connect(self.main_window.update_sidebar)
        self.scroll_area.setWidget(self.canvas)
        
        self.layout.addWidget(self.scroll_area)

        # SIZE GRIP
        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch()
        sizegrip = QSizeGrip(self)
        bottom_bar.addWidget(sizegrip)
        bottom_bar.setContentsMargins(0, 0, 0, 0)
        
        # === FIX: TỰ ĐỘNG CUỘN XUỐNG CUỐI KHI MỞ ===
        QTimer.singleShot(200, self.scroll_to_end)

    def scroll_to_end(self):
        # === FIX: FORCE UPDATE GEOMETRY ===
        self.canvas.adjustSize()
        QApplication.processEvents() 
        h_bar = self.scroll_area.horizontalScrollBar()
        if h_bar:
            h_bar.setValue(h_bar.maximum())

    def toggle_content(self):
        if self.is_minimized:
            self.scroll_area.show()
            self.btn_min.setText("−")
            self.setMinimumHeight(200)
            self.setMaximumHeight(16777215)
        else:
            self.scroll_area.hide()
            self.btn_min.setText("+")
            self.setFixedHeight(36)
        self.is_minimized = not self.is_minimized

    def delete_project(self):
        res = QMessageBox.question(self, "Xóa", f"Xóa vĩnh viễn '{self.engine.project_name}'?", 
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if res == QMessageBox.StandardButton.Yes:
            if os.path.exists(self.engine.project_dir): shutil.rmtree(self.engine.project_dir)
            self.setParent(None)
            self.deleteLater()

    def handle_logic(self, action):
        cid = self.canvas.selected_node_id
        if not cid: return
        eng = self.engine
        commit = eng.all_commits[cid]
        
        if action == 'push_commit':
            nid = eng._get_new_commit_id()
            c = Commit(nid, "WIP", commit.branch_name)
            eng.branches[commit.branch_name].commit(c)
            eng.all_commits[nid] = c
            eng.commit_x_map[nid] = eng.current_max_x + eng.x_step
            eng.current_max_x += eng.x_step

        elif action == 'create_feature':
            name = f"feature/{eng.commit_counter}"
            c = Commit(eng._get_new_commit_id(), "Start", name)
            eng._create_new_branch(name, 'feature', c, commit)
            
        elif action == 'create_develop':
            if 'develop' not in eng.branches:
                c = Commit(eng._get_new_commit_id(), "Dev Init", "develop")
                eng._create_new_branch('develop', 'develop', c, commit)
            else:
                QMessageBox.information(self, "Info", "Nhánh Develop đã tồn tại. Dùng menu Merge để gộp.")

        elif action.startswith('merge_to_'):
            target_name = action.replace('merge_to_', '')
            if target_name in eng.branches:
                target = eng.branches[target_name]
                nid = eng._get_new_commit_id()
                msg = f"Merge {commit.branch_name}"
                mc = Commit(nid, msg, target.name)
                target.commit(mc)
                mc.add_parent(commit)
                commit.add_child(mc)
                eng.all_commits[nid] = mc
                eng.current_max_x += eng.x_step
                eng.commit_x_map[nid] = eng.current_max_x
                eng.current_branch_name = target.name
            
        elif action == 'delete_node':
            if commit.children:
                QMessageBox.warning(self, "Lỗi", "Không thể xóa node ở giữa!")
                return
            eng.branches[commit.branch_name].commits.remove(commit)
            del eng.all_commits[cid]
            path = eng.get_commit_folder_path(cid)
            if os.path.exists(path): shutil.rmtree(path)
            self.canvas.selected_node_id = None

        eng.calculate_commit_positions()
        eng.save_data()
        self.canvas.update()
        QTimer.singleShot(50, self.scroll_to_end)

# ====================================================================
# SIDEBAR & MAIN
# ====================================================================

class Sidebar(QFrame):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.current_engine = None
        self.current_node_id = None
        
        self.setStyleSheet("background-color: white; border-left: 1px solid #e2e8f0;")
        self.setFixedWidth(280) 

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self.lbl_info = QLabel("Chọn node để xem...")
        self.lbl_info.setStyleSheet("color: #64748b; font-size: 12px; padding: 10px; background: #f1f5f9; border-radius: 4px;")
        layout.addWidget(self.lbl_info)

        file_box = QFrame()
        file_box.setStyleSheet("background: #f8fafc; border-radius: 4px; padding: 5px;")
        fb_layout = QVBoxLayout(file_box)
        btn_row = QHBoxLayout()
        self.btn_up = QPushButton("⬆ Upload")
        self.btn_up.clicked.connect(self.upload)
        self.btn_open = QPushButton("📂 Open")
        self.btn_open.clicked.connect(self.open_folder)
        
        # === FIX: MẶC ĐỊNH DISABLE KHI MỚI MỞ ===
        self.btn_up.setEnabled(False)
        self.btn_open.setEnabled(False)

        btn_row.addWidget(self.btn_up)
        btn_row.addWidget(self.btn_open)
        fb_layout.addLayout(btn_row)
        layout.addWidget(file_box)

        layout.addWidget(QLabel("Ghi Chú:"))
        self.txt_note = QTextEdit()
        self.txt_note.setStyleSheet("border: 1px solid #cbd5e1; border-radius: 4px;")
        self.txt_note.textChanged.connect(self.save_note)
        layout.addWidget(self.txt_note)

        layout.addWidget(QLabel("File trong commit:"))
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setStyleSheet("border: 1px solid #cbd5e1; border-radius: 4px;")
        self.tree.itemDoubleClicked.connect(self.edit_file)
        layout.addWidget(self.tree)

    def update_view(self, engine, nid):
        self.current_engine = engine
        self.current_node_id = nid
        self.tree.clear()
        
        if not engine or not nid:
            self.lbl_info.setText("Chưa chọn node.")
            self.txt_note.clear()
            self.btn_up.setEnabled(False)
            self.btn_open.setEnabled(False)
            return

        commit = engine.all_commits[nid]
        self.lbl_info.setText(f"PROJECT: {engine.project_name}\nBRANCH: {commit.branch_name}\nID: {nid}")
        self.txt_note.blockSignals(True)
        self.txt_note.setText(commit.note)
        self.txt_note.blockSignals(False)
        
        self.btn_up.setEnabled(True)
        path = engine.get_commit_folder_path(nid)
        if commit.has_folder and os.path.exists(path):
            self.btn_open.setEnabled(True)
            self.load_tree(path)
        else:
            self.btn_open.setEnabled(False)

    def load_tree(self, path):
        root = QTreeWidgetItem(self.tree, [os.path.basename(path)])
        root.setIcon(0, QApplication.style().standardIcon(QApplication.style().StandardPixmap.SP_DirIcon))
        
        for r, d, f in os.walk(path):
            curr = root
            rel = os.path.relpath(r, path)
            if rel != ".":
                for part in rel.split(os.sep):
                    found = None
                    for i in range(curr.childCount()):
                        if curr.child(i).text(0) == part:
                            found = curr.child(i)
                            break
                    if not found:
                        found = QTreeWidgetItem(curr, [part])
                        found.setIcon(0, QApplication.style().standardIcon(QApplication.style().StandardPixmap.SP_DirIcon))
                    curr = found
            for file in f:
                item = QTreeWidgetItem(curr, [file])
                item.setData(0, Qt.ItemDataRole.UserRole, os.path.join(r, file))
                item.setIcon(0, QApplication.style().standardIcon(QApplication.style().StandardPixmap.SP_FileIcon))
        self.tree.expandAll()

    def edit_file(self, item, col):
        fpath = item.data(0, Qt.ItemDataRole.UserRole)
        if fpath and os.path.isfile(fpath):
            FileEditorDialog(fpath, self).exec()

    def upload(self):
        # === FIX: KIỂM TRA NULL TRƯỚC KHI CHẠY ===
        if not self.current_engine or not self.current_node_id:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn một Node trước khi Upload!")
            return

        d = QFileDialog.getExistingDirectory(self, "Chọn Folder Code")
        if d:
            pd = QProgressDialog("Copying...", "Cancel", 0, 100, self)
            pd.show()
            self.current_engine.copy_folder_with_progress(d, self.current_engine.get_commit_folder_path(self.current_node_id), 
                                                          lambda c, t: pd.setValue(int(c/t*100)) if t else 0)
            self.current_engine.all_commits[self.current_node_id].has_folder = True
            self.current_engine.save_data()
            self.update_view(self.current_engine, self.current_node_id)
            self.current_engine.canvas.update()

    def open_folder(self):
        if not self.current_engine or not self.current_node_id: return
        p = self.current_engine.get_commit_folder_path(self.current_node_id)
        if os.path.exists(p):
            if sys.platform == 'win32': os.startfile(p)
            else: subprocess.Popen(['xdg-open', p])

    def save_note(self):
        if self.current_engine:
            self.current_engine.update_note(self.current_node_id, self.txt_note.toPlainText())

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        if not os.path.exists(DATA_ROOT_DIR): os.makedirs(DATA_ROOT_DIR)

        self.setWindowTitle("Git Flow Compact Edition")
        self.resize(1200, 700) 
        self.setStyleSheet(MODERN_STYLESHEET) 
        
        main_split = QSplitter(Qt.Orientation.Horizontal)
        
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        top = QHBoxLayout()
        btn_add = QPushButton("➕ New Project")
        btn_add.clicked.connect(self.add_project)
        top.addWidget(btn_add)
        top.addStretch()
        left_layout.addLayout(top)
        
        self.proj_container = QWidget()
        self.proj_layout = QVBoxLayout(self.proj_container)
        self.proj_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.proj_layout.setSpacing(10) 
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.proj_container)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_layout.addWidget(scroll)
        
        main_split.addWidget(left_widget)
        self.sidebar = Sidebar(self)
        main_split.addWidget(self.sidebar)
        main_split.setSizes([900, 280])
        
        self.setCentralWidget(main_split)
        self.load_projects()

    def add_project(self):
        name, ok = QInputDialog.getText(self, "Tạo Dự Án", "Tên dự án (không dấu):")
        if ok and name:
            safe = "".join([c for c in name if c.isalnum() or c=='_']).strip()
            self.create_wrapper(safe)

    def load_projects(self):
        for name in os.listdir(DATA_ROOT_DIR):
            if os.path.isdir(os.path.join(DATA_ROOT_DIR, name)):
                self.create_wrapper(name)

    def create_wrapper(self, name):
        w = ProjectWrapper(name, self)
        self.proj_layout.addWidget(w)

    def update_sidebar(self, engine, nid):
        self.sidebar.update_view(engine, nid)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())