from __future__ import annotations

import traitlets as tl

from aiidalab_qe.common.mixins import HasStructure
from aiidalab_qe.common.wizard import QeConfirmableWizardStepModel, State


class StructureStepModel(
    QeConfirmableWizardStepModel,
    HasStructure,
):
    identifier = "structure"

    structure_name = tl.Unicode("")
    manager_output = tl.Unicode("")

    installing_sssp = tl.Bool(False)
    sssp_installed = tl.Bool(allow_none=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.confirmation_exceptions += [
            "installing_sssp",
            "sssp_installed",
        ]

    def get_model_state(self) -> dict:
        return {"uuid": self.structure_uuid} if self.has_structure else {}

    def set_model_state(self, state: dict):
        self.structure_uuid = state.get("uuid")

    def update_widget_text(self):
        if not self.has_structure:
            self.structure_name = ""
        else:
            self.manager_output = ""
            self.structure_name = str(self.structure.get_formula())

    def update_state(self):
        super().update_state()
        if self.confirmed:
            self.state = State.SUCCESS
        elif not self.has_structure:
            self.state = State.READY
        else:
            self.state = State.CONFIGURED

    def reset(self):
        self.structure_uuid = None
        self.structure_name = ""
        self.manager_output = ""

    def _check_blockers(self):
        if not self.sssp_installed:
            yield "The SSSP library is not installed"
