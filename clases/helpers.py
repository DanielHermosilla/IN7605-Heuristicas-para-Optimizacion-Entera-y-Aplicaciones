import osmnx as ox
import numpy as np
import geopandas as gpd
import networkx as nx
import matplotlib.pyplot as plt
import math
from pathlib import Path
import json
import csv
import random
import math
import pathlib


def obtenerGrafo(cantidadNodos, seed=42, noise_level=0.7, ciudad="santiago"):
    """
    Obtiene un grafo representando las cafeterías disponibles en Buenos Aires.

    Parámetros
    ----------
    cantidadNodos: int
        Cantidad de nodos a tener. Si sobrepasa la cantidad total de cafeterías, devuelve el mínimo.


    seed: int
        Semilla para determinar el ruido entre aristas

    noise_level: float
        Ruido que se añade a cada arista, para simular tráfico.

    Retorna
    -------

    nx.Graph: grafo con metadata para poder graficar y nodos correspondientes a cada cafetería.
    """
    # -----
    # Leer grafo de Buenos Aires
    # -----
    rng = np.random.default_rng(seed)
    G = ox.load_graphml(f"data/{ciudad}_drive.graphml")
    pois = gpd.read_file(f"data/cafes_{ciudad}.geojson")
    pois = pois[pois.geometry.type == "Point"].reset_index(drop=True)

    # -----
    # Obtener puntos de interés y muestrear
    # -----
    pois = pois.sample(min(cantidadNodos, len(pois)), random_state=seed).reset_index(
        drop=True
    )
    lats = pois.geometry.y.values
    lons = pois.geometry.x.values
    poi_nodes = ox.nearest_nodes(G, lons, lats)
    N = len(pois)

    # -----
    # Construir grafo completo optimizado
    # -----
    def dists_from(src):
        try:
            return nx.single_source_dijkstra_path_length(
                G, source=src, weight="travel_time"
            )
        except Exception:
            return nx.single_source_dijkstra_path_length(G, source=src, weight="length")

    K = nx.complete_graph(N)
    for i in range(N):
        dist_i = dists_from(poi_nodes[i])
        for j in range(i + 1, N):
            base_w = float(dist_i[poi_nodes[j]])
            noisy_w = base_w * rng.uniform(1.0 - noise_level, 1.0 + noise_level)
            K.add_edge(i, j, weight=noisy_w)

    # -----
    # Guardar metadatos para graficar después
    # -----
    K.graph["poi_nodes"] = poi_nodes
    K.graph["city"] = ciudad
    K.graph["pos"] = {
        i: (G.nodes[poi_nodes[i]]["x"], G.nodes[poi_nodes[i]]["y"]) for i in range(N)
    }

    return K


def graficar(K, labels=False, edge_alpha=0.25, ciudad="santiago"):
    """
    Grafica el grafo obtenido con 'obtenerGrafo'.

    Parámetros
    ----------
    K: networkx.MultiDiGraph (o Graph)
        Grafo a graficar

    labels: bool
        Lógico que determina si añadimos etiquetas a las aristas

    edge_alpha: float
        Opacidad de las aristas
    """

    # -----
    # Cargar grafo
    # -----
    if ciudad == "buenos_aires":
        path = "data/buenos_aires_drive.graphml"
    else:
        path = "data/santiago_drive.graphml"
    Gbg = ox.load_graphml(path)

    # -----
    # Leer metadata de gráfico
    # -----
    pos = K.graph["pos"]

    # -----
    # Definir estilos
    # -----
    pesos = [d["weight"] for _, _, d in K.edges(data=True)]
    wmin, wmax = min(pesos), max(pesos)
    eps = 1e-9
    ancho_aristas = [1.0 + 3.0 * (wmax - w) / (wmax - wmin + eps) for w in pesos]
    labels_aristas = {(i, j): f"{K[i][j]['weight']/60:.1f} min" for i, j in K.edges()}

    # -----
    # Dibujar fondo de Buenos Aires
    # -----
    fig, ax = ox.plot_graph(
        Gbg,
        node_size=0,
        edge_color="#d9d9d9",
        edge_linewidth=0.6,
        bgcolor="white",
        show=False,
        close=False,
    )

    # -----
    # Dibujar el grafo
    # -----
    nx.draw_networkx_edges(
        K, pos, ax=ax, width=ancho_aristas, edge_color="tab:blue", alpha=edge_alpha
    )
    nx.draw_networkx_nodes(
        K,
        pos,
        ax=ax,
        node_size=40,
        node_color="crimson",
        edgecolors="white",
        linewidths=0.8,
    )
    nx.draw_networkx_labels(K, pos, ax=ax, font_size=8)

    if labels:
        nx.draw_networkx_edge_labels(
            K, pos, ax=ax, edge_labels=labels_aristas, font_size=7, rotate=False
        )

    plt.tight_layout()
    plt.show()


