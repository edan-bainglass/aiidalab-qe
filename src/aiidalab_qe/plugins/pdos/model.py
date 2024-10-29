import traitlets as tl

from aiida import orm
from aiida_quantumespresso.calculations.functions.create_kpoints_from_distance import (
    create_kpoints_from_distance,
)
from aiida_quantumespresso.workflows.pdos import PdosWorkChain
from aiidalab_qe.common.panel import SettingsModel


class PdosModel(SettingsModel):
    dependencies = [
        "input_structure",
        "workchain.protocol",
    ]

    input_structure = tl.Instance(orm.StructureData, allow_none=True)
    protocol = tl.Unicode(allow_none=True)

    kpoints_distance = tl.Float(0.1)
    mesh_grid = tl.Unicode("")
    use_pdos_degauss = tl.Bool(False)
    pdos_degauss = tl.Float(0.005)

    def __init__(self, include=False, *args, **kwargs):
        super().__init__(include, *args, **kwargs)

        self._defaults = {
            "kpoints_distance": self.traits()["kpoints_distance"].default_value,
        }

    def update(self, specific=""):
        with self.hold_trait_notifications():
            self._update_defaults(specific)
            self.kpoints_distance = self._defaults["kpoints_distance"]

    def get_model_state(self):
        return {
            "nscf_kpoints_distance": self.kpoints_distance,
            "use_pdos_degauss": self.use_pdos_degauss,
            "pdos_degauss": self.pdos_degauss,
        }

    def set_model_state(self, parameters: dict):
        self.nscf_kpoints_distance = parameters.get(
            "nscf_kpoints_distance",
            self.traits()["kpoints_distance"].default_value,
        )
        self.use_pdos_degauss = parameters.get("use_pdos_degauss", False)
        self.pdos_degauss = parameters.get("pdos_degauss", 0.005)

    def reset(self):
        with self.hold_trait_notifications():
            self.kpoints_distance = self._defaults["kpoints_distance"]
            self.use_pdos_degauss = self.traits()["use_pdos_degauss"].default_value
            self.pdos_degauss = self.traits()["pdos_degauss"].default_value

    def _update_defaults(self, specific=""):
        if not specific or specific != "mesh":
            parameters = PdosWorkChain.get_protocol_inputs(self.protocol)
            self._update_kpoints_distance(parameters)

        self._update_kpoints_mesh()

    def _update_kpoints_mesh(self, _=None):
        if self.input_structure is None:
            mesh_grid = ""
        elif self.kpoints_distance > 0:
            mesh = create_kpoints_from_distance.process_class._func(
                self.input_structure,
                orm.Float(self.kpoints_distance),
                orm.Bool(False),
            )
            mesh_grid = f"Mesh {mesh.get_kpoints_mesh()[0]!s}"
        else:
            mesh_grid = "Please select a number higher than 0.0"
        self._defaults["mesh_grid"] = mesh_grid
        self.mesh_grid = mesh_grid

    def _update_kpoints_distance(self, parameters):
        if self.has_pbc:
            kpoints_distance = parameters["nscf"]["kpoints_distance"]
        else:
            kpoints_distance = 100.0
            self.use_pdos_degauss = True
        self._defaults["kpoints_distance"] = kpoints_distance
