import ipywidgets as ipw

from aiidalab_qe.common.panel import ResultsPanel

from .model import GeneralResultsModel


class GeneralResultsPanel(ResultsPanel[GeneralResultsModel]):
    def __init__(self, model: GeneralResultsModel, **kwargs):
        super().__init__(model, **kwargs)

    def _render(self):
        self.general_info = ipw.HTML(layout=ipw.Layout(margin="0"))
        ipw.dlink(
            (self._model, "info"),
            (self.general_info, "value"),
        )

        self.results_container.children = [
            self.general_info,
        ]