def cargarInstanciaORTools(path, relabel_zero_based=True):
    """
    Lee un archivo de coloración de grafos en formato DIMACS.
    Formato esperado (líneas típicas):
      - 'c ...'                  -> comentarios (se ignoran)
      - 'p edge n m'             -> cabecera, con n = #nodos, m = #aristas
      - 'e u v'                  -> arista entre u y v (índices 1..n)

    Parámetros
    ----------
    path : str
        Ruta al archivo (por ejemplo 'gcol15.txt').
    relabel_zero_based : bool
        Si es True, re-etiqueta los nodos a 0..n-1 (útil para trabajar con arrays).

    Retorna
    -------
    G : networkx.Graph
        Grafo simple no dirigido, sin pesos.
    meta : dict
        Información auxiliar: {'n', 'm', 'one_indexed', 'path'}.
    """
    n = None  # número de nodos declarado en la cabecera (si existe)
    m = None  # número de aristas declarado en la cabecera (si existe)
    edges = []  # acumularemos las aristas aquí

    # Abrimos el archivo línea por línea
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue  # saltar líneas vacías
            if line.startswith("c"):
                continue  # saltar comentarios

            if line.startswith("p"):
                # Ejemplo: "p edge 100 2528"
                parts = line.split()
                # Buscamos los dos últimos números como n y m (robusto ante espacios extra)
                # Si el archivo usa "p edge n m", deberíamos tener al menos 4 tokens.
                if len(parts) >= 4:
                    # Normalmente: parts = ["p", "edge", n, m]
                    n = int(parts[-2])
                    m = int(parts[-1])
                else:
                    raise ValueError("Cabecera 'p' inválida: " + line)
                continue

            if line.startswith("e"):
                # Ejemplo: "e 1 2" -> arista (1,2)
                parts = line.split()
                # Esperamos al menos 3 tokens: ['e', 'u', 'v']
                if len(parts) >= 3:
                    u = int(parts[1])
                    v = int(parts[2])
                    edges.append((u, v))
                continue

    # Si no hubo cabecera 'p', inferimos n como el máximo índice que apareció
    if n is None:
        if not edges:
            raise ValueError("No se encontraron aristas ni cabecera 'p'.")
        n = max(max(u, v) for (u, v) in edges)
        m = len(edges)
    else:
        # Si hubo 'p', m podría no coincidir con len(edges) (no es grave para construir el grafo)
        if m is None:
            m = len(edges)

    # Construimos un grafo etiquetado 1..n (como dicta DIMACS)
    G = nx.Graph()
    G.add_nodes_from(range(1, n + 1))
    G.add_edges_from(edges)

    meta = {"n": n, "m": m, "one_indexed": True, "path": path}

    # re-etiquetar a 0..n-1, que es cómodo para arrays numpy
    if relabel_zero_based:
        mapping = {u: u - 1 for u in G.nodes()}
        G = nx.relabel_nodes(G, mapping, copy=True)
        meta["one_indexed"] = False

    return G, meta


