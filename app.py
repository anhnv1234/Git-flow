import sys
import os
import time
import math
import shutil 
import json   
import subprocess
import difflib
import html
import zipfile
import datetime
from collections import OrderedDict

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QMenu, QMessageBox, QScrollArea, QLabel, 
    QPushButton, QTextEdit, QFileDialog, QSplitter, QFrame,
    QProgressBar, QTreeWidget, QTreeWidgetItem, QDialog, QInputDialog,
    QPlainTextEdit, QSizePolicy, QToolButton, QSizeGrip, QFileIconProvider,
    QLineEdit
)
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPainterPath, QAction, QIcon,
    QTextCharFormat, QTextCursor, QTextImageFormat
)
from PyQt6.QtCore import Qt, QPointF, QRect, QTimer, pyqtSignal, QFileInfo, QSize, QThread, QUrl

# ====================================================================
# CẤU HÌNH PATH & STYLE
# ====================================================================

# ====================================================================
# CẤU HÌNH PATH & STYLE
# ====================================================================

# Xác định đường dẫn gốc (đã sửa để chạy được cả file exe và code thường)
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Đường dẫn file cấu hình để lưu lựa chọn của người dùng
CONFIG_FILE = os.path.join(BASE_DIR, 'settings.json')

# Mặc định chưa có, sẽ được gán khi khởi động app
DATA_ROOT_DIR = None

# Bảng màu Neon rực rỡ
BRANCH_COLORS = {
    'master':  {'node': '#00b8e6', 'lane': '#e0f7fa', 'line': '#00b8e6'}, # Cyan
    'hotfix':  {'node': '#ff0055', 'lane': '#ffebee', 'line': '#ff0055'}, # Red
    'release': {'node': '#ff9900', 'lane': '#fff3e0', 'line': '#ff9900'}, # Orange
    'develop': {'node': '#aa00ff', 'lane': '#f3e5f5', 'line': '#aa00ff'}, # Purple
    'feature': {'node': '#00cc66', 'lane': '#e8f5e9', 'line': '#00cc66'}  # Green
}

MODERN_STYLESHEET = """
    QMainWindow { background-color: #f8fafc; }
    QMessageBox { background-color: white; font-size: 13px; color: #334155; }
    
    /* === BUTTON === */
    QPushButton {
        background-color: #e2e8f0; color: #334155; border: 1px solid #cbd5e1; 
        border-radius: 6px; padding: 6px 12px; font-weight: bold; font-size: 12px;
    }
    QPushButton:hover { background-color: #cbd5e1; color: #0f172a; }
    QPushButton:pressed { background-color: #94a3b8; color: #0f172a; }
    QPushButton:disabled { background-color: #f1f5f9; color: #94a3b8; border-color: #e2e8f0; }

    /* === CONTEXT MENU === */
    QMenu { background-color: white; border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px; }
    QMenu::item { padding: 6px 24px 6px 12px; color: #334155; font-size: 12px; background-color: transparent; }
    QMenu::item:selected { background-color: #eff6ff; color: #1d4ed8; border-radius: 3px; }
    QMenu::separator { height: 1px; background: #e2e8f0; margin: 4px 0; }

    /* === SCROLL BAR === */
    QScrollArea { border: none; background: transparent; }
    QScrollBar:vertical { border: none; background: #f1f5f9; width: 12px; margin: 0px; border-radius: 6px; }
    QScrollBar::handle:vertical { background: #cbd5e1; min-height: 30px; border-radius: 6px; margin: 2px; }
    QScrollBar::handle:vertical:hover { background: #94a3b8; }
    QScrollBar:horizontal { border: none; background: #f1f5f9; height: 12px; margin: 0px; border-radius: 6px; }
    QScrollBar::handle:horizontal { background: #cbd5e1; min-width: 30px; border-radius: 6px; margin: 2px; }
    QScrollBar::handle:horizontal:hover { background: #94a3b8; }
    
    /* === SEARCH INPUT === */
    QLineEdit {
        border: 1px solid #cbd5e1; border-radius: 12px; padding: 2px 10px;
        background: white; color: #334155; font-size: 11px;
    }
    QLineEdit:focus { border: 1px solid #3b82f6; }
"""

# ====================================================================
# HELPER: WORKER & DIALOGS
# ====================================================================

def initialize_data_storage():
    """
    Hàm này kiểm tra xem đã có đường dẫn lưu dữ liệu chưa.
    Nếu chưa, hiện hộp thoại yêu cầu chọn folder và lưu lại vào settings.json.
    """
    global DATA_ROOT_DIR
    
    saved_path = None
    
    # 1. Thử đọc từ file settings.json nếu tồn tại
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                saved_path = config.get('data_root_dir')
        except Exception:
            pass # Lỗi đọc file thì bỏ qua, coi như chưa có

    # 2. Kiểm tra đường dẫn đã lưu có hợp lệ không
    if saved_path and os.path.isdir(saved_path):
        DATA_ROOT_DIR = saved_path
        return

    # 3. Nếu chưa có hoặc đường dẫn cũ không còn tồn tại -> Hỏi người dùng
    # Cần tạo tạm một QWidget để làm cha cho hộp thoại (vì MainWindow chưa hiện)
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Icon.Information)
    msg.setWindowTitle("Cấu hình lần đầu")
    msg.setText("Chào mừng! Vui lòng chọn thư mục để lưu trữ dữ liệu GitFlow.")
    msg.setStandardButtons(QMessageBox.StandardButton.Ok)
    msg.exec()

    chosen_dir = QFileDialog.getExistingDirectory(None, "Chọn thư mục lưu dữ liệu GitFlow")

    if chosen_dir:
        DATA_ROOT_DIR = chosen_dir
        # Lưu lại vào file settings để lần sau không hỏi nữa
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump({'data_root_dir': chosen_dir}, f)
        except Exception as e:
            QMessageBox.warning(None, "Lỗi", f"Không thể lưu cấu hình: {e}")
    else:
        # Nếu người dùng bấm Cancel, dùng thư mục mặc định cạnh file app
        default_path = os.path.join(BASE_DIR, 'GitFlow_Data')
        if not os.path.exists(default_path):
            os.makedirs(default_path)
        DATA_ROOT_DIR = default_path
        QMessageBox.information(None, "Mặc định", f"Bạn chưa chọn thư mục. Dữ liệu sẽ lưu tại:\n{DATA_ROOT_DIR}")


