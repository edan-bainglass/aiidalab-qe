import ipywidgets as ipw
import pytest

from aiida import orm
from aiida.common.links import LinkType
from aiida.engine import ProcessState
from aiidalab_qe.app.result.components.status import (
    WorkChainStatusModel,
    WorkChainStatusPanel,
)
from aiidalab_qe.app.result.components.status.tree import (
    CalculationTreeNode,
    ProcessTreeNode,
    SimplifiedProcessTree,
    SimplifiedProcessTreeModel,
    WorkChainTreeNode,
)


def mock_calcjob(label):
    calcjob = orm.CalcJobNode()
    calcjob.set_process_state(ProcessState.FINISHED)
    calcjob.set_process_label(label)
    return calcjob


def mock_workchain(label):
    workchain = orm.WorkChainNode()
    workchain.set_process_state(ProcessState.FINISHED)
    workchain.set_process_label(label)
    return workchain


@pytest.fixture(scope="module")
def mock_qeapp_workchain():
    qe_workchain = mock_workchain("QeAppWorkChain")
    relax_workchain = mock_workchain("PwRelaxWorkChain")
    relax_calcjob = mock_calcjob("PwCalculation")
    parameters = orm.Dict(dict={"CONTROL": {"calculation": "relax"}})
    parameters.store()
    relax_calcjob.base.links.add_incoming(
        parameters,
        link_type=LinkType.INPUT_CALC,
        link_label="parameters",
    )
    relax_calcjob.base.links.add_incoming(
        relax_workchain,
        link_type=LinkType.CALL_CALC,
        link_label="iteration_01",
    )
    relax_workchain.base.links.add_incoming(
        qe_workchain,
        link_type=LinkType.CALL_WORK,
        link_label="relax",
    )
    relax_workchain.set_metadata_inputs({"": orm.StructureData()})
    qe_workchain.set_metadata_inputs({"relax": {}})
    relax_workchain.set_metadata_inputs({"pw": {}})
    qe_workchain.store()
    relax_workchain.store()
    relax_calcjob.store()
    yield qe_workchain


class TestSimplifiedProcessTree:
    model: SimplifiedProcessTreeModel
    node: orm.WorkChainNode
    tree: SimplifiedProcessTree

    @property
    def workchain_node(self) -> WorkChainTreeNode:
        return self.tree.trunk.branches[0]  # type: ignore

    @property
    def calculation_node(self) -> CalculationTreeNode:
        return self.workchain_node.branches[0]  # type: ignore

    @pytest.fixture(scope="class", autouse=True)
    def setup(self, request):
        model = SimplifiedProcessTreeModel()
        request.cls.model = model
        request.cls.tree = SimplifiedProcessTree(model=model)

    def test_initialization(self):
        loading_widget = self.tree.children[0]  # type: ignore
        assert loading_widget is self.tree.loading_message
        assert (
            loading_widget.message.value
            == self.tree.loading_message.message.value
            == "Loading process tree"
        )
        assert "simplified-process-tree" in self.tree._dom_classes
        assert not self.tree.rendered

    def test_render(self):
        self.tree.render()
        assert self.tree.children[0].value == "Process node not yet available"
        assert not self.tree.rendered  # no process node yet

    def test_update_on_process_change(self, mock_qeapp_workchain):
        self.model.process_uuid = mock_qeapp_workchain.uuid
        assert self.tree.rendered
        human_label = ProcessTreeNode._MAPPING["QeAppWorkChain"]
        assert self.tree.trunk.label.value == human_label
        assert not self.tree.trunk.collapsed
        assert len(self.tree.trunk.branches) == 1

    def test_workchain_node(self):
        workchain_node = self.workchain_node
        assert isinstance(workchain_node, WorkChainTreeNode)
        assert workchain_node.level == 1
        assert workchain_node.emoji.value == "✅"
        assert workchain_node.state.value == "finished"
        human_label = ProcessTreeNode._MAPPING["PwRelaxWorkChain"]
        assert workchain_node.label.value == human_label
        assert isinstance(workchain_node.label, ipw.HTML)
        assert workchain_node.collapsed
        assert len(workchain_node.branches) == 0

    def test_expand(self):
        workchain_node = self.workchain_node
        workchain_node.expand()
        assert "open" in workchain_node.branches._dom_classes
        assert workchain_node.toggle.icon == "minus"

    def test_collapse(self):
        workchain_node = self.workchain_node
        workchain_node.collapse()
        assert "open" not in workchain_node.branches._dom_classes
        assert workchain_node.toggle.icon == "plus"

    def test_expand_recursive(self):
        self.tree.trunk.expand(recursive=True)
        assert not self.tree.trunk.collapsed
        assert not self.workchain_node.collapsed

    def test_collapse_recursive(self):
        self.tree.trunk.collapse(recursive=True)
        assert self.tree.trunk.collapsed
        assert self.workchain_node.collapsed

    def test_collapse_all_button(self):
        self.tree.trunk.expand(recursive=True)
        self.tree.collapse_button.click()
        assert self.tree.trunk.collapsed
        assert self.workchain_node.collapsed

    def test_calculation_node(self):
        calculation_node = self.calculation_node
        assert isinstance(calculation_node, CalculationTreeNode)
        assert calculation_node.level == 2
        assert calculation_node.emoji.value == "✅"
        assert calculation_node.state.value == "finished"
        human_label = ProcessTreeNode._PW_MAPPING["relax"]["PwCalculation"]
        assert isinstance(calculation_node.label, ipw.Button)
        assert calculation_node.label.description == human_label


class TestWorkChainStatusPanel:
    model: WorkChainStatusModel
    panel: WorkChainStatusPanel

    @property
    def tree(self) -> SimplifiedProcessTree:
        return self.panel.simplified_process_tree

    @pytest.fixture(scope="class", autouse=True)
    def setup(self, request, mock_qeapp_workchain):
        model = WorkChainStatusModel()
        model.process_uuid = mock_qeapp_workchain.uuid
        request.cls.model = model
        request.cls.panel = WorkChainStatusPanel(model=model)

    def test_render(self):
        self.panel.render()
        assert self.panel.children[0] is self.panel.accordion
        assert self.panel.accordion.selected_index == 0
        assert self.panel.simplified_process_tree.rendered

    def test_calculation_node_link(self):
        # TODO uncomment if and when the comments below are resolved; discard otherwise
        # from aiidalab_qe.common.node_view import CalcJobNodeViewerWidget

        self.tree.trunk.expand(recursive=True)
        calculation_node: CalculationTreeNode = self.tree.trunk.branches[0].branches[0]
        calculation_node.label.click()
        assert self.panel.accordion.selected_index == 1
        assert self.panel.process_tree.value == calculation_node.uuid
        assert self.panel.process_tree._tree.nodes == (calculation_node.process_node,)
        # TODO understand why the following does not trigger automatically as in the app
        # TODO understand why the following triggers a thread
        # self.panel.process_tree.set_trait(
        #     "selected_nodes",
        #     [calculation_node.process_node],
        # )
        # assert isinstance(panel.node_view, CalcJobNodeViewerWidget)
