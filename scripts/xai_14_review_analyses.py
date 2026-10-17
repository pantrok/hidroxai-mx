#!/usr/bin/env python
"""Benchmark XAI · paso 14: análisis pedidos por la revisión simulada v0.6.

Cubre RR-1 a RR-4 y RR-6, más los opcionales RR-5 y RR-11. Los criterios están en
proof_ledger.md, sección "Análisis de revisión (2026-10-16)", versionada en el commit ca12106
antes de calcular.

Todo es descriptivo (post hoc, revisión):
- no cambia veredictos de §7 ni cifras del diseño principal;
- no reentrena modelos;
- usa predicciones, niveles de alerta, métricas y pesos guardados.

Análisis:
- RR-1: ablación de las alertas (F, F0, T, TV), contrastes A–D con bootstrap pareado de
  estaciones y B por año del walk-forward. Incluye RR-11 (valor económico relativo).
- RR-2: techo de ruido de la concordancia de explicaciones. Recalcula TreeSHAP e IG por semilla
  y por ventana con los pesos guardados (autorizado por el autor; unos 30 min de CPU) y guarda
  la caché en data/interim/xai_benchmark/review/.
- RR-3 y RR-4: IC con bootstrap por grupos conectados de HydroRIVERS y con Bonferroni por familia.
- RR-5: disponibilidad de datos de presas.
- RR-6: descriptores por estación.
- Versiones de software.

Salidas: results/xai_benchmark/rev_*.csv, e_revision.json, tables/T10_*, T11_*, T13_*,
         S1_descriptores.csv, figures_esi/figS3–S5_* y numbers.json → revision_pares y software.
Correr después de xai_08 y xai_12, que reescriben y completan numbers.json.

Uso:  python scripts/xai_14_review_analyses.py [--skip-rr2]
"""
from __future__ import annotations

import argparse
import importlib.metadata as md
import json
import platform
import sys
import time
from datetime import date
from itertools import combinations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from hidroxai_mx.alert import evaluation as AE
from hidroxai_mx.alert import fuzzy as F
from hidroxai_mx.models import criteria as C
from hidroxai_mx.models import data as D
from hidroxai_mx.models import manifest
from hidroxai_mx.models import metrics as M
from hidroxai_mx.utils import FEATURES, PROCESSED, ROOT, get_logger

log = get_logger("xai_14")
OUT = ROOT / "results" / "xai_benchmark"
INTERIM = ROOT / "data" / "interim" / "xai_benchmark"
CACHE = INTERIM / "review"
TOPO = ROOT / "data" / "scratch" / "hydrorivers" / "HydroRIVERS_v10_na_topologia.parquet"
TAG = "descriptivo (post hoc, revisión)"
SEED, N_BOOT, N_SAMPLE, IG_STEPS = 20261010, 10_000, 2000, 64
SEEDS = (20261010, 20261011, 20261012)
LEARNED, DEEP = ("xgboost", "tcn", "convnext", "patchtst"), ("tcn", "convnext", "patchtst")
SLUG = {"Lerma–Santiago": "lerma_santiago", "Pánuco": "panuco", "Alta del Balsas": "alta_balsas",
        "Cutzamala": "cutzamala"}
EVENTS = {"P90": (0.90, 2), "P99": (0.99, 3)}
VETO = 0.15
VARIANTS = ("F", "F0", "T", "TV")
CONTRASTS = {"A": ("F0", "T"), "B": ("F", "F0"), "C": ("TV", "T"), "D": ("F", "TV")}
MEASURES = ("spearman_180", "jaccard_top10", "jaccard_top20", "spearman_canal", "spearman_rezago")
INTERMITTENT = 0.05


def _r(x, n: int = 4):
    return None if x is None or pd.isna(x) else round(float(x), n)


def _ci(v) -> list:
    return [_r(x) for x in v]


# ----------------------------------------------------------------------------- bootstrap
def boot_units(counts: dict[str, np.ndarray], m1: str, m2: str, level: float = 0.95,
               n_boot: int = N_BOOT, seed: int = SEED) -> tuple[float, float, float]:
    """ΔCSI(m1 − m2) remuestreando unidades (estaciones o grupos) con sus tablas sumadas.

    counts[m]: [unidades, 3] con aciertos, fallos y falsas. Mismo flujo aleatorio que
    `alert.evaluation.boot_delta_csi`.
    """
    def csi(s):
        tot = s.sum(-1)
        with np.errstate(invalid="ignore", divide="ignore"):
            return s[..., 0] / tot
    point = float(csi(counts[m1].sum(0)) - csi(counts[m2].sum(0)))
    n = len(counts[m1])
    idx = np.random.default_rng(seed).integers(0, n, size=(n_boot, n))
    bs = csi(counts[m1][idx].sum(1)) - csi(counts[m2][idx].sum(1))
    a = (1 - level) / 2
    return point, float(np.nanquantile(bs, a)), float(np.nanquantile(bs, 1 - a))


def group_median_ci(values: pd.Series, groups: pd.Series, level: float = 0.95,
                    n_boot: int = N_BOOT, seed: int = SEED) -> tuple[float, float, float]:
    """Mediana e IC remuestreando grupos con reemplazo; cada grupo aporta todas sus estaciones."""
    v = values.dropna()
    g = groups.reindex(v.index)
    codes, uniq = pd.factorize(g)
    order = np.argsort(v.to_numpy())
    vals, codes = v.to_numpy()[order], codes[order]
    G = len(uniq)
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, G, size=(n_boot, G))
    cnt = np.zeros((n_boot, G))
    np.add.at(cnt, (np.repeat(np.arange(n_boot), G), pick.ravel()), 1)
    w = cnt[:, codes]                                   # peso de cada estación en cada réplica
    cw = np.cumsum(w, axis=1)
    tot = cw[:, -1]
    meds = np.empty(n_boot)
    for i in range(n_boot):                             # mediana del multiconjunto (como np.median)
        k1, k2 = (tot[i] - 1) // 2, tot[i] // 2
        meds[i] = 0.5 * (vals[np.searchsorted(cw[i], k1 + 1)] + vals[np.searchsorted(cw[i], k2 + 1)])
    a = (1 - level) / 2
    return float(np.median(v)), float(np.quantile(meds, a)), float(np.quantile(meds, 1 - a))