def to_color_array(colors, n):
    """
    Convierte 'colors' a un arreglo numpy de enteros de largo n (o None).
    Acepta:
      - dict {nodo: color}  (nodos 0..n-1)
      - lista/array con el color de cada nodo en orden 0..n-1
      - None  -> devuelve None

    Notas:
      - No valida si los colores están en [0..k-1]; aquí sólo normalizamos formato.
      - Para grafos re-etiquetados a 0..n-1, esto es lo más práctico.
    """
    if colors is None:
        return None

    # Si es un diccionario {nodo: color}, lo volcamos a un array
    if isinstance(colors, dict):
        arr = np.zeros(n, dtype=int)
        for u, c in colors.items():
            arr[int(u)] = int(c)
        return arr

    # Si es lista/tupla/array, nos aseguramos que sea numpy.int y del largo n
    arr = np.asarray(list(colors), dtype=int)
    if arr.size != n:
        raise ValueError(f"'colors' debe tener largo n={n}, se obtuvo {arr.size}.")
    return arr


def count_conflicts(G, color_arr):
    """
    Cuenta el número de aristas en conflicto (extremos con el mismo color).
    """
    # Recorremos todas las aristas y comparamos el color de sus extremos
    cnt = 0
    for u, v in G.edges():
        if color_arr[u] == color_arr[v]:
            cnt += 1
    return cnt


def _pick_palette(k):
    """
    Construye una lista de 'k' colores (hex) para pintar nodos por clase/color.
    Usamos la paleta 'tab20' de matplotlib repetida si hiciera falta.
    """
    import matplotlib  # lo importamos aquí para no llenar el espacio global

    base = matplotlib.colormaps.get_cmap("tab20").colors  # paleta de 20 colores
    # Si k > 20, repetimos la paleta las veces necesarias
    repeticiones = int(math.ceil(k / float(len(base))))
    colores_hex = []
    for _ in range(repeticiones):
        for rgb in base:
            colores_hex.append(matplotlib.colors.to_hex(rgb))
    return colores_hex[:k]  # nos quedamos con los primeros k


def graficarColoracion(
    G,
    colors=None,  # dict {nodo: color} o lista/array por índice
    k=None,  # nº de colores (si None, se infiere del máximo en 'colors')
    highlight_conflicts=True,  # si True, dibuja aristas en conflicto en rojo
    node_size=None,  # tamaño de los nodos (si None, se escala con n)
    edge_alpha=0.5,  # opacidad de aristas
    pos=None,  # layout (dict nodo -> (x,y)); si None, se calcula
    seed=42,  # semilla para el layout
    with_labels=False,  # si True, escribe el id de cada nodo (útil en grafos chicos)
):
    """
    Dibuja el grafo 'G' y, opcionalmente, un coloreo sobre sus nodos.
    Si se entrega 'colors', además puede resaltar en rojo las aristas en conflicto.
    Devuelve (fig, ax, pos) por si el usuario quiere reutilizar el layout.

    """
    n = G.number_of_nodes()

    # Normalizamos 'colors' a un array numpy o dejamos None si no se entregó
    color_arr = to_color_array(colors, n) if colors is not None else None

    # Si no nos dicen el tamaño de los nodos, definimos uno "decente" según n
    if node_size is None:
        if n <= 120:
            node_size = 300
        else:
            # a mayor n, hacemos el nodo más pequeño para que no tape todo
            node_size = max(40, int(12000 / n))

    # Si no nos dan un layout, usamos spring_layout (fuerzas) con semilla fija
    if pos is None:
        pos = nx.spring_layout(G, seed=seed)  # k por defecto (automático)

    # Creamos la figura y un eje
    fig, ax = plt.subplots(figsize=(8, 6))

    # 1) Primero dibujamos TODAS las aristas en gris claro (fondo)
    nx.draw_networkx_edges(
        G, pos, ax=ax, width=0.6, alpha=edge_alpha, edge_color="#bbbbbb"
    )

    # 2) Ahora dibujamos los nodos: con o sin colores según 'colors'
    if color_arr is None:
        # Sin coloreo: todos los nodos del mismo color azul
        nx.draw_networkx_nodes(
            G,
            pos,
            ax=ax,
            node_size=node_size,
            node_color="#4477aa",
            linewidths=0.5,
            edgecolors="white",
        )
        title = f"Grafo: n={n}, m={G.number_of_edges()}"
    else:
        # Con coloreo: asignamos una paleta
        if k is None:
            # Si no nos pasan k, lo inferimos del máximo color observado (+1)
            k = int(color_arr.max()) + 1
        palette = _pick_palette(k)
        # Construimos la lista de colores de cada nodo según su clase/color
        node_colors = [palette[int(c)] for c in color_arr]

        nx.draw_networkx_nodes(
            G,
            pos,
            ax=ax,
            node_size=node_size,
            node_color=node_colors,
            linewidths=0.5,
            edgecolors="white",
        )

        # Resaltar conflictos: aristas cuyos extremos tienen el mismo color
        conflictos = 0
        if highlight_conflicts:
            conflict_edges = []
            for u, v in G.edges():
                if color_arr[u] == color_arr[v]:
                    conflict_edges.append((u, v))
            conflictos = len(conflict_edges)
            if conflict_edges:
                nx.draw_networkx_edges(
                    G,
                    pos,
                    edgelist=conflict_edges,
                    ax=ax,
                    width=1.2,
                    alpha=0.9,
                    edge_color="#d62728",  # rojo para conflictos
                )

        title = f"Coloreo con k={k} | conflictos={conflictos} | n={n}, m={G.number_of_edges()}"

    # 4) Etiquetas de nodos (para grafos pequeños es útil)
    if with_labels and n <= 200:
        nx.draw_networkx_labels(G, pos, ax=ax, font_size=8)

    # 5) Detalles finales de la figura
    ax.set_title(title)
    ax.set_xticks([])
    ax.set_yticks([])
    plt.tight_layout()

    # return fig, ax, pos
    plt.show()


