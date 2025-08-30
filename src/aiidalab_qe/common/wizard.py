from __future__ import annotations

import enum
import os
import typing as t

import ipywidgets as ipw
import traitlets as tl

from aiidalab_qe.common.mixins import Confirmable, HasBlockers, HasModels
from aiidalab_qe.common.mvc import Model
from aiidalab_widgets_base import LoadingWidget


class State(enum.Enum):
    """Local copy of AWB's `WizardAppWidgetStep.State`"""

    FAIL = -1
    INIT = 0
    CONFIGURED = 1
    READY = 2
    ACTIVE = 3
    SUCCESS = 4


class QeWizardStepModel(Model):
    identifier = "qe-wizard-step"

    state = tl.UseEnum(State, default_value=State.INIT)

    def __init__(self, auto_advance: bool = True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.auto_advance = auto_advance

    @property
    def is_finished(self) -> bool:
        return self.state in (State.SUCCESS, State.FAIL)

    def update_state(self):
        pass
        # print(self.__class__.__name__, "updating")


WSM = t.TypeVar("WSM", bound=QeWizardStepModel)


class QeWizardStep(ipw.VBox, t.Generic[WSM]):
    def __init__(self, model: WSM, **kwargs):
        self.loading_message = LoadingWidget(f"Loading {model.identifier} step")

        super().__init__(children=[self.loading_message], **kwargs)

        self._model = model

        self._model.observe(
            self._on_state_change,
            "state",
        )

        self.rendered = False

        self._background_class = ""

    def render(self):
        if self.rendered:
            return
        self._render()
        self.rendered = True
        self._post_render()

    def _on_state_change(self, change):
        self._update_background_color(change["new"])

    def _render(self):
        raise NotImplementedError()

    def _post_render(self):
        pass

    def _update_background_color(self, state: State):
        self.remove_class(self._background_class)
        self._background_class = f"qe-app-step-{state.name.lower()}"
        self.add_class(self._background_class)


class QeConfirmableWizardStepModel(
    QeWizardStepModel,
    Confirmable,
    HasBlockers,
):
    blockers = tl.List(tl.Unicode())
    blocker_messages = tl.Unicode("")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.confirmation_exceptions += [
            "state",
            "locked",
            "blockers",
            "blocker_messages",
        ]

    @property
    def is_blocked(self):
        return any(self.blockers)

    def lock(self):
        super().lock()
        self.unobserve_all("confirmed")

    def update_blockers(self):
        blockers = list(self._check_blockers())
        if isinstance(self, HasModels):
            for _, model in self.get_models():
                if isinstance(model, HasBlockers):
                    blockers += model.blockers
        self.blockers = blockers

    def update_blocker_messages(self):
        if self.is_blocked:
            formatted = "\n".join(f"<li>{item}</li>" for item in self.blockers)
            self.blocker_messages = f"""
                <div class="alert alert-danger">
                    <b>The step is blocked due to the following reason(s):</b>
                    <ul>
                        {formatted}
                    </ul>
                </div>
            """
        else:
            self.blocker_messages = ""

    def _check_blockers(self):
        raise NotImplementedError


CWSM = t.TypeVar("CWSM", bound=QeConfirmableWizardStepModel)


class QeConfirmableWizardStep(QeWizardStep[CWSM]):
    def __init__(
        self,
        model: CWSM,
        confirm_kwargs=None,
        **kwargs,
    ):
        super().__init__(model, **kwargs)
        self._model.observe(
            self._on_confirmation_change,
            "confirmed",
        )
        self._model.observe(
            self._on_blockers_change,
            "blockers",
        )

        if confirm_kwargs is None:
            confirm_kwargs = {}

        self.confirm_button_style = confirm_kwargs.get("button_style", "success")
        self.confirm_button_icon = confirm_kwargs.get("icon", "check-circle")
        self.confirm_button_description = confirm_kwargs.get("description", "Confirm")
        self.confirm_button_tooltip = confirm_kwargs.get("tooltip", "Confirm")

    def confirm(self, _=None):
        self._model.confirm()

    def _render(self):
        self.content = ipw.VBox()

        self.confirm_button = ipw.Button(
            description=self.confirm_button_description,
            tooltip=self.confirm_button_tooltip,
            button_style=self.confirm_button_style,
            icon=self.confirm_button_icon,
            layout=ipw.Layout(width="auto"),
            disabled=not self._model.is_blocked,
        )
        ipw.dlink(
            (self._model, "state"),
            (self.confirm_button, "disabled"),
            lambda state: self._model.is_blocked or state != State.CONFIGURED,
        )
        self.confirm_button.on_click(self.confirm)

        self.blocker_messages = ipw.HTML()
        self.blocker_messages.add_class("blocker-messages")
        ipw.dlink(
            (self._model, "blocker_messages"),
            (self.blocker_messages, "value"),
        )

        self.confirm_box = ipw.VBox(
            children=[
                self.confirm_button,
                self.blocker_messages,
            ]
        )
        self.children += (self.confirm_box,)

    def _on_confirmation_change(self, _):
        self._model.update_state()

    def _on_blockers_change(self, _):
        if self.rendered:
            self._enable_confirm_button()
        self._model.update_blocker_messages()
        self._model.update_state()

    def _enable_confirm_button(self):
        can_confirm = self._model.is_blocked or self._model.state != State.CONFIGURED
        self.confirm_button.disabled = can_confirm


class QeDependentWizardStepModel(
    QeWizardStepModel,
):
    previous_step_state = tl.UseEnum(State)

    @property
    def is_ready(self) -> bool:
        return self.previous_step_state is State.SUCCESS


DWSM = t.TypeVar("DWSM", bound=QeDependentWizardStepModel)


class QeDependentWizardStep(QeWizardStep[DWSM]):
    missing_information_warning = "Missing information"

    def __init__(self, model: DWSM, **kwargs):
        super().__init__(model, **kwargs)
        self.previous_children = list(self.children)
        self.warning_message = ipw.HTML(
            f"""
            <div class="alert alert-danger">
                <b>Warning:</b> {self.missing_information_warning}
            </div>
        """
        )
        self._model.observe(
            self._on_previous_step_state_change,
            "previous_step_state",
        )

    def render(self):
        if "PYTEST_CURRENT_TEST" in os.environ:
            super().render()
            return
        if self._model.is_ready:
            self._hide_missing_information_warning()
            if not self.rendered:
                super().render()
                self.previous_children = list(self.children)
        else:
            self._show_missing_information_warning()

    def _on_previous_step_state_change(self, _):
        self._model.update_state()

    def _show_missing_information_warning(self):
        self.children = [self.warning_message]
        self.rendered = False

    def _hide_missing_information_warning(self):
        self.children = self.previous_children


class QeConfirmableDependentWizardStepModel(
    QeDependentWizardStepModel,
    QeConfirmableWizardStepModel,
):
    previous_step_state = tl.UseEnum(State)


CDWSM = t.TypeVar("CDWSM", bound=QeConfirmableDependentWizardStepModel)


class QeConfirmableDependentWizardStep(
    QeDependentWizardStep[CDWSM],
    QeConfirmableWizardStep[CDWSM],
):
    """A confirmable dependent wizard step."""
