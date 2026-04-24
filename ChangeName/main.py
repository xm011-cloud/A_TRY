#!/usr/bin/env python3
"""
批量文件重命名工具 - 图形界面版（优化窗口缩放）
支持拖拽文件/文件夹，支持多种重命名规则，窗口自适应缩放
"""

import os
import re
import threading
from pathlib import Path
from typing import List, Tuple
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# 尝试导入拖拽支持
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False
    TkinterDnD = tk.Tk


class FileRenamerGUI:
    def __init__(self):
        self.root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
        self.root.title("批量文件重命名工具")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)

        # 数据
        self.files: List[Path] = []
        self.preview_data: List[Tuple[Path, Path]] = []

        # 创建界面
        self.create_widgets()
        self.setup_drag_drop()

        # 变量绑定
        self.bind_events()
        self.update_preview()

        self.root.mainloop()

    def create_widgets(self):
        """创建所有控件，使用grid布局并配置权重实现缩放"""
        # 主框架，填充整个窗口
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        # 配置主框架的行列权重：第0行（文件列表）和第2行（预览）可拉伸
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=3)   # 文件列表区域
        main_frame.rowconfigure(1, weight=0)   # 规则区域（固定高度）
        main_frame.rowconfigure(2, weight=2)   # 预览区域

        # ========== 1. 文件列表区域 ==========
        list_frame = ttk.LabelFrame(main_frame, text="文件列表 (支持拖拽文件/文件夹)", padding="5")
        list_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(1, weight=1)

        # 按钮栏
        btn_frame = ttk.Frame(list_frame)
        btn_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        btn_frame.columnconfigure(7, weight=1)  # 右侧留空占位

        ttk.Button(btn_frame, text="添加文件", command=self.add_files).grid(row=0, column=0, padx=2)
        ttk.Button(btn_frame, text="添加文件夹", command=self.add_folder).grid(row=0, column=1, padx=2)
        ttk.Button(btn_frame, text="清空全部", command=self.clear_files).grid(row=0, column=2, padx=2)
        ttk.Button(btn_frame, text="移除选中", command=self.remove_selected).grid(row=0, column=3, padx=2)

        self.recursive_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(btn_frame, text="递归子目录", variable=self.recursive_var).grid(row=0, column=4, padx=(10, 0))

        # 文件列表框 + 滚动条
        list_container = ttk.Frame(list_frame)
        list_container.grid(row=1, column=0, sticky="nsew")
        list_container.columnconfigure(0, weight=1)
        list_container.rowconfigure(0, weight=1)

        self.file_listbox = tk.Listbox(list_container, selectmode=tk.EXTENDED)
        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=self.file_listbox.yview)
        self.file_listbox.configure(yscrollcommand=scrollbar.set)
        self.file_listbox.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        # ========== 2. 规则设置区域 ==========
        rule_frame = ttk.LabelFrame(main_frame, text="重命名规则", padding="10")
        rule_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        # 规则区域使用网格布局，配置列权重使输入框可扩展
        for i in range(6):
            rule_frame.columnconfigure(i, weight=1 if i % 2 == 1 else 0)

        row = 0
        # 替换
        ttk.Label(rule_frame, text="替换:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        self.replace_old = tk.StringVar()
        self.replace_new = tk.StringVar()
        ttk.Entry(rule_frame, textvariable=self.replace_old).grid(row=row, column=1, sticky="ew", padx=5, pady=2)
        ttk.Label(rule_frame, text="→").grid(row=row, column=2, padx=5)
        ttk.Entry(rule_frame, textvariable=self.replace_new).grid(row=row, column=3, sticky="ew", padx=5, pady=2)
        row += 1

        # 前缀/后缀
        ttk.Label(rule_frame, text="前缀:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        self.prefix = tk.StringVar()
        ttk.Entry(rule_frame, textvariable=self.prefix).grid(row=row, column=1, sticky="ew", padx=5, pady=2)
        ttk.Label(rule_frame, text="后缀:").grid(row=row, column=2, sticky="w", padx=5, pady=2)
        self.suffix = tk.StringVar()
        ttk.Entry(rule_frame, textvariable=self.suffix).grid(row=row, column=3, sticky="ew", padx=5, pady=2)
        row += 1

        # 正则替换
        ttk.Label(rule_frame, text="正则替换:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        self.regex_pattern = tk.StringVar()
        self.regex_repl = tk.StringVar()
        ttk.Entry(rule_frame, textvariable=self.regex_pattern).grid(row=row, column=1, sticky="ew", padx=5, pady=2)
        ttk.Label(rule_frame, text="→").grid(row=row, column=2, padx=5)
        ttk.Entry(rule_frame, textvariable=self.regex_repl).grid(row=row, column=3, sticky="ew", padx=5, pady=2)
        self.ignore_case = tk.BooleanVar(value=False)
        ttk.Checkbutton(rule_frame, text="忽略大小写", variable=self.ignore_case).grid(row=row, column=4, columnspan=2, sticky="w", padx=5)
        row += 1

        # 序号模式
        ttk.Label(rule_frame, text="序号模式:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        self.number_pattern = tk.StringVar()
        ttk.Entry(rule_frame, textvariable=self.number_pattern).grid(row=row, column=1, columnspan=3, sticky="ew", padx=5, pady=2)
        ttk.Label(rule_frame, text="(例如: photo_{:03d} → photo_001.jpg)").grid(row=row, column=4, columnspan=2, sticky="w", padx=5)
        row += 1

        # 扩展名过滤
        ttk.Label(rule_frame, text="仅处理扩展名:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        self.ext_filter = tk.StringVar()
        ttk.Entry(rule_frame, textvariable=self.ext_filter).grid(row=row, column=1, columnspan=3, sticky="ew", padx=5, pady=2)
        ttk.Label(rule_frame, text="(多个用逗号分隔，如 .jpg,.png)").grid(row=row, column=4, columnspan=2, sticky="w", padx=5)
        row += 1

        # 文件名筛选
        ttk.Label(rule_frame, text="筛选文件名:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        self.name_filter = tk.StringVar()
        ttk.Entry(rule_frame, textvariable=self.name_filter).grid(row=row, column=1, columnspan=3, sticky="ew", padx=5, pady=2)
        ttk.Label(rule_frame, text="(正则匹配，不填则不过滤)").grid(row=row, column=4, columnspan=2, sticky="w", padx=5)

        # ========== 3. 预览区域 ==========
        preview_frame = ttk.LabelFrame(main_frame, text="预览 (将重命名的文件)", padding="5")
        preview_frame.grid(row=2, column=0, sticky="nsew")
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)

        # 文本框 + 双滚动条
        self.preview_text = tk.Text(preview_frame, wrap=tk.NONE, font=("Consolas", 9))
        vsb = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=self.preview_text.yview)
        hsb = ttk.Scrollbar(preview_frame, orient=tk.HORIZONTAL, command=self.preview_text.xview)
        self.preview_text.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.preview_text.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        # ========== 4. 底部按钮栏 ==========
        action_frame = ttk.Frame(main_frame)
        action_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        action_frame.columnconfigure(2, weight=1)  # 右侧占位

        ttk.Button(action_frame, text="刷新预览", command=self.update_preview).grid(row=0, column=0, padx=5)
        ttk.Button(action_frame, text="执行重命名", command=self.execute_rename).grid(row=0, column=1, padx=5)

        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def bind_events(self):
        """规则输入框变更时自动刷新预览"""
        vars_to_trace = [
            self.replace_old, self.replace_new, self.prefix, self.suffix,
            self.regex_pattern, self.regex_repl, self.number_pattern,
            self.ext_filter, self.name_filter
        ]
        for var in vars_to_trace:
            var.trace_add('write', lambda *_: self.update_preview())
        self.ignore_case.trace_add('write', lambda *_: self.update_preview())

    def setup_drag_drop(self):
        if HAS_DND:
            self.file_listbox.drop_target_register(DND_FILES)
            self.file_listbox.dnd_bind('<<Drop>>', self.on_drop)
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind('<<Drop>>', self.on_drop)

    def on_drop(self, event):
        raw_data = event.data
        paths = self.parse_drop_data(raw_data)
        for p in paths:
            self.add_path(p)
        self.update_preview()

    def parse_drop_data(self, data: str) -> List[str]:
        import shlex
        data = data.strip()
        if data.startswith('{') and data.endswith('}'):
            data = data[1:-1]
        try:
            parts = shlex.split(data)
        except:
            parts = data.split()
        return [os.path.normpath(p) for p in parts]

    def add_files(self):
        paths = filedialog.askopenfilenames(title="选择文件")
        for p in paths:
            self.add_path(p)
        self.update_preview()

    def add_folder(self):
        folder = filedialog.askdirectory(title="选择文件夹")
        if not folder:
            return
        self.add_path(folder, is_folder=True)
        self.update_preview()

    def add_path(self, path: str, is_folder: bool = False):
        p = Path(path)
        if not p.exists():
            return
        if is_folder or p.is_dir():
            recursive = self.recursive_var.get()
            files = list(p.rglob("*")) if recursive else list(p.glob("*"))
            files = [f for f in files if f.is_file()]
            self.files.extend(files)
        else:
            self.files.append(p)
        # 去重
        self.files = list({str(f): f for f in self.files}.values())

    def clear_files(self):
        self.files.clear()
        self.update_preview()

    def remove_selected(self):
        selected = self.file_listbox.curselection()
        for idx in reversed(selected):
            if idx < len(self.files):
                del self.files[idx]
        self.update_preview()

    def update_preview(self):
        # 更新文件列表框显示
        self.file_listbox.delete(0, tk.END)
        for f in self.files:
            self.file_listbox.insert(tk.END, str(f))

        self.preview_data.clear()
        if not self.files:
            self.preview_text.delete(1.0, tk.END)
            self.preview_text.insert(tk.END, "无文件")
            self.status_var.set("文件数: 0")
            return

        # 解析过滤条件
        ext_filter_str = self.ext_filter.get().strip()
        ext_list = []
        if ext_filter_str:
            ext_list = [e.strip().lower() for e in ext_filter_str.split(',')]
            ext_list = [e if e.startswith('.') else f'.{e}' for e in ext_list]

        name_pattern = self.name_filter.get().strip()
        name_regex = None
        if name_pattern:
            flags = re.IGNORECASE if self.ignore_case.get() else 0
            try:
                name_regex = re.compile(name_pattern, flags)
            except re.error:
                self.preview_text.delete(1.0, tk.END)
                self.preview_text.insert(tk.END, "错误：筛选正则无效")
                return

        rename_func = self.build_rename_function()

        filtered = []
        for src in self.files:
            if ext_list and src.suffix.lower() not in ext_list:
                continue
            if name_regex and not name_regex.search(src.name):
                continue
            filtered.append(src)

        filtered.sort(key=lambda p: p.name)

        lines = []
        for idx, src in enumerate(filtered, 1):
            try:
                new_name = rename_func(src, idx)
                if not new_name:
                    new_name = src.name
                dst = src.parent / new_name
                self.preview_data.append((src, dst))
                lines.append(f"{src.name}  →  {dst.name}")
            except Exception as e:
                lines.append(f"{src.name}  →  错误: {e}")

        self.preview_text.delete(1.0, tk.END)
        if lines:
            self.preview_text.insert(tk.END, "\n".join(lines))
        else:
            self.preview_text.insert(tk.END, "没有符合过滤条件的文件")

        self.status_var.set(f"文件总数: {len(self.files)} | 符合条件: {len(filtered)}")

    def build_rename_function(self):
        rules = []

        old = self.replace_old.get()
        new = self.replace_new.get()
        if old:
            rules.append(lambda name: name.replace(old, new))

        prefix = self.prefix.get()
        suffix = self.suffix.get()

        if prefix:
            rules.append(lambda name: prefix + name)
        if suffix:
            def add_suffix(name):
                stem = Path(name).stem
                ext = Path(name).suffix
                return f"{stem}{suffix}{ext}"
            rules.append(add_suffix)

        regex_pat = self.regex_pattern.get()
        regex_repl = self.regex_repl.get()
        if regex_pat:
            flags = re.IGNORECASE if self.ignore_case.get() else 0
            try:
                regex = re.compile(regex_pat, flags)
                rules.append(lambda name: regex.sub(regex_repl, name))
            except re.error:
                pass

        number_pat = self.number_pattern.get().strip()
        if number_pat:
            def number_rename(src: Path, idx: int) -> str:
                return number_pat.format(idx) + src.suffix
            return number_rename

        def combined_rename(src: Path, idx: int) -> str:
            name = src.name
            for rule in rules:
                name = rule(name)
            return name
        return combined_rename

    def execute_rename(self):
        if not self.preview_data:
            messagebox.showinfo("提示", "没有要重命名的文件")
            return
        if not messagebox.askyesno("确认重命名", f"即将重命名 {len(self.preview_data)} 个文件。\n是否继续？", icon='warning'):
            return

        # 检查冲突
        conflicts = [(src, dst) for src, dst in self.preview_data if dst.exists() and dst != src]
        if conflicts:
            msg = "以下目标文件已存在，将被覆盖：\n" + "\n".join(f"{src.name} -> {dst.name}" for src, dst in conflicts[:10])
            if len(conflicts) > 10:
                msg += f"\n...等{len(conflicts)}个"
            msg += "\n\n是否继续？"
            if not messagebox.askyesno("冲突警告", msg, icon='warning'):
                return

        success = 0
        errors = []
        for src, dst in self.preview_data:
            try:
                if dst.exists() and dst != src:
                    dst.unlink()
                src.rename(dst)
                success += 1
            except Exception as e:
                errors.append(f"{src.name} -> {dst.name}: {e}")

        # 更新文件列表为新路径
        new_files = [dst for _, dst in self.preview_data if dst.exists()]
        self.files = new_files
        self.update_preview()

        msg = f"完成！成功 {success} 个，失败 {len(errors)} 个。"
        if errors:
            msg += "\n错误详情：\n" + "\n".join(errors[:5])
        messagebox.showinfo("结果", msg)
        self.status_var.set(msg)


if __name__ == "__main__":
    app = FileRenamerGUI()
