"""
Legacy DM Workspace Facade
Delegates top-level rendering to views.dm.workspace.
"""

from views.dm.workspace import render_dm_workspace, show_npc_stat_block

__all__ = ["render_dm_workspace", "show_npc_stat_block"]
