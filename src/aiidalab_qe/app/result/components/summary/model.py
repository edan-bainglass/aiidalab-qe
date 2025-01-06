from __future__ import annotations

import json
from pathlib import Path

import traitlets as tl
from importlib_resources import files
from jinja2 import Environment

from aiida import orm
from aiida.cmdline.utils.common import get_workchain_report
from aiida_quantumespresso.workflows.pw.bands import PwBandsWorkChain
from aiidalab_qe.app.parameters import DEFAULT_PARAMETERS
from aiidalab_qe.app.result.components import ResultsComponentModel
from aiidalab_qe.app.static import styles, templates
from aiidalab_qe.common.time import format_time, relative_time

DEFAULT: dict = DEFAULT_PARAMETERS  # type: ignore


FUNCTIONAL_LINK_MAP = {
    "PBE": "https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.77.3865",
    "PBEsol": "https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.100.136406",
}

PSEUDO_LINK_MAP = {
    "SSSP": "https://www.materialscloud.org/discover/sssp/table/efficiency",
    "PseudoDojo": "http://www.pseudo-dojo.org/",
}

FUNCTIONAL_REPORT_MAP = {
    "LDA": "local density approximation (LDA)",
    "PBE": "generalized gradient approximation of Perdew-Burke-Ernzerhof (PBE)",
    "PBEsol": "the revised generalized gradient approximation of Perdew-Burke-Ernzerhof (PBE) for solids",
}

# Periodicity
PERIODICITY_MAPPING = {
    (True, True, True): "xyz",
    (True, True, False): "xy",
    (True, False, False): "x",
    (False, False, False): "molecule",
}

VDW_CORRECTION_VERSION = {
    3: "Grimme-D3",
    4: "Grimme-D3BJ",
    5: "Grimme-D3M",
    6: "Grimme-D3MBJ",
    "ts-vdw": "Tkatchenko-Scheffler",
    "none": "None",
}