class FileWorker(QThread):
    progress_signal = pyqtSignal(int, int, str)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, src, dst):
        super().__init__()
        self.src = src
        self.dst = dst

    def run(self):
        try:
            if os.path.exists(self.dst): shutil.rmtree(self.dst)
            os.makedirs(self.dst)
            if not os.path.exists(self.src): 
                self.finished_signal.emit()
                return

            total_files = sum([len(files) for r, d, files in os.walk(self.src)])
            copied_files = 0
            
            for root, dirs, files in os.walk(self.src):
                rel_path = os.path.relpath(root, self.src)
                target_dir = os.path.join(self.dst, rel_path)
                if not os.path.exists(target_dir): os.makedirs(target_dir)
                
                for file in files:
                    shutil.copy2(os.path.join(root, file), os.path.join(target_dir, file))
                    copied_files += 1
                    self.progress_signal.emit(copied_files, total_files, file)

            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))

class DiffDialog(QDialog):
    def __init__(self, old_content, new_content, file_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"🔍 So sánh Code: {file_name}")
        self.resize(1200, 800)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)
        self.setStyleSheet("background-color: #f8fafc;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # --- HEADER ---
        header_frame = QFrame()
        header_frame.setStyleSheet("background: #e2e8f0; border-bottom: 1px solid #cbd5e1; padding: 8px;")
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(10, 5, 10, 5)
        
        lbl_old = QLabel("🔴 BẢN CŨ (Trước đó)")
        lbl_old.setStyleSheet("color: #b91c1c; font-weight: bold;")
        
        lbl_new = QLabel("🟢 BẢN MỚI (Hiện tại)")
        lbl_new.setStyleSheet("color: #15803d; font-weight: bold;")
        
        h_layout.addWidget(lbl_old)
        h_layout.addStretch()
        h_layout.addWidget(lbl_new)
        layout.addWidget(header_frame)

        # --- CONTENT SPLITTER ---
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)
        splitter.setStyleSheet("QSplitter::handle { background-color: #cbd5e1; }")
        
        self.txt_old = QTextEdit()
        self.setup_editor(self.txt_old, is_old=True)
        
        self.txt_new = QTextEdit()
        self.setup_editor(self.txt_new, is_old=False)

        splitter.addWidget(self.txt_old)
        splitter.addWidget(self.txt_new)
        splitter.setSizes([600, 600])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        
        layout.addWidget(splitter, stretch=1)
        
        # --- FOOTER ---
        footer_frame = QFrame()
        footer_frame.setStyleSheet("background: white; border-top: 1px solid #cbd5e1; padding: 5px;")
        f_layout = QHBoxLayout(footer_frame)
        btn_close = QPushButton("Đóng")
        btn_close.clicked.connect(self.accept)
        btn_close.setFixedWidth(120)
        f_layout.addStretch()
        f_layout.addWidget(btn_close)
        layout.addWidget(footer_frame)

        self.calculate_diff(old_content, new_content)

    def setup_editor(self, editor, is_old):
        bg_color = "#fff1f2" if is_old else "#f0fdf4"
        editor.setReadOnly(True)
        editor.setFont(QFont("Consolas", 10))
        editor.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        editor.setStyleSheet(f"QTextEdit {{ border: none; background-color: {bg_color}; color: #334155; padding: 10px; }}")

    def calculate_diff(self, old, new):
        d = difflib.Differ()
        old_lines = old.splitlines() if old else []
        new_lines = new.splitlines() if new else []
        diff = list(d.compare(old_lines, new_lines))
        
        html_old = []
        html_new = []
        
        css_del = 'background-color: #fca5a5; text-decoration: line-through; color: #7f1d1d;'
        css_add = 'background-color: #86efac; color: #14532d; font-weight: bold;'
        css_nil = 'background-color: #f1f5f9; color: #cbd5e1;'
        css_norm = 'color: #334155;'
        
        def wrap(lineno, text, style):
            s_text = html.escape(text) if text else "&nbsp;"
            num_str = f"{lineno:>3} | " if lineno else "    | "
            return f'<div style="white-space: pre; font-family: Consolas; {style}"><span style="color:#94a3b8; user-select:none;">{num_str}</span>{s_text}</div>'

        line_old_idx = 0
        line_new_idx = 0

        for line in diff:
            code = line[:2]
            text = line[2:]
            
            if code == "- ":
                line_old_idx += 1
                html_old.append(wrap(line_old_idx, text, css_del))
                html_new.append(wrap(None, "", css_nil))
            elif code == "+ ":
                line_new_idx += 1
                html_old.append(wrap(None, "", css_nil))
                html_new.append(wrap(line_new_idx, text, css_add))
            elif code == "  ":
                line_old_idx += 1
                line_new_idx += 1
                html_old.append(wrap(line_old_idx, text, css_norm))
                html_new.append(wrap(line_new_idx, text, css_norm))
            elif code == "? ":
                continue

        self.txt_old.setHtml("".join(html_old))
        self.txt_new.setHtml("".join(html_new))
        
        sb_old = self.txt_old.verticalScrollBar()
        sb_new = self.txt_new.verticalScrollBar()
        sb_old.valueChanged.connect(sb_new.setValue)
        sb_new.valueChanged.connect(sb_old.setValue)
        
        h_sb_old = self.txt_old.horizontalScrollBar()
        h_sb_new = self.txt_new.horizontalScrollBar()
        h_sb_old.valueChanged.connect(h_sb_new.setValue)
        h_sb_new.valueChanged.connect(h_sb_old.setValue)

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
        btn_save = QPushButton("💾 Lưu Thay Đổi")
        btn_save.clicked.connect(self.save_file)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)
        self.load_file()
    def load_file(self):
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self.editor.setPlainText(f.read())
        except Exception as e: QMessageBox.critical(self, "Lỗi", str(e))
    def save_file(self):
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write(self.editor.toPlainText())
            self.accept()
        except Exception as e: QMessageBox.critical(self, "Lỗi", str(e))

