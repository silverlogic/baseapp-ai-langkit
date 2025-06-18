import factory
from langchain.tools import Tool


class ToolFactory(factory.Factory):
    name = factory.Sequence(lambda n: f"Tool {n}")
    description = factory.Faker("sentence")

    def tool_function(self, x):
        return x

    func = factory.LazyAttribute(lambda obj: obj.tool_function)

    class Meta:
        model = Tool
