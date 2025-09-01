from __future__ import annotations

import contextlib

import traitlets as tl

from aiida import orm
from aiida.engine import ProcessState, processes
from aiidalab_qe.common.mixins import HasModels, HasProcess
from aiidalab_qe.common.process import STATE_ICONS
from aiidalab_qe.common.wizard import DependentWizardStepModel, State

from .components import ResultsComponentModel


class ResultsStepModel(
    DependentWizardStepModel,
    HasModels[ResultsComponentModel],
    HasProcess,
):
    identifier = "results"

    process_info = tl.Unicode("")
    process_remote_folder_is_clean = tl.Bool(False)

    STATUS_TEMPLATE = "<h4>Workflow status: {}</h4"

    def update(self):
        self._update_process_remote_folder_state()

    def kill_process(self):
        if process_node := self.fetch_process_node():
            processes.control.kill_processes([process_node])

    def clean_remote_data(self):
        if not (process_node := self.fetch_process_node()):
            return
        for called_descendant in process_node.called_descendants:
            if isinstance(called_descendant, orm.CalcJobNode):
                with contextlib.suppress(Exception):
                    called_descendant.outputs.remote_folder._clean()
        self.process_remote_folder_is_clean = True

    def update_state(self):
        super().update_state()
        if not (process_node := self.fetch_process_node()):
            self.state = State.INIT
            return

        if process_state := process_node.process_state:
            status = self._get_process_status(process_state.value)
        else:
            status = "Unknown"

        if process_state is ProcessState.CREATED:
            self.state = State.ACTIVE
        elif process_state in (
            ProcessState.RUNNING,
            ProcessState.WAITING,
        ):
            self.state = State.ACTIVE
            status = self._get_process_status("running")  # overwrite status
        elif process_state in (
            ProcessState.EXCEPTED,
            ProcessState.KILLED,
        ):
            self.state = State.FAIL
        elif process_node.is_failed:
            self.state = State.FAIL
        elif process_node.is_finished_ok:
            self.state = State.SUCCESS

        self.process_info = self.STATUS_TEMPLATE.format(status)

    def reset(self):
        self.process_uuid = None
        self.process_info = ""

    def _update_process_remote_folder_state(self):
        process_node = self.fetch_process_node()
        if not (process_node and process_node.called_descendants):
            return
        cleaned = []
        for called_descendant in process_node.called_descendants:
            if isinstance(called_descendant, orm.CalcJobNode):
                with contextlib.suppress(Exception):
                    cleaned.append(called_descendant.outputs.remote_folder.is_empty)
        self.process_remote_folder_is_clean = all(cleaned)

    def _link_model(self, model: ResultsComponentModel):
        tl.dlink(
            (self, "process_uuid"),
            (model, "process_uuid"),
        )
        tl.dlink(
            (self, "monitor_counter"),
            (model, "monitor_counter"),
        )

    def _get_process_status(self, state: str):
        return f"{state.capitalize()} {STATE_ICONS[state]}"
