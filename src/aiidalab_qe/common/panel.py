"""Class to .

Authors:

    AiiDAlab Team
"""

from __future__ import annotations

import os
import typing as t

import ipywidgets as ipw
import traitlets as tl

from aiida import orm
from aiida.common.extendeddicts import AttributeDict
from aiidalab_qe.common.mixins import Confirmable, HasProcess
from aiidalab_qe.common.mvc import Model

DEFAULT_PARAMETERS = {}


class Panel(ipw.VBox):
    """Base class for all the panels.

    The base class has a method to return the value of all the widgets in
    the panel as a dictionary. The dictionary is used to construct the
    input file for the calculation. The class also has a method to load a dictionary to set the value of the widgets in the panel.

    title: the title to be shown in the GUI
    identifier: which plugin this panel belong to.

    """

    title = "Panel"

    # TODO remove `identifier` (and `parent`) from signature
    # TODO add `model` parameter
    # TODO add `identifier` property to route to model.identifier
    def __init__(self, parent=None, identifier=None, **kwargs):
        """Initialize the panel.

        :param kwargs: keyword arguments to pass to the ipw.VBox constructor.
        """
        self.parent = parent
        self.identifier = identifier or getattr(self, "identifier", "plugin")
        super().__init__(
            children=kwargs.pop("children", []),
            **kwargs,
        )


class SettingsOutline(ipw.HBox):
    title = "Outline"
    description = ""

    def __init__(self, **kwargs):
        self.include = ipw.Checkbox(
            description=self.title,
            indent=False,
            style={"description_width": "initial"},
        )

        super().__init__(
            children=[
                self.include,
                ipw.HTML(f"""
                    <div style="line-height: 140%; padding-top: 0px; padding-bottom: 5px">
                        {self.description}
                    </div>
                """),
            ],
            **kwargs,
        )


class SettingsModel(Model, Confirmable):
    title = "Model"
    dependencies: list[str] = []

    include = tl.Bool(False)
    loaded_from_process = tl.Bool(False)

    _defaults = {}

    def update(self, specific=""):
        """Updates the model.

        Parameters
        ----------
        `specific` : `str`, optional
            If provided, specifies the level of update.
        """
        pass

    def get_model_state(self) -> dict:
        """Retrieves the model current state as a dictionary."""
        raise NotImplementedError()

    def set_model_state(self, parameters: dict):
        """Distributes the parameters of a loaded calculation to the model."""
        raise NotImplementedError()

    def reset(self):
        """Resets the model to present defaults."""
        pass


SM = t.TypeVar("SM", bound=SettingsModel)


class SettingsPanel(Panel, t.Generic[SM]):
    title = "Settings"
    description = ""

    def __init__(self, model: SM, **kwargs):
        from aiidalab_qe.common.widgets import LoadingWidget

        self.loading_message = LoadingWidget(f"Loading {self.identifier} settings")

        super().__init__(
            children=[self.loading_message],
            **kwargs,
        )

        self._model = model

        self.rendered = False
        self.updated = False

        self.links = []

    def render(self):
        raise NotImplementedError()

    def refresh(self, specific=""):
        """Refreshes the settings panel.

        Unlinks the panel's widgets. If the panel's model is included in the
        calculation, also updates the model's defaults. Resets the model to
        these defaults if there is no input structure.

        Parameters
        ----------
        `specific` : `str`, optional
            If provided, specifies the level of refresh.
        """
        self.updated = False
        self._unsubscribe()
        if self._model.include:
            self.update(specific)
        if "PYTEST_CURRENT_TEST" in os.environ:
            # Skip resetting to avoid having to inject a structure when testing
            return
        if hasattr(self._model, "input_structure") and not self._model.input_structure:
            self._reset()

    def update(self, specific=""):
        """Updates the model if not yet updated.

        Parameters
        ----------
        `specific` : `str`, optional
            If provided, specifies the level of update.
        """
        if self.updated:
            return
        if not self._model.loaded_from_process:
            self._model.update(specific)
        self.updated = True

    def _unsubscribe(self):
        """Unlinks any linked widgets."""
        for link in self.links:
            link.unlink()
        self.links.clear()

    def _reset(self):
        """Resets the model to present defaults."""
        self.updated = False
        self._model.reset()


