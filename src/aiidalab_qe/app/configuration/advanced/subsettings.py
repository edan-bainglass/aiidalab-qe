import ipywidgets as ipw
import traitlets as tl


class AdvancedSubModel(tl.HasTraits):
    dependencies = []

    _defaults = {}

    def update(self, specific=""):
        """Updates the model.

        Parameters
        ----------
        `specific` : `str`, optional
            If provided, specifies the level of update.
        """
        raise NotImplementedError

    def reset(self):
        """Resets the model to present defaults."""
        raise NotImplementedError

    def _update_defaults(self, specific=""):
        """Updates the model's default values.

        Parameters
        ----------
        `specific` : `str`, optional
            If provided, specifies the level of update.
        """
        raise NotImplementedError


class AdvancedSubSettings(ipw.VBox):
    identifier = "sub"

    def __init__(self, model: AdvancedSubModel, **kwargs):
        from aiidalab_qe.common.widgets import LoadingWidget

        self.loading_message = LoadingWidget(f"Loading {self.identifier} settings")

        super().__init__(
            layout={"justify_content": "space-between", **kwargs.get("layout", {})},
            children=[self.loading_message],
            **kwargs,
        )

        self._model = model
        self._model.observe(
            self._on_override_change,
            "override",
        )

        self.links = []

        self.rendered = False
        self.updated = False

    def render(self):
        raise NotImplementedError

    def refresh(self, specific=""):
        """Refreshes the subsettings section.

        Unlinks any linked widgets and updates the model's defaults.
        Resets the model to these defaults if there is no input structure.

        Parameters
        ----------
        `specific` : `str`, optional
            If provided, specifies the level of refresh.
        """
        self.updated = False
        self._unsubscribe()
        self._update(specific)
        if hasattr(self._model, "input_structure") and not self._model.input_structure:
            self._reset()

    def _on_override_change(self, change):
        if not change["new"]:
            self._reset()

    def _update(self, specific=""):
        """Updates the model if not yet updated.

        Parameters
        ----------
        `specific` : `str`, optional
            If provided, specifies the level of update.
        """
        if self.updated:
            return
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
