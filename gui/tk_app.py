"""
股票数据可视化 - Tkinter 版本（精简升级版）

保留原版 Tkinter 风格，代码更清晰，方便对比。
如需运行：py -3 gui/tk_app.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from pathlib import Path


class StockGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("股票数据分析（Tkinter 升级版）")
        self.root.geometry("1000x700")

        self.df = None

        self._create_widgets()

    def _create_widgets(self):
        # 顶部按钮栏
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill=tk.X)

        ttk.Button(top_frame, text="打开数据文件", command=self.load_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="绘制 RSI", command=self.plot_rsi).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="退出", command=self.root.quit).pack(side=tk.RIGHT, padx=5)

        # 数据表格
        self.tree = ttk.Treeview(self.root, columns=("日期", "收盘", "开盘", "高", "低"), show="headings", height=12)
        for col in ("日期", "收盘", "开盘", "高", "低"):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120, anchor=tk.CENTER)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 图表区域
        self.fig, self.ax = plt.subplots(figsize=(8, 4))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    def load_data(self):
        filepath = filedialog.askopenfilename(
            title="选择股票数据 CSV",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")]
        )
        if not filepath:
            return

        try:
            self.df = pd.read_csv(filepath)
            self._refresh_table()
            messagebox.showinfo("成功", f"已加载 {len(self.df)} 条记录")
        except Exception as e:
            messagebox.showerror("错误", f"加载失败：{e}")

    def _refresh_table(self):
        if self.df is None:
            return

        # 清空表格
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 插入前 50 行
        for _, row in self.df.head(50).iterrows():
            values = [row.get(c, "") for c in ("日期", "收盘", "开盘", "高", "低")]
            self.tree.insert("", tk.END, values=values)

    def plot_rsi(self):
        if self.df is None or "收盘" not in self.df.columns:
            messagebox.showwarning("提示", "请先加载包含「收盘」列的数据")
            return

        self.ax.clear()

        # 简单 RSI
        period = 14
        delta = self.df["收盘"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        self.ax.plot(self.df.index, self.df["收盘"], label="收盘价", color="blue")
        ax2 = self.ax.twinx()
        ax2.plot(self.df.index, rsi, label=f"RSI({period})", color="red", alpha=0.7)
        ax2.axhline(70, color="gray", linestyle="--", alpha=0.5)
        ax2.axhline(30, color="gray", linestyle="--", alpha=0.5)

        self.ax.set_title("价格与 RSI")
        self.ax.legend(loc="upper left")
        ax2.legend(loc="upper right")

        self.canvas.draw()


if __name__ == "__main__":
    root = tk.Tk()
    app = StockGUI(root)
    root.mainloop()