# ----------------------------------------------------------------------------- datos comunes
def load_common():
    link = pd.read_csv(PROCESSED / "estaciones_hidrorivers.csv", dtype={"clave": str})
    basin_of = D.station_basins(link)
    claves = [k for k in link["clave"] if pd.notna(basin_of.get(k))]
    ft = pd.read_parquet(FEATURES / "feature_table.parquet",
                         columns=["clave_estacion", "fecha", "calidad", *D.CHANNELS[:4]],
                         filters=[("clave_estacion", "in", claves)])
    panels = {k: D.daily_panel(ft, k) for k in claves}
    return link, basin_of, claves, panels


def train_obs(panels: dict, part) -> dict:
    out = {}
    for k, p in panels.items():
        m = (p.index >= part[0]) & (p.index <= part[1]) & (p["calidad"] == 0)
        v = p.loc[m, D.TARGET].to_numpy(dtype=float)
        out[k] = v[np.isfinite(v)]
    return out


def connected_groups(link: pd.DataFrame, stations: list[str]) -> pd.Series:
    """Componentes conexas sobre HydroRIVERS (una estación está aguas abajo de la otra)."""
    topo = pd.read_parquet(TOPO, columns=["HYRIV_ID", "NEXT_DOWN"])
    nxt = dict(zip(topo["HYRIV_ID"].to_numpy(), topo["NEXT_DOWN"].to_numpy(), strict=True))
    reach = link.set_index("clave")["hyriv_id"].reindex(stations)
    down = {}
    for k, r in reach.items():
        s: set = set()
        if pd.notna(r):
            x = int(r)
            while x and x in nxt and x not in s:
                s.add(x)
                x = int(nxt[x])
        down[k] = s
    parent = {k: k for k in stations}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for i, a in enumerate(stations):
        for b in stations[i + 1:]:
            ra, rb = reach[a], reach[b]
            if pd.notna(ra) and pd.notna(rb) and (int(ra) in down[b] or int(rb) in down[a]):
                parent[find(a)] = find(b)
    comp = pd.Series({k: find(k) for k in stations})
    return pd.Series(pd.factorize(comp)[0], index=comp.index, name="grupo")


# ----------------------------------------------------------------------------- RR-1 y RR-11
def rr1(panels: dict, evaluable: dict, units: dict[str, pd.Series], e3: dict) -> tuple[dict, pd.DataFrame]:
    fis = F.build_protocol_fis()
    obs_tr = train_obs(panels, D.PARTITIONS["train"])
    rows = []
    for b in D.BASINS:
        for h in D.HORIZONS:
            a = pd.read_parquet(INTERIM / "alerts" / f"{SLUG[b]}_h{h}.parquet")
            lvl0 = F.level_index(fis.infer_array({"percentil": a["percentil"].to_numpy(),
                                                  "dispersion": np.zeros(len(a))}))
            for k, idx in a.groupby("clave").indices.items():
                if k not in evaluable[h]:
                    continue
                o = a["observado"].to_numpy()[idx]
                p, s, lv = a["percentil"].to_numpy()[idx], a["dispersion"].to_numpy()[idx], a["nivel"].to_numpy()[idx]
                for e, (q, ml) in EVENTS.items():
                    obs = o > np.quantile(obs_tr[k], q)
                    dec = {"F": lv >= ml, "F0": lvl0[idx] >= ml, "T": p >= q, "TV": (p >= q) & (s < VETO)}
                    for v, pred in dec.items():
                        rows.append({"cuenca": b, "h": h, "clave": k, "evento": e, "variante": v,
                                     **AE.counts(obs, pred)})
    ct = pd.DataFrame(rows)
    # F y T deben reproducir la contingencia oficial (difuso / umbral)
    off = pd.read_csv(OUT / "rq3_contingency.csv", dtype={"clave": str})
    chk = off.replace({"metodo": {"difuso": "F", "umbral": "T"}}).rename(columns={"metodo": "variante"})
    mrg = ct.merge(chk, on=["cuenca", "h", "clave", "evento", "variante"], suffixes=("", "_of"))
    assert len(mrg) == len(chk) and (mrg["aciertos"] == mrg["aciertos_of"]).all() \
        and (mrg["falsas"] == mrg["falsas_of"]).all(), "F/T no reproducen rq3_contingency.csv"
    var_rows, con_rows, res = [], [], {"variantes": {}, "contrastes": {}}
    for (e, h), x in ct.groupby(["evento", "h"]):
        tabs = {}
        for v in VARIANTS:
            y = x[x["variante"] == v].set_index("clave").sort_index()[["aciertos", "fallos", "falsas", "negativos"]]
            tabs[v] = y
            sc = AE.scores(y.sum())
            var_rows.append({"evento": e, "h": h, "variante": v, **{k: _r(val) for k, val in sc.items()},
                             **{k: int(val) for k, val in y.sum().items()}})
            res["variantes"][f"{e}_h{h}_{v}"] = {k: _r(val) for k, val in sc.items()}
        for uname, ug in units.items():
            keys = tabs["F"].index
            grp = ug.reindex(keys) if uname != "estaciones" else pd.Series(np.arange(len(keys)), index=keys)
            cnt = {v: tabs[v][["aciertos", "fallos", "falsas"]].groupby(grp.to_numpy()).sum().to_numpy()
                   for v in VARIANTS}
            for cname, (m1, m2) in CONTRASTS.items():
                ci = boot_units(cnt, m1, m2)
                con_rows.append({"evento": e, "h": h, "contraste": cname, "definicion": f"{m1} − {m2}",
                                 "remuestreo": uname, "delta_csi": _r(ci[0]), "ic_lo": _r(ci[1]), "ic_hi": _r(ci[2])})
                res["contrastes"][f"{e}_h{h}_{cname}_{uname}"] = _ci(ci)
    # el bootstrap de estaciones F − T debe reproducir el ΔCSI oficial (mismo orden y flujo aleatorio)
    for (e, h), x in ct.groupby(["evento", "h"]):
        cnt_ft = {v: x[x["variante"] == v].set_index("clave").sort_index()[["aciertos", "fallos", "falsas"]].to_numpy()
                  for v in ("F", "T")}
        assert _ci(boot_units(cnt_ft, "F", "T")) == _ci(e3["H3"]["delta_csi_ic"][f"{e}_h{h}"]), f"no reproduce e_rq3 {e} h{h}"

    def verdicts(h: int) -> dict:
        get = {c: res["contrastes"][f"P90_h{h}_{c}_estaciones"] for c in CONTRASTS}
        dis = get["B"][1] > 0 and get["C"][1] > 0
        d = get["D"]
        return {"desacuerdo": bool(dis), "frontera": bool(get["A"][1] > 0),
                "difuso_frente_a_nitido": "difuso aporta" if d[1] > 0 else ("nítido mejor" if d[2] < 0 else "equivalente")}
    res["criterios"] = {"P90_h1": verdicts(1), "P90_h7_confirmacion": verdicts(7)}
    pd.DataFrame(var_rows).to_csv(OUT / "rev_rr1_variantes.csv", index=False)
    pd.DataFrame(con_rows).to_csv(OUT / "rev_rr1_contrastes.csv", index=False)
    ct.to_csv(OUT / "rev_rr1_contingencia.csv", index=False)
    return res, ct


