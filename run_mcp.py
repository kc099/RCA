#!/usr/bin/env python
import argparse
import asyncio
import sys

from app.agent.mcp import MCPAgent, AgentState
from app.agent.data_analytics_mcp import DataAnalyticsMCPAgent
from app.config import config
from app.logger import logger


class MCPRunner:
    """Runner class for MCP Agent with proper path handling and configuration."""

    def __init__(self, use_data_analytics_agent=True):
        self.root_path = config.root_path
        self.server_reference = "app.mcp.server"

        # Use DataAnalyticsMCPAgent instead of the default MCPAgent
        if use_data_analytics_agent:
            self.agent = DataAnalyticsMCPAgent()
            logger.info("Using DataAnalyticsMCPAgent for data analytics focused tasks")
        else:
            self.agent = MCPAgent()
            logger.info("Using default MCPAgent")

        # Track initialization state
        self.initialized = False
        # Track conversation state
        self.conversation_active = True

    async def initialize(
        self,
        connection_type: str,
        server_url: str | None = None,
    ) -> None:
        """Initialize the MCP agent with the appropriate connection."""
        if self.initialized:
            return

        logger.info(f"Initializing agent with {connection_type} connection...")

        if connection_type == "stdio":
            await self.agent.initialize(
                connection_type="stdio",
                command=sys.executable,
                args=["-m", self.server_reference],
            )
        else:  # sse
            await self.agent.initialize(connection_type="sse", server_url=server_url)

        logger.info(f"Connected to MCP server via {connection_type}")
        self.initialized = True

    async def run_interactive(self) -> None:
        """Run the agent in interactive mode."""
        print("\nMCP Agent Interactive Mode (type 'exit' to quit)\n")
        while True:
            user_input = input("\nEnter your request: ")
            if user_input.lower() in ["exit", "quit", "q"]:
                break
            response = await self.agent.run(user_input)
            print(f"\nAgent: {response}")

    async def run_single_prompt(self, prompt: str) -> None:
        """Run the agent with a single prompt."""
        await self.agent.run(prompt)

    async def run_default(self) -> None:
        """Run the agent in default mode with continuous prompts."""
        print("\nMCP Data Analytics Agent (type 'exit' to quit)\n")

        # Initialize conversation state
        self.conversation_active = True
        current_conversation_id = 1

        while self.conversation_active:
            try:
                prompt = input("\nEnter your prompt: ")

                # Check for exit command
                if prompt.lower() in ["exit", "quit", "q"]:
                    self.conversation_active = False
                    break

                if not prompt.strip():
                    logger.warning("Empty prompt provided. Please try again.")
                    continue

                logger.warning("Processing your request...")

                # Run the agent without cleaning up after each request
                response = await self.agent.run(prompt)

                # Print the response
                print(f"\nAgent: {response}")
                logger.info("Request processing completed.")

                # Check if agent is waiting for input - skip cleanup in that case
                if hasattr(self.agent, 'state') and self.agent.state == AgentState.WAITING_FOR_INPUT:
                    logger.info("Agent is waiting for user input - maintaining connection")
                    continue

                # Increment conversation ID for the next request
                current_conversation_id += 1

            except Exception as e:
                # Log the error but don't exit - allow the user to try again
                logger.error(f"Error processing request: {str(e)}", exc_info=True)
                print(f"\nError: {str(e)}")
                print("You can try another prompt or type 'exit' to quit.")
                # Continue the loop to allow more prompts
                continue

    async def cleanup(self) -> None:
        """Clean up agent resources."""
        if self.initialized:
            # Only clean up if we're truly done with the conversation
            if not hasattr(self.agent, 'state') or self.agent.state != AgentState.WAITING_FOR_INPUT:
                await self.agent.cleanup()
                logger.info("Session ended")
                self.initialized = False
                self.conversation_active = False


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run the MCP Agent")
    parser.add_argument(
        "--connection",
        "-c",
        choices=["stdio", "sse"],
        default="stdio",
        help="Connection type: stdio or sse",
    )
    parser.add_argument(
        "--server-url",
        default="http://127.0.0.1:8000/sse",
        help="URL for SSE connection",
    )
    parser.add_argument(
        "--interactive", "-i", action="store_true", help="Run in interactive mode"
    )
    parser.add_argument("--prompt", "-p", help="Single prompt to execute and exit")
    parser.add_argument(
        "--use-mcp-agent",
        action="store_false",
        dest="use_data_analytics_agent",
        help="Use the default MCPAgent instead of DataAnalyticsMCPAgent",
    )
    parser.set_defaults(use_data_analytics_agent=True)
    return parser.parse_args()


async def run_mcp() -> None:
    """Main entry point for the MCP runner."""
    args = parse_args()
    runner = MCPRunner(args.use_data_analytics_agent)

    try:
        await runner.initialize(args.connection, args.server_url)

        if args.prompt:
            await runner.run_single_prompt(args.prompt)
            # Only cleanup if running a single prompt
            await runner.cleanup()
        elif args.interactive:
            await runner.run_interactive()
        else:
            await runner.run_default()

    except KeyboardInterrupt:
        logger.info("Program interrupted by user")
    except Exception as e:
        logger.error(f"Error running MCPAgent: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        # Only cleanup at the end of the session
        if runner.conversation_active:
            await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(run_mcp())
