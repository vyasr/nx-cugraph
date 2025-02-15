# Copyright (c) 2024, NVIDIA CORPORATION.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import networkx as nx
import pytest

import nx_cugraph as nxcg
from nx_cugraph import _nxver

from .testing_utils import assert_graphs_equal


@pytest.mark.parametrize(
    "create_using", [nx.Graph, nx.DiGraph, nx.MultiGraph, nx.MultiDiGraph]
)
@pytest.mark.parametrize("radius", [-1, 0, 1, 1.5, 2, float("inf"), None])
@pytest.mark.parametrize("center", [True, False])
@pytest.mark.parametrize("undirected", [False, True])
@pytest.mark.parametrize("multiple_edges", [False, True])
@pytest.mark.parametrize("n", [0, 3])
def test_ego_graph_cycle_graph(
    create_using, radius, center, undirected, multiple_edges, n
):
    Gnx = nx.cycle_graph(7, create_using=create_using)
    if multiple_edges:
        # Test multigraph with multiple edges
        if not Gnx.is_multigraph():
            return
        Gnx.add_edges_from(nx.cycle_graph(7, create_using=nx.DiGraph).edges)
        Gnx.add_edge(0, 1, 10)
    Gcg = nxcg.from_networkx(Gnx, preserve_all_attrs=True)
    assert_graphs_equal(Gnx, Gcg)  # Sanity check

    kwargs = {"radius": radius, "center": center, "undirected": undirected}
    Hnx = nx.ego_graph(Gnx, n, **kwargs)
    Hcg = nx.ego_graph(Gnx, n, **kwargs, backend="cugraph")
    use_compat_graphs = _nxver < (3, 3) or nx.config.backends.cugraph.use_compat_graphs
    assert_graphs_equal(Hnx, Hcg._cudagraph if use_compat_graphs else Hcg)
    Hcg = nx.ego_graph(Gcg, n, **kwargs)
    assert_graphs_equal(Hnx, Hcg)
    Hcg = nx.ego_graph(Gcg._to_compat_graph(), n, **kwargs)
    assert_graphs_equal(Hnx, Hcg._cudagraph)
    with pytest.raises(nx.NodeNotFound, match="not in G"):
        nx.ego_graph(Gnx, -1, **kwargs)
    with pytest.raises(nx.NodeNotFound, match="not in G"):
        nx.ego_graph(Gnx, -1, **kwargs, backend="cugraph")
    # Using sssp with default weight of 1 should give same answer as bfs
    nx.set_edge_attributes(Gnx, 1, name="weight")
    Gcg = nxcg.from_networkx(Gnx, preserve_all_attrs=True)
    assert_graphs_equal(Gnx, Gcg)  # Sanity check

    kwargs["distance"] = "weight"
    H2nx = nx.ego_graph(Gnx, n, **kwargs)
    is_nx32 = _nxver[:2] == (3, 2)
    if undirected and Gnx.is_directed() and Gnx.is_multigraph():
        if is_nx32:
            # `should_run` was added in nx 3.3
            match = "Weighted ego_graph with undirected=True not implemented"
        elif _nxver >= (3, 4):
            match = "not implemented by 'cugraph'"
        else:
            match = "not implemented by cugraph"
        with pytest.raises(
            RuntimeError if _nxver < (3, 4) else NotImplementedError, match=match
        ):
            nx.ego_graph(Gnx, n, **kwargs, backend="cugraph")
        with pytest.raises(NotImplementedError, match="ego_graph"):
            nx.ego_graph(Gcg, n, **kwargs, backend="cugraph")
        if _nxver < (3, 4) or not nx.config.fallback_to_nx:
            with pytest.raises(NotImplementedError, match="ego_graph"):
                nx.ego_graph(Gcg, n, **kwargs)
        else:
            # This is an interesting case. `nxcg.ego_graph` is not implemented for
            # these arguments, so it falls back to networkx. Hence, as it is currently
            # implemented, the input graph is `nxcg.CudaGraph`, but the output graph
            # is `nx.Graph`. Should networkx convert back to "cugraph" backend?
            H2cg = nx.ego_graph(Gcg, n, **kwargs)
            assert type(H2nx) is type(H2cg)
            assert_graphs_equal(H2nx, nxcg.from_networkx(H2cg, preserve_all_attrs=True))
    else:
        H2cg = nx.ego_graph(Gnx, n, **kwargs, backend="cugraph")
        assert_graphs_equal(H2nx, H2cg._cudagraph if use_compat_graphs else H2cg)
        with pytest.raises(nx.NodeNotFound, match="not found in graph"):
            nx.ego_graph(Gnx, -1, **kwargs)
        with pytest.raises(nx.NodeNotFound, match="not found in graph"):
            nx.ego_graph(Gnx, -1, **kwargs, backend="cugraph")
