"""
Registry for tools in the system.
"""
from typing import Dict, List, Any
from .base_tool import BaseTool

class ToolRegistry:
    """
    Registry for all available tools in the system.
    Provides a central place to access tools by name.
    """
    _tools: Dict[str, BaseTool] = {}
    
    @classmethod
    def register(cls, tool: BaseTool) -> None:
        """
        Register a tool in the registry.
        
        Args:
            tool: The tool instance to register
        """
        cls._tools[tool.name] = tool
    
    @classmethod
    def get_tool(cls, name: str) -> BaseTool:
        """
        Get a tool by name.
        
        Args:
            name: The name of the tool to retrieve
            
        Returns:
            The tool instance
            
        Raises:
            KeyError: If the tool is not found
        """
        if name not in cls._tools:
            raise KeyError(f"Tool '{name}' not found in registry")
        return cls._tools[name]
    
    @classmethod
    def list_tools(cls) -> List[BaseTool]:
        """
        List all registered tools.
        
        Returns:
            List of all registered tool instances
        """
        return list(cls._tools.values())
    
    @classmethod
    def list_tool_names(cls) -> List[str]:
        """
        List all registered tool names.
        
        Returns:
            List of all registered tool names
        """
        return list(cls._tools.keys()) 