class WorkChainSummaryModel(ResultsComponentModel):
    identifier = "workflow summary"

    failed_calculation_report = tl.Unicode("")

    has_failure_report = False

    @property
    def include(self):
        return True

    def generate_report_html(self):
        """Read from the builder parameters and generate a html for reporting
        the inputs for the `QeAppWorkChain`.
        """
        env = Environment()
        template = files(templates).joinpath("workflow_summary.jinja").read_text()
        parameters = self._generate_report_parameters()
        report = {key: value for key, value in parameters.items() if value is not None}
        schema = json.load(Path(__file__).parent.joinpath("schema.json").open())
        return env.from_string(template).render(
            report=report,
            schema=schema,
            format=DEFAULT["summary_format"],
        )

    def generate_report_text(self, report_dict):
        """Generate a text for reporting the inputs for the `QeAppWorkChain`

        :param report_dict: dictionary generated by the `generate_report_dict` function.
        """
        report_string = (
            "All calculations are performed within the density-functional "
            "theory formalism as implemented in the Quantum ESPRESSO code. "
            "The pseudopotential for each element is extracted from the "
            f'{report_dict["Pseudopotential library"][0]} '
            "library. The wave functions "
            "of the valence electrons are expanded in a plane wave basis set, using an "
            "energy cutoff equal to "
            f'{round(report_dict["Plane wave energy cutoff (wave functions)"][0])} Ry '
            "for the wave functions and "
            f'{round(report_dict["Plane wave energy cutoff (charge density)"][0])} Ry '
            "for the charge density and potential. "
            "The exchange-correlation energy is "
            "calculated using the "
            f'{FUNCTIONAL_REPORT_MAP[report_dict["Functional"][0]]}. '
            "A Monkhorst-Pack mesh is used for sampling the Brillouin zone, where the "
            "distance between the k-points is set to "
        )
        kpoints_distances = []
        kpoints_calculations = []

        for calc in ("SCF", "NSCF", "Bands"):
            if f"K-point mesh distance ({calc})" in report_dict:
                kpoints_distances.append(
                    str(report_dict[f"K-point mesh distance ({calc})"][0])
                )
                kpoints_calculations.append(calc)

        report_string += ", ".join(kpoints_distances)
        report_string += " for the "
        report_string += ", ".join(kpoints_calculations)
        report_string += " calculation"
        if len(kpoints_distances) > 1:
            report_string += "s, respectively"
        report_string += "."

        return report_string

    def generate_failure_report(self):
        """Generate a html for reporting the failure of the `QeAppWorkChain`."""
        process_node = self.fetch_process_node()
        if not (process_node and process_node.exit_status):
            return
        final_calcjob = self._get_final_calcjob(process_node)
        env = Environment()
        template = files(templates).joinpath("workflow_failure.jinja").read_text()
        style = files(styles).joinpath("style.css").read_text()
        self.failed_calculation_report = env.from_string(template).render(
            style=style,
            process_report=get_workchain_report(process_node, "REPORT"),
            calcjob_exit_message=final_calcjob.exit_message,
        )
        self.has_failure_report = True

    def _generate_report_parameters(self):
        """Generate the report parameters from the ui parameters and workchain's input.

        Parameters extracted from ui parameters, directly from the widgets,
        such as the ``pseudo_family`` and ``relax_type``.

        Parameters extracted from workchain's inputs, such as the ``energy_cutoff_wfc``
        and ``energy_cutoff_rho``.

        Return a dictionary of the parameters.
        """
        from aiida.orm.utils.serialize import deserialize_unsafe

        qeapp_wc = self.fetch_process_node()

        ui_parameters = qeapp_wc.base.extras.get("ui_parameters", {})
        if isinstance(ui_parameters, str):
            ui_parameters = deserialize_unsafe(ui_parameters)
        # Construct the report parameters needed for the report
        # drop support for old ui parameters
        if "workchain" not in ui_parameters:
            return {}

        inputs = qeapp_wc.inputs
        structure: orm.StructureData = inputs.structure
        basic = ui_parameters["workchain"]
        advanced = ui_parameters["advanced"]
        ctime = qeapp_wc.ctime
        mtime = qeapp_wc.mtime

        report = {
            "workflow_properties": {
                "pk": qeapp_wc.pk,
                "uuid": str(qeapp_wc.uuid),
                "label": qeapp_wc.label,
                "description": qeapp_wc.description,
                "creation_time": f"{format_time(ctime)} ({relative_time(ctime)})",
                "modification_time": f"{format_time(mtime)} ({relative_time(mtime)})",
            },
        }

        report |= {
            "initial_structure_properties": {
                "structure_pk": structure.pk,
                "structure_uuid": structure.uuid,
                "formula": structure.get_formula(),
                "num_atoms": len(structure.sites),
            }
        }

        symmetry_group_info = self._get_symmetry_group_info(structure)
        report["initial_structure_properties"] |= symmetry_group_info

        report |= {
            "basic_settings": {
                "relaxed": "off"
                if basic["relax_type"] == "none"
                else basic["relax_type"],
                "protocol": basic["protocol"],
                "spin_type": "off" if basic["spin_type"] == "none" else "on",
                "electronic_type": basic["electronic_type"],
                "periodicity": PERIODICITY_MAPPING.get(structure.pbc, "xyz"),
            },
            "advanced_settings": {},
        }

        pseudo_family = advanced.get("pseudo_family")
        pseudo_family_info = pseudo_family.split("/")
        pseudo_library = pseudo_family_info[0]
        pseudo_version = pseudo_family_info[1]
        functional = pseudo_family_info[2]
        if pseudo_library == "SSSP":
            pseudo_protocol = pseudo_family_info[3]
        elif pseudo_library == "PseudoDojo":
            pseudo_protocol = pseudo_family_info[4]
        report["advanced_settings"] |= {
            "functional": {
                "url": FUNCTIONAL_LINK_MAP[functional],
                "value": functional,
            },
            "pseudo_library": {
                "url": PSEUDO_LINK_MAP[pseudo_library],
                "value": f"{pseudo_library} {pseudo_protocol} v{pseudo_version}",
            },
        }

        # Extract the pw calculation parameters from the workchain's inputs
        # energy_cutoff is same for all pw calculations when pseudopotentials are fixed
        # as well as the smearing settings (smearing and degauss) and scf kpoints distance
        # read from the first pw calculation of relax workflow.
        # It is safe then to extract these parameters from the first pw calculation, since the
        # builder is anyway set with subworkchain inputs even it is not run which controlled by
        # the properties inputs.
        relax = inputs.relax.base
        pw_parameters = relax.pw.parameters.get_dict()
        system = pw_parameters["SYSTEM"]
        occupation = system["occupations"]
        report["advanced_settings"] |= {
            "energy_cutoff_wfc": f"{system['ecutwfc']} Ry",
            "energy_cutoff_rho": f"{system['ecutrho']} Ry",
            "occupation_type": occupation,
        }
        if occupation == "smearing":
            report["advanced_settings"] |= {
                "smearing": system["smearing"],
                "degauss": f"{system['degauss']} Ry",
            }
        inv_ang = "Å<sup>-1</sup>"
        kpoints = relax.kpoints_distance.base.attributes.get("value")
        report["advanced_settings"]["scf_kpoints_distance"] = f"{kpoints} {inv_ang}"
        if "bands" in inputs:
            key = "bands_kpoints_distance"
            kpoints = PwBandsWorkChain.get_protocol_inputs(basic["protocol"])[key]
            report["advanced_settings"][key] = f"{kpoints} {inv_ang}"
        if "pdos" in inputs:
            key = "nscf_kpoints_distance"
            kpoints = inputs.pdos.nscf.kpoints_distance.base.attributes.get("value")
            report["advanced_settings"][key] = f"{kpoints} {inv_ang}"

        vdw_corr = VDW_CORRECTION_VERSION.get(
            system.get("dftd3_version"),
            system.get("vdw_corr", "none"),
        )
        report["advanced_settings"] |= {
            "tot_charge": system.get("tot_charge", 0.0),
            "vdw_corr": "off" if vdw_corr == "none" else vdw_corr,
        }

        if basic["spin_type"] == "collinear":
            if tot_magnetization := system.get("tot_magnetization", False):
                report["advanced_settings"]["tot_magnetization"] = tot_magnetization
            else:
                report["advanced_settings"]["initial_magnetic_moments"] = advanced[
                    "initial_magnetic_moments"
                ]

        if hubbard_dict := ui_parameters["advanced"].pop("hubbard_parameters", None):
            hubbard_parameters = hubbard_dict["hubbard_u"]
            report["advanced_settings"]["hubbard_u"] = hubbard_parameters

        spin_orbit = system.get("lspinorb", False)
        report["advanced_settings"]["spin_orbit"] = "on" if spin_orbit else "off"

        return report

    def _get_symmetry_group_info(self, structure: orm.StructureData) -> dict:
        # HACK the use of the clone for non-molecular systems is due to a rigid
        # condition in AiiDA < 2.6 that only considers 3D systems as pymatgen
        # `Structure` objects (`Molecule` otherwise). Once AiiDAlab is updated with
        # AiiDA 2.6 throughout, we can fall back to using `StructureData.get_pymatgen`
        # (which this method mimics) to obtain the correct pymatgen object
        # (`Molecule` for 0D systems | `Structure` otherwise)
        if any(structure.pbc):
            return self._get_pymatgen_structure(structure)
        return self._get_pymatgen_molecule(structure)

    @staticmethod
    def _get_pymatgen_structure(structure: orm.StructureData) -> dict:
        from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

        clone = structure.clone()
        clone.pbc = (True, True, True)
        analyzer = SpacegroupAnalyzer(structure=clone.get_pymatgen_structure())
        symbol = analyzer.get_space_group_symbol()
        number = analyzer.get_space_group_number()
        return {
            "space_group": f"{symbol} ({number})",
            "cell_lengths": "{:.3f} {:.3f} {:.3f}".format(*structure.cell_lengths),
            "cell_angles": "{:.0f} {:.0f} {:.0f}".format(*structure.cell_angles),
        }

    @staticmethod
    def _get_pymatgen_molecule(structure: orm.StructureData) -> dict:
        from pymatgen.symmetry.analyzer import PointGroupAnalyzer

        analyzer = PointGroupAnalyzer(mol=structure.get_pymatgen_molecule())
        return {"point_group": analyzer.get_pointgroup()}

    @staticmethod
    def _get_final_calcjob(node: orm.WorkChainNode) -> orm.CalcJobNode | None:
        """Get the final calculation job node called by a workchain node.

        Parameters
        ----------
        `node`: `orm.WorkChainNode`
            The work chain node to get the final calculation job node from.

        Returns
        -------
        `orm.CalcJobNode` | `None`
            The final calculation job node called by the workchain node if available.
        """
        try:
            final_calcjob = [
                process
                for process in node.called_descendants
                if isinstance(process, orm.CalcJobNode) and process.is_finished
            ][-1]
        except IndexError:
            final_calcjob = None
        return final_calcjob