class ModernProgressDialog(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(400, 150)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
        self.setStyleSheet("background: white; border: 1px solid #cbd5e1; border-radius: 8px;")
        layout = QVBoxLayout(self)
        self.lbl_status = QLabel("Đang chuẩn bị...")
        self.lbl_status.setStyleSheet("font-weight: bold; color: #334155; font-size: 14px; border: none;")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_status)
        self.lbl_file = QLabel("...")
        self.lbl_file.setStyleSheet("color: #64748b; font-size: 11px; font-style: italic; border: none;")
        self.lbl_file.setWordWrap(True)
        self.lbl_file.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_file)
        self.pbar = QProgressBar()
        self.pbar.setStyleSheet("""
            QProgressBar { border: 1px solid #e2e8f0; border-radius: 4px; text-align: center; height: 20px; background: #f8fafc; }
            QProgressBar::chunk { background-color: #3b82f6; width: 10px; margin: 0.5px; }
        """)
        self.pbar.setRange(0, 100)
        layout.addWidget(self.pbar)
    def update_progress(self, val, total, filename):
        percent = int(val / total * 100) if total > 0 else 0
        self.pbar.setValue(percent)
        self.lbl_file.setText(f"File: {filename}")
        self.lbl_status.setText(f"Đang xử lý... {percent}%")

# ====================================================================
# ENGINE CORE
# ====================================================================

class Commit:
    def __init__(self, id, message, branch_name, is_tag=None, note="", has_folder=False, source_id=None):
        self.id = id
        self.message = message
        self.branch_name = branch_name
        self.parents = []     
        self.children = []
        self.x = 0; self.y = 0 
        self.is_tag = is_tag
        self.note = note
        self.has_folder = has_folder
        self.source_id = source_id if source_id else id 

    def add_parent(self, commit):
        if commit not in self.parents: self.parents.append(commit)
    def add_child(self, commit):
        if commit not in self.children: self.children.append(commit)
    def to_dict(self):
        return {
            "id": self.id, "message": self.message, "branch_name": self.branch_name,
            "is_tag": self.is_tag, "parent_ids": [p.id for p in self.parents],
            "x": self.x, "y": self.y, "note": self.note, 
            "has_folder": self.has_folder,
            "source_id": self.source_id 
        }

class Branch:
    def __init__(self, name, color_key, head):
        self.name = name
        self.color_key = color_key
        colors = BRANCH_COLORS.get(color_key, BRANCH_COLORS['feature'])
        self.color = colors['node']
        self.lane_color = colors['lane']
        self.line = colors['line']
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
        self.x_step = 100; self.y_step = 70; self.base_start_x = 60
        self.current_max_x = self.base_start_x; self.current_max_y = 300 
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

    def resolve_storage_path(self, commit_id):
        if commit_id not in self.all_commits: return None
        commit = self.all_commits[commit_id]
        if commit.source_id and commit.source_id != commit.id:
            return self.get_commit_folder_path(commit.source_id)
        return self.get_commit_folder_path(commit.id)

    def link_commit_files(self, src_commit_id, dst_commit_id):
        if src_commit_id not in self.all_commits or dst_commit_id not in self.all_commits: return
        src = self.all_commits[src_commit_id]
        dst = self.all_commits[dst_commit_id]
        dst.source_id = src.source_id
        if src.has_folder:
            dst.has_folder = True

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
                           c_data["is_tag"], c_data.get("note", ""), 
                           c_data.get("has_folder", False),
                           c_data.get("source_id", None)) 
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
        c1 = Commit(f"{self.project_name[0]}-1", "Init", "master", is_tag=" ")
        c1.source_id = c1.id 
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
        if self.canvas: self.canvas.update_size(self.current_max_x + 400, self.current_max_y)

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
# CANVAS
# ====================================================================

