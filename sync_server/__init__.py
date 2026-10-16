"""Sync backend: optional progress sync for the MentorSmith Android app.

It exists so the Android app never has to hold an AI provider key. It is not
required: the app works fully offline without it.

The submodule ``sync_server.app`` is deliberately **not** re-exported here.
Doing so would bind the name ``app`` on the package to the FastAPI instance and
shadow the module of the same name, which breaks ``import sync_server.app``.
"""

__all__ = ["store"]