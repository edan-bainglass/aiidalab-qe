"""Panel for Bands plugin."""

from aiidalab_qe.common.code.model import CodeModel, PwCodeModel
from aiidalab_qe.common.panel import ResourceSettingsModel, ResourceSettingsPanel


class BandsResourceSettingsModel(ResourceSettingsModel):
    """Model for the band structure plugin."""

    identifier = "bands"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.add_models(
            {
                "pw": PwCodeModel(
                    name="pw.x",
                    description="pw.x",
                    default_calc_job_plugin="quantumespresso.pw",
                ),
                "projwfc_bands": CodeModel(
                    name="projwfc.x",
                    description="projwfc.x",
                    default_calc_job_plugin="quantumespresso.projwfc",
                ),
            }
        )


class BandsResourceSettingsPanel(ResourceSettingsPanel[BandsResourceSettingsModel]):
    title = "Band Structure"