class GitFlowCanvas(QWidget):
    node_selected = pyqtSignal(object, str) 

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.engine.canvas = self 
        self.selected_node_id = None
        self.node_positions = {} 
        
        self.highlighted_links = set()
        self.highlighted_nodes = set()
        
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setStyleSheet("background-color: white;") 
        
        self.node_radius = 8 
        self.anim_frame = 0
        self.filter_text = ""
        
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.animate_nodes)
        self.anim_timer.start(30)

        self.update_size(engine.current_max_x + 400, engine.current_max_y)

    def update_size(self, w, h):
        self.setMinimumSize(int(w), int(h))
        self.resize(int(w), int(h))

    def animate_nodes(self):
        if self.selected_node_id:
            self.anim_frame += 0.15 
            self.update()

    def set_filter(self, text):
        self.filter_text = text.lower()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setClipRect(event.rect())
        painter.fillRect(event.rect(), QColor("white"))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        
        self.node_positions.clear()
        
        self.draw_lanes(painter)
        self.draw_connections(painter)
        self.draw_branch_extensions(painter)
        self.draw_nodes_and_labels(painter)
        
        painter.end()

    def draw_lanes(self, painter):
        w = max(self.width(), self.engine.current_max_x + 400)
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
        draw_list = []
        GAP_THRESHOLD = self.engine.x_step * 1.2 

        for commit in self.engine.all_commits.values():
            for parent in commit.parents:
                p_branch = self.engine.branches.get(parent.branch_name)
                if not p_branch: continue

                is_same_branch = (parent.branch_name == commit.branch_name)
                distance = abs(commit.x - parent.x)
                
                base_color = QColor(p_branch.line)
                is_highlighted = (parent.id, commit.id) in self.highlighted_links
                
                if is_highlighted:
                    base_color = base_color.lighter(120)
                    width = 4.5 
                    base_color.setAlpha(220) 
                    z_order = 10
                    line_type = 'solid'
                else:
                    width = 3.0 
                    base_color.setAlpha(255)
                    if self.filter_text: base_color.setAlpha(40)
                    z_order = 1
                    line_type = 'solid'

                if is_same_branch and distance > GAP_THRESHOLD:
                    gap_color = QColor(base_color)
                    gap_color.setAlpha(150)
                    draw_list.append({
                        'p': parent, 'c': commit, 
                        'color': gap_color, 'width': 2.0, 
                        'type': 'gap',
                        'z': 0
                    })
                    continue 

                draw_list.append({
                    'p': parent, 'c': commit, 
                    'color': base_color, 'width': width, 
                    'type': line_type,
                    'z': z_order
                })

        draw_list.sort(key=lambda x: x['z'])

        for item in draw_list:
            parent, commit = item['p'], item['c']
            
            if item.get('type') == 'gap':
                pen = QPen(item['color'], item['width'], Qt.PenStyle.DashLine)
                pen.setDashPattern([5, 5])
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawLine(QPointF(parent.x, parent.y), QPointF(commit.x, commit.y))
            else:
                path = QPainterPath(QPointF(parent.x, parent.y))
                if parent.y == commit.y:
                    path.lineTo(QPointF(commit.x, commit.y))
                else:
                    dist = commit.x - parent.x
                    cp1 = QPointF(parent.x + dist * 0.5, parent.y)
                    cp2 = QPointF(commit.x - dist * 0.5, commit.y)
                    path.cubicTo(cp1, cp2, QPointF(commit.x, commit.y))

                pen = QPen(item['color'], item['width'])
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)

    def draw_branch_extensions(self, painter):
        w = max(self.width(), self.engine.current_max_x + 400)
        static_alpha = 100 

        TRUNK_PREFIXES = ['master', 'develop', 'release', 'hotfix']

        for b_name, branch in self.engine.branches.items():
            head = branch.head
            y = self.engine.branch_line_offset.get(b_name)
            if not y: continue
            
            should_draw = True
            is_trunk = any(b_name.lower().startswith(prefix) for prefix in TRUNK_PREFIXES)

            if not is_trunk:
                if head.children:
                    has_continuation = False
                    for child in head.children:
                        if child.branch_name == branch.name:
                            has_continuation = True
                            break
                    if not has_continuation:
                        should_draw = False

            if should_draw and head.x < w:
                col = QColor(branch.line)
                col.setAlpha(static_alpha) 
                
                pen = QPen(col, 2.0, Qt.PenStyle.DashLine)
                pen.setDashPattern([5, 5])
                painter.setPen(pen)
                painter.drawLine(QPointF(head.x + self.node_radius, y), QPointF(w, y))

    def draw_nodes_and_labels(self, painter):
        for commit in self.engine.all_commits.values():
            branch = self.engine.branches.get(commit.branch_name)
            if not branch: continue
            self.node_positions[commit.id] = QPointF(commit.x, commit.y)
            
            is_match = True
            if self.filter_text:
                search_data = f"{commit.id} {commit.message} {commit.is_tag}".lower()
                is_match = self.filter_text in search_data

            is_highlighted = commit.id in self.highlighted_nodes
            is_selected = (commit.id == self.selected_node_id)
            
            node_color = QColor(branch.color)
            
            if not is_match:
                node_color.setAlpha(40)
                painter.setPen(QPen(QColor(200, 200, 200, 50), 1))
                painter.setBrush(node_color)
                painter.drawEllipse(QPointF(commit.x, commit.y), self.node_radius, self.node_radius)
            else:
                if is_selected:
                    blink_val = (math.sin(self.anim_frame * 2.0) + 1) / 2
                    
                    glow_color = QColor(branch.color)
                    glow_color.setAlpha(150)
                    painter.setBrush(glow_color)
                    painter.setPen(Qt.PenStyle.NoPen)
                    glow_radius = self.node_radius + 5 + (blink_val * 4)
                    painter.drawEllipse(QPointF(commit.x, commit.y), glow_radius, glow_radius)
                    
                    painter.setPen(QPen(QColor("white"), 3.0))
                
                elif is_highlighted:
                    glow_color = QColor(branch.color)
                    glow_color.setAlpha(100) 
                    painter.setBrush(glow_color)
                    painter.setPen(Qt.PenStyle.NoPen)
                    glow_radius_static = self.node_radius + 4
                    painter.drawEllipse(QPointF(commit.x, commit.y), glow_radius_static, glow_radius_static)
                    
                    painter.setPen(QPen(QColor("white"), 2.0))
                else:
                    painter.setPen(QPen(QColor("white"), 2.0))

                painter.setBrush(node_color)
                painter.drawEllipse(QPointF(commit.x, commit.y), self.node_radius, self.node_radius)

            if commit.is_tag:
                tag_col = QColor('#1e293b')
                if not is_match: tag_col.setAlpha(40)
                painter.setPen(tag_col)
                painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
                painter.drawText(int(commit.x) - 15, int(commit.y) - 15, commit.is_tag)

            if commit.has_folder:
                folder_col = QColor("#ffaa00")
                if not is_match: folder_col.setAlpha(40)
                painter.setBrush(folder_col)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(commit.x + 8, commit.y - 8), 4, 4)

    def mousePressEvent(self, event):
        clicked_id = None
        for nid, pos in self.node_positions.items():
            if (event.position() - pos).manhattanLength() < 20: 
                clicked_id = nid
                break
        
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected_node_id = clicked_id
            if clicked_id:
                self.trace_lineage(clicked_id)
                self.node_selected.emit(self.engine, clicked_id)
            else:
                self.highlighted_links.clear()
                self.highlighted_nodes.clear()
                self.node_selected.emit(None, "")
            self.update()
        elif event.button() == Qt.MouseButton.RightButton and clicked_id:
            self.selected_node_id = clicked_id
            self.trace_lineage(clicked_id)
            self.node_selected.emit(self.engine, clicked_id)
            self.update()
            self.show_context_menu(event.globalPosition().toPoint())

    def trace_lineage(self, start_node_id):
        self.highlighted_links.clear()
        self.highlighted_nodes.clear()
        queue = [start_node_id]
        visited = {start_node_id}
        self.highlighted_nodes.add(start_node_id)
        while queue:
            curr_id = queue.pop(0)
            if curr_id not in self.engine.all_commits: continue
            commit = self.engine.all_commits[curr_id]
            for p in commit.parents:
                self.highlighted_links.add((p.id, curr_id))
                self.highlighted_nodes.add(p.id)
                if p.id not in visited:
                    visited.add(p.id)
                    queue.append(p.id)
        queue = [start_node_id]
        visited_fwd = {start_node_id}
        while queue:
            curr_id = queue.pop(0)
            if curr_id not in self.engine.all_commits: continue
            commit = self.engine.all_commits[curr_id]
            for child in commit.children:
                self.highlighted_links.add((curr_id, child.id))
                self.highlighted_nodes.add(child.id)
                if child.id not in visited_fwd:
                    visited_fwd.add(child.id)
                    queue.append(child.id)

    def show_context_menu(self, pos):
        menu = QMenu(self)
        wrapper = self.parent().parent().parent() 
        if not isinstance(wrapper, QWidget): wrapper = self.parent().parent()
        if not hasattr(wrapper, 'handle_logic'): return
        commit = self.engine.all_commits[self.selected_node_id]
        checkout_menu = menu.addMenu("🔀 Chuyển nhánh (Checkout)")
        for b_name in self.engine.branches:
            if b_name != self.engine.current_branch_name:
                checkout_menu.addAction(f"Sang {b_name.upper()}", lambda t=b_name: wrapper.handle_logic(f'checkout_{t}'))
        menu.addSeparator()
        menu.addAction("➕ Commit Mới", lambda: wrapper.handle_logic('push_commit'))
        merge_menu = menu.addMenu("🔀 Merge vào...")
        for b_name in self.engine.branches:
            if b_name != commit.branch_name:
                merge_menu.addAction(b_name.upper(), lambda t=b_name: wrapper.handle_logic(f'merge_to_{t}'))
        create_menu = menu.addMenu("✨ Tạo Nhánh Mới")
        create_menu.addAction("Feature", lambda: wrapper.handle_logic('create_feature'))
        if commit.branch_name == 'master':
            if 'develop' not in self.engine.branches:
                create_menu.addAction("Develop (Mới)", lambda: wrapper.handle_logic('create_develop'))
            create_menu.addAction("Hotfix", lambda: wrapper.handle_logic('create_hotfix'))
        menu.addSeparator()
        menu.addAction("🗑️ Xóa Node", lambda: wrapper.handle_logic('delete_node'))
        menu.exec(pos)

