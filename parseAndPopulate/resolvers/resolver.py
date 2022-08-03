from abc import ABC, abstractclassmethod, abstractmethod

from pyang.statements import Statement


class Resolver(ABC):
    @abstractclassmethod
    def __init__(self) -> None:
        self.parsed_yang: Statement
        self.property_name: str

    @abstractmethod
    def resolve(self):
        pass
