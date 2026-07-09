import argparse
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageDraw, ImageTk


class MaskDrawApp:
    def __init__(self, root, image_path, mask_out, image_out=None, load_mask=None, output=None):
        self.root = root
        self.image_path = Path(image_path)
        self.mask_out = Path(mask_out)
        self.image_out = Path(image_out) if image_out else self.mask_out.with_name("target_prepared.png")
        self.output = Path(output) if output else None
        self.root.title("手动蒙版工具")
        self.root.geometry("1200x900")

        self.image = Image.open(self.image_path).convert("RGB")
        if load_mask and Path(load_mask).exists():
            loaded_mask = Image.open(load_mask).convert("L")
            if loaded_mask.size != self.image.size:
                raise ValueError(f"蒙版尺寸必须和原图一致: 原图 {self.image.size}, 蒙版 {loaded_mask.size}")
            self.mask = loaded_mask
        else:
            self.mask = Image.new("L", self.image.size, 0)
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.last = None
        self.tk_image = None

        top = ttk.Frame(root)
        top.pack(fill=tk.X, padx=6, pady=4)
        ttk.Label(top, text=f"原图: {self.image_path}  尺寸: {self.image.width}x{self.image.height}").pack(side=tk.LEFT)
        ttk.Button(top, text="保存目标图+蒙版", command=self.save_all).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top, text="打开输出", command=self.open_output).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top, text="清空", command=self.clear_mask).pack(side=tk.RIGHT, padx=4)

        tools = ttk.Frame(root)
        tools.pack(fill=tk.X, padx=6, pady=(0, 4))
        ttk.Label(tools, text="左键涂白 / 右键擦除    画笔").pack(side=tk.LEFT)
        self.brush = tk.IntVar(value=36)
        ttk.Scale(tools, from_=4, to=200, variable=self.brush, orient=tk.HORIZONTAL, length=220).pack(side=tk.LEFT, padx=6)
        self.status = ttk.Label(tools, text=f"保存到: {self.image_out} / {self.mask_out}")
        self.status.pack(side=tk.RIGHT)

        self.canvas = tk.Canvas(root, bg="#202020", cursor="cross")
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.canvas.bind("<Configure>", lambda _e: self.refresh())
        self.canvas.bind("<Button-1>", lambda e: self.start(e, 255))
        self.canvas.bind("<B1-Motion>", lambda e: self.paint(e, 255))
        self.canvas.bind("<ButtonRelease-1>", self.stop)
        self.canvas.bind("<Button-3>", lambda e: self.start(e, 0))
        self.canvas.bind("<B3-Motion>", lambda e: self.paint(e, 0))
        self.canvas.bind("<ButtonRelease-3>", self.stop)
        self.refresh()

    def canvas_to_image(self, event):
        x = int((event.x - self.offset_x) / self.scale)
        y = int((event.y - self.offset_y) / self.scale)
        if x < 0 or y < 0 or x >= self.image.width or y >= self.image.height:
            return None
        return x, y

    def start(self, event, color):
        self.last = None
        self.paint(event, color)

    def stop(self, _event):
        self.last = None

    def paint(self, event, color):
        pt = self.canvas_to_image(event)
        if pt is None:
            return
        x, y = pt
        r = max(1, int(self.brush.get()))
        draw = ImageDraw.Draw(self.mask)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=color)
        if self.last is not None:
            draw.line((self.last[0], self.last[1], x, y), fill=color, width=r * 2)
        self.last = pt
        self.refresh()

    def clear_mask(self):
        self.mask = Image.new("L", self.image.size, 0)
        self.refresh()
        self.status.config(text="已清空蒙版")

    def save_all(self):
        self.image_out.parent.mkdir(parents=True, exist_ok=True)
        self.mask_out.parent.mkdir(parents=True, exist_ok=True)
        self.image.save(self.image_out)
        self.mask.save(self.mask_out)
        self.status.config(text=f"已保存: {self.image_out} / {self.mask_out}")

    def open_output(self):
        if self.output and self.output.exists():
            subprocess.Popen(["explorer", "/select,", str(self.output)])
        else:
            subprocess.Popen(["explorer", str(self.mask_out.parent)])

    def refresh(self):
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        self.scale = min(cw / self.image.width, ch / self.image.height, 1.0)
        dw = max(1, int(self.image.width * self.scale))
        dh = max(1, int(self.image.height * self.scale))
        self.offset_x = (cw - dw) // 2
        self.offset_y = (ch - dh) // 2

        view = self.image.resize((dw, dh), Image.Resampling.LANCZOS).convert("RGBA")
        small_mask = self.mask.resize((dw, dh), Image.Resampling.NEAREST)
        overlay = Image.new("RGBA", (dw, dh), (255, 0, 0, 0))
        overlay.putalpha(small_mask.point(lambda p: 110 if p > 127 else 0))
        view.alpha_composite(overlay)
        self.tk_image = ImageTk.PhotoImage(view)
        self.canvas.delete("all")
        self.canvas.create_image(self.offset_x, self.offset_y, image=self.tk_image, anchor=tk.NW)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--mask-out", required=True)
    parser.add_argument("--image-out")
    parser.add_argument("--load-mask")
    parser.add_argument("--output")
    args = parser.parse_args()
    root = tk.Tk()
    MaskDrawApp(root, args.image, args.mask_out, args.image_out, args.load_mask, args.output)
    root.mainloop()


if __name__ == "__main__":
    main()
