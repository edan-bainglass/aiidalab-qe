"""Widgets for the upload and selection of structure data.

Authors: AiiDAlab team
"""

import pathlib

import ipywidgets as ipw

from aiidalab_qe.app.structure.model import StructureStepModel
from aiidalab_qe.app.utils import get_entry_items
from aiidalab_qe.common import (
    AddingTagsEditor,
    LazyLoadedOptimade,
    LazyLoadedStructureBrowser,
)
from aiidalab_qe.common.infobox import InAppGuide
from aiidalab_widgets_base import (
    BasicCellEditor,
    BasicStructureEditor,
    StructureExamplesWidget,
    StructureManagerWidget,
    StructureUploadWidget,
    WizardAppWidgetStep,
)

# The Examples list of (name, file) tuple curretly passed to
# StructureExamplesWidget.
file_path = pathlib.Path(__file__).parent
Examples = [
    ("Bulk silicon (primitive cell)", file_path / "examples" / "Si.cif"),
    ("Silicon oxide (alpha quartz)", file_path / "examples" / "SiO2.cif"),
    ("Diamond (primitive cell)", file_path / "examples" / "Diamond.cif"),
    ("Gallium arsenide (primitive cell)", file_path / "examples" / "GaAs.cif"),
    ("Gold (conventional cell)", file_path / "examples" / "Au.cif"),
    ("Cobalt (primitive cell)", file_path / "examples" / "Co.cif"),
    ("Lithium carbonate", file_path / "examples" / "Li2CO3.cif"),
    ("Phenylacetylene molecule", file_path / "examples" / "Phenylacetylene.xyz"),
    ("ETFA molecule", file_path / "examples" / "ETFA.xyz"),
    ("LiCoO2", file_path / "examples" / "LiCoO2.cif"),
]


class StructureSelectionStep(ipw.VBox, WizardAppWidgetStep):
    """Integrated widget for the selection and edition of structure.
    The widget includes a structure manager that allows to select a structure
    from different sources. It also includes the structure editor. Both the
    structure importers and the structure editors can be extended by plugins.
    """

    def __init__(self, model: StructureStepModel, **kwargs):
        from aiidalab_qe.common.widgets import LoadingWidget

        super().__init__(
            children=[LoadingWidget("Loading structure selection step")],
            **kwargs,
        )

        self._model = model
        self._model.observe(
            self._on_confirmation_change,
            "confirmed",
        )
        self._model.observe(
            self._on_input_structure_change,
            "input_structure",
        )

        self.rendered = False

    def render(self):
        """docstring"""
        if self.rendered:
            return

        importers = [
            StructureUploadWidget(title="Upload file"),
            LazyLoadedOptimade(title="OPTIMADE"),
            LazyLoadedStructureBrowser(title="AiiDA database"),
            StructureExamplesWidget(title="From Examples", examples=Examples),
        ]

        plugin_importers = get_entry_items("aiidalab_qe.properties", "importer")
        importers.extend([importer() for importer in plugin_importers.values()])

        editors = [
            BasicCellEditor(title="Edit cell"),
            BasicStructureEditor(title="Edit structure"),
            AddingTagsEditor(title="Edit StructureData"),
        ]

        plugin_editors = get_entry_items("aiidalab_qe.properties", "editor")
        editors.extend([editor() for editor in plugin_editors.values()])

        self.manager = StructureManagerWidget(
            importers=importers,
            editors=editors,
            node_class="StructureData",
            storable=False,
            configuration_tabs=[
                "Cell",
                "Selection",
                "Appearance",
                "Download",
            ],
        )

        if self._model.confirmed:  # loaded from a process
            # NOTE important to do this prior to setting up the links
            # to avoid an override of the structure in the model,
            # which in turn would trigger a reset of the model
            self.manager.input_structure = self._model.input_structure

        ipw.dlink(
            (self.manager, "structure_node"),
            (self._model, "input_structure"),
        )
        ipw.link(
            (self._model, "manager_output"),
            (self.manager.output, "value"),
        )

        self.structure_name_text = ipw.Text(
            placeholder="[No structure selected]",
            description="Selected:",
            disabled=True,
            layout=ipw.Layout(width="auto", flex="1 1 auto"),
        )
        ipw.dlink(
            (self._model, "structure_name"),
            (self.structure_name_text, "value"),
        )

        self.confirm_button = ipw.Button(
            description="Confirm",
            tooltip="Confirm the currently selected structure and go to the next step.",
            button_style="success",
            icon="check-circle",
            layout=ipw.Layout(width="auto"),
        )
        ipw.dlink(
            (self, "state"),
            (self.confirm_button, "disabled"),
            lambda state: state != self.State.CONFIGURED,
        )
        self.confirm_button.on_click(self.confirm)

        self.message_area = ipw.HTML()
        ipw.dlink(
            (self._model, "message_area"),
            (self.message_area, "value"),
        )

        self.children = [
            InAppGuide(
                children=[
                    ipw.HTML("""
                    <div>
                        In this step, you can select a structure as follows:
                        <ul>
                            <li>
                                <b>Upload file</b>:
                                upload a structure file from your computer.
                            </li>
                            <li>
                                <b>OPTIMADE</b>:
                                search for structures in the OPTIMADE database.
                            </li>
                            <li>
                                <b>AiiDA database</b>:
                                search for structures in your AiiDA database.
                            </li>
                            <li>
                                <b>From Examples</b>:
                                select a structure from a list of example structures.
                            </li>
                        </ul>
                        Once selected, you may inspect the structure. You can also edit
                        the structure using the available structure editors. When done,
                        you can choose to modify the structure label and/or provide a
                        description. These will be attached to the input structure node
                        in your AiiDA database. When you are ready, click "Confirm" to
                        proceed to the next step.
                        <br>
                        <div class="alert alert-success">
                            <h4>Tasks</h4>
                            <ol>
                                <li>Click on the <b>From examples</b> tab</li>
                                <li>Select <b>Gold</b> from the dropdown list</li>
                                <li>Click the <b>Confirm</b> button to proceed.</li>
                            </ol>
                        </div>
                        <div class="alert alert-warning">
                            <b>Warning:</b> If the confirmed structure is not yet stored
                            in the AiiDA database, it will be stored automatically when
                            you proceed to the next step.
                        </div>
                        <div class="alert alert-warning">
                            <b>Warning:</b> Changes after confirmation will unconfirm
                            this step and reset the following steps.
                        </div>
                    </div>
                """),
                ],
            ),
            ipw.HTML("""
                <p>
                    Select a structure from one of the following sources and then
                    click "Confirm" to go to the next step.
                </p>
            """),
            self.manager,
            self.structure_name_text,
            self.message_area,
            self.confirm_button,
        ]

        self.rendered = True

    def is_saved(self):
        return self._model.confirmed

    def confirm(self, _=None):
        self.manager.store_structure()
        self._model.message_area = ""
        self._model.confirm()

    def can_reset(self):
        return self._model.confirmed

    def reset(self):
        self._model.reset()

    def _on_input_structure_change(self, _):
        self._model.update_widget_text()
        self._update_state()

    def _on_confirmation_change(self, _):
        self._update_state()

    def _update_state(self):
        if self._model.confirmed:
            self.state = self.State.SUCCESS
        elif self._model.input_structure is None:
            self.state = self.State.READY
        else:
            self.state = self.State.CONFIGURED
