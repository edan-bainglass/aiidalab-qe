from copy import deepcopy

import traitlets as tl
from aiida_pseudo.common.units import U

from aiida import orm
from aiida.common import exceptions
from aiida.plugins import GroupFactory
from aiida_quantumespresso.workflows.pw.base import PwBaseWorkChain
from aiidalab_qe.app.parameters import DEFAULT_PARAMETERS
from aiidalab_qe.setup.pseudos import PSEUDODOJO_VERSION, SSSP_VERSION, PseudoFamily

from ..subsettings import AdvancedSubModel

SsspFamily = GroupFactory("pseudo.family.sssp")
PseudoDojoFamily = GroupFactory("pseudo.family.pseudo_dojo")
CutoffsPseudoPotentialFamily = GroupFactory("pseudo.family.cutoffs")

DEFAULT: dict = DEFAULT_PARAMETERS  # type: ignore


class PseudosModel(AdvancedSubModel):
    dependencies = [
        "input_structure",
        "protocol",
        "spin_orbit",
    ]

    input_structure = tl.Instance(orm.StructureData, allow_none=True)
    protocol = tl.Unicode()
    spin_orbit = tl.Unicode()
    override = tl.Bool()

    dictionary = tl.Dict(
        key_trait=tl.Unicode(),  # element symbol
        value_trait=tl.Unicode(),  # pseudopotential node uuid
        default_value={},
    )
    family = tl.Unicode(
        "/".join(
            [
                DEFAULT["advanced"]["pseudo_family"]["library"],
                str(DEFAULT["advanced"]["pseudo_family"]["version"]),
                DEFAULT["advanced"]["pseudo_family"]["functional"],
                DEFAULT["advanced"]["pseudo_family"]["accuracy"],
            ]
        )
    )
    functional = tl.Unicode(DEFAULT["advanced"]["pseudo_family"]["functional"])
    functional_options = tl.List(
        trait=tl.Unicode(),
        default_value=[
            "PBE",
            "PBEsol",
        ],
    )
    library = tl.Unicode(
        " ".join(
            [
                DEFAULT["advanced"]["pseudo_family"]["library"],
                DEFAULT["advanced"]["pseudo_family"]["accuracy"],
            ]
        )
    )
    library_options = tl.List(
        trait=tl.Unicode(),
        default_value=[
            "SSSP efficiency",
            "SSSP precision",
            "PseudoDojo standard",
            "PseudoDojo stringent",
        ],
    )
    cutoffs = tl.List(
        trait=tl.List(tl.Float()),  # [[ecutwfc values], [ecutrho values]]
        default_value=[[0.0], [0.0]],
    )
    ecutwfc = tl.Float()
    ecutrho = tl.Float()
    status_message = tl.Unicode()
    family_help_message = tl.Unicode()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.PSEUDO_HELP_SOC = """
            <div class="pseudo-text">
                Spin-orbit coupling (SOC) calculations are supported exclusively with
                PseudoDojo pseudopotentials. PseudoDojo offers these pseudopotentials
                in two versions: standard and stringent. Here, we utilize the FR
                (fully relativistic) type from PseudoDojo. Please ensure you choose
                appropriate cutoff values for your calculations.
            </div>
        """

        self.PSEUDO_HELP_WO_SOC = """
            <div class="pseudo-text">
                If you are unsure, select 'SSSP efficiency', which for most
                calculations will produce sufficiently accurate results at
                comparatively small computational costs. If your calculations require a
                higher accuracy, select 'SSSP accuracy' or 'PseudoDojo stringent',
                which will be computationally more expensive. SSSP is the standard
                solid-state pseudopotentials. The PseudoDojo used here has the SR
                relativistic type.
            </div>
        """

        self.family_help_message = self.PSEUDO_HELP_WO_SOC

        self._defaults = {
            "family": self.traits()["family"].default_value,
            "functional": self.traits()["functional"].default_value,
            "functional_options": [
                "PBE",
                "PBEsol",
            ],
            "library": self.traits()["library"].default_value,
            "library_options": [
                "SSSP efficiency",
                "SSSP precision",
                "PseudoDojo standard",
                "PseudoDojo stringent",
            ],
            "dictionary": {},
            "cutoffs": [[0.0], [0.0]],
        }

    def update(self, which):
        with self.hold_trait_notifications():
            self._update_defaults(which)

    def update_default_pseudos(self):
        try:
            pseudo_family = self._get_pseudo_family_from_database()
            pseudos = pseudo_family.get_pseudos(structure=self.input_structure)
        except ValueError as exception:
            self._status_message = f"""
                <div class='alert alert-danger'>
                    ERROR: {exception!s}
                </div>
            """
            return

        self._defaults["dictionary"] = {
            kind: pseudo.uuid for kind, pseudo in pseudos.items()
        }
        self.dictionary = self._get_default_dictionary()

    def update_default_cutoffs(self):
        """Update wavefunction and density cutoffs from pseudo family."""
        try:
            pseudo_family = self._get_pseudo_family_from_database()
            current_unit = pseudo_family.get_cutoffs_unit()
            cutoff_dict = pseudo_family.get_cutoffs()
        except exceptions.NotExistent:
            self._status_message = f"""
                <div class='alert alert-danger'>
                    ERROR: required pseudo family `{self.family}` is
                    not installed. Please use `aiida-pseudo install` to install
                    it."
                </div>
            """
        except ValueError as exception:
            self._status_message = f"""
                <div class='alert alert-danger'>
                    ERROR: failed to obtain recommended cutoffs for pseudos
                    `{pseudo_family}`: {exception}
                </div>
            """
        else:
            kinds = self.input_structure.kinds if self.input_structure else []

        ecutwfc_list = []
        ecutrho_list = []
        for kind in kinds:
            cutoff = cutoff_dict.get(kind.symbol, {})
            ecutrho, ecutwfc = (
                U.Quantity(v, current_unit).to("Ry").to_tuple()[0]
                for v in cutoff.values()
            )
            ecutwfc_list.append(ecutwfc)
            ecutrho_list.append(ecutrho)

        self._defaults["cutoffs"] = [ecutwfc_list or [0.0], ecutrho_list or [0.0]]
        self.cutoffs = self._get_default_cutoffs()

    def update_library_options(self):
        if self.spin_orbit == "soc":
            library_options = [
                "PseudoDojo standard",
                "PseudoDojo stringent",
            ]
            self.family_help_message = self.PSEUDO_HELP_SOC
        else:
            library_options = [
                "SSSP efficiency",
                "SSSP precision",
                "PseudoDojo standard",
                "PseudoDojo stringent",
            ]
            self.family_help_message = self.PSEUDO_HELP_WO_SOC
        self._defaults["library_options"] = library_options
        self.library_options = self._defaults["library_options"]

        self.update_family_parameters()

    def update_family_parameters(self):
        if self.spin_orbit == "soc":
            if self.protocol in ["fast", "moderate"]:
                pseudo_family_string = "PseudoDojo/0.4/PBE/FR/standard/upf"
            else:
                pseudo_family_string = "PseudoDojo/0.4/PBE/FR/stringent/upf"
        else:
            pseudo_family_string = PwBaseWorkChain.get_protocol_inputs(self.protocol)[
                "pseudo_family"
            ]

        pseudo_family = PseudoFamily.from_string(pseudo_family_string)

        self._defaults["library"] = f"{pseudo_family.library} {pseudo_family.accuracy}"
        self._defaults["functional"] = pseudo_family.functional

        with self.hold_trait_notifications():
            self.library = self._defaults["library"]
            self.functional = self._defaults["functional"]

    def update_family(self):
        library, accuracy = self.library.split()
        functional = self.functional
        # XXX (jusong.yu): a validator is needed to check the family string is
        # consistent with the list of pseudo families defined in the setup_pseudos.py
        if library == "PseudoDojo":
            if self.spin_orbit == "soc":
                pseudo_family_string = (
                    f"PseudoDojo/{PSEUDODOJO_VERSION}/{functional}/FR/{accuracy}/upf"
                )
            else:
                pseudo_family_string = (
                    f"PseudoDojo/{PSEUDODOJO_VERSION}/{functional}/SR/{accuracy}/upf"
                )
        elif library == "SSSP":
            pseudo_family_string = f"SSSP/{SSSP_VERSION}/{functional}/{accuracy}"
        else:
            raise ValueError(
                f"Unknown pseudo family parameters: {library} | {accuracy}"
            )

        self._defaults["family"] = pseudo_family_string
        self.family = self._defaults["family"]

    def reset(self):
        with self.hold_trait_notifications():
            self.dictionary = self._get_default_dictionary()
            self.cutoffs = self._get_default_cutoffs()
            self.library_options = self._defaults["library_options"]
            self.library = self._defaults["library"]
            self.functional = self._defaults["functional"]
            self.functional_options = self._defaults["functional_options"]
            self.family = self._defaults["family"]
            self.family_help_message = self.PSEUDO_HELP_WO_SOC
            self.status_message = ""

    def _update_defaults(self, which):
        if self.input_structure is None:
            self._defaults.update(
                {
                    "dictionary": {},
                    "cutoffs": [[0.0], [0.0]],
                }
            )
        else:
            self.update_default_pseudos()
            self.update_default_cutoffs()
        self.update_family_parameters()
        self.update_family()

    def _get_pseudo_family_from_database(self):
        """Get the pseudo family from the database."""
        return (
            orm.QueryBuilder()
            .append(
                (
                    PseudoDojoFamily,
                    SsspFamily,
                    CutoffsPseudoPotentialFamily,
                ),
                filters={"label": self.family},
            )
            .one()[0]
        )

    def _get_default_dictionary(self):
        return deepcopy(self._defaults["dictionary"])

    def _get_default_cutoffs(self):
        return deepcopy(self._defaults["cutoffs"])
