"""
Data Analytics MCP Agent Module

This module extends the MCPAgent with data analytics filtering capabilities.
"""

from typing import Optional
import re

from app.agent.mcp import MCPAgent
from app.filter.data_analytics_filter import DataAnalyticsFilter
from app.logger import logger
from app.schema import Message, AgentState


class DataAnalyticsMCPAgent(MCPAgent):
    """
    An MCP agent specialized for data analytics tasks.
    
    This agent extends MCPAgent with a moderation layer to ensure
    only data analytics related queries are processed.
    """

    name: str = "data_analytics_mcp_agent"
    description: str = "An MCP agent specialized in data analytics tasks only"
    
    # Add data analytics filtering
    filter: DataAnalyticsFilter = None
    _is_analytics_request: bool = False
    _awaiting_user_input: bool = False
    
    async def initialize(
        self,
        connection_type: Optional[str] = None,
        server_url: Optional[str] = None,
        command: Optional[str] = None,
        args: Optional[list] = None,
        filter_threshold: float = 0.6,
    ) -> None:
        """
        Initialize the MCP connection with data analytics filtering.
        
        Args:
            connection_type: Type of connection to use ("stdio" or "sse")
            server_url: URL of the MCP server (for SSE connection)
            command: Command to run (for stdio connection)
            args: Arguments for the command (for stdio connection)
            filter_threshold: Threshold for data analytics filtering
        """
        # Initialize the data analytics filter
        self.filter = DataAnalyticsFilter(threshold=filter_threshold)
        
        # Initialize the parent MCPAgent
        await super().initialize(
            connection_type=connection_type,
            server_url=server_url,
            command=command,
            args=args,
        )
        
        # Enhance system prompt with data analytics focus
        analytics_prompt = (
            "\n\nYou are specialized in data analytics tasks. "
            "You can help users analyze data, create visualizations, perform statistical analysis, "
            "clean and transform datasets, and derive insights from numerical information. "
            "You should decline non-analytics related requests politely, explaining that you're "
            "specialized in data analytics tasks."
        )
        
        # Update the system message with analytics focus
        if self.memory.messages and self.memory.messages[0].role == "system":
            self.memory.messages[0].content += analytics_prompt
    
    async def run(self, request: str) -> str:
        """
        Process the request after moderation check.
        
        Args:
            request: The user request to process
            
        Returns:
            Response string
        """
        if not request:
            return "No request provided."
        
        # Reset the awaiting user input flag when a new request comes in
        self._awaiting_user_input = False
        
        # Reset the state if it was waiting for input
        if self.state == AgentState.WAITING_FOR_INPUT:
            self.state = AgentState.IDLE
        
        # Check if request is allowed by the filter
        is_analytics, analysis = self.filter.is_data_analytics_query(request)
        self._is_analytics_request = is_analytics
        
        # Log the analysis results
        logger.info(f"Request analysis: {analysis}")
        
        if not is_analytics:
            # Generate rejection message
            rejection_message = self.filter.get_rejection_message(request, analysis)
            
            # Add messages to memory for context using the correct method
            self.memory.add_message(Message.user_message(request))
            self.memory.add_message(Message.assistant_message(rejection_message))
            
            # Return rejection message directly
            return rejection_message
        
        # Process allowed request
        return await super().run(request)
    
    async def think(self) -> bool:
        """
        Process current state and decide next actions with analytics focus.
        
        Returns:
            Boolean indicating if action should be taken
        """
        # If we're waiting for user input, don't proceed
        if self._awaiting_user_input:
            logger.info("Agent is waiting for user input before proceeding")
            # Set the state to WAITING_FOR_INPUT to pause the execution loop
            self.state = AgentState.WAITING_FOR_INPUT
            return False
            
        # Execute the normal think process
        result = await super().think()
        
        # After thinking, check if the last assistant message contains a question
        # that would require user input before proceeding
        if result and self.memory.messages:
            last_messages = self.memory.messages[-3:]  # Look at recent messages
            for msg in reversed(last_messages):
                if msg.role == "assistant" and msg.content:
                    # Check if the message contains a question
                    if self._contains_question(msg.content):
                        logger.info("Agent asked a question, waiting for user input")
                        self._awaiting_user_input = True
                        # Set the state to WAITING_FOR_INPUT to pause the execution loop
                        self.state = AgentState.WAITING_FOR_INPUT
                        return False
                    break
        
        return result
    
    def _contains_question(self, text: str) -> bool:
        """
        Check if the text contains a question that should pause for user input.
        
        Args:
            text: The text to check for questions
            
        Returns:
            Boolean indicating if a question is present
        """
        # Check for question marks
        if "?" in text:
            return True
            
        # Check for common question phrases
        question_phrases = [
            r"could you",
            r"can you",
            r"would you",
            r"please provide",
            r"please specify",
            r"what .* would you like",
            r"which .* would you prefer",
            r"how would you like",
            r"do you want",
            r"would you like",
        ]
        
        for phrase in question_phrases:
            if re.search(phrase, text.lower()):
                return True
                
        return False