# Cutting Stock instance generator (no typing, Py 3.9–3.11)
import json
import csv
import random
import math
import pathlib
import matplotlib.pyplot as plt


class ItemType:
    """Un tipo de pieza (ancho y demanda)."""

    def __init__(self, _id, width, demand):
        self.id = int(_id)
        self.width = int(width)
        self.demand = int(demand)

    def to_dict(self):
        return {"id": self.id, "width": self.width, "demand": self.demand}


class CSPInstance:
    """Instancia de Cutting Stock."""

    def __init__(self, name, stock_length, items):
        self.name = str(name)
        self.stock_length = int(stock_length)  # L
        self.items = list(items)

    # -------- utilidades docentes --------
    def total_width_demand(self):
        return sum(it.width * it.demand for it in self.items)

    def trivial_lower_bound_rolls(self):
        """LB = ceil( sum_i d_i * w_i / L )."""
        return math.ceil(self.total_width_demand() / self.stock_length)

    def max_item_width(self):
        return max(it.width for it in self.items) if self.items else 0

    def is_basically_feasible(self):
        """Factibilidad básica: todos w_i <= L y demandas >= 0."""
        if any((it.width <= 0 or it.demand < 0) for it in self.items):
            return False
        return self.max_item_width() <= self.stock_length

    # -------- guardado / carga --------
    def to_json(self, path):
        data = {
            "name": self.name,
            "stock_length": self.stock_length,
            "items": [it.to_dict() for it in self.items],
        }
        path = pathlib.Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def to_csv(self, path):
        """CSV: primera fila con comentario de L, luego header id,width,demand."""
        path = pathlib.Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([f"# stock_length = {self.stock_length}", "", ""])
            w.writerow(["id", "width", "demand"])
            for it in self.items:
                w.writerow([it.id, it.width, it.demand])

    @staticmethod
    def from_json(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = [ItemType(it["id"], it["width"], it["demand"]) for it in data["items"]]
        return CSPInstance(data["name"], data["stock_length"], items)


def generar_instancia_CSP(
    n_types,
    stock_length,
    width_range=(5, 60),
    demand_range=(5, 60),
    tightness=0.65,
    ensure_diversity=True,
    seed=None,
    name=None,
):
    """
    Genera una instancia aleatoria de Cutting Stock.

    Parámetros
    ----------
    n_types : cantidad de tipos de piezas.
    stock_length : L (longitud del rollo grande).
    width_range : (min_w, max_w) para anchos de pieza.
    demand_range : (min_d, max_d) para demandas por tipo.
    tightness : en (0,1]. Aprox. controla un sesgo hacia anchos más grandes.
    ensure_diversity : intenta evitar que todos los anchos sean iguales.
    seed : semilla RNG (reproducible).
    name : nombre de la instancia.

    Devuelve
    --------
    CSPInstance
    """
    rng = random.Random(seed)

    min_w, max_w = width_range
    min_d, max_d = demand_range
    if not (1 <= min_w <= max_w < stock_length):
        raise ValueError("width_range debe estar por debajo de L y min_w>=1")
    if not (1 <= min_d <= max_d):
        raise ValueError("demandas deben ser positivas")

    # Sesgo sencillo: mezcla uniforme con u^2 (favorece valores altos según 'tightness').
    def sample_width():
        u = rng.random()
        alpha = float(tightness)
        u_prime = (1 - alpha) * u + alpha * (u**2)
        w = min_w + int(u_prime * (max_w - min_w))
        w = max(min_w, min(w, max_w))
        # garantía de factibilidad básica
        w = min(w, stock_length - 1)
        return w

    items = []
    widths = []
    for i in range(int(n_types)):
        w = sample_width()
        d = rng.randint(min_d, max_d)
        items.append(ItemType(i, w, d))
        widths.append(w)

    if ensure_diversity and len(set(widths)) == 1 and n_types >= 2:
        j = rng.randrange(n_types)
        alt = rng.randint(min_w, max_w)
        alt = min(alt, stock_length - 1)
        items[j].width = alt

    inst = CSPInstance(
        name
        or f"csp_{n_types}t_L{stock_length}_seed{seed if seed is not None else 'na'}",
        stock_length,
        items,
    )
    if not inst.is_basically_feasible():
        raise ValueError("Instancia no es básicamente factible (revisa rangos).")
    return inst


def plotear_instancia_CSP(
    inst,
    patterns=None,
    rolls_to_show=None,
    bar_height=0.7,
    colors=None,
    title=None,
):
    """
    Dibuja “rollos” como barras horizontales de longitud L.
    Si entregas 'patterns' (lista de patrones, cada patrón es una lista de anchos), los dibuja secuencialmente.
    Útil para docencia (no es solución).
    """
    L = inst.stock_length
    if colors is None:
        colors = [
            "#3b82f6",
            "#22c55e",
            "#f59e0b",
            "#ef4444",
            "#a855f7",
            "#06b6d4",
            "#84cc16",
            "#e11d48",
        ]
    if patterns is None:
        patterns = [[] for _ in range(3)]
    if rolls_to_show is not None:
        patterns = patterns[:rolls_to_show]

    H = len(patterns) * (bar_height + 0.35) + 0.6
    plt.figure(figsize=(10, max(2.5, H)))
    y = 0.5

    for r_idx, pat in enumerate(patterns):
        # fondo del rollo
        plt.hlines(y, 0, L, colors="lightgray", linewidth=8, alpha=0.7)
        # piezas
        x0 = 0
        for k, w in enumerate(pat):
            x1 = x0 + w
            plt.fill_between(
                [x0, x1],
                [y - bar_height / 2, y - bar_height / 2],
                [y + bar_height / 2, y + bar_height / 2],
                color=colors[k % len(colors)],
                alpha=0.9,
            )
            plt.text(
                (x0 + x1) / 2,
                y,
                str(w),
                ha="center",
                va="center",
                color="white",
                fontsize=10,
            )
            x0 = x1
        # sobrante
        if x0 < L:
            plt.fill_between(
                [x0, L],
                [y - bar_height / 2, y - bar_height / 2],
                [y + bar_height / 2, y + bar_height / 2],
                color="#e5e7eb",
                alpha=0.8,
            )
            plt.text(
                (x0 + L) / 2,
                y,
                "gap=" + str(L - x0),
                ha="center",
                va="center",
                color="#374151",
                fontsize=9,
            )
        y += bar_height + 0.35

    plt.xlim(0, L)
    plt.ylim(0, y + 0.2)
    plt.xlabel("Longitud usada sobre el rollo (L)")
    t = title or "{} — L={}, tipos={}, LB={}".format(
        inst.name, L, len(inst.items), inst.trivial_lower_bound_rolls()
    )
    plt.title(t)
    plt.yticks([])
    plt.grid(axis="x", alpha=0.25)
    plt.tight_layout()
    plt.show()