def rr11(ct: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    alphas = np.round(np.arange(0.01, 1.0, 0.01), 2)
    rows, out = [], {}
    x = ct[(ct["evento"] == "P90") & (ct["h"] == 1)]
    for v in VARIANTS:
        s_ = x[x["variante"] == v][["aciertos", "fallos", "falsas", "negativos"]].sum()
        n = s_.sum()
        hit, fa, miss = s_["aciertos"] / n, s_["falsas"] / n, s_["fallos"] / n
        base = hit + miss
        e_f = alphas * (hit + fa) + miss
        e_c = np.minimum(alphas, base)
        val = (e_c - e_f) / (e_c - alphas * base)
        rows += [{"variante": v, "costo_perdida": a_, "valor_relativo": _r(vv)} for a_, vv in zip(alphas, val, strict=True)]
        pos = alphas[val > 0]
        out[v] = {"valor_maximo": _r(val.max()), "costo_perdida_del_maximo": _r(alphas[val.argmax()], 2),
                  "rango_valor_positivo": [_r(pos.min(), 2), _r(pos.max(), 2)] if len(pos) else None}
    curve = pd.DataFrame(rows)
    curve.to_csv(OUT / "rev_rr11_valor_relativo.csv", index=False)
    return {"evento": "P90", "h": 1, "frecuencia_base": _r(base), "por_variante": out}, curve


def rr1_walk_forward(panels: dict, chosen: dict) -> dict:
    """B = F − F0 por año del walk-forward (ensamble de 4 miembros), P90, h = 1."""
    fis = F.build_protocol_fis()
    wf, wfn = INTERIM / "walk_forward", INTERIM / "walk_forward_nets"
    out = {}
    for y in (2021, 2022, 2023, 2024, 2025):
        obs_y = train_obs(panels, D.walk_forward_partitions(y)["train"])
        cnt = {"F": [], "F0": []}
        for b in D.BASINS:
            tag = f"{SLUG[b]}_h1_y{y}"
            meta = pd.read_parquet(wf / "meta" / f"{tag}_test.parquet")
            mem = np.stack([np.load((wf if m == "xgboost" else wfn) / "preds" / f"{chosen[f'{m}_h1']}_{tag}.npz")["flow_test"]
                            for m in LEARNED])
            lv = AE.ensemble_levels(fis, mem, meta, obs_y)
            lv0 = F.level_index(fis.infer_array({"percentil": lv["percentil"], "dispersion": np.zeros(len(meta))}))
            g = meta.groupby("clave")["y_flow"]
            ok = (g.size() >= 180) & (g.var() > 0)
            o = meta["y_flow"].to_numpy()
            for k, idx in meta.groupby("clave").indices.items():
                if not ok.get(k, False):
                    continue
                obs = o[idx] > lv["umbral"]["P90"][idx]
                for v, pred in (("F", lv["nivel"][idx] >= 2), ("F0", lv0[idx] >= 2)):
                    c = AE.counts(obs, pred)
                    cnt[v].append([c["aciertos"], c["fallos"], c["falsas"]])
        out[str(y)] = _ci(boot_units({v: np.array(a) for v, a in cnt.items()}, "F", "F0"))
    return out


# ----------------------------------------------------------------------------- RR-2
def _per_window(attr: np.ndarray) -> np.ndarray:
    a = np.abs(attr)
    tot = a.sum(axis=(1, 2), keepdims=True)
    return np.divide(a, tot, out=np.zeros_like(a), where=tot > 0).astype(np.float32)


def rr2_compute(panels: dict, basin_of, claves, chosen: dict, big: list[str], threads: int) -> None:
    import torch
    import xgboost as xgb

    from hidroxai_mx.models import nets
    from hidroxai_mx.models import xgb as XG
    from hidroxai_mx.xai import attributions as A
    torch.set_num_threads(threads)
    CACHE.mkdir(parents=True, exist_ok=True)
    for b in big:
        bp = {k: panels[k] for k in claves if basin_of[k] == b}
        for h in D.HORIZONS:
            path = CACHE / f"rr2_{SLUG[b]}_h{h}.npz"
            if path.exists():
                continue
            t0 = time.perf_counter()
            tag = f"{SLUG[b]}_h{h}"
            g = D.group_arrays(bp, h)
            meta = pd.read_parquet(INTERIM / "cpu" / "meta" / f"{tag}_test.parquet")
            assert (g["test"]["meta"]["clave"].to_numpy() == meta["clave"].to_numpy()).all()
            idx = A.stratified_sample(meta, N_SAMPLE, SEED)
            X = g["test"]["X"][idx]
            del g
            out = {"claves": meta["clave"].to_numpy()[idx].astype(str)}
            for m in LEARNED:
                cfg = chosen[f"{m}_h{h}"]
                for s in SEEDS:
                    rid = f"{cfg}_{tag}_s{s}"
                    if m == "xgboost":
                        booster = xgb.Booster()
                        booster.load_model(INTERIM / "cpu" / "models" / f"{rid}.json")
                        attr = XG.tree_shap(booster, X)
                    else:
                        net = nets.build(m, int(cfg.split("-")[1]))
                        net.load_state_dict(torch.load(INTERIM / "nets" / "weights" / f"{rid}.pt", weights_only=True))
                        attr = A.integrated_gradients(net, X, n_steps=IG_STEPS)[0]
                    out[f"{m}_s{s}"] = _per_window(attr)
            np.savez_compressed(path, **out)
            log.info("RR-2 %s h=%d: %.0f s", b, h, time.perf_counter() - t0)


def _measure(name: str, a: np.ndarray, b: np.ndarray) -> float:
    if name == "spearman_180":
        return float(spearmanr(a.ravel(), b.ravel())[0])
    if name.startswith("jaccard_top"):
        k = int(name.removeprefix("jaccard_top"))
        ta, tb = set(np.argsort(a.ravel())[-k:]), set(np.argsort(b.ravel())[-k:])
        return len(ta & tb) / len(ta | tb)
    if name == "spearman_canal":
        return float(spearmanr(a.sum(0), b.sum(0))[0])
    return float(spearmanr(a.sum(1), b.sum(1))[0])       # spearman_rezago


def rr2_evaluate(big: list[str]) -> tuple[dict, pd.DataFrame]:
    imp = pd.read_csv(OUT / "rq2_importance.csv")
    rows, max_diff = [], 0.0
    for b in big:
        for h in D.HORIZONS:
            z = np.load(CACHE / f"rr2_{SLUG[b]}_h{h}.npz")
            cl = z["claves"]
            rng = np.random.default_rng(SEED)
            half = np.zeros(len(cl), dtype=bool)
            for k in sorted(set(cl)):
                ix = np.flatnonzero(cl == k)
                half[rng.permutation(ix)[: len(ix) // 2]] = True
            full, seedmaps, halves = {}, {}, {}
            for m in LEARNED:
                per = [z[f"{m}_s{s}"] for s in SEEDS]
                seedmaps[m] = [p.mean(0) for p in per]
                full[m] = np.mean(seedmaps[m], axis=0)
                halves[m] = (np.mean([p[half].mean(0) for p in per], axis=0),
                             np.mean([p[~half].mean(0) for p in per], axis=0))
                ref = (imp[(imp["cuenca"] == b) & (imp["h"] == h) & (imp["modelo"] == m)]
                       .pivot(index="rezago_ventana", columns="canal", values="importancia")
                       .sort_index(ascending=False)[list(D.CHANNELS)].to_numpy())
                max_diff = max(max_diff, float(np.abs(ref - full[m]).max()))
            for meas in MEASURES:
                for m in LEARNED:
                    for (i, j) in combinations(range(len(SEEDS)), 2):
                        rows.append({"cuenca": b, "h": h, "medida": meas, "tipo": "entre_semillas", "modelo_a": m,
                                     "modelo_b": m, "valor": _measure(meas, seedmaps[m][i], seedmaps[m][j])})
                    rows.append({"cuenca": b, "h": h, "medida": meas, "tipo": "entre_mitades", "modelo_a": m,
                                 "modelo_b": m, "valor": _measure(meas, *halves[m])})
                for a_, b_ in combinations(LEARNED, 2):
                    rows.append({"cuenca": b, "h": h, "medida": meas, "tipo": "entre_modelos", "modelo_a": a_,
                                 "modelo_b": b_, "valor": _measure(meas, full[a_], full[b_])})
    assert max_diff < 1e-6, f"el promedio de semillas no reproduce rq2_importance.csv ({max_diff:.2e})"
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "rev_rr2_medidas.csv", index=False)
    res = {"reproduce_rq2_importance_max_abs": float(f"{max_diff:.3g}"), "por_medida": {}}
    for meas in MEASURES:
        x = df[df["medida"] == meas]
        combos, below_major, indist, detail = 0, 0, 0, {}
        for (b, h), y in x.groupby(["cuenca", "h"]):
            combos += 1
            ws = y[y["tipo"] == "entre_semillas"].groupby("modelo_a")["valor"].median()
            wh = y[y["tipo"] == "entre_mitades"].set_index("modelo_a")["valor"]
            bm = y[y["tipo"] == "entre_modelos"]
            below = [(r.valor < min(ws[r.modelo_a], ws[r.modelo_b])) for r in bm.itertuples()]
            below_h = [(r.valor < min(wh[r.modelo_a], wh[r.modelo_b])) for r in bm.itertuples()]
            below_major += sum(below) >= 4
            indist += bm["valor"].median() >= ws.median()
            detail[f"{b}_h{h}"] = {"entre_modelos_mediana": _r(bm["valor"].median(), 3),
                                   "entre_semillas_mediana": _r(ws.median(), 3),
                                   "entre_mitades_mediana": _r(wh.median(), 3),
                                   "pares_bajo_techo_semillas": int(sum(below)),
                                   "pares_bajo_techo_mitades": int(sum(below_h))}
        verdict = ("el desacuerdo supera el ruido" if below_major >= 2 / 3 * combos else
                   "indistinguible del ruido" if indist > combos / 2 else "intermedio")
        res["por_medida"][meas] = {"combinaciones": combos, "con_mayoria_de_pares_bajo_el_techo": int(below_major),
                                   "entre_modelos_mayor_o_igual_al_techo": int(indist), "veredicto": verdict,
                                   "detalle": detail}
    return res, df


# ----------------------------------------------------------------------------- RR-3 y RR-4
def rr34(st: pd.DataFrame, groups: dict[str, pd.Series], ct: pd.DataFrame, e1: dict, e3: dict) -> tuple[dict, pd.DataFrame]:
    fam = {"H1": 8, "H1b": 9, "H3": 2}
    rows, res = [], {}

    def ci_med(vals: pd.Series, how: str, level: float):
        if how == "estaciones":
            return M.bootstrap_median_ci(vals.to_numpy(), level=level)
        return group_median_ci(vals, groups[how], level=level)

    for how in ("estaciones", *groups):
        for adj in ("ninguno", "bonferroni"):
            tag = f"{how}|{adj}"
            # H1
            lv = 0.95 if adj == "ninguno" else 1 - 0.05 / fam["H1"]
            ci1 = {}
            for m in LEARNED:
                for h in (7, 14):
                    x = st[(st["modelo"] == m) & (st["h"] == h)].set_index("clave")["ss"]
                    ci1[f"{m}_h{h}"] = ci_med(x, how, lv)
            # H1-b
            lvb = 0.95 if adj == "ninguno" else 1 - 0.05 / fam["H1b"]
            ci1b, v1b = {}, {}
            for h in D.HORIZONS:
                x = st[st["h"] == h].pivot_table(index="clave", columns="modelo", values="nse")
                for m in DEEP:
                    ci1b[f"{m}_h{h}"] = ci_med((x[m] - x["xgboost"]).dropna(), how, lvb)
                v1b[f"h{h}"] = C.h1b([ci1b[f"{m}_h{h}"] for m in DEEP])
            # H3
            lv3 = 0.95 if adj == "ninguno" else 1 - 0.05 / fam["H3"]
            ci3 = {}
            for e, h in (("P90", 1), ("P90", 7)):
                x = ct[(ct["evento"] == e) & (ct["h"] == h)]
                tabs = {v: x[x["variante"] == v].set_index("clave").sort_index()[["aciertos", "fallos", "falsas"]]
                        for v in ("F", "T")}
                keys = tabs["F"].index
                grp = (pd.Series(np.arange(len(keys)), index=keys) if how == "estaciones"
                       else groups[how].reindex(keys))
                cnt = {v: t.groupby(grp.to_numpy()).sum().to_numpy() for v, t in tabs.items()}
                ci3[f"{e}_h{h}"] = boot_units(cnt, "F", "T", level=lv3)
            ver = {"H1": C.h1(ci1), "H1b": v1b, "H3": C.h3(ci3["P90_h1"], ci3["P90_h7"])}
            res[tag] = {"H1": {k: _ci(v) for k, v in ci1.items()}, "H1b": {k: _ci(v) for k, v in ci1b.items()},
                        "H3": {k: _ci(v) for k, v in ci3.items()}, "veredictos": ver}
            if adj == "ninguno":   # ΔNSE contra ARIMA, descriptivo, sin ajuste
                dn = {}
                for h in D.HORIZONS:
                    x = st[st["h"] == h].pivot_table(index="clave", columns="modelo", values="nse")
                    for m in LEARNED:
                        dn[f"{m}_h{h}"] = _ci(ci_med((x[m] - x["arima"]).dropna(), how, 0.95))
                res[tag]["delta_nse_vs_arima"] = dn
            for hyp in ("H1", "H1b", "H3"):
                for k, v in res[tag][hyp].items():
                    rows.append({"remuestreo": how, "ajuste": adj, "hipotesis": hyp, "clave": k,
                                 "mediana": v[0], "ic_lo": v[1], "ic_hi": v[2]})
    official = {"H1": e1["H1"]["veredicto"], "H1b": e1["H1b"]["veredicto"], "H3": e3["H3"]["veredicto"]}
    # control: estaciones sin ajuste = veredictos oficiales
    assert res["estaciones|ninguno"]["veredictos"] == official, "el bootstrap de estaciones no reproduce §7"
    changes = {tag: {hyp: {"oficial": official[hyp], "sensibilidad": r["veredictos"][hyp],
                           "cambia": official[hyp] != r["veredictos"][hyp]} for hyp in official}
               for tag, r in res.items()}
    pd.DataFrame(rows).to_csv(OUT / "rev_rr34_ic.csv", index=False)
    return {"resultados": res, "cambios": changes, "familias_bonferroni": fam}, pd.DataFrame(rows)


# ----------------------------------------------------------------------------- RR-6 y RR-5
def rr6(panels: dict, link: pd.DataFrame, basin_of, st: pd.DataFrame, sm: pd.DataFrame,
        evaluable: set[str]) -> tuple[dict, pd.DataFrame]:
    sel = pd.read_csv(PROCESSED / "estaciones_seleccionadas_hidrometricas.csv", dtype={"clave": str}).set_index("clave")
    up = link.set_index("clave")["upland_km2"]
    agg = sm[sm["grupo"] == "agregado"]
    best = {h: agg[agg["h"] == h].sort_values("nse_mediana").iloc[-1]["modelo"] for h in (1, 7)}
    days = pd.date_range("2010-01-01", D.PARTITIONS["test"][1], freq="D")
    rows = []
    for k in sorted(evaluable):
        p = panels[k]
        q0 = p[D.TARGET].where(p["calidad"] == 0)
        tr = q0.loc[D.PARTITIONS["train"][0]:D.PARTITIONS["train"][1]].dropna()
        qa = q0.reindex(days).dropna()
        zero = float((qa == 0).mean()) if len(qa) else np.nan
        pr = p["precip_idw_mm"].reindex(days)
        nb = sel.loc[k, "vecinos_clima"] if k in sel.index else np.nan
        rows.append({"clave": k, "cuenca": basin_of[k], "area_drenaje_km2": _r(up.get(k), 1),
                     "gasto_medio_entrenamiento_m3s": _r(tr.mean(), 3), "p90_entrenamiento_m3s": _r(tr.quantile(0.9), 3),
                     "fraccion_dias_gasto_cero": _r(zero), "regimen": "intermitente" if zero > INTERMITTENT else "perenne",
                     "estaciones_clima_idw": len(str(nb).split(",")) if pd.notna(nb) else None,
                     "fraccion_dias_precip_valida": _r(pr.notna().mean()),
                     f"nse_h1_{best[1]}": _r(st[(st["h"] == 1) & (st["modelo"] == best[1]) & (st["clave"] == k)]["nse"].squeeze()),
                     f"nse_h7_{best[7]}": _r(st[(st["h"] == 7) & (st["modelo"] == best[7]) & (st["clave"] == k)]["nse"].squeeze())})
    s1 = pd.DataFrame(rows)
    s1.to_csv(OUT / "tables" / "S1_descriptores.csv", index=False)
    num = ["area_drenaje_km2", "gasto_medio_entrenamiento_m3s", "p90_entrenamiento_m3s", "fraccion_dias_gasto_cero",
           "fraccion_dias_precip_valida"]
    summ = {}
    for b, x in s1.groupby("cuenca"):
        summ[b] = {c: {"mediana": _r(x[c].median()), "min": _r(x[c].min()), "max": _r(x[c].max())} for c in num}
        summ[b]["estaciones"] = int(len(x))
        summ[b]["intermitentes"] = int((x["regimen"] == "intermitente").sum())
    nse_cols = [f"nse_h1_{best[1]}", f"nse_h7_{best[7]}"]
    by_reg = {r: {c: {"mediana": _r(x[c].median()), "fraccion_negativa": _r((x[c] < 0).mean(), 3)} for c in nse_cols}
              | {"estaciones": int(len(x))} for r, x in s1.groupby("regimen")}
    return {"umbral_intermitente": INTERMITTENT, "mejor_modelo": {f"h{h}": m for h, m in best.items()},
            "por_cuenca": summ, "nse_por_regimen": by_reg}, s1


def rr5() -> dict:
    raw = ROOT / "data" / "raw"
    dams = [str(p.relative_to(ROOT)) for p in raw.rglob("*") if "presa" in p.name.lower()]
    topo_cols = pd.read_parquet(TOPO).columns.tolist() if TOPO.exists() else []
    return {"disponible": bool(dams), "archivos_de_presas": dams,
            "atributos_hydrorivers": topo_cols,
            "nota": "sin catálogo de presas en el conjunto y sin atributos de regulación en HydroRIVERS v1.0; "
                    "no se descargó ninguna base nueva" if not dams else "ver archivos"}


def software() -> dict:
    pk = ("torch", "xgboost", "statsmodels", "captum", "numpy", "pandas", "scipy", "matplotlib", "geopandas")
    return {"fuente": "scripts/xai_14_review_analyses.py (importlib.metadata del entorno local)",
            "python": platform.python_version(), "paquetes": {p: md.version(p) for p in pk},
            "alcance": "entorno local: ARIMA, XGBoost, explicaciones, alertas y evaluación",
            "kaggle": "las redes se entrenaron en la imagen de GPU de Kaggle (Tesla T4); sus versiones no quedaron "
                      "registradas en la salida del notebook"}


# ----------------------------------------------------------------------------- figuras (estilo figures_esi)
def figures(con: pd.DataFrame, curve: pd.DataFrame, rr2df: pd.DataFrame | None, s1: pd.DataFrame, best: dict) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    import xai_12_figures_esi as ESI

    # S3: contrastes A–D (estaciones) y valor económico relativo
    fig, axes = plt.subplots(1, 2, figsize=(ESI.W2, 72 * ESI.MM), gridspec_kw={"width_ratios": [1.2, 1]})
    ax = axes[0]
    x = con[(con["remuestreo"] == "estaciones") & (con["evento"] == "P90")]
    cols = {1: ESI.FUZZY, 7: "#767676", 14: "#E69F00"}
    mk = {1: "o", 7: "s", 14: "^"}
    for i, c in enumerate(CONTRASTS):
        for j, h in enumerate(D.HORIZONS):
            r = x[(x["contraste"] == c) & (x["h"] == h)].iloc[0]
            yy = -i + (j - 1) * 0.22
            ax.errorbar(r.delta_csi, yy, xerr=[[r.delta_csi - r.ic_lo], [r.ic_hi - r.delta_csi]], ls="none",
                        marker=mk[h], ms=4, capsize=2, elinewidth=0.9, color=cols[h])
    ax.set_yticks([-i for i in range(len(CONTRASTS))],
                  [f"{c}: {CONTRASTS[c][0]} − {CONTRASTS[c][1]}" for c in CONTRASTS])
    ax.axvline(0, color="black", lw=0.6)
    ax.set_xlabel("ΔCSI, discharge > P90 (95% CI)")
    ax.legend(handles=[Line2D([], [], ls="none", marker=mk[h], color=cols[h], label=f"{h} d") for h in D.HORIZONS],
              title="Lead time", loc="upper right")
    ESI.letter(ax, "a")
    ax = axes[1]
    sty = {"F": (ESI.FUZZY, "-"), "F0": (ESI.FUZZY, "--"), "T": ("#767676", "-"), "TV": ("#767676", ":")}
    for v, g in curve.groupby("variante"):
        ax.plot(g["costo_perdida"], g["valor_relativo"], color=sty[v][0], ls=sty[v][1], lw=1, label=v)
    ax.set_ylim(-0.1, 1)
    ax.axhline(0, color="black", lw=0.6)
    ax.set_xlabel("Cost/loss ratio")
    ax.set_ylabel("Relative economic value\n(P90, lead time 1 d)")
    ax.legend(loc="upper right")
    ESI.letter(ax, "b")
    fig.tight_layout()
    ESI.save(fig, "figS3_rr1_alert_ablations", 174)

    if rr2df is not None:
        fig, axes = plt.subplots(1, len(MEASURES), figsize=(ESI.W2, 62 * ESI.MM), sharey=False)
        lab = {"spearman_180": "Spearman (180)", "jaccard_top10": "Jaccard top-10", "jaccard_top20": "Jaccard top-20",
               "spearman_canal": "Spearman (input)", "spearman_rezago": "Spearman (day)"}
        kinds = (("entre_modelos", "Between models", "#D55E00", "o"), ("entre_semillas", "Across seeds", ESI.FUZZY, "s"),
                 ("entre_mitades", "Across halves", "#767676", "^"))
        for ax, meas, s in zip(axes, MEASURES, "abcde", strict=True):
            y = rr2df[rr2df["medida"] == meas]
            for j, (kd, _, col, _m) in enumerate(kinds):
                v = y[y["tipo"] == kd]["valor"].to_numpy()
                ax.boxplot(v, positions=[j], widths=0.55, patch_artist=True, showfliers=False,
                           boxprops={"facecolor": ESI.lighten(col, 0.35), "edgecolor": col, "linewidth": 0.8},
                           medianprops={"color": col, "linewidth": 1.2}, whiskerprops={"color": col},
                           capprops={"color": col})
            ax.set_xticks(range(3), ["Btw", "Seed", "Half"])
            ax.set_xlabel(lab[meas])
            ESI.letter(ax, s)
        axes[0].set_ylabel("Agreement between importance maps")
        fig.legend(handles=[Line2D([], [], ls="none", marker="s", color=k[2], label=f"{k[1]}") for k in kinds],
                   loc="lower center", ncol=3, bbox_to_anchor=(0.5, 0.0))
        fig.tight_layout(rect=(0, 0.08, 1, 1))
        ESI.save(fig, "figS4_rr2_noise_ceiling", 174)

    fig, axes = plt.subplots(1, 2, figsize=(ESI.W2, 70 * ESI.MM), sharex=True)
    for ax, (h, col_name), s in zip(axes, ((1, f"nse_h1_{best[1]}"), (7, f"nse_h7_{best[7]}")), "ab", strict=True):
        for b, g in s1.groupby("cuenca"):
            c_, m_ = ESI.BASIN_STYLE[b]
            ax.scatter(g["fraccion_dias_gasto_cero"] * 100, g[col_name], s=14, marker=m_, color=c_, edgecolor="white",
                       lw=0.4, label=b)
        lo = -1.0                                            # escala visible; los valores menores se marcan
        off = s1[s1[col_name] < lo]
        for r in off.itertuples():
            xv = r.fraccion_dias_gasto_cero * 100
            ax.plot(xv, lo + 0.05, marker="v", color="#4D4D4D", ms=4, ls="none")
            ax.annotate(f"{getattr(r, col_name):.1f}" if getattr(r, col_name) > -10 else f"{getattr(r, col_name):.0f}", (xv, lo + 0.05), xytext=(4, 0), textcoords="offset points",
                        va="center", color="#333333")
        ax.set_ylim(lo, 1.05)
        ax.axvline(INTERMITTENT * 100, color="#767676", ls="--", lw=0.8)
        ax.axhline(0, color="black", lw=0.6)
        ax.set_xscale("symlog", linthresh=1)
        ax.set_xlabel("Days with zero discharge (%)")
        ax.set_ylabel(f"NSE, {ESI.STYLE[best[h]]['label']} (lead time {h} d)")
        ESI.letter(ax, s)
    axes[0].legend(loc="lower left")
    fig.tight_layout()
    ESI.save(fig, "figS5_rr6_nse_by_regime", 174)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-rr2", action="store_true")
    ap.add_argument("--threads", type=int, default=16)
    a = ap.parse_args()
    t0 = time.perf_counter()
    e1, e2, e3 = (json.loads((OUT / f"e_rq{i}.json").read_text(encoding="utf-8")) for i in (1, 2, 3))
    chosen = e1["configuracion_elegida"]
    st = pd.read_csv(OUT / "rq1_station_metrics.csv", dtype={"clave": str})
    sm = pd.read_csv(OUT / "rq1_summary.csv")
    evaluable = {h: set(st.loc[(st["h"] == h) & (st["modelo"] == "persistencia"), "clave"]) for h in D.HORIZONS}
    all_ev = sorted(set().union(*evaluable.values()))
    link, basin_of, claves, panels = load_common()
    big = e2["cuencas_con_inferencia"]

    grp = connected_groups(link, all_ev)
    units = link.set_index("clave")["unidad_piloto"].reindex(all_ev)
    grp.to_frame().assign(unidad_piloto=units).to_csv(OUT / "rev_rr3_grupos.csv", index_label="clave")
    groups = {"grupos_conectados": grp, "unidades_piloto": pd.Series(pd.factorize(units)[0], index=units.index)}
    log.info("RR-3: %d grupos conectados, %d unidades", grp.nunique(), groups["unidades_piloto"].nunique())

    res_rr1, ct = rr1(panels, evaluable, {"estaciones": None, **groups}, e3)
    res_rr1["walk_forward_B_P90_h1"] = {"tipo": "opcional; ensamble de 4 miembros", "ic": rr1_walk_forward(panels, chosen)}
    res_rr11, curve = rr11(ct)
    log.info("RR-1 %s", res_rr1["criterios"])

    res_rr2, rr2df = None, None
    rr2_cached = all((CACHE / f"rr2_{SLUG[b]}_h{h}.npz").exists() for b in big for h in D.HORIZONS)
    if not a.skip_rr2:
        rr2_compute(panels, basin_of, claves, chosen, big, a.threads)
        res_rr2, rr2df = rr2_evaluate(big)
        log.info("RR-2 %s", {k: v["veredicto"] for k, v in res_rr2["por_medida"].items()})
    res_rr34, _ = rr34(st, groups, ct, e1, e3)
    res_rr6, s1 = rr6(panels, link, basin_of, st, sm, evaluable[1])
    res = {"fecha": date.today().isoformat(), "fuente": "scripts/xai_14_review_analyses.py", "tipo": TAG,
           "criterios": "proof_ledger.md, 'Análisis de revisión (2026-10-16)', commit ca12106 (antes de calcular)",
           "rr1_alertas": {"fuente": "rev_rr1_*.csv", "tipo": TAG, **res_rr1},
           "rr11_valor_relativo": {"fuente": "rev_rr11_valor_relativo.csv", "tipo": TAG, **res_rr11},
           "rr2_techo_de_ruido": ({"fuente": "rev_rr2_medidas.csv; caché en data/interim/xai_benchmark/review",
                                   "tipo": TAG, **res_rr2} if res_rr2 else {"estado": "no corrido (--skip-rr2)"}),
           "rr3_rr4_sensibilidad": {"fuente": "rev_rr34_ic.csv; rev_rr3_grupos.csv", "tipo": TAG,
                                    "grupos": {"grupos_conectados": int(grp.nunique()),
                                               "tamaños": sorted(grp.value_counts().astype(int).tolist(), reverse=True),
                                               "unidades_piloto": int(groups["unidades_piloto"].nunique())},
                                    **res_rr34},
           "rr6_descriptores": {"fuente": "tables/S1_descriptores.csv", "tipo": TAG, **res_rr6},
           "rr5_presas": {"tipo": TAG, **rr5()}}
    sec = round(time.perf_counter() - t0, 1)
    prev = OUT / "e_revision.json"
    if rr2_cached and prev.exists():      # el registro de cómputo es el de la corrida que recalculó RR-2
        res["computo"] = json.loads(prev.read_text(encoding="utf-8"))["computo"]
    else:
        res["computo"] = {"horas_cpu": round(sec / 3600, 3), "nota": "corrida completa, con el recálculo de RR-2"}
        manifest.replace(OUT / "compute_manifest.csv", fecha=date.today().isoformat(), tipo="evaluacion",
                         run="xai_14_review_analyses", modelo="revision_pares",
                         dispositivo=platform.processor() or "cpu", hilos=a.threads, segundos=sec, pared_s=sec)
    (OUT / "e_revision.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    nums = json.loads((OUT / "numbers.json").read_text(encoding="utf-8"))
    nums["revision_pares"] = res
    nums["software"] = software()
    (OUT / "numbers.json").write_text(json.dumps(nums, indent=2, ensure_ascii=False), encoding="utf-8")

    con = pd.read_csv(OUT / "rev_rr1_contrastes.csv")
    figures(con, curve, rr2df, s1, {int(k[1:]): v for k, v in res_rr6["mejor_modelo"].items()})
    tables(res, con)
    log.info("listo en %.0f s", sec)


def tables(res: dict, con: pd.DataFrame) -> None:
    pd.read_csv(OUT / "rev_rr1_variantes.csv").to_csv(OUT / "tables" / "T13_ablaciones_alertas.csv", index=False)
    con.to_csv(OUT / "tables" / "T13b_contrastes_alertas.csv", index=False)
    if "por_medida" in res["rr2_techo_de_ruido"]:
        rows = []
        for meas, v in res["rr2_techo_de_ruido"]["por_medida"].items():
            for combo, d in v["detalle"].items():
                rows.append({"medida": meas, "combinacion": combo, **d})
            rows.append({"medida": meas, "combinacion": "veredicto", "entre_modelos_mediana": None,
                         "pares_bajo_techo_semillas": v["con_mayoria_de_pares_bajo_el_techo"], "veredicto": v["veredicto"]})
        pd.DataFrame(rows).to_csv(OUT / "tables" / "T10_techo_ruido.csv", index=False)
    ch = res["rr3_rr4_sensibilidad"]["cambios"]
    rows = []
    for tag, d in ch.items():
        how, adj = tag.split("|")
        for hyp, v in d.items():
            rows.append({"remuestreo": how, "ajuste": adj, "hipotesis": hyp, "oficial": json.dumps(v["oficial"], ensure_ascii=False),
                         "sensibilidad": json.dumps(v["sensibilidad"], ensure_ascii=False), "cambia": v["cambia"]})
    pd.DataFrame(rows).to_csv(OUT / "tables" / "T11_veredictos_sensibilidad.csv", index=False)


if __name__ == "__main__":
    main()