class ResultsModel(Model, HasProcess):
    title = "Model"
    identifier = "model"

    process_state_notification = tl.Unicode("")

    _this_process_label = ""
    _this_process_uuid = None

    CSS_MAP = {
        "finished": "success",
        "excepted": "danger",
        "killed": "danger",
        "queued": "warning",
        "waiting": "info",
        "running": "info",
        "created": "info",
    }

    @property
    def include(self):
        return self.identifier in self.properties

    @property
    def has_results(self):
        node = self._fetch_child_process_node()
        return node and node.is_finished_ok

    @property
    def process_state(self):
        node = self._fetch_child_process_node()
        return node.process_state.value if node and node.process_state else "queued"

    def update_process_state_notification(self):
        state = self.process_state
        self.process_state_notification = f"""
            <div class="alert alert-{self.CSS_MAP.get(state, "info")}">
                <b>Status:</b> {state.upper()}
            </div>
        """

    def _get_child_outputs(self, child="this"):
        if not (node := self._fetch_child_process_node(child)):
            outputs = super().outputs
            child = child if child != "this" else self.identifier
            return getattr(outputs, child) if child in outputs else AttributeDict({})
        return AttributeDict({key: getattr(node.outputs, key) for key in node.outputs})

    def _fetch_child_process_node(self, child="this") -> orm.ProcessNode | None:
        if not self.process_uuid:
            return
        uuid = getattr(self, f"_{child}_process_uuid")
        label = getattr(self, f"_{child}_process_label")
        if not uuid:
            uuid = (
                orm.QueryBuilder()
                .append(
                    orm.WorkChainNode,
                    filters={"uuid": self.process_uuid},
                    tag="root_process",
                )
                .append(
                    orm.WorkChainNode,
                    filters={"attributes.process_label": label},
                    project="uuid",
                    with_incoming="root_process",
                )
                .first(flat=True)
            )
        return orm.load_node(uuid) if uuid else None  # type: ignore


RM = t.TypeVar("RM", bound=ResultsModel)


class ResultsPanel(Panel, t.Generic[RM]):
    """Base class for all the result panels.

    The base class has a method to load the result of the calculation.
    And a show method to display it in the panel.
    It has a update method to update the result in the panel.
    """

    title = "Results"
    identifier = "results"

    # To specify which plugins (outputs) are needed
    # for this result panel.
    workchain_labels = []

    def __init__(self, model: RM, **kwargs):
        from aiidalab_qe.common.widgets import LoadingWidget

        self.loading_message = LoadingWidget(f"Loading {self.title.lower()} results")

        self._model = model
        if self.identifier != "summary":
            self._model.observe(
                self._on_monitor_counter_change,
                "monitor_counter",
            )

        self.rendered = False

        self.links = []

        self.process_state_notification = ipw.HTML()
        ipw.dlink(
            (self._model, "process_state_notification"),
            (self.process_state_notification, "value"),
        )

        self.load_results_button = ipw.Button(
            description="Load results",
            button_style="warning",
            tooltip="Load the results",
            icon="refresh",
        )
        ipw.dlink(
            (self._model, "monitor_counter"),
            (self.load_results_button, "disabled"),
            lambda _: not self._model.has_results,
        )
        self.load_results_button.on_click(self._on_load_results_click)

        super().__init__(
            children=[
                self.process_state_notification,
                ipw.HBox(
                    children=[
                        self.load_results_button,
                        ipw.HTML("""
                        <div style="margin-left: 10px">
                            <b>Note:</b> Load time may vary depending on the size of the calculation
                        </div>
                    """),
                    ]
                ),
            ],
            **kwargs,
        )

    def render(self):
        raise NotImplementedError()

    def _on_load_results_click(self, _):
        self.children = [self.loading_message]
        self.render()

    def _on_monitor_counter_change(self, _):
        self._model.update_process_state_notification()
