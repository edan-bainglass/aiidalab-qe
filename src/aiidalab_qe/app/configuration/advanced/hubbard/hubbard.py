import ipywidgets as ipw

from aiida_quantumespresso.data.hubbard_structure import HubbardStructureData

from ..subsettings import AdvancedSubSettings
from .model import HubbardModel


class HubbardSettings(AdvancedSubSettings):
    identifier = "hubbard"

    def __init__(self, model: HubbardModel, **kwargs):
        super().__init__(model, **kwargs)

        self._model.observe(
            self._on_input_structure_change,
            "input_structure",
        )
        self._model.observe(
            self._on_hubbard_activation,
            "is_active",
        )
        self._model.observe(
            self._on_eigenvalues_definition,
            "has_eigenvalues",
        )

    def render(self):
        if self.rendered:
            return

        self.activate_hubbard_checkbox = ipw.Checkbox(
            description="",
            indent=False,
            layout=ipw.Layout(max_width="10%"),
        )
        ipw.link(
            (self._model, "is_active"),
            (self.activate_hubbard_checkbox, "value"),
        )
        ipw.dlink(
            (self._model, "override"),
            (self.activate_hubbard_checkbox, "disabled"),
            lambda override: not override,
        )

        self.eigenvalues_help = ipw.HTML(
            value="For transition metals and lanthanoids, the starting eigenvalues can be defined (Magnetic calculation).",
            layout=ipw.Layout(width="auto"),
        )
        self.define_eigenvalues_checkbox = ipw.Checkbox(
            description="Define eigenvalues",
            indent=False,
            layout=ipw.Layout(max_width="30%"),
        )
        ipw.link(
            (self._model, "has_eigenvalues"),
            (self.define_eigenvalues_checkbox, "value"),
        )
        ipw.dlink(
            (self._model, "override"),
            (self.define_eigenvalues_checkbox, "disabled"),
            lambda override: not override,
        )

        self.hubbard_widget = ipw.VBox()
        self.eigenvalues_widget = ipw.VBox()

        self.container = ipw.VBox()

        self.children = [
            ipw.HBox(
                children=[
                    ipw.HTML("<b>Hubbard (DFT+U)</b>"),
                    self.activate_hubbard_checkbox,
                ]
            ),
            self.container,
        ]

        self.rendered = True

        self.refresh()

    def _on_input_structure_change(self, _):
        self.refresh(specific="structure")

    def _on_hubbard_activation(self, _):
        self._toggle_hubbard_widget()

    def _on_eigenvalues_definition(self, _):
        self._toggle_eigenvalues_widget()

    def _update(self, specific=""):
        if self.updated:
            return
        self._show_loading()
        if not self._model.loaded_from_process:
            self._model.update(specific)
        self._build_hubbard_widget()
        if isinstance(self._model.input_structure, HubbardStructureData):
            self._model.set_parameters_from_hubbard_structure()
        self._toggle_hubbard_widget()
        self._toggle_eigenvalues_widget()
        self.updated = True

    def _show_loading(self):
        if self.rendered:
            self.hubbard_widget.children = [self.loading_message]

    def _build_hubbard_widget(self):
        if not self.rendered:
            return

        children = []

        if self._model.input_structure:
            children.append(ipw.HTML("Define U value [eV] "))

        for label in self._model.orbital_labels:
            float_widget = ipw.BoundedFloatText(
                description=label,
                min=0,
                max=20,
                step=0.1,
                layout={"width": "160px"},
            )
            link = ipw.link(
                (self._model, "parameters"),
                (float_widget, "value"),
                [
                    lambda parameters, label=label: parameters.get(label, 0.0),
                    lambda value, label=label: {
                        **self._model.parameters,
                        label: value,
                    },
                ],
            )
            self.links.append(link)
            children.append(float_widget)

        if self._model.needs_eigenvalues_widget:
            children.extend(
                [
                    self.eigenvalues_help,
                    self.define_eigenvalues_checkbox,
                ]
            )

        self.hubbard_widget.children = children

        if self._model.needs_eigenvalues_widget:
            self._build_eigenvalues_widget()
        else:
            self.eigenvalues_widget.children = []

    def _build_eigenvalues_widget(self):
        def update(index, spin, state, symbol, value):
            eigenvalues = [*self._model.eigenvalues]
            eigenvalues[index][spin][state] = [state + 1, spin, symbol, value]
            return eigenvalues

        children = []

        for kind_index, (kind, num_states) in enumerate(self._model.applicable_kinds):
            label_layout = ipw.Layout(justify_content="flex-start", width="50px")
            spin_up_row = ipw.HBox([ipw.Label("Up:", layout=label_layout)])
            spin_down_row = ipw.HBox([ipw.Label("Down:", layout=label_layout)])

            for state_index in range(num_states):
                eigenvalues_up = ipw.Dropdown(
                    description=f"{state_index+1}",
                    options=["-1", "0", "1"],
                    layout=ipw.Layout(width="65px"),
                    style={"description_width": "initial"},
                )
                link = ipw.link(
                    (self._model, "eigenvalues"),
                    (eigenvalues_up, "value"),
                    [
                        lambda eigenvalues,
                        kind_index=kind_index,
                        state_index=state_index: str(
                            eigenvalues[kind_index][0][state_index][-1]
                        ),
                        lambda value,
                        kind_index=kind_index,
                        state_index=state_index,
                        kind_name=kind.name: update(
                            kind_index,
                            0,
                            state_index,
                            kind_name,
                            int(value),
                        ),
                    ],
                )
                self.links.append(link)
                spin_up_row.children += (eigenvalues_up,)

                eigenvalues_down = ipw.Dropdown(
                    description=f"{state_index+1}",
                    options=["-1", "0", "1"],
                    layout=ipw.Layout(width="65px"),
                    style={"description_width": "initial"},
                )
                link = ipw.link(
                    (self._model, "eigenvalues"),
                    (eigenvalues_down, "value"),
                    [
                        lambda eigenvalues,
                        kind_index=kind_index,
                        state_index=state_index: str(
                            eigenvalues[kind_index][1][state_index][-1]
                        ),
                        lambda value,
                        kind_index=kind_index,
                        state_index=state_index,
                        kind_name=kind.name: update(
                            kind_index,
                            1,
                            state_index,
                            kind_name,
                            int(value),
                        ),
                    ],
                )
                self.links.append(link)
                spin_down_row.children += (eigenvalues_down,)

            children.append(
                ipw.HBox(
                    [
                        ipw.Label(kind.name, layout=label_layout),
                        ipw.VBox(
                            children=[
                                spin_up_row,
                                spin_down_row,
                            ]
                        ),
                    ]
                )
            )

        self.eigenvalues_widget.children = children

    def _toggle_hubbard_widget(self):
        if not self.rendered:
            return
        self.container.children = [self.hubbard_widget] if self._model.is_active else []

    def _toggle_eigenvalues_widget(self):
        if not self.rendered:
            return
        self.hubbard_widget.children = (
            [
                *self.hubbard_widget.children,
                self.eigenvalues_widget,
            ]
            if self._model.has_eigenvalues
            else [*self.hubbard_widget.children][:-1]
        )
