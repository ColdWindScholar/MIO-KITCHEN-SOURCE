# !/usr/bin/env python3
import re
import struct
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

# Android sparse image format [web:44]
SPARSE_HEADER_MAGIC = 0xED26FF3A
CHUNK_TYPE_RAW = 0xCAC1
CHUNK_TYPE_DONT_CARE = 0xCAC3
SPARSE_HEADER_SZ = 28
CHUNK_HEADER_SZ = 12
BUF = 1024 * 1024


def le16(x: int) -> bytes:
    return struct.pack("<H", x)


def le32(x: int) -> bytes:
    return struct.pack("<I", x)


def parse_size_suffix(s: str) -> int:
    s = s.strip()
    m = re.fullmatch(r"([0-9]+)([KMG]?)", s, flags=re.IGNORECASE)
    if not m:
        raise ValueError(f"Tamanho inválido: {s}")
    v = int(m.group(1))
    suf = m.group(2).upper()
    if suf == "":
        return v
    if suf == "K":
        return v * 1024
    if suf == "M":
        return v * 1024 * 1024
    if suf == "G":
        return v * 1024 * 1024 * 1024
    raise ValueError(f"Sufixo inválido: {s}")


def safe_delete_old_parts(out_dir: Path, base_name: str):
    pat = re.compile(rf"^{re.escape(base_name)}\.\d+$")
    for p in out_dir.iterdir():
        if p.is_file() and pat.match(p.name):
            p.unlink(missing_ok=True)


def write_sparse_piece(out_path: Path, in_f, block_size: int, chunk_bytes: int, dontcare_blocks: int):
    if chunk_bytes % block_size != 0:
        raise RuntimeError("chunk_bytes precisa ser múltiplo do block_size.")

    raw_blocks = chunk_bytes // block_size
    total_blocks = dontcare_blocks + raw_blocks
    total_chunks = 2

    # sparse_header_t (28 bytes) [web:44]
    hdr = b"".join([
        le32(SPARSE_HEADER_MAGIC),
        le16(1),
        le16(0),
        le16(SPARSE_HEADER_SZ),
        le16(CHUNK_HEADER_SZ),
        le32(block_size),
        le32(total_blocks),
        le32(total_chunks),
        le32(0),
    ])

    # DONT_CARE chunk [web:44]
    dontcare = b"".join([
        le16(CHUNK_TYPE_DONT_CARE),
        le16(0),
        le32(dontcare_blocks),
        le32(CHUNK_HEADER_SZ),
    ])

    # RAW chunk [web:44]
    raw_total_sz = CHUNK_HEADER_SZ + chunk_bytes
    raw = b"".join([
        le16(CHUNK_TYPE_RAW),
        le16(0),
        le32(raw_blocks),
        le32(raw_total_sz),
    ])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as out:
        out.write(hdr)
        out.write(dontcare)
        out.write(raw)

        remaining = chunk_bytes
        while remaining > 0:
            b = in_f.read(min(BUF, remaining))
            if not b:
                raise RuntimeError("EOF inesperado ao ler dados do arquivo de entrada.")
            out.write(b)
            remaining -= len(b)


