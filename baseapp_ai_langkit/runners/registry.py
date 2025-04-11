from typing import List, Type

from baseapp_ai_langkit.base.interfaces.base_runner import BaseRunnerInterface


class RunnerRegistry:
    _registry: List[Type[BaseRunnerInterface]] = []

    @classmethod
    def register(cls, runner_cls: Type[BaseRunnerInterface]):
        cls._registry.append(runner_cls)

    @classmethod
    def get_all(cls):
        return cls._registry


def register_runner(runner_cls: Type[BaseRunnerInterface]):
    RunnerRegistry.register(runner_cls)
    return runner_cls
