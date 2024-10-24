import ipywidgets as ipw

from .model import AdvancedModel
from .subsettings import AdvancedSubSettings


class SmearingSettings(AdvancedSubSettings):
    identifier = "smearing"

    def __init__(self, model: AdvancedModel, **kwargs):
        super().__init__(model, **kwargs)

        self._model.observe(
            self._on_protocol_change,
            "protocol",
        )

    def render(self):
        if self.rendered:
            return

        self.smearing = ipw.Dropdown(
            options=["cold", "gaussian", "fermi-dirac", "methfessel-paxton"],
            description="Smearing type:",
            disabled=False,
            style={"description_width": "initial"},
        )
        ipw.link(
            (self._model.smearing, "type"),
            (self.smearing, "value"),
        )
        ipw.dlink(
            (self._model, "override"),
            (self.smearing, "disabled"),
            lambda override: not override,
        )

        self.degauss = ipw.FloatText(
            step=0.005,
            description="Smearing width (Ry):",
            disabled=False,
            style={"description_width": "initial"},
        )
        ipw.link(
            (self._model.smearing, "degauss"),
            (self.degauss, "value"),
        )
        ipw.dlink(
            (self._model, "override"),
            (self.degauss, "disabled"),
            lambda override: not override,
        )

        self.children = [
            ipw.HTML("""
                <p>
                    The smearing type and width is set by the chosen <b>protocol</b>.
                    Tick the box to override the default, not advised unless you've
                    mastered <b>smearing effects</b> (click
                    <a href="http://theossrv1.epfl.ch/Main/ElectronicTemperature"
                    target="_blank">here</a> for a discussion).
                </p>
            """),
            ipw.HBox(
                children=[
                    self.smearing,
                    self.degauss,
                ]
            ),
        ]

        self.rendered = True

        self._refresh()

    def _on_protocol_change(self, _):
        self._refresh()

    def _update(self):
        if self.updated:
            return
        self._model.smearing.update()
        self.updated = True
