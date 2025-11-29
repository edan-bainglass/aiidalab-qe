from __future__ import annotations

import traitlets as tl

from aiidalab_qe.common.panel import ResultsModel


class GeneralResultsModel(ResultsModel):
    title = "General"
    identifier = "general"

    info = tl.Unicode()

    _this_process_label = "PwRelaxWorkChain"

    @property
    def include(self):
        return True

    def update(self):
        super().update()

        if not (outputs := getattr(self._get_child_outputs(), "output_parameters", {})):
            self.info = ""
            return

        info = f"""
            <h4><b>Wall time:</b> {outputs.get("wall_time", "N/A")}</h4>
        """

        info += f"""
            <h2>General</h2>
            <b>Total energy (eV):</b> {outputs.get("energy", "N/A")}<br>
            <b>Total force (eV/Å):</b> {outputs.get("total_force", "N/A")}<br>
            <b>Volume (Å³):</b> {outputs.get("volume", "N/A")}<br>
            <b>Fermi energy (eV):</b> {outputs.get("fermi_energy", "N/A")}<br>
        """

        convergence_info = outputs.get("convergence_info", {})
        scf = convergence_info.get("scf_conv", False)
        info += f"""
            <h2>Convergence</h2>
            <h4><b>SCF</b></h4>
            <b>Converged:</b> {scf.get("convergence_achieved", "N/A")}<br>
            <b>Error:</b> {scf.get("scf_error", "N/A")}<br>
            <b>Steps:</b> {scf.get("n_scf_steps", "N/A")}<br>
        """
        if opt := convergence_info.get("opt_conv", None):
            info += f"""
                <h4><b>Geometry optimization</b></h4>
                <b>Converged:</b> {opt.get("convergence_achieved", "N/A")}<br>
                <b>Gradient norm:</b> {opt.get("grad_norm", "N/A")}<br>
                <b>Steps:</b> {opt.get("n_opt_steps", "N/A")}<br>
            """

        self.info = f"<div style='line-height: 1.5;'>{info}</div>"
