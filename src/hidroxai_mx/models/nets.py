"""Redes del benchmark en PyTorch puro (protocolo, sección 4).

Todas reciben X [lote, 30, canales] y devuelven [lote] (objetivo estandarizado).
"""
from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F


# --------------------------------------------------------------------------- TCN
class _TemporalBlock(nn.Module):
    def __init__(self, c_in: int, c_out: int, kernel: int, dilation: int, dropout: float):
        super().__init__()
        self.pad = (kernel - 1) * dilation
        self.conv1 = nn.Conv1d(c_in, c_out, kernel, dilation=dilation)
        self.conv2 = nn.Conv1d(c_out, c_out, kernel, dilation=dilation)
        self.drop = nn.Dropout(dropout)
        self.down = nn.Conv1d(c_in, c_out, 1) if c_in != c_out else nn.Identity()

    def forward(self, x):                      # x [B, C, T]; convoluciones causales
        y = self.drop(F.relu(self.conv1(F.pad(x, (self.pad, 0)))))
        y = self.drop(F.relu(self.conv2(F.pad(y, (self.pad, 0)))))
        return F.relu(y + self.down(x))


class TCN(nn.Module):
    """4 bloques residuales, kernel 3, dilaciones 1-2-4-8 (campo receptivo 31)."""

    def __init__(self, n_inputs: int = 6, channels: int = 32, levels: int = 4,
                 kernel: int = 3, dropout: float = 0.1):
        super().__init__()
        blocks, c = [], n_inputs
        for i in range(levels):
            blocks.append(_TemporalBlock(c, channels, kernel, 2 ** i, dropout))
            c = channels
        self.net = nn.Sequential(*blocks)
        self.head = nn.Linear(channels, 1)

    def forward(self, x):
        return self.head(self.net(x.transpose(1, 2))[:, :, -1]).squeeze(-1)


# ------------------------------------------------------------------- ConvNeXt-1D
class _ConvNeXtBlock(nn.Module):
    def __init__(self, dim: int, kernel: int = 7, layer_scale: float = 1e-6):
        super().__init__()
        self.dw = nn.Conv1d(dim, dim, kernel, padding=kernel // 2, groups=dim)
        self.norm = nn.LayerNorm(dim)
        self.pw1 = nn.Linear(dim, 4 * dim)
        self.pw2 = nn.Linear(4 * dim, dim)
        self.gamma = nn.Parameter(layer_scale * torch.ones(dim))

    def forward(self, x):                      # x [B, C, T]
        y = self.dw(x).transpose(1, 2)         # [B, T, C]
        y = self.pw2(F.gelu(self.pw1(self.norm(y)))) * self.gamma
        return x + y.transpose(1, 2)


class ConvNeXt1D(nn.Module):
    """Proyección 1×1, 3 bloques ConvNeXt (depthwise kernel 7), pooling global."""

    def __init__(self, n_inputs: int = 6, dim: int = 32, depth: int = 3, kernel: int = 7):
        super().__init__()
        self.stem = nn.Conv1d(n_inputs, dim, 1)
        self.blocks = nn.Sequential(*[_ConvNeXtBlock(dim, kernel) for _ in range(depth)])
        self.norm = nn.LayerNorm(dim)
        self.head = nn.Linear(dim, 1)

    def forward(self, x):
        y = self.blocks(self.stem(x.transpose(1, 2))).mean(dim=-1)
        return self.head(self.norm(y)).squeeze(-1)


# ---------------------------------------------------------------------- PatchTST
class _EncoderLayer(nn.Module):
    """Capa Transformer (pre-norm) que guarda sus pesos de atención para la Fase 3."""

    def __init__(self, d_model: int, heads: int, dropout: float):
        super().__init__()
        self.attn = nn.MultiheadAttention(d_model, heads, dropout=dropout, batch_first=True)
        self.n1, self.n2 = nn.LayerNorm(d_model), nn.LayerNorm(d_model)
        self.ff = nn.Sequential(nn.Linear(d_model, 2 * d_model), nn.GELU(), nn.Dropout(dropout),
                                nn.Linear(2 * d_model, d_model))
        self.drop = nn.Dropout(dropout)
        self.last_attn: torch.Tensor | None = None

    def forward(self, x):
        h = self.n1(x)
        a, w = self.attn(h, h, h, need_weights=True, average_attn_weights=False)
        self.last_attn = w.detach()            # [B, heads, patches, patches]
        x = x + self.drop(a)
        return x + self.drop(self.ff(self.n2(x)))


class PatchTST(nn.Module):
    """Parches por canal (independencia de canal) y cabeza lineal sobre todos los canales."""

    def __init__(self, n_inputs: int = 6, seq_len: int = 30, patch: int = 5, stride: int = 5,
                 d_model: int = 32, layers: int = 2, heads: int = 4, dropout: float = 0.1):
        super().__init__()
        self.patch, self.stride, self.n_inputs = patch, stride, n_inputs
        self.n_patches = (seq_len - patch) // stride + 1
        self.embed = nn.Linear(patch, d_model)
        self.pos = nn.Parameter(torch.zeros(1, self.n_patches, d_model))
        nn.init.normal_(self.pos, std=0.02)
        self.layers = nn.ModuleList([_EncoderLayer(d_model, heads, dropout) for _ in range(layers)])
        self.drop = nn.Dropout(dropout)
        self.head = nn.Linear(n_inputs * self.n_patches * d_model, 1)

    def forward(self, x):                      # x [B, T, C]
        b = x.shape[0]
        p = x.transpose(1, 2).unfold(-1, self.patch, self.stride)   # [B, C, P, patch]
        z = self.drop(self.embed(p.reshape(b * self.n_inputs, self.n_patches, self.patch)) + self.pos)
        for layer in self.layers:
            z = layer(z)
        return self.head(z.reshape(b, -1)).squeeze(-1)

    def attention_maps(self) -> list[torch.Tensor]:
        """Pesos de atención de la última pasada: por capa [B·canales, cabezas, P, P]."""
        return [layer.last_attn for layer in self.layers]


ARCHITECTURES = {"tcn": (TCN, "channels"), "convnext": (ConvNeXt1D, "dim"),
                 "patchtst": (PatchTST, "d_model")}


def build(name: str, size: int, n_inputs: int = 6) -> nn.Module:
    """Construye la red `name` con su hiperparámetro de malla (canales / dim / d_model)."""
    cls, arg = ARCHITECTURES[name]
    return cls(n_inputs=n_inputs, **{arg: size})
