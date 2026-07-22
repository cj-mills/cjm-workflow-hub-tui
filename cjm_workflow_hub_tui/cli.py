"""The console-script driver (cjm-workflow-hub): resolve the workspace, export
it so the graph capability + every launched stage TUI resolve workspace-scoped
paths, then run the hub app. The hub is the front door — it opens on whatever
the workspace graph holds and never needs sources/paths on its argv."""

import argparse
import os

from cjm_substrate.core.workspace import resolve_workspace

from .app import HubApp


def build_parser() -> argparse.ArgumentParser:  # Configured CLI parser
    """The hub driver's argument surface (everything else the workspace answers)."""
    p = argparse.ArgumentParser(
        prog="cjm-workflow-hub",
        description="Workspace front door for the transcription workflow: "
                    "collection-grouped sources with stage-at-a-glance pipeline "
                    "status, launch into the stage TUIs, and the collection "
                    "curation surface (confirm/rename/refile/order/merge).")
    p.add_argument("--workspace", default=None,
                   help="Workspace root (5daadfc4; default: CJM_WORKSPACE env, else "
                        "upward walk from cwd). Exported so the graph capability and "
                        "every launched stage TUI resolve workspace-scoped paths")
    p.add_argument("--manifests-dir", default=None,
                   help="Capability manifests directory (default: the workspace's "
                        ".cjm/manifests when one is active, else .cjm/manifests under the cwd)")
    p.add_argument("--graph-db-path", default=None,
                   help="Explicit graph db (default: the graph capability's persisted "
                        "workspace-scoped config; none anywhere = loud refusal)")
    p.add_argument("--graph-capability", default="cjm-capability-graph-sqlite",
                   help="Graph-storage capability name")
    return p


def main() -> int:  # Console-script entry point (cjm-workflow-hub)
    """Resolve the workspace, export it, run the hub."""
    args = build_parser().parse_args()
    ws = resolve_workspace(explicit=args.workspace)
    if ws is not None:
        os.environ["CJM_WORKSPACE"] = str(ws.root)
    manifests_dir = args.manifests_dir or (
        str(ws.substrate_data_dir / "manifests") if ws is not None else ".cjm/manifests")
    app = HubApp(manifests_dir, graph_db_path=args.graph_db_path,
                 graph_capability=args.graph_capability)
    app.run()
    return 0
