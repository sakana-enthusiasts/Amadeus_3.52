from abc import ABC, abstractmethod


class EvidenceRepository(ABC):
    @abstractmethod
    def add(self, evidence) -> None:
        raise NotImplementedError

    @abstractmethod
    def query(self, *, compound_id=None, property_id=None, sources=(), temperature_range=None):
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
