import asyncio
import dataclasses
from abc import ABC, abstractmethod
from concurrent.futures import Executor
from typing import Any, Dict, Generic, List, Optional, Tuple, Type, TypeVar

from starkware.starkware_utils.commitment_tree.binary_fact_tree import BinaryFactDict
from starkware.starkware_utils.commitment_tree.binary_fact_tree_node import (
    BinaryFactDict,
    TBinaryFactTreeNode,
    TInnerNodeFact,
)
from starkware.starkware_utils.validated_dataclass import ValidatedDataclass
from starkware.storage.storage import FactFetchingContext, HashFunctionType

T = TypeVar("T")
TCalculationNode = TypeVar("TCalculationNode", bound="CalculationNode")
NodeFactDict = Dict[bytes, TInnerNodeFact]

class Calculation(Generic[T], ABC):
    """
    A calculation that can produce a result of type T. The calculation is dependent on the results
    of other calculations. Those calculations can be of type other than T.
    The result of the calculation can be produced when the results of the dependency calculations
    are given.
    """

    @abstractmethod
    def get_dependency_calculations(self) -> List["Calculation"]:
        """
        Returns a list of the calculations that this calculation depends on.
        """

    @abstractmethod
    def calculate(
        self,
        dependency_results: List[Any],
        hash_func: HashFunctionType,
        fact_nodes: NodeFactDict,
    ) -> T:
        """
        Produces the result of this calculation, given a list of results for the dependency
        calculations. The order of dependency_results should match the order of the list returned by
        get_dependency_calculations.

        The calculation might need to calculate hashes along the way. It will use hash_func for
        that.

        Any facts generated during the calculation will be saved in fact_nodes
        (using their hash as the key).
        """

    def calculate_new_fact_nodes(
        self,
        dependency_results: List[Any],
        hash_func: HashFunctionType,
    ) -> Tuple[T, NodeFactDict]:
        """
        Same as calculate(), but return the facts.
        """
        fact_nodes: NodeFactDict = {}
        result = self.calculate(
            dependency_results=dependency_results, hash_func=hash_func, fact_nodes=fact_nodes
        )
        return result, fact_nodes

    def full_calculate(
        self,
        hash_func: HashFunctionType,
        fact_nodes: NodeFactDict,
    ) -> T:
        """
        Produces the result of this calculation.

        Recursively calcuates the result of the dependency calculations.

        Any facts generated during the calculation will be saved in fact_nodes
        (using their hash as the key).
        """
        dependency_results: List[Any] = [
            dependency_calculation.full_calculate(fact_nodes=fact_nodes, hash_func=hash_func)
            for dependency_calculation in self.get_dependency_calculations()
        ]

        return self.calculate(
            dependency_results=dependency_results, hash_func=hash_func, fact_nodes=fact_nodes
        )

    def full_calculate_new_fact_nodes(
        self,
        hash_func: HashFunctionType,
    ) -> Tuple[T, NodeFactDict]:
        """
        Produces the result of this calculation. Returns the result and a dict containing generated
        facts.

        Recursively calcuates the result of the dependency calculations.
        """
        fact_nodes: NodeFactDict = {}
        result = self.full_calculate(hash_func=hash_func, fact_nodes=fact_nodes)
        return result, fact_nodes

    async def full_calculate_with_executor(
        self,
        executor: Optional[Executor],
        hash_func: HashFunctionType,
        fact_nodes: NodeFactDict,
        depth: int,
    ) -> T:
        """
        Produces the result of this calculation.

        Gets the dependency calculations at the layer that is `depth` layers from the current node.
        Distributes those calculations using the executor.

        Any facts generated during the calculation will be saved in fact_nodes
        (using their hash as the key).
        """
        if depth == 0:
            # We can't use full_calculate here due to thread-safety issues.
            result, sub_facts = await asyncio.get_event_loop().run_in_executor(
                executor, self.full_calculate_new_fact_nodes, hash_func
            )
            fact_nodes.update(sub_facts)
            return result

        dependency_results = await asyncio.gather(
            *[
                dependency_calculation.full_calculate_with_executor(
                    executor=executor, hash_func=hash_func, fact_nodes=fact_nodes, depth=depth - 1
                )
                for dependency_calculation in self.get_dependency_calculations()
            ]
        )
        # We can't use full_calculate here due to thread-safety issues.
        result, sub_facts = await asyncio.get_event_loop().run_in_executor(
            executor, self.calculate_new_fact_nodes, dependency_results, hash_func
        )
        fact_nodes.update(sub_facts)
        return result


class CalculationNode(Calculation[TBinaryFactTreeNode], ABC):
    """
    A calculation that produces a BinaryFactTreeNode. The calculation can be created from either a
    node or from a combination of two other calculations of the same type.
    """

    @classmethod
    @abstractmethod
    async def combine(
        cls: Type[TCalculationNode],
        ffc: FactFetchingContext,
        left: TCalculationNode,
        right: TCalculationNode,
        facts: Optional[BinaryFactDict],
    ) -> TCalculationNode:
        """
        Combines two calculations into a calculation that its children are the given calculations.
        The function might need to read facts from the DB using FFC.
        If so, and if facts argument is not None, facts is filled with the facts read.
        """

    @classmethod
    @abstractmethod
    def create(cls: Type[TCalculationNode], node: TBinaryFactTreeNode) -> TCalculationNode:
        """
        Creates a Calculation object from a node. It will produce the node and will have no
        dependencies.
        """


class HashCalculation(Calculation[bytes]):
    """
    A calculation that produces a hash result.
    """


@dataclasses.dataclass(frozen=True)
class ConstantCalculation(HashCalculation, ValidatedDataclass):
    """
    A calculation that contains a hash and simply produces it. It doesn't depend on any other
    calculations. It constitutes a leaf calculation so that other calculations can depend on it.
    """

    hash_value: bytes

    def calculate(
        self,
        dependency_results: list,
        hash_func: HashFunctionType,
        fact_nodes: NodeFactDict,
    ) -> bytes:
        assert len(dependency_results) == 0, "ConstantCalculation has no dependencies."
        return self.hash_value

    def get_dependency_calculations(self) -> List[Calculation[bytes]]:
        return []
