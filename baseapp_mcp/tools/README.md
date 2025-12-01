# MCP Tools - Compatibilidade com baseapp_ai_langkit

## Visão Geral

O módulo `baseapp_mcp.tools` fornece uma abstração independente de `baseapp_ai_langkit`, mas mantém compatibilidade quando `baseapp_ai_langkit` está disponível. Isso permite que:

1. **`baseapp_mcp` seja independente**: Não requer `baseapp_ai_langkit` para funcionar
2. **Tools MCP funcionem em agents**: Quando `baseapp_ai_langkit` está disponível, as tools MCP podem ser usadas em `LangGraphAgent` e outros agents

## Estrutura

### `BaseMCPToolInterface`
Interface base local que define a estrutura mínima necessária para uma tool MCP:
- `name: str`
- `description: str`
- `args_schema: Optional[Type[BaseModel]]`
- `tool_func(*args, **kwargs)` - método abstrato
- `to_langchain_tool()` - método abstrato

### `MCPTool`
Classe base para todas as tools MCP que:
- Herda de `BaseMCPToolInterface` (sempre)
- Herda de `InlineTool` (quando `baseapp_ai_langkit` está disponível)
- Fornece rate limiting, token tracking, logging, etc.

### `compat.py`
Módulo de compatibilidade que:
- Detecta se `baseapp_ai_langkit` está disponível
- Cria dinamicamente uma classe base que herda de ambos quando possível
- Fornece funções utilitárias para verificar compatibilidade

## Como Funciona

### Sem baseapp_ai_langkit

```python
from baseapp_mcp.tools.base_mcp_tool import MCPTool

class MyTool(MCPTool):
    name = "my_tool"
    description = "My tool"
    
    def tool_func_core(self, query: str):
        return {"result": query}

tool = MyTool(user_identifier="user123")
# tool herda apenas de BaseMCPToolInterface
```

### Com baseapp_ai_langkit

```python
from baseapp_mcp.tools.base_mcp_tool import MCPTool
from baseapp_ai_langkit.base.agents.langgraph_agent import LangGraphAgent

class MyTool(MCPTool):
    name = "my_tool"
    description = "My tool"
    
    def tool_func_core(self, query: str):
        return {"result": query}

tool = MyTool(user_identifier="user123")
# tool herda de BaseMCPToolInterface E InlineTool
# isinstance(tool, InlineTool) == True

# Pode ser usado em agents
agent = LangGraphAgent(
    tools_list=[MyTool],  # ✅ Funciona!
    ...
)
```

## Uso em Agents

### LangGraphAgent

```python
from baseapp_ai_langkit.base.agents.langgraph_agent import LangGraphAgent
from baseapp_mcp.tools.search_tool import SearchTool
from baseapp_mcp.tools.fetch_tool import FetchTool

# Tools MCP podem ser usadas diretamente
agent = LangGraphAgent(
    tools_list=[SearchTool, FetchTool],
    ...
)
```

### Verificação de Compatibilidade

```python
from baseapp_mcp.tools.compat import is_inline_tool_compatible

tool = MyTool(user_identifier="user123")

if is_inline_tool_compatible(tool):
    # Tool pode ser usada em agents
    agent = LangGraphAgent(tools_list=[MyTool])
```

## Implementação Técnica

### Criação Dinâmica da Classe Base

A função `create_mcp_tool_base_class()` cria dinamicamente uma classe base:

1. **Sem baseapp_ai_langkit**: Retorna `BaseMCPToolInterface`
2. **Com baseapp_ai_langkit**: Retorna uma classe que herda de `(InlineTool, BaseMCPToolInterface)`

Isso garante que:
- `isinstance(tool, InlineTool)` funciona quando disponível
- A tool tem todos os métodos necessários (`tool_func`, `to_langchain_tool`)
- Não há dependência obrigatória de `baseapp_ai_langkit`

### Ordem de Herança

Quando `InlineTool` está disponível:
```python
class MCPTool(InlineTool, BaseMCPToolInterface):
    ...
```

A ordem é importante:
- `InlineTool` primeiro: garante que `isinstance()` funciona
- `BaseMCPToolInterface` segundo: fornece a interface base

### Método `to_langchain_tool()`

`MCPTool` implementa `to_langchain_tool()` que retorna um `StructuredTool` do LangChain:

```python
def to_langchain_tool(self) -> StructuredTool:
    return StructuredTool(
        name=self.name,
        func=self.tool_func,
        description=self.description,
        args_schema=self.args_schema,
    )
```

Isso permite que as tools sejam usadas diretamente em agents LangChain.

## Testes

Para testar a compatibilidade:

```python
# Teste sem baseapp_ai_langkit
from baseapp_mcp.tools.compat import get_inline_tool_class
assert get_inline_tool_class() is None  # Quando não disponível

# Teste com baseapp_ai_langkit
from baseapp_ai_langkit.base.tools.inline_tool import InlineTool
from baseapp_mcp.tools.base_mcp_tool import MCPTool

tool = MyTool(user_identifier="user123")
assert isinstance(tool, InlineTool)  # ✅ Funciona quando disponível
```

## Benefícios

1. **Independência**: `baseapp_mcp` não requer `baseapp_ai_langkit`
2. **Compatibilidade**: Tools funcionam em agents quando `baseapp_ai_langkit` está disponível
3. **Flexibilidade**: Pode ser usado em projetos com ou sem `baseapp_ai_langkit`
4. **Type Safety**: Mantém type hints e verificação de tipos

## Limitações

- A compatibilidade é detectada em tempo de importação, não em tempo de execução
- Se `baseapp_ai_langkit` for instalado após a importação, a compatibilidade não será ativada
- Requer reinicialização do processo Python para detectar mudanças na disponibilidade

