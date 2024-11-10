from __future__ import annotations

import contextlib

import traitlets as tl

from aiida import orm
from aiida.common.exceptions import NotExistent
from aiida.engine.processes import control
from aiidalab_qe.common.mvc import Model


class ResultsModel(Model):
    process_uuid = tl.Unicode(allow_none=True)

    process_info = tl.Unicode("")
    process_remote_folder_is_clean = tl.Bool(False)

    @property
    def process_node(self):
        return self.get_process_node()

    def update(self):
        self._update_process_remote_folder_state()

    def get_process_node(self):
        try:
            return orm.load_node(self.process_uuid) if self.process_uuid else None
        except NotExistent:
            return None

    def kill_process(self):
        if process_node := self.get_process_node():
            control.kill_processes([process_node])

    def clean_remote_data(self):
        if not (process_node := self.get_process_node()):
            return
        for called_descendant in process_node.called_descendants:
            if isinstance(called_descendant, orm.CalcJobNode):
                with contextlib.suppress(Exception):
                    called_descendant.outputs.remote_folder._clean()
        self.process_remote_folder_is_clean = True

    def reset(self):
        self.process_uuid = None
        self.process_info = ""

    def _update_process_remote_folder_state(self):
        if not (process_node := self.get_process_node()):
            return
        cleaned = []
        for called_descendant in process_node.called_descendants:
            if isinstance(called_descendant, orm.CalcJobNode):
                with contextlib.suppress(Exception):
                    cleaned.append(called_descendant.outputs.remote_folder.is_empty)
        self.process_remote_folder_is_clean = all(cleaned)