# ====================================================================
# PROJECT WRAPPER
# ====================================================================

class ProjectWrapper(QWidget):
    def __init__(self, project_name, main_window):
        super().__init__()
        self.main_window = main_window
        self.engine = ProjectEngine(project_name)
        self.is_minimized = True 
        
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
        self.setFixedHeight(36)
        self.setStyleSheet("""
            ProjectWrapper { background: white; border: 1px solid #cbd5e1; border-radius: 6px; margin-bottom: 8px; }
        """)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0) 
        self.layout.setSpacing(0)
        
        # HEADER
        header = QFrame()
        header.setFixedHeight(36) 
        header.setStyleSheet("""
            QFrame { background-color: #f1f5f9; border-bottom: 1px solid #cbd5e1; border-top-left-radius: 6px; border-top-right-radius: 6px; }
            QLabel { color: #334155; font-weight: bold; font-size: 12px; }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 0, 5, 0) 
        
        icon = QLabel("📦")
        title = QLabel(project_name.upper())
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Tìm (Msg, ID, Tag)...")
        self.search_input.setFixedWidth(150)
        self.search_input.textChanged.connect(self.on_search_changed)

        btn_style = "QToolButton { border-radius: 10px; border: none; background: transparent; font-weight: bold; color: #64748b; } QToolButton:hover { background: #e2e8f0; color: #1e293b; }"
        
        self.btn_end = QToolButton()
        self.btn_end.setText("⏩ End")
        self.btn_end.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_end.setStyleSheet("QToolButton { border: 1px solid #cbd5e1; border-radius: 4px; padding: 2px 8px; background: white; color: #334155; } QToolButton:hover { background: #f8fafc; color: #0f172a; }")
        self.btn_end.clicked.connect(self.scroll_to_end)

        self.btn_min = QToolButton()
        self.btn_min.setText("+") 
        self.btn_min.setFixedSize(20, 20)
        self.btn_min.setStyleSheet(btn_style)
        self.btn_min.clicked.connect(self.toggle_content)

        self.btn_close = QToolButton()
        self.btn_close.setText("✕")
        self.btn_close.setFixedSize(20, 20)
        self.btn_close.setStyleSheet(btn_style.replace("#e2e8f0", "#fee2e2").replace("#1e293b", "#ef4444"))
        self.btn_close.clicked.connect(self.delete_project)

        header_layout.addWidget(icon)
        header_layout.addWidget(title)
        header_layout.addSpacing(10)
        header_layout.addWidget(self.search_input)
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
        self.scroll_area.hide()
        
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
    
    def on_search_changed(self, text):
        self.canvas.set_filter(text)

    def scroll_to_end(self):
        if self.is_minimized: self.toggle_content()
        QApplication.processEvents()
        h_bar = self.scroll_area.horizontalScrollBar()
        if h_bar: h_bar.setValue(h_bar.maximum())

    def toggle_content(self):
        if self.is_minimized:
            self.scroll_area.show()
            self.btn_min.setText("−")
            self.setMinimumHeight(200)
            self.setMaximumHeight(16777215)
            QTimer.singleShot(100, self.scroll_to_end)
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
        
        if action.startswith('checkout_'):
            target_branch = action.replace('checkout_', '')
            eng.current_branch_name = target_branch
            QMessageBox.information(self, "Checkout", f"Đã chuyển sang nhánh: {target_branch.upper()}")
            return

        elif action == 'push_commit':
            if eng.current_branch_name not in eng.branches:
                if commit.branch_name in eng.branches:
                     eng.current_branch_name = commit.branch_name
                elif 'master' in eng.branches:
                     eng.current_branch_name = 'master'
                else:
                     eng.current_branch_name = list(eng.branches.keys())[0]

            nid = eng._get_new_commit_id()
            target_branch_obj = eng.branches[eng.current_branch_name]
            
            c = Commit(nid, "WIP", eng.current_branch_name)
            target_branch_obj.commit(c)
            c.add_parent(commit)
            commit.add_child(c)
            eng.all_commits[nid] = c
            eng.commit_x_map[nid] = eng.current_max_x + eng.x_step
            eng.current_max_x += eng.x_step
            
            eng.link_commit_files(commit.id, nid)

        elif action == 'create_feature':
            name = f"feature/{eng.commit_counter}"
            nid = eng._get_new_commit_id()
            c = Commit(nid, "Start", name)
            eng._create_new_branch(name, 'feature', c, commit)
            eng.link_commit_files(commit.id, nid)
            
        elif action == 'create_develop':
            if 'develop' not in eng.branches:
                nid = eng._get_new_commit_id()
                c = Commit(nid, "Dev Init", "develop")
                eng._create_new_branch('develop', 'develop', c, commit)
                eng.link_commit_files(commit.id, nid)
            else:
                QMessageBox.information(self, "Info", "Nhánh Develop đã tồn tại.")

        elif action == 'create_hotfix':
            name = f"hotfix/{eng.commit_counter}"
            nid = eng._get_new_commit_id()
            c = Commit(nid, "Hotfix", name)
            eng._create_new_branch(name, 'hotfix', c, commit)
            eng.link_commit_files(commit.id, nid)

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
                eng.link_commit_files(commit.id, nid)
            
        elif action == 'delete_node':
            if commit.children:
                QMessageBox.warning(self, "Lỗi", "Không thể xóa node ở giữa (Node này đang có node con)!")
                return
            
            for parent in commit.parents:
                if commit in parent.children:
                    parent.children.remove(commit)

            if commit in eng.branches[commit.branch_name].commits:
                eng.branches[commit.branch_name].commits.remove(commit)
            
            if cid in eng.all_commits:
                del eng.all_commits[cid]
            
            if commit.source_id == commit.id:
                path = eng.get_commit_folder_path(cid)
                if os.path.exists(path): 
                    try: shutil.rmtree(path)
                    except: pass
            
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
        self.icon_provider = QFileIconProvider() 
        self.thread_worker = None 
        
        self.setStyleSheet("background-color: white; border-left: 1px solid #e2e8f0;")
        self.setFixedWidth(300) 

        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # 1. Info Label
        self.lbl_info = QLabel("Chọn node để xem...")
        self.lbl_info.setStyleSheet("color: #64748b; font-size: 12px; padding: 10px; background: #f1f5f9; border-radius: 4px;")
        layout.addWidget(self.lbl_info)

        # 2. File Actions Box
        file_box = QFrame()
        file_box.setStyleSheet("background: #f8fafc; border-radius: 4px; padding: 5px;")
        fb_layout = QVBoxLayout(file_box)
        
        btn_row = QHBoxLayout()
        self.btn_up = QPushButton("⬆ Upload")
        self.btn_up.clicked.connect(self.upload)
        self.btn_open = QPushButton("📂 Folder")
        self.btn_open.clicked.connect(self.open_folder)
        btn_row.addWidget(self.btn_up)
        btn_row.addWidget(self.btn_open)
        fb_layout.addLayout(btn_row)

        self.btn_vscode = QPushButton("📝 Edit in VS Code")
        self.btn_vscode.setStyleSheet("QPushButton { background-color: #0ea5e9; color: white; border: none; } QPushButton:hover { background-color: #0284c7; } QPushButton:disabled { background-color: #cbd5e1; }")
        self.btn_vscode.clicked.connect(self.edit_in_vscode)
        fb_layout.addWidget(self.btn_vscode)
        
        self.lbl_lock = QLabel("🔒 Node bị khóa")
        self.lbl_lock.setStyleSheet("color: #ef4444; font-size: 11px; font-weight: bold; margin-top: 4px;")
        self.lbl_lock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_lock.hide()
        fb_layout.addWidget(self.lbl_lock)

        self.btn_up.setEnabled(False)
        self.btn_open.setEnabled(False)
        self.btn_vscode.setEnabled(False)
        layout.addWidget(file_box)

        # 3. RICH TEXT NOTE EDITOR
        layout.addWidget(QLabel("📝 Ghi Chú (Rich Text):"))
        
        # Toolbar Layout
        toolbar = QHBoxLayout()
        toolbar.setSpacing(2)
        
        btn_bold = QToolButton()
        btn_bold.setText("B")
        btn_bold.setToolTip("In đậm")
        btn_bold.setStyleSheet("font-weight: bold;")
        btn_bold.clicked.connect(self.text_bold)
        
        btn_italic = QToolButton()
        btn_italic.setText("I")
        btn_italic.setToolTip("In nghiêng")
        btn_italic.setStyleSheet("font-style: italic;")
        btn_italic.clicked.connect(self.text_italic)

        btn_img = QToolButton()
        btn_img.setText("🖼️")
        btn_img.setToolTip("Chèn ảnh")
        btn_img.clicked.connect(self.insert_image)

        toolbar.addWidget(btn_bold)
        toolbar.addWidget(btn_italic)
        toolbar.addWidget(btn_img)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.txt_note = QTextEdit()
        self.txt_note.setPlaceholderText("Nhập ghi chú... (Hỗ trợ ảnh, định dạng)")
        self.txt_note.setStyleSheet("border: 1px solid #cbd5e1; border-radius: 4px; background: white;")
        self.txt_note.textChanged.connect(self.save_note) 
        layout.addWidget(self.txt_note)

        # 4. File Tree
        layout.addWidget(QLabel("📂 File trong commit:"))
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setStyleSheet("border: 1px solid #cbd5e1; border-radius: 4px;")
        self.tree.itemDoubleClicked.connect(self.edit_file)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_tree_context_menu)
        layout.addWidget(self.tree)

    def text_bold(self):
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Bold if self.txt_note.fontWeight() != QFont.Weight.Bold else QFont.Weight.Normal)
        self.txt_note.mergeCurrentCharFormat(fmt)
        self.txt_note.setFocus()

    def text_italic(self):
        fmt = QTextCharFormat()
        fmt.setFontItalic(not self.txt_note.fontItalic())
        self.txt_note.mergeCurrentCharFormat(fmt)
        self.txt_note.setFocus()

    def insert_image(self):
        fname, _ = QFileDialog.getOpenFileName(self, 'Chọn ảnh', '.', "Images (*.png *.jpg *.jpeg *.bmp)")
        if fname:
            uri = QUrl.fromLocalFile(fname).toString()
            img_html = f'<br><img src="{uri}" width="200" /><br>'
            self.txt_note.insertHtml(img_html)

    def save_note(self):
        if self.current_engine:
            self.current_engine.update_note(self.current_node_id, self.txt_note.toHtml())

    def update_view(self, engine, nid):
        self.current_engine = engine
        self.current_node_id = nid
        self.tree.clear()
        
        if not engine or not nid:
            self.lbl_info.setText("Chưa chọn node.")
            self.txt_note.clear()
            self.btn_up.setEnabled(False)
            self.btn_open.setEnabled(False)
            self.btn_vscode.setEnabled(False)
            self.lbl_lock.hide()
            return

        commit = engine.all_commits[nid]
        self.lbl_info.setText(f"PROJECT: {engine.project_name}\nBRANCH: {commit.branch_name}\nID: {nid}")
        
        self.txt_note.blockSignals(True)
        self.txt_note.setHtml(commit.note) 
        self.txt_note.blockSignals(False)
        
        is_locked = len(commit.children) > 0
        if is_locked:
            self.btn_up.setEnabled(False)
            self.btn_vscode.setEnabled(False)
            self.lbl_lock.show()
            self.lbl_lock.setText(f"🔒 Bị khóa: Xóa {len(commit.children)} node con trước.")
        else:
            self.btn_up.setEnabled(True)
            self.lbl_lock.hide()
        
        real_path = engine.resolve_storage_path(nid)
        has_content = commit.has_folder and real_path and os.path.exists(real_path)
        
        self.btn_open.setEnabled(has_content)
        if not is_locked:
            self.btn_vscode.setEnabled(has_content)
        
        if has_content:
            self.load_tree(real_path)

    def load_tree(self, path):
        root = QTreeWidgetItem(self.tree, [os.path.basename(path)])
        root.setIcon(0, self.icon_provider.icon(QFileInfo(path)))
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
                        found.setIcon(0, self.icon_provider.icon(QFileInfo(os.path.join(r))))
                    curr = found
            for file in f:
                full_path = os.path.join(r, file)
                item = QTreeWidgetItem(curr, [file])
                item.setData(0, Qt.ItemDataRole.UserRole, full_path)
                item.setIcon(0, self.icon_provider.icon(QFileInfo(full_path)))
        self.tree.expandAll()

    def show_tree_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item: return
        fpath = item.data(0, Qt.ItemDataRole.UserRole)
        if not fpath or not os.path.isfile(fpath): return
        menu = QMenu(self)
        menu.addAction("👀 So sánh với bản cũ (Diff)", lambda: self.diff_file(fpath))
        menu.exec(self.tree.mapToGlobal(pos))

    def diff_file(self, current_file_path):
        commit = self.current_engine.all_commits[self.current_node_id]
        if not commit.parents:
            QMessageBox.information(self, "Info", "Node này không có cha. Không thể so sánh.")
            return

        parent = commit.parents[0]
        parent_store_path = self.current_engine.resolve_storage_path(parent.id)
        if not parent_store_path or not os.path.exists(parent_store_path):
            QMessageBox.warning(self, "Lỗi", "Không tìm thấy dữ liệu của node cha.")
            return

        current_store_path = self.current_engine.resolve_storage_path(commit.id)
        rel_path = os.path.relpath(current_file_path, current_store_path)
        old_file_path = os.path.join(parent_store_path, rel_path)

        if not os.path.exists(old_file_path):
            QMessageBox.warning(self, "Lỗi", "File này không tồn tại trong phiên bản cũ.")
            return

        try:
            with open(old_file_path, 'r', encoding='utf-8') as f: old_content = f.read()
            with open(current_file_path, 'r', encoding='utf-8') as f: new_content = f.read()
            DiffDialog(old_content, new_content, os.path.basename(current_file_path), self).exec()
        except Exception as e:
            QMessageBox.warning(self, "Lỗi", f"Không thể đọc file: {e}")

    def edit_file(self, item, col):
        fpath = item.data(0, Qt.ItemDataRole.UserRole)
        if fpath and os.path.isfile(fpath):
            FileEditorDialog(fpath, self).exec()

    def upload(self):
        if not self.current_engine or not self.current_node_id:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn Node trước!")
            return
        d = QFileDialog.getExistingDirectory(self, "Chọn Folder Code")
        if d:
            commit = self.current_engine.all_commits[self.current_node_id]
            commit.source_id = commit.id 
            dst_path = self.current_engine.get_commit_folder_path(commit.id)
            self.run_file_worker(d, dst_path, "Đang tải file lên...")

    def run_file_worker(self, src, dst, title):
        pd = ModernProgressDialog(title, self)
        pd.show()
        self.thread_worker = FileWorker(src, dst)
        self.thread_worker.progress_signal.connect(pd.update_progress)
        def on_finished():
            pd.close()
            commit = self.current_engine.all_commits[self.current_node_id]
            commit.has_folder = True
            self.current_engine.save_data()
            self.update_view(self.current_engine, self.current_node_id)
            self.current_engine.canvas.update()
            QMessageBox.information(self, "Thành công", "Xử lý file hoàn tất!")
        self.thread_worker.finished_signal.connect(on_finished)
        self.thread_worker.error_signal.connect(lambda e: (pd.close(), QMessageBox.critical(self, "Lỗi", e)))
        self.thread_worker.start()

    def open_folder(self):
        if not self.current_engine or not self.current_node_id: return
        p = self.current_engine.resolve_storage_path(self.current_node_id)
        if p and os.path.exists(p):
            if sys.platform == 'win32': os.startfile(p)
            else: subprocess.Popen(['xdg-open', p])

    def edit_in_vscode(self):
        if not self.current_engine or not self.current_node_id: return
        commit = self.current_engine.all_commits[self.current_node_id]
        if commit.source_id != commit.id:
            src_path = self.current_engine.resolve_storage_path(self.current_node_id)
            dst_path = self.current_engine.get_commit_folder_path(commit.id)
            pd = ModernProgressDialog("Đang tạo không gian làm việc...", self)
            pd.show()
            self.thread_worker = FileWorker(src_path, dst_path)
            self.thread_worker.progress_signal.connect(pd.update_progress)
            def on_finished_vscode():
                pd.close()
                commit.source_id = commit.id
                self.current_engine.save_data()
                self.update_view(self.current_engine, self.current_node_id)
                self.launch_vscode(dst_path)
            self.thread_worker.finished_signal.connect(on_finished_vscode)
            self.thread_worker.start()
        else:
            self.launch_vscode(self.current_engine.get_commit_folder_path(commit.id))

    def launch_vscode(self, path):
        if os.path.exists(path):
            try: subprocess.Popen(["code", path], shell=True)
            except Exception as e: QMessageBox.critical(self, "Lỗi", f"Không thể mở VS Code: {e}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        if not os.path.exists(DATA_ROOT_DIR): os.makedirs(DATA_ROOT_DIR)

        self.setWindowTitle("Git Flow Ultimate - Sync Edition")
        self.resize(1300, 800) 
        self.setStyleSheet(MODERN_STYLESHEET) 

        # --- MENU BAR CHO BACKUP ---
        menubar = self.menuBar()
        drive_menu = menubar.addMenu("☁️ Google Drive / Backup")
        
        action_backup = QAction("📤 Backup dữ liệu (Zip)", self)
        action_backup.triggered.connect(self.backup_data)
        drive_menu.addAction(action_backup)
        
        action_restore = QAction("📥 Khôi phục dữ liệu (Restore)", self)
        action_restore.triggered.connect(self.restore_data)
        drive_menu.addAction(action_restore)

        # --- GIAO DIỆN CHÍNH ---
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
        main_split.setSizes([950, 350]) 
        
        self.setCentralWidget(main_split)
        self.load_projects()

    def backup_data(self):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"GitFlow_Backup_{timestamp}.zip"
        
        file_path, _ = QFileDialog.getSaveFileName(self, "Lưu File Backup (Chọn Google Drive)", default_name, "Zip Files (*.zip)")
        
        if file_path:
            try:
                pd = ModernProgressDialog("Đang nén dữ liệu...", self)
                pd.show()
                QApplication.processEvents()
                
                with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(DATA_ROOT_DIR):
                        for file in files:
                            abs_path = os.path.join(root, file)
                            rel_path = os.path.relpath(abs_path, DATA_ROOT_DIR)
                            zipf.write(abs_path, rel_path)
                            
                pd.close()
                QMessageBox.information(self, "Thành công", f"Đã backup dữ liệu tới:\n{file_path}\n\n(Dữ liệu sẽ tự động lên mây nếu bạn lưu trong Google Drive)")
            except Exception as e:
                QMessageBox.critical(self, "Lỗi Backup", str(e))

    def restore_data(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Chọn File Backup", "", "Zip Files (*.zip)")
        if file_path:
            reply = QMessageBox.warning(self, "Cảnh báo", 
                                        "Thao tác này sẽ XÓA TOÀN BỘ dữ liệu hiện tại và thay thế bằng bản backup.\nBạn có chắc chắn không?",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    pd = ModernProgressDialog("Đang khôi phục...", self)
                    pd.show()
                    QApplication.processEvents()

                    if os.path.exists(DATA_ROOT_DIR):
                        shutil.rmtree(DATA_ROOT_DIR)
                    os.makedirs(DATA_ROOT_DIR)

                    with zipfile.ZipFile(file_path, 'r') as zipf:
                        zipf.extractall(DATA_ROOT_DIR)
                    
                    pd.close()
                    QMessageBox.information(self, "Thành công", "Khôi phục dữ liệu xong! Ứng dụng sẽ tải lại.")
                    
                    for i in reversed(range(self.proj_layout.count())): 
                        self.proj_layout.itemAt(i).widget().setParent(None)
                    self.load_projects()
                    
                except Exception as e:
                    QMessageBox.critical(self, "Lỗi Restore", str(e))

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
    # 1. Fix ID cho Taskbar Windows
    try:
        import ctypes
        myappid = 'mycompany.gitflow.app.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    # 2. Khởi tạo App
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseDesktopOpenGL)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Set Font mặc định cho đẹp (tùy chọn)
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # 3. GẮN ICON (Code cũ của bạn)
    icon_path = os.path.join(BASE_DIR, 'R.ico')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # --- [MỚI] --- 4. GỌI HÀM CHỌN THƯ MỤC DỮ LIỆU
    initialize_data_storage()
    
    # Kiểm tra lại lần cuối để đảm bảo biến global đã có giá trị
    if not DATA_ROOT_DIR:
        # Fallback cực đoan nếu mọi thứ thất bại
        DATA_ROOT_DIR = os.path.join(BASE_DIR, 'GitFlow_Data')

    # 5. Hiển thị cửa sổ chính
    # Lúc này MainWindow khởi tạo sẽ dùng đúng DATA_ROOT_DIR mà người dùng vừa chọn
    win = MainWindow()
    win.show()
    
    sys.exit(app.exec())
