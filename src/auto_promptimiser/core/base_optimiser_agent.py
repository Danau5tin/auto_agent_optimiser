from abc import ABC, abstractmethod


class BaseOptimiserAgent(ABC):
    @abstractmethod
    async def optimise(self) -> None:
        pass