def run_lpdump_size_bytes(lpdump_bin: Path, image_path: Path, slot: int) -> int:
    p = subprocess.run(
        [str(lpdump_bin), f"--slot={slot}", str(image_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    m = re.search(r"\bSize:\s*([0-9]+)\b", p.stdout)
    if not m:
        raise RuntimeError("Não foi possível encontrar 'Size:' na saída do lpdump.")
    return int(m.group(1))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Split super.img -> sparse parts (.000..)")
        self.geometry("900x520")

        # defaults baseados no projeto (cwd/bin/...) como você pediu
        self.cwd = Path.cwd()
        self.bin_dir = self.cwd / "bin"
        self.def_lpdump = self._pick_bin("lpdump")
        self.def_input = self.cwd / "super.img"
        self.def_outdir = self.cwd / "out"

        self._build_ui()

    def _pick_bin(self, name: str) -> Path:
        a = self.bin_dir / name
        b = self.bin_dir / f"{name}.exe"
        if a.exists():
            return a
        if b.exists():
            return b
        return a  # default mesmo se ainda não existir

    def _build_ui(self):
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)

        # Inputs
        self.var_input = tk.StringVar(value=str(self.def_input))
        self.var_outdir = tk.StringVar(value=str(self.def_outdir))
        self.var_lpdump = tk.StringVar(value=str(self.def_lpdump))
        self.var_slot = tk.IntVar(value=0)
        self.var_parts = tk.IntVar(value=15)
        self.var_block = tk.StringVar(value="4K")
        self.var_suffix = tk.StringVar(value=".%03d")  # usa idx 0.. => .000, .001...
        self.var_keep_old = tk.BooleanVar(value=False)
        self.var_size_override = tk.StringVar(value="")  # vazio = usa lpdump

        row = 0
        ttk.Label(frm, text="Input image:").grid(row=row, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.var_input, width=75).grid(row=row, column=1, sticky="we", padx=6)
        ttk.Button(frm, text="Escolher...", command=self.pick_input).grid(row=row, column=2, sticky="e")
        row += 1

        ttk.Label(frm, text="Output dir:").grid(row=row, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.var_outdir, width=75).grid(row=row, column=1, sticky="we", padx=6)
        ttk.Button(frm, text="Escolher...", command=self.pick_outdir).grid(row=row, column=2, sticky="e")
        row += 1

        ttk.Label(frm, text="lpdump bin:").grid(row=row, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.var_lpdump, width=75).grid(row=row, column=1, sticky="we", padx=6)
        ttk.Button(frm, text="Escolher...", command=self.pick_lpdump).grid(row=row, column=2, sticky="e")
        row += 1

        opt = ttk.Frame(frm)
        opt.grid(row=row, column=0, columnspan=3, sticky="we", pady=(6, 6))
        for i in range(10):
            opt.grid_columnconfigure(i, weight=0)
        opt.grid_columnconfigure(9, weight=1)

        ttk.Label(opt, text="Parts:").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(opt, from_=2, to=9999, textvariable=self.var_parts, width=6).grid(row=0, column=1, padx=(4, 14))

        ttk.Label(opt, text="Slot:").grid(row=0, column=2, sticky="w")
        ttk.Spinbox(opt, from_=0, to=10, textvariable=self.var_slot, width=4).grid(row=0, column=3, padx=(4, 14))

        ttk.Label(opt, text="Block:").grid(row=0, column=4, sticky="w")
        ttk.Entry(opt, textvariable=self.var_block, width=6).grid(row=0, column=5, padx=(4, 14))

        ttk.Label(opt, text="Suffix fmt:").grid(row=0, column=6, sticky="w")
        ttk.Entry(opt, textvariable=self.var_suffix, width=10).grid(row=0, column=7, padx=(4, 14))

        ttk.Label(opt, text="Size override (bytes):").grid(row=0, column=8, sticky="w")
        ttk.Entry(opt, textvariable=self.var_size_override, width=16).grid(row=0, column=9, sticky="w", padx=(4, 0))

        row += 1

        chk = ttk.Frame(frm)
        chk.grid(row=row, column=0, columnspan=3, sticky="we")
        ttk.Checkbutton(chk, text="Keep old parts (não apagar antigas)", variable=self.var_keep_old).pack(side="left")
        ttk.Button(chk, text="Executar split", command=self.run_split).pack(side="right")
        ttk.Button(chk, text="Limpar log", command=self.clear_log).pack(side="right", padx=8)
        row += 1

        # Memo / log (ScrolledText)
        ttk.Label(frm, text="Log:").grid(row=row, column=0, sticky="w", pady=(10, 2))
        row += 1

        self.memo = ScrolledText(frm, height=18, state="disabled")
        self.memo.grid(row=row, column=0, columnspan=3, sticky="nsew")
        frm.grid_rowconfigure(row, weight=1)
        frm.grid_columnconfigure(1, weight=1)

        # tags para cores (azul/vermelho)
        self.memo.configure(state="normal")
        self.memo.tag_configure("INFO", foreground="black")
        self.memo.tag_configure("OK", foreground="#1e5eff")     # azul
        self.memo.tag_configure("ERR", foreground="#d00000")    # vermelho
        self.memo.configure(state="disabled")

    def log(self, msg: str, tag: str = "INFO"):
        self.memo.configure(state="normal")
        self.memo.insert(tk.END, msg + "\n", tag)  # tags mudam cor no Text widget [web:91]
        self.memo.configure(state="disabled")
        self.memo.yview(tk.END)

    def clear_log(self):
        self.memo.configure(state="normal")
        self.memo.delete("1.0", tk.END)
        self.memo.configure(state="disabled")

    def pick_input(self):
        p = filedialog.askopenfilename(title="Escolha super.img", initialdir=str(self.cwd))
        if p:
            self.var_input.set(p)

    def pick_outdir(self):
        p = filedialog.askdirectory(title="Escolha pasta de saída", initialdir=str(self.cwd))
        if p:
            self.var_outdir.set(p)

    def pick_lpdump(self):
        p = filedialog.askopenfilename(title="Escolha lpdump", initialdir=str(self.bin_dir))
        if p:
            self.var_lpdump.set(p)

    def run_split(self):
        try:
            raw_image = Path(self.var_input.get()).expanduser()
            out_dir = Path(self.var_outdir.get()).expanduser()
            lpdump_bin = Path(self.var_lpdump.get()).expanduser()

            parts = int(self.var_parts.get())
            slot = int(self.var_slot.get())
            block_size = parse_size_suffix(self.var_block.get())
            suffix_fmt = self.var_suffix.get()
            keep_old = bool(self.var_keep_old.get())
            size_override_txt = self.var_size_override.get().strip()
            size_override = int(size_override_txt) if size_override_txt else None

            # validações básicas
            if not raw_image.exists():
                raise RuntimeError(f"Input não existe: {raw_image}")
            if not lpdump_bin.exists() and size_override is None:
                raise RuntimeError(f"lpdump não encontrado: {lpdump_bin} (ou use Size override)")
            if parts < 2:
                raise RuntimeError("Parts deve ser >= 2")

            # inicia log
            self.log("----", "INFO")
            self.log(f"Input: {raw_image}", "INFO")
            self.log(f"OutDir: {out_dir}", "INFO")
            self.log(f"Parts: {parts} (gera .000..)", "INFO")
            self.log(f"Block: {block_size} bytes", "INFO")

            # size_sup
            if size_override is None:
                size_sup = run_lpdump_size_bytes(lpdump_bin, raw_image, slot)
                self.log(f"Size (lpdump): {size_sup} bytes", "INFO")
            else:
                size_sup = size_override
                self.log(f"Size (override): {size_sup} bytes", "INFO")

            # cálculo igual ao shell
            size_mb = size_sup // (1024 * 1024)
            piece_size_mb = (size_mb + parts - 1) // parts
            chunk_size_bytes = piece_size_mb * 1024 * 1024

            self.log(f"Piece size: {piece_size_mb} MB", "INFO")
            self.log(f"Chunk bytes: {chunk_size_bytes}", "INFO")

            # prepara out dir
            out_dir.mkdir(parents=True, exist_ok=True)
            if not keep_old:
                safe_delete_old_parts(out_dir, raw_image.name)
                self.log("Old parts removidas.", "INFO")

            # valida tamanho do arquivo
            in_size = raw_image.stat().st_size
            if in_size % block_size != 0:
                raise RuntimeError(f"Tamanho do arquivo ({in_size}) não é múltiplo do block_size ({block_size}).")

            blocks_per_chunk = chunk_size_bytes // block_size
            if blocks_per_chunk <= 0:
                raise RuntimeError("Chunk menor que bloco; ajuste Block ou Parts.")

            left = in_size
            written = 0

            with raw_image.open("rb") as f:
                for idx in range(parts):  # 0..parts-1
                    if left <= 0:
                        break

                    to_write = min(chunk_size_bytes, left)
                    to_write = (to_write // block_size) * block_size
                    if to_write == 0:
                        break

                    dontcare_blocks = idx * blocks_per_chunk

                    # suffix (ex: .%03d -> .000)
                    try:
                        suffix = suffix_fmt % idx
                    except Exception as e:
                        raise RuntimeError(f"Suffix inválido: {suffix_fmt!r} ({e})")

                    out_path = out_dir / f"{raw_image.name}{suffix}"
                    write_sparse_piece(out_path, f, block_size, to_write, dontcare_blocks)

                    left -= to_write
                    written += 1
                    self.log(f"OK: {out_path.name} ({to_write} bytes RAW chunk)", "OK")

            self.log(f"SUCESSO: geradas {written} partes.", "OK")
            messagebox.showinfo("Sucesso", f"Geradas {written} partes em:\n{out_dir}")  # [web:102]

        except Exception as e:
            self.log(f"ERRO: {e}", "ERR")
            messagebox.showerror("Erro", str(e))  # [web:102]


if __name__ == "__main__":
    App().mainloop()
