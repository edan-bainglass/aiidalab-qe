"""The main widget that shows the application in the Jupyter notebook.

Authors: AiiDAlab team
"""

import ipywidgets as ipw
import traitlets as tl
from IPython.display import Javascript, display

from aiida.orm import load_node
from aiida.orm.utils.serialize import deserialize_unsafe
from aiidalab_qe.app.configuration import ConfigureQeAppWorkChainStep
from aiidalab_qe.app.configuration.model import ConfigurationModel
from aiidalab_qe.app.result import ViewQeAppWorkChainStatusAndResultsStep
from aiidalab_qe.app.result.model import ResultsModel
from aiidalab_qe.app.structure import StructureSelectionStep
from aiidalab_qe.app.structure.model import StructureModel
from aiidalab_qe.app.submission import SubmitQeAppWorkChainStep
from aiidalab_qe.app.submission.model import SubmissionModel
from aiidalab_qe.common.widgets import LoadingWidget
from aiidalab_widgets_base import WizardAppWidget, WizardAppWidgetStep


class App(ipw.VBox):
    """The main widget that combines all the application steps together."""

    # The PK or UUID of the work chain node.
    process = tl.Union([tl.Unicode(), tl.Int()], allow_none=True)

    def __init__(self, qe_auto_setup=True):
        # Initialize the models
        self.structure_model = StructureModel()
        self.configure_model = ConfigurationModel()
        self.submit_model = SubmissionModel()
        self.results_model = ResultsModel()

        # Create the application steps
        self.structure_step = StructureSelectionStep(
            model=self.structure_model,
            auto_advance=True,
        )
        self.configure_step = ConfigureQeAppWorkChainStep(
            model=self.configure_model,
            auto_advance=True,
        )
        self.submit_step = SubmitQeAppWorkChainStep(
            model=self.submit_model,
            auto_advance=True,
            qe_auto_setup=qe_auto_setup,
        )
        self.results_step = ViewQeAppWorkChainStatusAndResultsStep(
            model=self.results_model,
        )

        # Wizard step observations
        ipw.dlink(
            (self.structure_step, "state"),
            (self.configure_step, "previous_step_state"),
        )
        self.structure_model.observe(
            self._on_structure_confirmation_change,
            "confirmed",
        )
        ipw.dlink(
            (self.configure_step, "state"),
            (self.submit_step, "previous_step_state"),
        )
        self.configure_model.observe(
            self._on_configuration_confirmation_change,
            "confirmed",
        )
        ipw.dlink(
            (self.submit_model, "process"),
            (self.results_model, "process"),
            transform=lambda node: node.uuid if node is not None else None,
        )

        # Add the application steps to the application
        self._wizard_app_widget = WizardAppWidget(
            steps=[
                ("Select structure", self.structure_step),
                ("Configure workflow", self.configure_step),
                ("Choose computational resources", self.submit_step),
                ("Status & Results", self.results_step),
            ]
        )
        self._wizard_app_widget.observe(
            self._on_step_change,
            "selected_index",
        )

        # Hide the header
        self._wizard_app_widget.children[0].layout.display = "none"  # type: ignore

        # Add a button to start a new calculation
        self.new_workchain_button = ipw.Button(
            layout=ipw.Layout(width="auto"),
            button_style="success",
            icon="plus-circle",
            description="Start New Calculation",
            tooltip="Open a new page to start a separate calculation",
        )

        self.new_workchain_button.on_click(self._on_new_workchain_button_click)

        self._process_loading_message = LoadingWidget(
            message="Loading process",
            layout=ipw.Layout(display="none"),
        )

        super().__init__(
            children=[
                self.new_workchain_button,
                self._process_loading_message,
                self._wizard_app_widget,
            ]
        )

        self._wizard_app_widget.selected_index = None

        self._update_blockers()

    @property
    def steps(self):
        return self._wizard_app_widget.steps

    @tl.observe("process")
    def _on_process_change(self, change):
        self._update_from_process(change["new"])

    def _on_new_workchain_button_click(self, _):
        display(Javascript("window.open('./qe.ipynb', '_blank')"))

    def _on_step_change(self, change):
        if (step_index := change["new"]) is not None:
            self._render_step(step_index)

    def _on_structure_confirmation_change(self, _):
        if self.structure_model.confirmed:
            self.configure_model.input_structure = self.structure_model.input_structure
        else:
            self.configure_model.input_structure = None
        self._update_blockers()

    def _on_configuration_confirmation_change(self, _):
        if self.configure_model.confirmed:
            self.submit_model.input_structure = self.structure_model.input_structure
            self.submit_model.input_parameters = self.configure_model.get_model_state()
        else:
            self.submit_model.input_structure = None
            self.submit_model.input_parameters = {}
        self._update_blockers()

    def _render_step(self, step_index):
        step = self.steps[step_index][1]
        step.render()

    def _update_blockers(self):
        self.submit_model.external_submission_blockers = [
            f"Unsaved changes in the <b>{title}</b> step. Please confirm the changes before submitting."
            for title, step in self.steps[:2]
            if not step.is_saved()
        ]

    def _update_from_process(self, pk):
        if pk is None:
            self._wizard_app_widget.reset()
            self._wizard_app_widget.selected_index = 0
        else:
            self._show_process_loading_message()
            process = load_node(pk)
            self._wizard_app_widget.selected_index = 3
            self.structure_model.input_structure = process.inputs.structure
            self.structure_model.confirm()
            parameters = process.base.extras.get("ui_parameters", {})
            if parameters and isinstance(parameters, str):
                parameters = deserialize_unsafe(parameters)
            self.configure_model.set_model_state(parameters)
            self.configure_model.confirm()
            self.submit_model.process = process
            self.submit_model.set_model_state(parameters)
            self.submit_step.state = WizardAppWidgetStep.State.SUCCESS
            self._hide_process_loading_message()

    def _show_process_loading_message(self):
        self._process_loading_message.layout.display = "flex"

    def _hide_process_loading_message(self):
        self._process_loading_message.layout.display = "none"
